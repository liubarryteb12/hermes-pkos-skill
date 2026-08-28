#!/usr/bin/env python3
"""render —— 确定性装配：Markdown 中间表示 + 主题 → 单文件离线 HTML。

用法：
  python render.py --content article.md --theme <theme-dir> \
      --route-id RT-… --source-id 条目名 --out out.html

确定性契约：同输入两次渲染产物逐字节一致（无时间戳、无随机序）。
LLM 只产 Markdown；HTML 组件一律来自 theme（禁止手写标签样式）。

[v2.2+] Safety: 渲染层绝对只读 — args.out 必须落在隔离区
  (_PKOS/_Export/ 或 .staging/)，拒绝把 HTML 写回 vault 源目录。
  这是为了在 LLM 误传路径或 v0 旧调用方传入 vault 路径时 fail loud。
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import hashlib
from pathlib import Path

# v3.1 共享库 (类型守卫 + 物理 Hash 断言 + Telemetry + Raw Fallback)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pkos_v31_lib import (
    MAX_RETRY, HOOK_VAULT_TTL_DAYS, hash_file, assert_unchanged,
    assert_typed, emit_render, raw_fallback, with_max_retry, write_with_retry,
)

# v3.0 控制引擎常量
MAX_RETRY = 2          # Hook 1: 防死循环硬拦截 (从 lib 重导出)
HOOK_VAULT_TTL = 30     # Hook 2: 核心库 30 天只读 TTL 提示（仅记录，不删）

# v2.2 写入白名单前缀：仅允许产物落这些隔离区
SAFE_OUT_PREFIXES = (
    "_PKOS/_Export/",
    "_PKOS/reports/",
    "_PKOS/exports/",
    ".staging/",
    "dist/",
    "out/",
    "build/",
)

# v2.3 拒绝前缀：绝对禁止的相对位置（这些段出现就 fail）
FORBIDDEN_OUT_SEGMENTS = (
    "entries",
    "00-", "10-", "20-", "30-", "40-",
    "50-", "60-", "70-", "80-", "90-",
)


def _resolve_real_path(out_path: Path) -> Path:
    """解析 symlink + 规范化 ..，返回绝对路径。"""
    try:
        return out_path.resolve(strict=False)
    except (OSError, RuntimeError):
        return out_path.absolute()


def assert_safe_out(out_path: Path) -> None:
    """渲染层绝对只读 — 出口路径必须在隔离区白名单内。

    v2.3.1 加固:
      1) symlink 解析: 真实路径不在白名单 = 拒
      2) .. 跳出: resolve 后检查前缀
      3) 空文件名 / 非 .html 后缀: 拒
      4) UNC / 网络盘: 拒
      5) 双重判定: 原始路径 + 真实路径(解析symlink/..后) 都必须在白名单
    """
    if not isinstance(out_path, Path):
        try:
            out_path = Path(str(out_path))
        except Exception:
            print("ERROR: render.py 收到非法 out 路径", file=sys.stderr)
            sys.exit(4)

    p_str = str(out_path).replace("\\", "/")
    fname = p_str.rsplit("/", 1)[-1] if "/" in p_str else p_str

    # 1. 必须以 .html 结尾
    if not fname.endswith(".html"):
        print(
            f"ERROR: render.py 拒绝 {p_str} — 渲染层只产出 .html，非 .html 后缀拒绝。",
            file=sys.stderr,
        )
        sys.exit(4)

    # 2. 空文件名 / 纯前缀路径
    if not fname or fname in (".html", "/.html"):
        print(f"ERROR: render.py 拒绝空文件名 {p_str}", file=sys.stderr)
        sys.exit(4)

    # 3. UNC / 网络盘
    if p_str.startswith("//") or p_str.startswith("\\\\"):
        print(f"ERROR: render.py 拒绝 UNC 路径 {p_str}", file=sys.stderr)
        sys.exit(4)

    # 4. 解析 symlink + .. 跳出 → 真实路径
    try:
        real = _resolve_real_path(out_path)
        real_str = str(real).replace("\\", "/")
    except Exception:
        real_str = p_str

    # 5. **白名单双重判定**: 原始路径与真实路径都必须通过
    #    v3.3: Windows 大小写不敏感归一化（防 Case 变体绕过前缀匹配）
    def passes_white(s: str) -> bool:
        s_low = s.lower()
        for prefix in SAFE_OUT_PREFIXES:
            if prefix.lower() in s_low:
                return True
        if "/_pkos/" in s_low:
            return True
        return False

    p_pass = passes_white(p_str)
    r_pass = passes_white(real_str)
    if not (p_pass and r_pass):
        print(
            f"ERROR: render.py 拒绝 {p_str} (real={real_str}) — 渲染层绝对只读。\n"
            f"  原始路径通过白名单: {p_pass}\n"
            f"  真实路径通过白名单: {r_pass}\n"
            f"  双层都必须通过才放行。",
            file=sys.stderr,
        )
        sys.exit(4)

    # 6. 黑名单：entries / 数字目录段（原始 + 真实，大小写归一化比对）
    parts = [seg.lower() for seg in p_str.split("/")]
    real_parts = [seg.lower() for seg in real_str.split("/")]
    for seg in FORBIDDEN_OUT_SEGMENTS:
        if seg.lower() in parts or seg.lower() in real_parts:
            print(
                f"ERROR: render.py 拒绝把 HTML 写入 {p_str} (real={real_str}) — "
                f"渲染层绝对只读，落 vault 源目录 {seg} 段是越权。",
                file=sys.stderr,
            )
            sys.exit(4)

    # 7. v3.3 [NTFS ADS 防御]: 文件名部分含 ':' 即拒绝（备用数据流注入 file.html:stream）
    #    合法盘符冒号只出现在路径首段（如 D:\），此处检查文件名段与中间段
    for seg in p_str.split("/"):
        if not seg:
            continue
        if ":" in seg and not (len(seg) == 2 and seg[1] == ":"):
            print(
                f"ERROR: render.py 拒绝 {p_str} — 检测到 NTFS 备用数据流(ADS)冒号 "
                f"(段 '{seg}')，防 file.html:stream 注入。",
                file=sys.stderr,
            )
            sys.exit(4)


def assert_source_unchanged(source_path: Path, pre_hash: str) -> None:
    """v3.0 [Self-check 断言 A]: 渲染后断言源文件 exists 且 SHA256 不变。

    Hook 2 (Immutable Vault Hook) + Hook 3 (Zero-Deletion Hook) 物理执行点。
    失败立即 sys.exit(5) 并打印差异摘要。
    """
    if not source_path.exists():
        print(
            f"FATAL [Self-check A]: 源文件不存在 {source_path} — "
            f"渲染层不得删除源 .md。",
            file=sys.stderr,
        )
        sys.exit(5)
    post_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    if post_hash != pre_hash:
        print(
            f"FATAL [Self-check A]: 源文件哈希变化 {source_path}\n"
            f"  pre  = {pre_hash}\n"
            f"  post = {post_hash}\n"
            f"渲染层违反 Immutable Vault 铁律。",
            file=sys.stderr,
        )
        sys.exit(5)


def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def md_to_body(md: str) -> tuple[str, str]:
    """返回 (title, body_html)。支持子集：# 标题、## 章节(自动编号)、###、段落、
    > 引用、ol/ul、表格、--- 分隔。"""
    lines = md.splitlines()
    title = ""
    body: list[str] = []
    i, sec_no = 0, 0
    para: list[str] = []

    def flush_para():
        if para:
            body.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()

    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            flush_para(); i += 1; continue
        m = re.match(r"^(#{1,3})\s+(.*)$", ln)
        if m:
            flush_para()
            level, text = len(m.group(1)), m.group(2).strip()
            if level == 1 and not title:
                title = text
                body.append(f'<h1 class="pk-title">{inline(text)}</h1>')
            elif level == 2:
                sec_no += 1
                body.append(f'<h2 class="pk-h2"><span class="pk-no">{sec_no:02d}</span>{inline(text)}</h2>')
            else:
                body.append(f"<h3 class=\"pk-h3\">{inline(text)}</h3>")
            i += 1; continue
        if ln.startswith(">"):
            flush_para()
            quote = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(lines[i].lstrip(">").strip()); i += 1
            inner = "".join(f"<p>{inline(q)}</p>" for q in quote if q)
            body.append(f'<blockquote class="pk-callout">{inner}</blockquote>')
            continue
        if re.match(r"^\d+\.\s+", ln):
            flush_para()
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i]):
                items.append(re.sub(r"^\d+\.\s+", "", lines[i]).strip()); i += 1
            body.append('<ol class="pk-steps">' +
                        "".join(f"<li>{inline(x)}</li>" for x in items) + "</ol>")
            continue
        if ln.lstrip().startswith("- "):
            flush_para()
            items = []
            while i < len(lines) and lines[i].lstrip().startswith("- "):
                items.append(lines[i].lstrip()[2:].strip()); i += 1
            body.append('<ul class="pk-dash">' +
                        "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>")
            continue
        if ln.strip().startswith("|") and i + 1 < len(lines) and set(lines[i + 1].replace("|", "").strip()) <= set("-: "):
            flush_para()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(cells); i += 1
            head = "".join(f"<th>{inline(c)}</th>" for c in rows[0])
            trs = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>"
                          for r in rows[1:])
            body.append(f'<table class="pk-zebra"><thead><tr>{head}</tr></thead><tbody>{trs}</tbody></table>')
            continue
        if ln.strip() == "---":
            flush_para(); i += 1; continue
        para.append(ln.strip()); i += 1

    flush_para()
    return title or "Untitled", "\n".join(body)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--content", required=True)
    ap.add_argument("--theme", required=True)
    ap.add_argument("--route-id", required=True)
    ap.add_argument("--source-id", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    tdir = Path(args.theme)
    tj = json.loads((tdir / "theme.json").read_text(encoding="utf-8"))
    css = (tdir / "theme.css").read_text(encoding="utf-8")
    md_text = Path(args.content).read_text(encoding="utf-8")

    # v3.0 [Self-check A 前置]: 渲染前记录源文件 SHA256
    source_path = Path(args.content)
    pre_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    # 剥掉 front matter（元数据不进正文）
    if md_text.lstrip().startswith("---"):
        end = md_text.find("\n---", 3)
        md_text = md_text[end + 4:] if end != -1 else md_text

    title, body = md_to_body(md_text)
    # 出处信息只藏进注释与 meta（用户裁定：读者不可见，制作人查源码可知）
    provenance = f"route={args.route_id} source={args.source_id} theme={tj['id']}"
    doc = (
        "<!doctype html>\n"
        f'<!-- pkos-output source={args.source_id} route={args.route_id} theme={tj["id"]} -->\n'
        '<html lang="zh-CN" data-style="' + tj["id"] + '">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{html.escape(title)}</title>\n"
        f'<meta name="generator" content="PKOS render.py ({provenance})">\n'
        "<style>\n" + css + "\n</style>\n</head>\n<body>\n"
        '<main class="pk-article">\n'
        + body + "\n"
        "</main>\n</body>\n</html>\n"
    )
    out = Path(args.out)
    assert_safe_out(out)

    # v3.1 [Type System] 出口产物必须为 ExportArtifact 类型
    # v3.1 [Verification Matrix] 写前/写后物理 Hash 断言
    # v3.1 [Event Bus] 触发 telemetry
    actual_path, degraded = write_with_retry(
        out=out,
        data=doc.encode("utf-8"),
        source_path=source_path,
        pre_hash=pre_hash,
        cap_id=f"pkos.exit.html.render[{args.route_id}]",
    )
    result = {
        "out": str(actual_path),
        "title": title,
        "bytes": len(doc.encode("utf-8")),
        "degraded": degraded,
    }
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
