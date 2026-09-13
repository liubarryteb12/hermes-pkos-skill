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

_pp = __import__("sys"); _pp.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scripts"))
import pkos_paths as _ppm
V = _ppm.get_vault()
# 09-06 修正：真收件箱 = vault/obsidian知识库/（剪藏插件投放点，34 件实测）；
# _PKOS/INBOX 已空、00-收件暂存/00_收件暂存 均不存在（用户重组库后废弃）。
# 装配产物直接落原目录同级的 _PKOS/INBOX 装配区，原件移 _processed（不删可追溯）。
INBOX = V / "obsidian知识库"
STAGE = V / "_PKOS" / "entries-staging"
PROCESSED = V / "_PKOS" / "INBOX" / "_processed"

# 完整域 slug → vault 路径映射（覆盖 vault-architecture.md 全部 11 个标准域）
DOMAIN_MAP = {
    "ai-usage": V / "02-AI与Codex" / "使用相关",
    "career-growth": V / "11-职业认知",
    "humanities": V / "10-人文社科",
    "gongkao": V / "01-考公备考" / "笔记",
    "personal": V / "03-个人办事",
    "assets": V / "05-素材与图表",
    "book-notes": V / "06-书籍笔记" / "笔记",
    "rcpm": V / "07-生信分析" / "R临床预测模型",
    "scrn": V / "07-生信分析" / "单细胞基因调控网络",
    "invest": V / "08-理财投资",
    "skills": V / "04-工作流与Skills",
    "ai-coding": V / "02-AI与Codex" / "使用相关" / "06-技术工具",       # legacy alias
    "selfhost-net": V / "02-AI与Codex" / "使用相关" / "02-AI视频与数字人",  # legacy alias
    "ai-art": V / "02-AI与Codex" / "使用相关" / "生图prompt",            # legacy alias
    "make-money": V / "02-AI与Codex" / "使用相关" / "03-AI副业与变现",   # legacy alias
    "obsidian-pkm": V / "02-AI与Codex" / "使用相关",                     # legacy alias
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
    """域分类：委托给 classifier.py（model-agnostic 规则引擎）。

    返回 (domain_slug, classification_result)：
      - domain_slug: 建议域 slug（DOMAIN_MAP 键）
      - classification_result: classifier 完整结果（含 confidence/needs_human_review）
    """
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "classifier", Path(__file__).resolve().parent / "classifier.py")
        clf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(clf)
        result = clf.classify_domain(text)
        return result.get("suggested_domain", "ai-usage"), result
    except Exception:
        # 分类器不可用时降级到 ai-usage 主域（保留原行为，不静默失败）
        return "ai-usage", {"confidence": 0.0, "needs_human_review": True,
                            "reasoning": "classifier_unavailable"}


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
    # STAGE 已废弃（历史残留，不再使用）——改为直接写域目录
    files = sorted(f for f in os.listdir(INBOX) if f.endswith(".md"))
    report = {"ok": 0, "skip": 0, "names": [], "needs_review": [], "low_confidence": []}
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
        domain, clf_result = guess_domain(raw)
        confidence = clf_result.get("confidence", 0.0)
        needs_review = clf_result.get("needs_human_review", False)
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
        # 分类器置信度留痕（可追溯，便于后续人工复核）
        fm_lines.append(f"classification-confidence: {confidence}")
        fm_lines.append(f"classification-review: {str(needs_review).lower()}")
        if clf_result.get("sub_domain"):
            fm_lines.append(f"classification-sub-domain: {clf_result['sub_domain']}")
        fm_lines += ["capture-method: reader", "pkos-schema: 1", "---", ""]
        entry = "\n".join(fm_lines) + body.rstrip() + "\n"

        if not dry:
            # 修复原子性：先写域目录（通过临时文件+rename），成功后再移源文件
            dest = DOMAIN_MAP.get(domain, DOMAIN_MAP["ai-usage"])
            dest.mkdir(parents=True, exist_ok=True)
            tmp = dest / (new_name + ".tmp")
            tmp.write_text(entry, encoding="utf-8")
            tmp.rename(dest / new_name)
            # 产物写入成功后才移源文件，避免中间状态悬空
            shutil.move(str(p), str(PROCESSED / f))
        report["ok"] += 1
        report["names"].append({
            "from": f, "to": new_name, "domain": domain,
            "confidence": confidence, "sub_domain": clf_result.get("sub_domain", ""),
        })
        # 低置信度 / 跨域边界 → 单列供用户裁决（不擅自决定）
        if needs_review:
            report["needs_review"].append({
                "file": f, "domain": domain, "confidence": confidence,
                "reasoning": clf_result.get("reasoning", ""),
                "alternatives": clf_result.get("alternatives", []),
            })
    print(json.dumps({"dry": dry, **report}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
