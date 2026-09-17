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
IMAGES_URL = "https://gemini.google.com/images"  # 2026-09-15 用户裁定：固定用 /images
# 更正 09-14 的错误结论「/images 新 UI 无 Send message 按钮」——按钮是输入后才渲染
# （输入前 send=0，输入后 send=1，09-15 实测）。当时用空编辑器判定，误判为没有。
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
    ap.add_argument("--timeout", type=int, default=600, help="生成等待上限秒（09-15 用户裁定翻倍 300→600）")
    ap.add_argument("--dl-timeout", type=int, default=120, help="下载落盘等待上限秒（09-15 用户裁定翻倍 60→120）")
    ap.add_argument("--session", default=DEFAULT_SESSION)
    ap.add_argument("--profile", default=DEFAULT_PROFILE)
    ap.add_argument("--opencli", default=str(DEFAULT_OPENCLI))
    ap.add_argument("--keep-in-downloads", action="store_true", help="归档后保留 Downloads 原件")
    ap.add_argument("--url", default=IMAGES_URL,
                    help="驱动页面 URL。09-15 用户裁定固定用 /images（已登录会话）。"
                         "注：Send message 按钮是输入 prompt 后才渲染，空编辑器下查不到是正常。")
    ap.add_argument("--hard-reset", action="store_true", default=True,
                    help="close 释放租约后重新 open（默认开，保证全新上下文）")
    ap.add_argument("--no-hard-reset", dest="hard_reset", action="store_false",
                    help="不 close，直接 open（仅调试用）")
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
        # 1) 会话复位（2026-09-09 实测：opencli extension 的 click/type 事件通道会随
        #    标签页老化失效——close 释放租约 + 重新 open 是复位手段）。
        #    2026-09-14 修正：close+open 每次新建标签页，新标签在后台合成下 Angular
        #    变更检测被节流，反而使发送恒失败（ERR_SEND_FAILED）。改为默认只 open
        #    （复用现有标签页），仅在显式 --hard-reset 时才 close 重开。
        #    入口固定 /images（2026-09-15 用户裁定），已登录会话可直接用。
        #    注：Send message 按钮是输入 prompt 后才渲染，空输入框下查不到是正常
        #    （09-15 用户截图确认：空框时右侧只有 Pro 下拉 + 麦克风）。
        #    Chrome 最小化时 CDP 鼠标/键盘事件静默丢失，PowerShell 恢复+前置窗口。
        if args.hard_reset:
            _opencli(opencli_path, args.profile, "browser", args.session, "close")
            time.sleep(2)
        _opencli(opencli_path, args.profile, "browser", args.session, "open", args.url)
        restore_ps = (
            "Add-Type -MemberDefinition '[DllImport(\"user32.dll\")] public static bool "
            "ShowWindowAsync(IntPtr h, int n); public static bool SetForegroundWindow(IntPtr h);' "
            "-Name WinR -Namespace NR; "
            "$p = Get-Process chrome | Where-Object {$_.MainWindowHandle -ne 0} | Select-Object -First 1; "
            "[NR.WinR]::ShowWindowAsync($p.MainWindowHandle, 9) | Out-Null; "
            "Start-Sleep -Milliseconds 300; "
            "[NR.WinR]::SetForegroundWindow($p.MainWindowHandle) | Out-Null"
        )
        try:
            subprocess.run(["powershell", "-Command", restore_ps],
                           capture_output=True, timeout=30)
        except Exception:
            pass  # 窗口恢复失败不阻断——headless 场景可能不需要
        time.sleep(8)
        # 1.5) 激活标签页（tab active=false 时事件注入失效）
        tabs = _opencli(opencli_path, args.profile, "browser", args.session, "tab", "list")
        m_page = re.search(r'"page":\s*"([A-F0-9]+)"', tabs)
        if m_page:
            _opencli(opencli_path, args.profile, "browser", args.session,
                     "tab", "select", m_page.group(1))
            time.sleep(1)
        # 1.6) 可见性覆写（2026-09-14 根因修复）
        #     症状：type 成功、click 返回 clicked:true、指针序列也发得出，但编辑器永不清空
        #     → ERR_SEND_FAILED。四级升级（close+open / Chrome 重启 / daemon restart /
        #     keys Enter）全无效。
        #     真因：Chrome 窗口被最小化时 document.hidden=true，Gemini 的 Angular 把发送
        #     挂起/丢弃。实测把 visibilityState/hidden 覆写为 visible 并派发 visibilitychange
        #     后，编辑器立即清空、会话正常启动、图片正常生成。
        #     不依赖窗口状态（PowerShell 恢复窗口在后台进程场景下不可靠）。
        _eval(opencli_path, args.profile, args.session,
              '(() => { try {'
              ' Object.defineProperty(document,"visibilityState",{get:()=>"visible",configurable:true});'
              ' Object.defineProperty(document,"hidden",{get:()=>false,configurable:true});'
              ' document.dispatchEvent(new Event("visibilitychange"));'
              ' } catch(e) {} return document.visibilityState; })()')
        time.sleep(1)
        # 1.7) 记录发送前已有 blob 大图（判定「新图」的基线，必须在注入/发送之前）
        try:
            _base_blobs = set(json.loads(_eval(
                opencli_path, args.profile, args.session,
                '(() => JSON.stringify([...document.querySelectorAll(\'img\')]'
                '.filter(i=>i.naturalWidth>400&&i.naturalHeight>400'
                '&&i.src.startsWith(\'blob:\')).map(i=>i.src)))()')))
        except ValueError:
            _base_blobs = set()

        # 2) 注入 prompt + 发送
        # 2026-09-09 实测（Gemini 新 Quill 编辑器）：
        #   - innerText 直写 / execCommand insertText / __quill.setText 均不被 Angular 认账
        #     （send 按钮不出现或点击无效），唯一可靠通道 = CDP 真实键盘输入（opencli type）
        #   - 发送按钮 send JS click 也无效，必须 opencli click（CDP 真实鼠标）
        _opencli(opencli_path, args.profile, "browser", args.session, "eval",
                 '(() => { const q=document.querySelector(".ql-container"); '
                 'if(q&&q.__quill){q.__quill.setText(""); return "cleared";} '
                 'const el=document.querySelector("div[contenteditable=\'true\']"); '
                 'if(el){el.innerText=""; el.dispatchEvent(new InputEvent("input",{bubbles:true}));} '
                 'return "cleared"; })()')
        time.sleep(1)
        typed = _opencli(opencli_path, args.profile, "browser", args.session,
                         "type", "--nth", "0", "div.ql-editor", prompt)
        # 诊断日志：type 后状态
        import sys
        print(f"[DIAG] type returned: {typed[:150]}", file=sys.stderr, flush=True)
        if '"typed": true' not in typed and '"typed":true' not in typed:
            print(f"[DIAG] type NOT OK, full: {typed[:400]}", file=sys.stderr, flush=True)
            # 回退旧版编辑器：execCommand 注入
            inject_js = (
                "(() => {"
                " const el=document.querySelector(\"div[contenteditable='true']\");"
                " if(!el) return 'no-input'; el.focus();"
                " const sel=window.getSelection(); const range=document.createRange();"
                " range.selectNodeContents(el); range.collapse(false);"
                " sel.removeAllRanges(); sel.addRange(range);"
                " const ok=document.execCommand('insertText', false, " + js_str(prompt) + ");"
                " return (ok && el.innerText.length>0) ? 'injected' : 'empty'; })()"
            )
            if _eval(opencli_path, args.profile, args.session, inject_js) != "injected":
                raise RuntimeError(ERR_TYPE)
        # 2026-09-15 用户截图确认：/images 新 UI 的发送按钮是**输入后才渲染**——
        # 空输入框时右侧只有 Pro 下拉 + 麦克风，看不到 Send message。
        # 按钮出现约需 800ms，固定 sleep(2) 在页面慢时会抢跑（判成 no-btn 掉进 CDP 回退）。
        # 这里轮询等按钮真出现，同时验证 prompt 已进编辑器，上限 8s。
        import sys as _s2
        btn_ready = False
        for _w in range(8):
            st = _eval(opencli_path, args.profile, args.session,
                       '(() => { const q=document.querySelector(".ql-container");'
                       ' const t=(q&&q.__quill)?q.__quill.getText().length:-1;'
                       ' const b=document.querySelector(\'button[aria-label="Send message"]\');'
                       ' return JSON.stringify({edLen:t, sendBtn: !!b}); })()')
            print(f"[DIAG] wait-btn {_w*1+1}s: {st}", file=_s2.stderr, flush=True)
            try:
                _j = json.loads(st)
                if _j.get("sendBtn") and _j.get("edLen", -1) > 5:
                    btn_ready = True
                    break
            except ValueError:
                pass
            time.sleep(1)
        if not btn_ready:
            print(f"[DIAG] btn not ready after 8s", file=_s2.stderr, flush=True)
        time.sleep(0.5)
        # 发送：CDP 真实鼠标点击（JS click 不触发 Angular handler）。
        # 2026-09-09 实测：首次 click 常被 Angular 忽略（状态未同步），需要
        # "再敲一个字符刷新 input 状态 → 等 10s → 重试 click"循环，最多 3 轮。
        # 2026-09-14 实测：CDP 真实鼠标 click 在 Gemini Quill 上返回 clicked:true 但
        # Angular handler 不触发（编辑器不清空、会话不启动）；close+open 复位、
        # Chrome 重启、daemon restart、keys Enter 四级升级全部无效。
        # 唯一有效通道 = JS 完整指针序列（pointerdown→mousedown→pointerup→mouseup→click），
        # 与 24/25 号技能里元宝模型菜单的实证一致。CDP click 降级为回退。
        ptr_js = (
            '(() => {'
            ' const b=document.querySelector(\'button[aria-label="Send message"]\');'
            ' if(!b) return "no-btn";'
            ' const r=b.getBoundingClientRect();'
            ' const x=r.left+r.width/2, y=r.top+r.height/2;'
            ' const o={bubbles:true,cancelable:true,composed:true,clientX:x,clientY:y,'
            ' view:window,button:0,buttons:1};'
            ' b.dispatchEvent(new PointerEvent("pointerdown",o));'
            ' b.dispatchEvent(new MouseEvent("mousedown",o));'
            ' b.dispatchEvent(new PointerEvent("pointerup",{...o,buttons:0}));'
            ' b.dispatchEvent(new MouseEvent("mouseup",{...o,buttons:0}));'
            ' b.dispatchEvent(new MouseEvent("click",{...o,buttons:0}));'
            ' return "seq-sent"; })()'
        )
        sent_ok = False
        import sys as _s
        for attempt in range(3):
            seq = _eval(opencli_path, args.profile, args.session, ptr_js)
            print(f"[DIAG] attempt {attempt+1} ptr seq: {seq}", file=_s.stderr, flush=True)
            if seq != "seq-sent":
                print(f"[DIAG] CDP fallback", file=_s.stderr, flush=True)
                _opencli(opencli_path, args.profile, "browser", args.session,
                         "click", 'button[aria-label="Send message"]')
            time.sleep(6)
            check = _eval(opencli_path, args.profile, args.session,
                          '(() => { const q=document.querySelector(".ql-container");'
                          ' return JSON.stringify({len: (q&&q.__quill)?q.__quill.getText().length:-1}); })()')
            print(f"[DIAG] after 6s editor: {check}", file=_s.stderr, flush=True)
            try:
                if json.loads(check).get("len", -1) <= 1:
                    sent_ok = True  # 输入框已清空 = 发送成功
                    break
            except ValueError:
                pass
            # 未发出：等 10s 重试（不再追加空格——会污染 prompt）
            time.sleep(10)
        if not sent_ok:
            # Enter 兜底（2026-09-10 全平台实测：focus+keys Enter 跨站可靠）
            _opencli(opencli_path, args.profile, "browser", args.session, "focus", "div.ql-editor")
            time.sleep(1)
            _opencli(opencli_path, args.profile, "browser", args.session, "keys", "Enter")
            time.sleep(6)
            check = _eval(opencli_path, args.profile, args.session,
                          '(() => { const q=document.querySelector(".ql-container");'
                          ' return JSON.stringify({len: (q&&q.__quill)?q.__quill.getText().length:-1}); })()')
            try:
                sent_ok = json.loads(check).get("len", -1) <= 1
            except ValueError:
                sent_ok = False
        if not sent_ok:
            raise RuntimeError(ERR_SEND)
        # 3) 轮询生成完成：判定「新出现的 blob 图」而不是「任何 blob 图」
        #    2026-09-14 修正（根因）：同一会话里复用标签页时，之前的图一直挂在 DOM 上，
        #    用大图的 len>0 判定会立刻命中上一张图，下载按钮随之重复下载同一张 ——
        #    实测 070601/070602/080102/080201 四张封面 sha256 完全相同。
        #    正确判据 = 与 1.7 步记录的基线集合相比，出现新成员才算生成了。
        gen_js = ("(() => { const big=[...document.querySelectorAll('img')]"
                  ".filter(i=>i.naturalWidth>400&&i.naturalHeight>400"
                  "&&i.src.startsWith('blob:')).map(i=>i.src);"
                  " return JSON.stringify({all: big, fresh: big.filter(x=>!%s.includes(x))}); })()"
                  % js_str(list(_base_blobs)))
        deadline = time.time() + args.timeout
        while time.time() < deadline:
            time.sleep(10)
            out = _eval(opencli_path, args.profile, args.session, gen_js)
            try:
                if json.loads(out).get("fresh"):
                    break
            except ValueError:
                continue
        else:
            raise RuntimeError(ERR_GEN_TIMEOUT)
        time.sleep(4)  # 等下载按钮就绪
        # 4) 点下载（aria-label 定位，实测坑 #2）
        #    2026-09-14 修正：JS b.click() 在 Gemini 页面上不触发下载（Angular 不认
        #    合成事件，实测 ERR_DOWNLOAD_TIMEOUT）。改用 CDP 真实鼠标点击，与发送按钮
        #    同一策略；失败时再回退 JS click。
        dl_sel = 'button[aria-label*="Download full size"]'
        dl_ok = False
        dl = _opencli(opencli_path, args.profile, args.session, "click", dl_sel)
        if '"clicked": true' in dl or '"clicked":true' in dl:
            dl_ok = True
        else:
            dl_js = ('(() => { const b=[...document.querySelectorAll("button")]'
                     '.find(x=>/download full size/i.test(x.getAttribute("aria-label")||""));'
                     ' if(!b) return "no-btn"; b.click(); return "clicked"; })()')
            dl_ok = _eval(opencli_path, args.profile, args.session, dl_js) == "clicked"
        if not dl_ok:
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
        "schema": "25-pkos-gemini-image:1", "stem": dest.stem, "prompt": prompt,
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
