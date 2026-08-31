#!/usr/bin/env python3
"""pkos.gemini.chat — OpenCLI 驱动已登录 Chrome 的 Gemini 网页对话工作流

流程: 发 prompt → 轮询回复 → 抓文本 → 落盘 workspace（绝不写 skill 目录）
产出: <out-dir>/<ts>-<slug>.md + .manifest.json
失败: {rejected: true, reason, error_code} exit 2 (P-07)
依赖: opencli CLI（--opencli 指定路径，默认 %LOCALAPPDATA%/OpenCLIApp/...）
不变量: 本脚本不写 PKOS 套件目录（产出物铁律）；telemetry 不涉及（utility 层直调）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

DEFAULT_OPENCLI = Path.home() / "AppData/Local/OpenCLIApp/node_modules/@jackwener/opencli/dist/src/main.js"
DEFAULT_PROFILE = "5d5kre8b"
DEFAULT_SESSION = "gemini-pkos"
DEFAULT_URL = "https://gemini.google.com/app"

ERR_OPENCLI_MISSING = "ERR_OPENCLI_RUNTIME_MISSING"
ERR_BRIDGE = "ERR_BROWSER_BRIDGE"
ERR_TYPE_FAILED = "ERR_PROMPT_INJECT_FAILED"
ERR_SEND_FAILED = "ERR_SEND_FAILED"
ERR_TIMEOUT = "ERR_REPLY_TIMEOUT"
ERR_EMPTY = "ERR_EMPTY_REPLY"
ERR_OUTDIR = "ERR_OUTPUT_DIR"


def _fail(code: str, reason: str) -> int:
    print(json.dumps({"rejected": True, "error_code": code, "reason": reason},
                     ensure_ascii=False, indent=2))
    return 2


def _opencli(opencli_path: Path, profile: str, *args: str, timeout: int = 90) -> tuple[int, str]:
    cmd = ["node", str(opencli_path), "--profile", profile, *args]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
    except FileNotFoundError:
        raise RuntimeError(ERR_OPENCLI_MISSING)
    except subprocess.TimeoutExpired:
        raise RuntimeError(ERR_BRIDGE)
    out = "\n".join(l for l in (r.stdout or "").splitlines()
                    if "Update available" not in l and "npm install" not in l)
    return r.returncode, out


def _eval(opencli_path: Path, profile: str, session: str, js: str) -> str:
    """eval 返回原始 stdout（可能是 JSON 字符串或裸文本，由调用方自行解析）。"""
    rc, out = _opencli(opencli_path, profile, "browser", session, "eval", js)
    return out.strip()


def js_str(s: str) -> str:
    """JSON 转义用于嵌入 JS。"""
    return json.dumps(s, ensure_ascii=False)


def send_prompt(opencli_path: Path, profile: str, session: str, prompt: str) -> None:
    """定位输入框 → type → 点发送。"""
    find_js = ("(() => { const el=document.querySelector(\"div[contenteditable='true']\");"
               " return JSON.stringify({found: !!el}); })()")
    rc, out = _opencli(opencli_path, profile, "browser", session, "eval", find_js)
    if "true" not in out:
        raise RuntimeError(ERR_TYPE_FAILED)
    # 用 opencli type 语义（fill contenteditable）经 eval 直接注入 + input 事件
    inject_js = (
        "(() => { const el=document.querySelector(\"div[contenteditable='true']\");"
        " if(!el) return 'no-input';"
        " el.focus();"
        " document.execCommand('insertText', false, " + js_str(prompt) + ");"
        " return 'injected'; })()"
    )
    out = _eval(opencli_path, profile, session, inject_js)
    if out != "injected":
        raise RuntimeError(ERR_TYPE_FAILED)
    send_js = ('(() => { const b=document.querySelector(\'button[aria-label="Send message"]\');'
               ' if(!b) return "no-send"; b.click(); return "sent"; })()')
    out = _eval(opencli_path, profile, session, send_js)
    if out != "sent":
        raise RuntimeError(ERR_SEND_FAILED)


def wait_reply(opencli_path: Path, profile: str, session: str,
               my_len: int, timeout_s: int, poll_s: int = 6) -> str:
    """轮询：最后一条 user 消息之后出现新的 Gemini said 且文本稳定即完成。"""
    state_js = (
        "(() => { const root=document.querySelector('chat-app');"
        " const t=root?root.innerText:document.body.innerText;"
        " const i=t.lastIndexOf('Gemini said');"
        " return JSON.stringify({tail: t.slice(Math.max(0, t.length-4000)), len: t.length}); })()"
    )
    deadline = time.time() + timeout_s
    prev_len = -1
    stable = 0
    while time.time() < deadline:
        time.sleep(poll_s)
        try:
            raw = _eval(opencli_path, profile, session, state_js)
        except RuntimeError:
            continue
        try:
            data = json.loads(raw)
        except ValueError:
            data = {"tail": raw, "len": len(raw)}
        text = data.get("tail", "") if isinstance(data, dict) else str(data)
        # 生成中的标志（出现在 tail 末尾附近即视为仍在流式）
        busy = any(m in text[-300:] for m in ("Creating", "Generating"))
        if not busy and data.get("len", 0) == prev_len and text.strip():
            stable += 1
            if stable >= 2:
                return text
        else:
            stable = 0
        prev_len = data.get("len", 0)
    raise RuntimeError(ERR_TIMEOUT)


def extract_reply(tail: str) -> str:
    """从 tail 取最后一条 Gemini said 之后的正文（截到页脚前）。"""
    i = tail.rfind("Gemini said")
    if i < 0:
        raise RuntimeError(ERR_EMPTY)
    body = tail[i + len("Gemini said"):].lstrip()
    for footer in ("Gemini is AI and can make mistakes.", "Pro\n", "Flash\n"):
        k = body.find(footer)
        if k > 0:
            body = body[:k]
    return body.strip()


def slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text)[:max_len].strip("-")
    return s or "reply"


def build_prompt(prompt: str, caller_role: str | None, gemini_role: str | None,
                 fmt: str) -> str:
    """双向角色 + 输出契约 + 反奉承尾标（ASKING-FRAMEWORK.md §一/§二/§三）。"""
    parts: list[str] = []
    if caller_role:
        parts.append(f"【我是谁】{caller_role}")
    if gemini_role:
        parts.append(f"【你是谁】{gemini_role}。以该身份的专业标准审视问题，不要附和我。")
    parts.append(f"【任务】{prompt}")
    if fmt == "direct":
        parts.append("输出要求：直接给结论，不要开场白、不要复述我的问题、不要总结陈词。")
    elif fmt == "steps":
        parts.append("输出要求：按编号步骤给出，每步一句话+一个要点，不要寒暄。")
    elif fmt == "table":
        parts.append("输出要求：用 markdown 表格回答，不要表格外的长段落。")
    parts.append("回答要求：直接、可证伪、不奉承。如果你的判断与我的前提冲突，先指出冲突；"
                 "不确定就说不确定并给出验证方法，不要编。")
    return "\n\n".join(parts)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="pkos.gemini.chat workflow")
    ap.add_argument("--prompt", default=None)
    ap.add_argument("--prompt-file", default=None)
    ap.add_argument("--out-dir", required=True, help="workspace 目录（产出落这里，绝不写 skill 目录）")
    ap.add_argument("--timeout", type=int, default=180, help="回复等待上限秒")
    ap.add_argument("--session", default=DEFAULT_SESSION)
    ap.add_argument("--profile", default=DEFAULT_PROFILE)
    ap.add_argument("--opencli", default=str(DEFAULT_OPENCLI))
    ap.add_argument("--caller-role", default=None, help="调用方角色声明（ASKING-FRAMEWORK §一）")
    ap.add_argument("--gemini-role", default=None, help="Gemini 专家角色（ASKING-FRAMEWORK §一）")
    ap.add_argument("--format", dest="fmt", choices=("direct", "steps", "table", "none"),
                    default="direct", help="输出契约（默认 direct=只要结论）")
    ap.add_argument("--raw", action="store_true", help="不加任何框架，纯裸问（对比/调试用）")
    args = ap.parse_args(argv)

    opencli_path = Path(args.opencli)
    if not opencli_path.exists():
        return _fail(ERR_OPENCLI_MISSING, f"opencli runtime not found: {opencli_path}")
    prompt = ""
    if args.prompt_file:
        pf = Path(args.prompt_file)
        if not pf.exists():
            return _fail(ERR_OUTDIR, f"prompt file missing: {pf}")
        prompt = pf.read_text(encoding="utf-8")
    elif args.prompt:
        prompt = args.prompt
    if not prompt.strip():
        return _fail(ERR_OUTDIR, "empty prompt")
    if not args.raw:
        prompt = build_prompt(prompt, args.caller_role, args.gemini_role, args.fmt)
    out_dir = Path(args.out_dir)
    if not out_dir.exists():
        return _fail(ERR_OUTDIR, f"out-dir must exist (workspace rule): {out_dir}")

    try:
        # 1) 打开/复用会话页
        _opencli(opencli_path, args.profile, "browser", args.session, "open", DEFAULT_URL, timeout=120)
        time.sleep(4)
        # 2) 发送
        send_prompt(opencli_path, args.profile, args.session, prompt)
        # 3) 轮询回复
        tail = wait_reply(opencli_path, args.profile, args.session, len(prompt), args.timeout)
        reply = extract_reply(tail)
        if not reply:
            raise RuntimeError(ERR_EMPTY)
    except RuntimeError as e:
        code = str(e)
        msg = {
            ERR_OPENCLI_MISSING: "opencli runtime missing; install OpenCLIApp or pass --opencli",
            ERR_BRIDGE: "browser bridge timeout; run `opencli doctor`",
        }.get(code, f"workflow failed: {code}")
        return _fail(code if code.startswith("ERR_") else ERR_BRIDGE, msg)

    # 4) 落盘 workspace
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    stem = f"{ts}-{slugify(prompt)}"
    md = out_dir / f"{stem}.md"
    manifest = out_dir / f"{stem}.manifest.json"
    body = (f"---\nprompt: {json.dumps(prompt, ensure_ascii=False)}\n"
            f"channel: gemini-web (OpenCLI)\nsession: {args.session}\n"
            f"captured_at: {ts}\n---\n\n# Prompt\n\n{prompt}\n\n# Gemini Reply\n\n{reply}\n")
    md.write_text(body, encoding="utf-8")
    manifest.write_text(json.dumps({
        "schema": "pkos-gemini-chat:1", "stem": stem, "prompt": prompt,
        "reply_chars": len(reply), "reply_sha256": hashlib.sha256(reply.encode()).hexdigest(),
        "session": args.session, "profile": args.profile, "captured_at": ts,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"accepted": True, "md": str(md), "manifest": str(manifest),
                      "reply_chars": len(reply)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
