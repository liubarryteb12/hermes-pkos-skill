#!/usr/bin/env python3
"""pkos.gemini.image — OpenCLI 驱动已登录 Chrome 的 Gemini 网页生图工作流

流程: 发 prompt → 轮询生成完成(blob 大图) → 点 Download full size → 轮询 Downloads → 归档 workspace + sha256 校验
产出: <out-dir>/<ts>-<slug>.<jpg|png> + .manifest.json
失败: {rejected: true, reason, error_code} exit 2 (P-07)
不变量: 产出只落 --out-dir（workspace 铁律）；不改 PKOS 套件任何文件。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

DEFAULT_OPENCLI = Path.home() / "AppData/Local/OpenCLIApp/node_modules/@jackwener/opencli/dist/src/main.js"
DEFAULT_PROFILE = "5d5kre8b"
DEFAULT_SESSION = "gemini-img"
IMAGES_URL = "https://gemini.google.com/images"
DOWNLOADS = Path.home() / "Downloads"

ERR_OPENCLI_MISSING = "ERR_OPENCLI_RUNTIME_MISSING"
ERR_BRIDGE = "ERR_BROWSER_BRIDGE"
ERR_TYPE = "ERR_PROMPT_INJECT_FAILED"
ERR_SEND = "ERR_SEND_FAILED"
ERR_GEN_TIMEOUT = "ERR_IMAGE_GEN_TIMEOUT"
ERR_DL_TIMEOUT = "ERR_DOWNLOAD_TIMEOUT"
ERR_HASH = "ERR_HASH_MISMATCH"
ERR_MAGIC = "ERR_NOT_IMAGE"
ERR_OUTDIR = "ERR_OUTPUT_DIR"

MAGIC = {b"\xff\xd8\xff": ".jpg", b"\x89PNG": ".png"}


def _fail(code: str, reason: str) -> int:
    print(json.dumps({"rejected": True, "error_code": code, "reason": reason},
                     ensure_ascii=False, indent=2))
    return 2


def _opencli(opencli_path: Path, profile: str, *args: str, timeout: int = 120) -> str:
    cmd = ["node", str(opencli_path), "--profile", profile, *args]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
    except FileNotFoundError:
        raise RuntimeError(ERR_OPENCLI_MISSING)
    except subprocess.TimeoutExpired:
        raise RuntimeError(ERR_BRIDGE)
    return "\n".join(l for l in (r.stdout or "").splitlines()
                     if "Update available" not in l and "npm install" not in l)


def _eval(opencli_path: Path, profile: str, session: str, js: str) -> str:
    out = _opencli(opencli_path, profile, "browser", session, "eval", js)
    return out.strip()


def js_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def latest_gemini_download(before: set[str]) -> Path | None:
    """Downloads 里最新的 Gemini_Generated_Image 文件（排除 .crdownload），且不在 before 集合中。"""
    if not DOWNLOADS.exists():
        return None
    cands = []
    for p in DOWNLOADS.glob("Gemini_Generated_Image_*"):
        if p.name in before or p.suffix == ".crdownload":
            continue
        cands.append(p)
    if not cands:
        return None
    return max(cands, key=lambda p: p.stat().st_mtime)


def slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text)[:max_len].strip("-")
    return s or "image"


def check_magic(p: Path) -> str | None:
    with p.open("rb") as f:
        head = f.read(8)
    for magic, ext in MAGIC.items():
        if head.startswith(magic):
            return ext
    return None


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="pkos.gemini.image workflow")
    ap.add_argument("--prompt", default=None)
    ap.add_argument("--prompt-file", default=None)
    ap.add_argument("--out-dir", required=True, help="workspace 目录（产出落这里，绝不写 skill 目录）")
    ap.add_argument("--timeout", type=int, default=300, help="生成等待上限秒")
    ap.add_argument("--dl-timeout", type=int, default=60, help="下载落盘等待上限秒")
    ap.add_argument("--session", default=DEFAULT_SESSION)
    ap.add_argument("--profile", default=DEFAULT_PROFILE)
    ap.add_argument("--opencli", default=str(DEFAULT_OPENCLI))
    ap.add_argument("--keep-in-downloads", action="store_true", help="归档后保留 Downloads 原件")
    args = ap.parse_args(argv)

    opencli_path = Path(args.opencli)
    if not opencli_path.exists():
        return _fail(ERR_OPENCLI_MISSING, f"opencli runtime not found: {opencli_path}")
    prompt = ""
    if args.prompt_file:
        pf = Path(args.prompt_file)
        if not pf.exists():
            return _fail(ERR_OUTDIR, f"prompt file missing: {pf}")
        prompt = pf.read_text(encoding="utf-8").strip()
    elif args.prompt:
        prompt = args.prompt
    if not prompt.strip():
        return _fail(ERR_OUTDIR, "empty prompt")
    out_dir = Path(args.out_dir)
    if not out_dir.exists():
        return _fail(ERR_OUTDIR, f"out-dir must exist (workspace rule): {out_dir}")

    before = {p.name for p in DOWNLOADS.glob("Gemini_Generated_Image_*")} if DOWNLOADS.exists() else set()

    try:
        # 1) 打开 Images 页
        _opencli(opencli_path, args.profile, "browser", args.session, "open", IMAGES_URL)
        time.sleep(5)
        # 2) 注入 prompt + 发送
        inject_js = (
            "(() => { const el=document.querySelector(\"div[contenteditable='true']\");"
            " if(!el) return 'no-input'; el.focus();"
            " document.execCommand('insertText', false, " + js_str(prompt) + ");"
            " return 'injected'; })()"
        )
        if _eval(opencli_path, args.profile, args.session, inject_js) != "injected":
            raise RuntimeError(ERR_TYPE)
        send_js = ('(() => { const b=document.querySelector(\'button[aria-label="Send message"]\');'
                   ' if(!b) return "no-send"; b.click(); return "sent"; })()')
        if _eval(opencli_path, args.profile, args.session, send_js) != "sent":
            raise RuntimeError(ERR_SEND)
        # 3) 轮询生成完成：naturalWidth>400 的 blob 大图（文案残留不可信，实测坑 #1）
        gen_js = ("(() => { const big=[...document.querySelectorAll('img')]"
                  ".filter(i=>i.naturalWidth>400&&i.naturalHeight>400"
                  "&&i.src.startsWith('blob:'));"
                  " return JSON.stringify({done: big.length>0}); })()")
        deadline = time.time() + args.timeout
        while time.time() < deadline:
            time.sleep(10)
            out = _eval(opencli_path, args.profile, args.session, gen_js)
            try:
                if json.loads(out).get("done"):
                    break
            except ValueError:
                continue
        else:
            raise RuntimeError(ERR_GEN_TIMEOUT)
        time.sleep(4)  # 等下载按钮就绪
        # 4) 点下载（aria-label 定位，实测坑 #2）
        dl_js = ('(() => { const b=[...document.querySelectorAll("button")]'
                 '.find(x=>/download full size/i.test(x.getAttribute("aria-label")||""));'
                 ' if(!b) return "no-btn"; b.click(); return "clicked"; })()')
        if _eval(opencli_path, args.profile, args.session, dl_js) != "clicked":
            raise RuntimeError(ERR_DL_TIMEOUT)
        # 5) 轮询 Downloads 落盘（实测坑 #3）
        deadline = time.time() + args.dl_timeout
        src = None
        while time.time() < deadline:
            time.sleep(4)
            src = latest_gemini_download(before)
            if src and src.stat().st_size > 10000:
                break
            src = None
        if not src:
            raise RuntimeError(ERR_DL_TIMEOUT)
    except RuntimeError as e:
        code = str(e)
        msg = {
            ERR_OPENCLI_MISSING: "opencli runtime missing",
            ERR_BRIDGE: "browser bridge timeout; run `opencli doctor`",
            ERR_GEN_TIMEOUT: f"image not ready within {args.timeout}s (Nano Banana may be busy)",
            ERR_DL_TIMEOUT: "download did not land in Downloads in time",
        }.get(code, f"workflow failed: {code}")
        return _fail(code if code.startswith("ERR_") else ERR_BRIDGE, msg)

    # 6) 魔数 + 归档 + 哈希校验
    ext = check_magic(src)
    if not ext:
        return _fail(ERR_MAGIC, f"downloaded file is not a known image format: {src.name}")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = out_dir / f"{ts}-{slugify(prompt)}{ext}"
    shutil.copy2(src, dest)
    h_src = hashlib.sha256(src.read_bytes()).hexdigest()
    h_dst = hashlib.sha256(dest.read_bytes()).hexdigest()
    if h_src != h_dst:
        return _fail(ERR_HASH, f"sha256 mismatch after copy: {h_src} vs {h_dst}")
    if not args.keep_in_downloads:
        src.unlink(missing_ok=True)
    manifest = dest.with_suffix(".manifest.json")
    manifest.write_text(json.dumps({
        "schema": "41-pkos-gemini-image:1", "stem": dest.stem, "prompt": prompt,
        "bytes": dest.stat().st_size, "sha256": h_dst,
        "source_download": src.name, "channel": "gemini-web (OpenCLI, Nano Banana)",
        "session": args.session, "profile": args.profile, "captured_at": ts,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"accepted": True, "image": str(dest), "manifest": str(manifest),
                      "bytes": dest.stat().st_size, "sha256": h_dst[:16] + "..."},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
