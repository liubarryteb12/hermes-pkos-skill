#!/usr/bin/env python3
"""构建 intake 分拣测试夹具：6 类物件 + 敏感目录，全部确定性生成。

产物目录 .staging/intake-fixture/inbox/
  clipping-note.md      外部资料 MD（无 FM）→ raw / card-file-md
  my-method.md          用户成品 MD（type: method）→ own-product
  report-text.pdf       手工构造 2 页文本 PDF → card-file-pdf
  report-scanned.pdf    同构但内容流无文本操作符 → gate:reject
  report-encrypted.pdf  trailer 带 /Encrypt 标记 → gate:reject
  sample.docx           pandoc 生成、内嵌图片 → card-file-docx
  huge.pdf              seek 稀疏写到 101MB → gate:ask（超 100MB）
  账户密码/secret.md    敏感目录 → 不进清单
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

FIX = Path(__file__).resolve().parents[1] / ".staging" / "intake-fixture"
INBOX = FIX / "inbox"


def build_pdf(pages: list[list[str]], encrypt: bool = False) -> bytes:
    """最小合法 PDF：catalog/pages/(page+content)*/font，xref 偏移精确计算。"""
    objs: list[str] = []
    n = len(pages)
    font_id = 3 + 2 * n
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n))
    objs.append("<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>")
    for i, lines in enumerate(pages):
        pid, cid = 3 + 2 * i, 4 + 2 * i
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                    f"/Contents {cid} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>")
        ops = ["BT", "/F1 12 Tf", "72 720 Td"]
        for j, ln in enumerate(lines):
            if j:
                ops.append("0 -16 Td")
            safe = ln.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
            ops.append(f"({safe}) Tj")
        ops.append("ET")
        stream = "\n".join(ops)
        objs.append(f"<< /Length {len(stream.encode())} >>\nstream\n{stream}\nendstream")
    objs.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = "%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out.encode()))
        out += f"{i} 0 obj\n{body}\nendobj\n"
    xref_pos = len(out.encode())
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n"
    enc_note = " /Encrypt 99 0 R" if encrypt else ""
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R{enc_note} >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n")
    if encrypt:
        out += ("99 0 obj\n<< /Filter /Standard /V 1 /R 2 /O (placeholderown) "
                "/U (placeholderuser) /P -44 >>\nendobj\n")
    return out.encode()


def main() -> int:
    INBOX.mkdir(parents=True, exist_ok=True)

    (INBOX / "clipping-note.md").write_text(
        "# Zettelkasten 实践入门\n\n这是一篇外部文章的本地 MD 导出，没有 front matter。\n\n"
        "- 要点一：卡片笔记强调自主组织\n- 要点二：链接比分类重要\n",
        encoding="utf-8")

    (INBOX / "my-method.md").write_text(
        "---\ntitle: 三步复盘法\ntype: method\ndomain: workflow-skills\n---\n\n"
        "## 步骤\n\n1. 记录事实\n2. 对比预期\n3. 提炼规则\n",
        encoding="utf-8")

    (INBOX / "report-text.pdf").write_bytes(build_pdf([
        ["PKOS Intake Text PDF Fixture", "Page one: deterministic extraction demo.",
         "This line exists so the text-layer probe finds Tj operators."],
        ["Page two: anchors.", "Each extracted page gets a pkos:page comment anchor."],
    ]))

    (INBOX / "report-scanned.pdf").write_bytes(build_pdf([[], []]))

    (INBOX / "report-encrypted.pdf").write_bytes(build_pdf(
        [["secret content"]], encrypt=True))

    # docx：先造一张 1x1 PNG，pandoc 内嵌后即含媒体
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c626001000000ffff03000006000557bfabd40000000049454e44ae426082")
    tmp = FIX / "_tmp"
    tmp.mkdir(exist_ok=True)
    (tmp / "tiny.png").write_bytes(png)
    (tmp / "doc-src.md").write_text(
        "# DOCX 转换夹具\n\n这一段文字用来验证 pandoc 确定性转换。\n\n![示意图](tiny.png)\n\n"
        "| 列A | 列B |\n|---|---|\n| 1 | 2 |\n", encoding="utf-8")
    subprocess.run(["pandoc", str(tmp / "doc-src.md"), "-o", str(INBOX / "sample.docx")],
                   check=True)

    # 101MB 超限件：seek 稀疏写，不占真实磁盘
    with open(INBOX / "huge.pdf", "wb") as f:
        f.write(b"%PDF-1.4\n")
        f.seek(101 * 1024 * 1024)
        f.write(b"%%EOF")

    (INBOX / "账户密码").mkdir(exist_ok=True)
    (INBOX / "账户密码" / "secret.md").write_text("机密", encoding="utf-8")

    print("fixtures ready at", INBOX)
    return 0


if __name__ == "__main__":
    sys.exit(main())
