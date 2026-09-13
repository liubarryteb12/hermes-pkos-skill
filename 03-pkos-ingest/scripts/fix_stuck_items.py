# -*- coding: utf-8 -*-
"""
Fix stuck items in _PKOS/INBOX/_processed/.

This script handles the common case where intake scripts wrote entries to
_processed/ but failed to complete the FM assembly (missing type/status/domain
fields). It's the standard remediation for "半成品堆积" scenarios.

Usage:
    python scripts/fix_stuck_items.py [--dry] [--min-items 10]

Output:
    - Stages fixed entries to _PKOS/_staging-fix-<date>/
    - Validates via validate_entry.py
    - Moves to domain folders
    - Preserves originals in _processed/ (backup)
"""
import re
import subprocess
import sys
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Paths
SKILL_ROOT = Path(__file__).resolve().parents[2]
VAULT = Path(r"D:\obsidian知识库\obsidian知识库")
PROCESSED = VAULT / "_PKOS" / "INBOX" / "_processed"
STAGING = VAULT / "_PKOS" / f"_staging-fix-{datetime.now().strftime('%Y%m%d')}"
VALIDATE = SKILL_ROOT / "contracts" / "validate_entry.py"

# Domain classification keywords (same as inbox_digest.py)
DOMAIN_RULES = [
    (["codex", "agent", "grok", "gpt", "chatgpt", "gemini", "cursor", "Claude",
      "openai", "anthropic", "llm", "AI工具", "编程", "代码", "脚本",
      "prompt", "skill", "mcp", "api"], "ai-coding"),
    (["obsidian", "workflow", "工作流", "效率", "productivity", "知识管理",
      "笔记", "写作", "排版", "公众号"], "ai-usage"),
    (["财", "钱", "收入", "赚", "副业", "变现", "理财", "投资", "股票",
      "基金", "税务", "汇率", "stablecoin", "usdt"], "invest"),
    (["人生", "个人", "成长", "认知", "思维", "心理", "情绪", "焦虑",
      "失业", "裁员", "职场", "职业", "工作"], "career-growth"),
    (["政治", "社会", "历史", "人性", "文化", "哲学", "经济", "国家",
      "制度", "法律", "人文"], "humanities"),
    (["小说", "科幻", "漫画", "二次元", "动漫", "游戏"], "ai-art"),
    (["单细胞", "scTenifold", "基因", "生物", "临床", "医学", "研究"], "scrn"),
]

DOMAIN_MAP = {
    "ai-coding": VAULT / "02-AI与Codex" / "使用相关" / "06-技术工具",
    "ai-usage": VAULT / "02-AI与Codex" / "使用相关" / "05-AI基础知识",
    "invest": VAULT / "08-理财投资",
    "career-growth": VAULT / "11-职业认知",
    "humanities": VAULT / "10-人文社科",
    "ai-art": VAULT / "02-AI与Codex" / "使用相关" / "生图prompt",
    "scrn": VAULT / "07-生信分析" / "单细胞基因调控网络",
}


def classify_domain(body, title):
    """Auto-classify by keyword matching."""
    text = (body + " " + title).lower()
    scores = defaultdict(int)
    for keywords, slug in DOMAIN_RULES:
        for kw in keywords:
            if kw.lower() in text:
                scores[slug] += 1
    if not scores:
        return "ai-coding"  # default fallback
    return max(scores, key=scores.get)


def fix_fm(fm_text, src_url=""):
    """Add missing required fields to existing FM."""
    lines = fm_text.split("\n")
    result = []
    added = set()
    for line in lines:
        result.append(line)
        if line.startswith("type:"):
            added.add("type")
        elif line.startswith("status:"):
            added.add("status")
        elif line.startswith("domain:"):
            added.add("domain")
        elif line.startswith("capture-method:"):
            added.add("capture-method")
        elif line.startswith("pkos-schema:"):
            added.add("pkos-schema")
        elif line.strip().startswith("tags:"):
            added.add("tags")

    if "type" not in added:
        result.append("type: clipping")
    if "status" not in added:
        result.append("status: triaged")
    if "domain" not in added:
        result.append("domain: ai-coding")  # placeholder, updated below
    if "capture-method" not in added:
        result.append("capture-method: clipper")
    if "pkos-schema" not in added:
        result.append("pkos-schema: 1")
    if "tags" not in added:
        result.append("tags:")
        result.append('  - "clippings"')
        result.append('  - "x-post"')

    return "\n".join(result)


def process_file(p, dry=False):
    """Read, fix FM, validate, and move to domain."""
    try:
        t = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return None, f"READ_ERROR: {e}"

    if not t.startswith("---"):
        return None, "NO_FM"

    e = t.find("\n---", 3)
    if e < 0:
        return None, "NO_CLOSING_DASHES"

    fm = t[3:e]
    body = t[e + 4:].lstrip("\n")

    # Extract source URL for classification
    m_src = re.search(r'^source:\s*(.+)$', fm, re.M)
    src_url = m_src.group(1).strip().strip('"') if m_src else ""

    # Classify domain
    domain = classify_domain(body, p.name)

    # Fix FM
    new_fm = fix_fm(fm, src_url)
    new_fm = re.sub(r'^domain:\s*.+$', f'domain: {domain}', new_fm, flags=re.M)

    # Validate
    staged = STAGING / p.name
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_text("---\n" + new_fm + "\n---\n" + body, encoding="utf-8")

    if not dry:
        r = subprocess.run(
            [sys.executable, str(VALIDATE), str(staged)],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if r.returncode != 0:
            return None, f"VALIDATE_FAIL: {r.stdout[:100]}"

        # Move to domain
        dest = DOMAIN_MAP.get(domain)
        if dest:
            dest.mkdir(parents=True, exist_ok=True)
            target = dest / staged.name
            target.write_text(staged.read_text(encoding="utf-8"), encoding="utf-8")
            staged.unlink()

    return domain, None


def main():
    dry = "--dry" in sys.argv
    min_items = 10
    for i, arg in enumerate(sys.argv):
        if arg == "--min-items" and i + 1 < len(sys.argv):
            min_items = int(sys.argv[i + 1])

    if not PROCESSED.exists():
        print(f"PROCESSED dir not found: {PROCESSED}")
        return 1

    files = list(PROCESSED.glob("*.md"))
    print(f"Found {len(files)} files in _processed/")

    if len(files) < min_items:
        print(f"Below threshold ({min_items}), skipping.")
        return 0

    STAGING.mkdir(parents=True, exist_ok=True)
    print(f"Processing with min_items={min_items}...")

    ok, skip, errors = 0, 0, []
    for p in sorted(files):
        domain, err = process_file(p, dry=dry)
        if err:
            errors.append((p.name, err))
            skip += 1
        else:
            ok += 1
            if not dry:
                print(f"  ✓ {p.name[:50]} -> {domain}")

    print(f"\nResults: {ok} ok, {skip} skipped")
    if errors:
        print(f"Errors ({len(errors)}):")
        for name, err in errors[:5]:
            print(f"  - {name}: {err}")

    if dry:
        print("\n[Dry run] No files moved.")
        return 0

    # Cleanup staging if all succeeded
    if ok > 0 and not any(e for _, e in errors):
        if STAGING.exists():
            try:
                shutil.rmtree(STAGING)
            except:
                pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
