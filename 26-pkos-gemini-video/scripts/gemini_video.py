#!/usr/bin/env python3
"""pkos.gemini.video — OpenCLI 驱动已登录 Chrome 的 Gemini 网页视频生成工作流

流程: 发 prompt → 轮询生成完成(<video> 出现且 src 可访问) → 点 Download video
      → 轮询 Downloads 落盘 → 归档 workspace + sha256 校验
产出: <out-dir>/<ts>-<slug>.mp4 + .manifest.json
失败: {rejected: true, reason, error_code} exit 2 (P-07)
不变量: 产出只落 --out-dir（workspace 铁律）；不改 PKOS 套件任何文件。

实测沉淀（2026-09-04，首次跑通 /videos 全链路）：
1. 入口 https://gemini.google.com/videos；视频模式由 "Deselect Videos" 按钮存在判定
   （无该按钮=不在视频页，必须先 open 正确 URL，别在 chat 页投 prompt
   ——投错页会生成文本对话而非视频，且不报错）
2. 完成判定：document.querySelectorAll('video').length>0（<video> 出现即代表
   生成结束；src 是 contribution.usercontent.google.com 的 download 链接，
   readyState 可能为 0 但文件已可下载——别等 readyState）
3. 生成耗时分钟级（实测约 3 分钟）：--timeout 默认 600 别设太小
4. 下载按钮 aria-label="Download video"（image 单元是 Download full size image，
   别混用）。Downloads 文件名 = prompt slug 化（如 stick_figure_walking_in_rain_.mp4），
   非 Gemini_Generated_Image_* 模式——轮询必须按"新文件"而非固定前缀匹配
5. mp4 魔数：前 4 字节后跟 b"ftyp"
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
DEFAULT_SESSION = "gem"
VIDEOS_URL = "https://gemini.google.com/videos"
DOWNLOADS = Path.home() / "Downloads"

ERR_OPENCLI_MISSING = "ERR_OPENCLI_RUNTIME_MISSING"
ERR_BRIDGE = "ERR_BROWSER_BRIDGE"
ERR_TYPE = "ERR_PROMPT_INJECT_FAILED"
ERR_SEND = "ERR_SEND_FAILED"
ERR_WRONG_MODE = "ERR_NOT_VIDEO_MODE"
ERR_GEN_TIMEOUT = "ERR_VIDEO_GEN_TIMEOUT"
ERR_DL_TIMEOUT = "ERR_DOWNLOAD_TIMEOUT"
ERR_HASH = "ERR_HASH_MISMATCH"
ERR_MAGIC = "ERR_NOT_VIDEO"
ERR_OUTDIR = "ERR_OUTPUT_DIR"

VIDEO_MAGIC = b"ftyp"


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


def slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text)[:max_len].strip("-")
    return s or "video"


def check_magic(p: Path) -> bool:
    with p.open("rb") as f:
        head = f.read(12)
    return VIDEO_MAGIC in head


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="pkos.gemini.video workflow")
    ap.add_argument("--prompt", default=None)
    ap.add_argument("--prompt-file", default=None)
    ap.add_argument("--out-dir", required=True, help="workspace 目录（产出落这里，绝不写 skill 目录）")
    ap.add_argument("--timeout", type=int, default=600, help="生成等待上限秒（视频分钟级）")
    ap.add_argument("--dl-timeout", type=int, default=120, help="下载落盘等待上限秒")
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

    before = {p.name for p in DOWNLOADS.iterdir()} if DOWNLOADS.exists() else set()

    try:
        # 1) 打开 Videos 页
        _opencli(opencli_path, args.profile, "browser", args.session, "open", VIDEOS_URL)
        time.sleep(6)
        # 2) 模式校验：必须在视频模式（Deselect Videos 按钮存在）
        mode = _eval(opencli_path, args.profile, args.session,
                     "(() => [...document.querySelectorAll('button')].some("
                     "b=>(b.getAttribute('aria-label')||'').includes('Deselect Videos')) ? 'video' : 'other')()")
        if mode != "video":
            raise RuntimeError(ERR_WRONG_MODE)
        # 3) 注入 prompt + 发送（同 image 单元三件套）
        inject_js = (
            "(() => { const el=document.querySelector(\"div[contenteditable='true'][role='textbox']\")"
            "||document.querySelector(\"div[contenteditable='true']\");"
            " if(!el) return 'no-input'; el.focus();"
            " document.execCommand('insertText', false, " + js_str(prompt) + ");"
            " return 'injected'; })()"
        )
        if _eval(opencli_path, args.profile, args.session, inject_js) != "injected":
            raise RuntimeError(ERR_TYPE)
        send_js = ('(() => { const b=[...document.querySelectorAll("button")]'
                   '.find(x=>/send/i.test(x.getAttribute("aria-label")||""));'
                   ' if(!b) return "no-send"; b.click(); return "sent"; })()')
        if _eval(opencli_path, args.profile, args.session, send_js) != "sent":
            raise RuntimeError(ERR_SEND)
        # 3.5) 发送确认（2026-09-05 实战坑：模板画廊态下点击可能丢失，prompt 滞留输入框）
        #      确认输入框已清空，否则重发一次
        confirm_js = ("(() => { const el=document.querySelector(\"div[contenteditable='true'][role='textbox']\")"
                      "||document.querySelector(\"div[contenteditable='true']\");"
                      " return (!el || el.innerText.trim()==='') ? 'clear' : 'stuck'; })()")
        time.sleep(3)
        if _eval(opencli_path, args.profile, args.session, confirm_js) == "stuck":
            if _eval(opencli_path, args.profile, args.session, send_js) != "sent":
                raise RuntimeError(ERR_SEND)
            time.sleep(3)
        # 4) 轮询生成完成：<video> 出现即 done（分钟级，readyState 不可靠）
        gen_js = "(() => JSON.stringify({n: document.querySelectorAll('video').length}))()"
        deadline = time.time() + args.timeout
        while time.time() < deadline:
            time.sleep(15)
            try:
                if json.loads(_eval(opencli_path, args.profile, args.session, gen_js)).get("n", 0) > 0:
                    break
            except ValueError:
                continue
        else:
            raise RuntimeError(ERR_GEN_TIMEOUT)
        time.sleep(4)  # 等下载按钮就绪
        # 5) 下载：先 scrollIntoView 再点（2026-09-05 实战坑：按钮在可视区外时 click 无效，
        #    y=-406 实测）；按钮路径失败则回退 a[download] 直触 video.src（带登录态，最可靠）
        dl_js = ('(() => { const b=[...document.querySelectorAll("button")]'
                 '.find(x=>(x.getAttribute("aria-label")||"").includes("Download video"));'
                 ' if(!b) return "no-btn"; b.scrollIntoView({block:"center"});'
                 ' const r=b.getBoundingClientRect();'
                 ' if(r.y<0||r.y>window.innerHeight) return "offscreen";'
                 ' b.click(); return "clicked"; })()')
        dl_result = _eval(opencli_path, args.profile, args.session, dl_js)
        if dl_result == "offscreen":
            time.sleep(2)
            dl_result = _eval(opencli_path, args.profile, args.session, dl_js)
        if dl_result != "clicked":
            # 回退：a[download] 直触 video.src
            fallback_js = ("(() => { const v=document.querySelector('video');"
                           " if(!v||!v.src) return 'no-src';"
                           " const a=document.createElement('a'); a.href=v.src;"
                           " a.download='gemini-video.mp4'; document.body.appendChild(a);"
                           " a.click(); a.remove(); return 'dl-triggered'; })()")
            if _eval(opencli_path, args.profile, args.session, fallback_js) not in ("dl-triggered", "clicked"):
                raise RuntimeError(ERR_DL_TIMEOUT)
        # 6) 轮询 Downloads 新文件（按"新出现"匹配，不按固定前缀；mp4 体积大，阈值 100KB）
        deadline = time.time() + args.dl_timeout
        src = None
        while time.time() < deadline:
            time.sleep(5)
            if DOWNLOADS.exists():
                cands = [p for p in DOWNLOADS.iterdir()
                         if p.name not in before and p.is_file()
                         and p.suffix not in (".crdownload", ".tmp")
                         and p.stat().st_size > 100000]
                if cands:
                    src = max(cands, key=lambda p: p.stat().st_mtime)
                    break
        if not src:
            raise RuntimeError(ERR_DL_TIMEOUT)
    except RuntimeError as e:
        code = str(e)
        msg = {
            ERR_OPENCLI_MISSING: "opencli runtime missing",
            ERR_BRIDGE: "browser bridge timeout; run `opencli doctor`",
            ERR_WRONG_MODE: "not in video mode (Deselect Videos missing); check URL=gemini.google.com/videos",
            ERR_GEN_TIMEOUT: f"video not ready within {args.timeout}s (generation is minute-scale)",
            ERR_DL_TIMEOUT: "download did not land in Downloads in time",
        }.get(code, f"workflow failed: {code}")
        return _fail(code if code.startswith("ERR_") else ERR_BRIDGE, msg)

    # 7) 魔数 + 归档 + 哈希校验
    if not check_magic(src):
        return _fail(ERR_MAGIC, f"downloaded file is not mp4: {src.name}")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = out_dir / f"{ts}-{slugify(prompt)}.mp4"
    shutil.copy2(src, dest)
    h_src = hashlib.sha256(src.read_bytes()).hexdigest()
    h_dst = hashlib.sha256(dest.read_bytes()).hexdigest()
    if h_src != h_dst:
        return _fail(ERR_HASH, f"sha256 mismatch after copy: {h_src} vs {h_dst}")
    if not args.keep_in_downloads:
        src.unlink(missing_ok=True)
    manifest = dest.with_suffix(".manifest.json")
    manifest.write_text(json.dumps({
        "schema": "26-pkos-gemini-video:1", "stem": dest.stem, "prompt": prompt,
        "bytes": dest.stat().st_size, "sha256": h_dst,
        "source_download": src.name, "channel": "gemini-web (OpenCLI, /videos)",
        "session": args.session, "profile": args.profile, "captured_at": ts,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"accepted": True, "video": str(dest), "manifest": str(manifest),
                      "bytes": dest.stat().st_size, "sha256": h_dst[:16] + "..."},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
