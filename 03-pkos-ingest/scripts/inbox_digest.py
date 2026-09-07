# -*- coding: utf-8 -*-
"""INBOX 消化执行器（09-05）：71 篇存量 → 装配为合规条目落 00-收件暂存。

管线（01-pkos-intake → 03-pkos-ingest 装配规则）：
  1. 读取原文件 front matter（title/source/published/created/description 原样保留）
  2. title 为匿名占位（Post by @xxx on X）时用 description 首句生成真标题
  3. 正文原样保留（只去壳不改写——ingest 铁律）
  4. 补齐 type/status/domain/capture-method/pkos-schema 标准字段
  5. 文件名 = created_slug-hash.md（assemble.py 同款规则）
  6. 原件移入 _PKOS/INBOX/_processed/（不删，可追溯）
之后每条 status=triaged，后续 analyzed 推进走 commit.py 状态机。
"""
import json
import os
import re
import hashlib
import shutil
import sys
import time
from pathlib import Path

V = Path(r"D:/obsidian知识库/obsidian知识库")
# 09-06 修正：真收件箱 = vault/obsidian知识库/（剪藏插件投放点，34 件实测）；
# _PKOS/INBOX 已空、00-收件暂存/00_收件暂存 均不存在（用户重组库后废弃）。
# 装配产物直接落原目录同级的 _PKOS/INBOX 装配区，原件移 _processed（不删可追溯）。
INBOX = V / "obsidian知识库"
STAGE = V / "_PKOS" / "entries-staging"
PROCESSED = V / "_PKOS" / "INBOX" / "_processed"

KW_MAP = {
    "ai-coding": ["codex", "claude", "agent", "api", "token", "llm", "skill", "workflow",
                  "多agent", "数字员工", "agi", "gpt", "gemini", "编程", "代码"],
    "selfhost-net": ["代理", "梯子", "vps", "ssh", "服务器", "proxy", "edge", "地区限制",
                     "域名", "google workspace", "edu邮箱", "教育邮箱", "地址证明"],
    "ai-art": ["提示词", "prompt", "写真", "人像", "漫画", "水彩", "插画", "aiart",
               "分镜", "画风", "彩铅", "绘本", "人脸", "角色参考"],
    "make-money": ["涨粉", "收益", "变现", "副业", "搞钱", "爆款", "起号", "小红书",
                   "视频号", "口播", "带货", "卖爆", "月入"],
    "obsidian-pkm": ["obsidian", "笔记", "知识库", "zettelkasten", "双链"],
}


def parse_fm(text):
    # 8 篇带 BOM（\ufeff--- 开头），strip 后再解析；真无 FM 的按整体正文处理
    m = re.match(r"^---\n(.*?)\n---\n", text.lstrip("\ufeff").lstrip(), re.S)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        km = re.match(r'^([a-zA-Z-]+):\s*"?(.*?)"?\s*$', line)
        if km and km.group(2):
            fm[km.group(1)] = km.group(2).strip()
    return fm, text[m.end():]


def guess_domain(text):
    low = text.lower()
    # 加权：写真/绘画类强信号 > 泛 AI 词（gpt/agi 常只作为工具名出现在艺术帖）
    weights = {}
    for k, kws in KW_MAP.items():
        w = sum(3 if kw in ("写真", "人像", "aiart", "漫画", "水彩", "插画", "彩铅",
                            "绘本", "分镜", "画风", "角色参考") else 1
                for kw in kws if kw in low)
        weights[k] = w
    best = max(weights, key=weights.get)
    return best if weights[best] > 0 else "ai-coding"   # 低置信兜底归 AI 主域


def make_title(fm, body, fname):
    """匿名标题恢复：description 首句（截 30 字）。"""
    title = fm.get("title", "")
    if title and not title.startswith("Post by @"):
        return title
    desc = fm.get("description", "")
    if desc:
        first = re.split(r"[。！\n]", desc)[0].strip()
        if len(first) >= 8:
            return first[:30]
    firstline = next((l.strip() for l in body.splitlines()
                      if l.strip() and not l.startswith("![") and not l.startswith(">")), "")
    return (firstline[:30] or fname[:30]).strip()


def slugify(t):
    return (re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-") or "entry")[:40]


def main():
    dry = "--dry" in sys.argv
    PROCESSED.mkdir(exist_ok=True)
    STAGE.mkdir(exist_ok=True)
    files = sorted(f for f in os.listdir(INBOX) if f.endswith(".md"))
    report = {"ok": 0, "skip": 0, "names": []}
    for f in files:
        p = INBOX / f
        raw = p.read_text(encoding="utf-8", errors="replace")
        fm, body = parse_fm(raw)
        if not fm:
            report["skip"] += 1
            continue
        title = make_title(fm, body, f)
        created = fm.get("created") or fm.get("published") or "2026-09-05"
        created = created[:10]
        source = fm.get("source", "")
        domain = guess_domain(raw)
        desc = (fm.get("description") or f"{title}——网络剪藏原文")[:150].replace('"', "'")
        published = fm.get("published", "")

        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:8]
        new_name = f"{created}_{slugify(title)}_{digest}.md"
        fm_lines = [
            "---",
            f'title: "{title}"',
            f'source: "{source}"',
            f"created: {created}",
            f"updated: {created}",
            "tags:",
            "  - clippings",
            f'description: "{desc}"',
            "type: clipping",
            "status: triaged",
            f"domain: {domain}",
        ]
        if published:
            fm_lines.append(f"published: {published}")
        fm_lines += ["capture-method: reader", "pkos-schema: 1", "---", ""]
        entry = "\n".join(fm_lines) + body.rstrip() + "\n"

        if not dry:
            (STAGE / new_name).write_text(entry, encoding="utf-8")
            shutil.move(str(p), str(PROCESSED / f))
        report["ok"] += 1
        report["names"].append({"from": f, "to": new_name, "domain": domain})
    print(json.dumps({"dry": dry, **report}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
