#!/usr/bin/env python3
"""pkos-audit 例行体检 —— 一键生成库内体检报告（全程只读，报告写到 --outdir）。

指标口径与 2026-08-23 手工体检（知识体系总览 §五）对齐：
  总笔记数排除 .obsidian / skills / 账户密码 及一切点目录；
  frontmatter 覆盖率=有 FM 块的笔记占比；孤立笔记=零入链笔记；空壳=正文<10字符；短笔记=正文<200字符。

用法：
  python audit.py --vault <库根> --outdir <报告目录> [--prev 上次.json]
      [--blindspot "本次牺牲了什么视角…"] [--max-list 30]

产物：<outdir>/<日期>_audit.md（人读）、<日期>_audit.json（机读，供下次增量对比），
     并向 <outdir>/blindspots.md 追加盲点账本条目（append-only）。
退出码：0 正常；2 用法/IO 错误。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_CONTRACTS = _SCRIPTS.parents[1] / "contracts" / "validate_entry.py"
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("validate_entry", _CONTRACTS)
ve = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(ve)

EXCLUDE_DIRS = {"_PKOS", "skills", "账户密码", ".staging", "node_modules", ".git"}

def _load_exempt_dirs(vault) -> set:
    """R2 豁免区：vault/_PKOS/exempt-zones.json 登记的目录动态并入排除集（数据驱动）。"""
    extra = set()
    try:
        cand = Path(vault) / "_PKOS" / "exempt-zones.json"
        if cand.is_file():
            for z in json.loads(cand.read_text(encoding="utf-8-sig")).get("zones", []):
                extra.add(str(z.get("path", "")).strip())
    except Exception:
        pass
    return {e for e in extra if e}

LINK_RE = re.compile(r"(!?)\[\[([^\[\]]+)\]\]")
CODE_FENCE_RE = re.compile(r"```.*?(?:```|\Z)", re.S)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}
SHORT_BODY = 200
HOLLOW_BODY = 10


def strip_code(text: str) -> str:
    """剥掉围栏代码块与行内代码——示例性 [[双链]] 不计入图谱。"""
    return INLINE_CODE_RE.sub("", CODE_FENCE_RE.sub("", text))

# 手工体检基线（知识体系总览.md §5.1，2026-08-23）
BASELINE = {
    "total_notes": 902,
    "fm_coverage_pct": 99.7,
    "orphan_notes": 57,
    "dangling_wikilinks": 0,
    "hollow_notes": 0,
    "short_notes": 239,
}


def excluded(parts: tuple[str, ...]) -> bool:
    return any(p.startswith(".") or p in EXCLUDE_DIRS for p in parts[:-1])


def split_fm(text: str):
    """返回 (fm|None, fm_broken, body, head)。head=front matter 段原文，供链接解析。"""
    try:
        fm, reason = ve.load_front_matter(text)
    except ve.FMParseError:
        return None, True, text, ""
    if fm is None:
        return None, False, text, ""
    end = text.find("\n---", 3)
    head = text[: end + 4] if end != -1 else ""
    body = text[end + 4:] if end != -1 else ""
    return fm, False, body, head



def _cf(s: str) -> str:
    return s.casefold()


def _note_key(filename: str) -> str:
    """笔记名键：仅剥掉结尾的 .md，绝不用 Path.stem（含点文件名会被截断）。"""
    return _cf(filename[:-3]) if filename.lower().endswith(".md") else _cf(filename)


def build_indexes(vault: Path):
    """解析索引全盘构建（链接存在性不受统计范围影响）；md_files 仅收统计范围内的笔记。

    统计范围排除：点目录 / skills / 账户密码（与手工体检口径一致）。
    """
    md_files: list[Path] = []
    notes_by_stem: dict[str, str] = {}
    files_by_name: dict[str, str] = {}
    files_by_stemless: dict[str, str] = {}
    files_by_relpath: dict[str, str] = {}
    files_by_pathsuffix: dict[str, str] = {}
    for p in vault.rglob("*"):
        if not p.is_file():
            continue
        fn = p.name
        rel = str(p.relative_to(vault))
        files_by_name.setdefault(_cf(fn), rel)
        base, dot, ext = fn.rpartition(".")
        if dot and len(ext) <= 5:
            files_by_stemless.setdefault(_cf(base), rel)
        rc = _cf(rel).replace("\\", "/")
        files_by_relpath.setdefault(rc, rel)
        if rc.endswith(".md"):
            files_by_relpath.setdefault(rc[:-3], rel)
        segs = rc.split("/")
        for i in range(1, len(segs)):
            files_by_pathsuffix.setdefault("/".join(segs[i:]), rel)
            if segs[-1].endswith(".md"):
                files_by_pathsuffix.setdefault("/".join(segs[i:-1] + [segs[-1][:-3]]), rel)
        if fn.lower().endswith(".md"):
            notes_by_stem.setdefault(_note_key(fn), rel)
            if not excluded(p.parts):
                md_files.append(p)
    return md_files, notes_by_stem, files_by_name, files_by_stemless, files_by_relpath, files_by_pathsuffix


def resolve_target(target: str, notes_by_stem, files_by_name, files_by_stemless, files_by_relpath,
                   src_rel: str | None = None, files_by_pathsuffix=None):
    """Obsidian 解析顺序：显式 .md → 笔记名 → 全文件名 → 无扩展名附件 → 库内相对路径
    → 相对当前笔记的 ../ 路径 → 路径后缀匹配（含 / 的目标按 Obsidian 后缀语义）。"""
    t = _cf(target.strip())
    if not t:
        return None
    tp = t.replace("\\", "/")
    if t.endswith(".md"):
        hit = notes_by_stem.get(t[:-3]) or files_by_name.get(t) or files_by_relpath.get(tp)
        if hit:
            return hit
        tp2 = tp[:-3]
    else:
        tp2 = tp
    if tp2.startswith("../") or "/../" in tp2 or tp2.startswith("./"):
        if src_rel:
            base_dir = "/".join(src_rel.replace("\\", "/").split("/")[:-1])
            norm = _cf(posixpath.normpath(f"{base_dir}/{tp2}"))
            return files_by_relpath.get(norm) or files_by_relpath.get(norm + ".md")
    if "/" in tp2 and files_by_pathsuffix is not None:
        hit = files_by_pathsuffix.get(tp2)
        if hit:
            return hit
    return notes_by_stem.get(t) or files_by_name.get(t) or files_by_relpath.get(tp) \
        or files_by_stemless.get(t)


def audit(vault: Path):
    global EXCLUDE_DIRS
    EXCLUDE_DIRS = EXCLUDE_DIRS | _load_exempt_dirs(vault)  # R2 豁免区
    md_files, notes_by_stem, files_by_name, files_by_stemless, files_by_relpath, files_by_pathsuffix = build_indexes(vault)
    notes = []          # (path, fm, fm_broken, body)
    for p in md_files:
        if not excluded(p.relative_to(vault).parts):
            try:
                text = p.read_text(encoding="utf-8-sig", errors="replace")
            except OSError:
                continue
            fm, broken, body, head = split_fm(text)
            notes.append((p, fm, broken, body, head))

    total = len(notes)
    fm_ok = sum(1 for _, fm, _, _, _ in notes if fm is not None)
    fm_broken = sum(1 for _, _, b, _, _ in notes if b)

    # 分布
    status_dist = Counter((fm or {}).get("status") or "(缺)" for _, fm, _, _, _ in notes if fm)
    type_dist = Counter((fm or {}).get("type") or "(缺)" for _, fm, _, _, _ in notes if fm)

    # 链接解析（键 = 库内相对路径）；front matter 内 wikilink 与正文同等入图（Obsidian 语义）
    inbound = Counter()
    dangling = []       # (src_rel, target)
    dangling_imgs = []
    edges = set()
    for p, _, _, body, head in notes:
        src_rel = str(p.relative_to(vault))
        linktext = head + "\n" + strip_code(body)
        for embed, raw in LINK_RE.findall(linktext):
            target = raw.split("|")[0].split("#")[0].strip()
            if not target:
                continue
            dest = resolve_target(target, notes_by_stem, files_by_name, files_by_stemless, files_by_relpath,
                                  src_rel, files_by_pathsuffix)
            if dest is None:
                if embed and Path(target).suffix.lower() in IMG_EXTS:
                    dangling_imgs.append((src_rel, target))
                else:
                    dangling.append((src_rel, target))
            elif dest.endswith(".md"):
                inbound[dest] += 1
                edges.add((src_rel, dest))

    orphan_notes = sorted(
        str(p.relative_to(vault)) for p, _, _, _, _ in notes if inbound.get(str(p.relative_to(vault)), 0) == 0
    )
    # 完全孤岛：零入链且零出链
    zero_out = {str(p.relative_to(vault)) for p, _, _, b, _ in notes if not LINK_RE.search(strip_code(b))}
    true_islands = sorted(set(orphan_notes) & zero_out)

    hollow = []
    shorts = []
    for p, _, _, body, _ in notes:
        bs = body.strip()
        rel = str(p.relative_to(vault))
        if len(bs) < HOLLOW_BODY:
            hollow.append(rel)
        elif len(bs) < SHORT_BODY:
            shorts.append(rel)

    # 重复检测：正文内容哈希相同且非空
    by_hash = {}
    for p, _, _, body, _ in notes:
        bs = body.strip()
        if len(bs) < HOLLOW_BODY:
            continue
        by_hash.setdefault(hashlib.sha256(bs.encode()).hexdigest(), []).append(str(p.relative_to(vault)))
    duplicates = sorted(v for v in by_hash.values() if len(v) > 1)

    # AI 可读性启发式抽评（代理口径，非人工评分）
    def readability(fm, body) -> float:
        score = 0.0
        if fm is not None:
            score += 1.0
            if fm.get("type"):
                score += 1.0
        if re.search(r"^#{1,3} ", body, flags=re.M):
            score += 1.0
        if len(LINK_RE.findall(strip_code(body))) >= 1:
            score += 1.0
        if len(body.strip()) >= SHORT_BODY:
            score += 1.0
        return score

    scores = [readability(fm, b) for _, fm, _, b, _ in notes]
    readability_avg = round(sum(scores) / len(scores), 2) if scores else 0.0

    return {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "totals": {
            "total_notes": total,
            "fm_present": fm_ok,
            "fm_coverage_pct": round(fm_ok * 100.0 / total, 1) if total else 0.0,
            "fm_broken": fm_broken,
            "orphan_notes": len(orphan_notes),
            "true_islands": len(true_islands),
            "dangling_wikilinks": len(dangling),
            "dangling_images": len(dangling_imgs),
            "hollow_notes": len(hollow),
            "short_notes": len(shorts),
            "duplicate_groups": len(duplicates),
            "readability_proxy_avg": readability_avg,
        },
        "status_distribution": dict(status_dist.most_common()),
        "type_distribution": dict(type_dist.most_common()),
        "dangling_wikilink_list": dangling,
        "dangling_image_list": dangling_imgs,
        "orphan_list": orphan_notes,
        "true_island_list": true_islands,
        "short_list": shorts,
        "duplicate_groups_list": duplicates,
        "_baseline": BASELINE,
    }


def diff_against_prev(cur: dict, prev: dict | None) -> dict:
    if not prev:
        return {"baseline_run": True, "new_dangling": [], "new_short": [], "new_dup_groups": []}
    pd = {tuple(x) for x in prev.get("dangling_wikilink_list", [])}
    cd = {tuple(x) for x in cur["dangling_wikilink_list"]}
    ps = set(prev.get("short_list", []))
    cs = set(cur["short_list"])
    pg = {frozenset(g) for g in prev.get("duplicate_groups_list", [])}
    cg = {frozenset(g) for g in cur["duplicate_groups_list"]}
    return {
        "baseline_run": False,
        "new_dangling": sorted(cd - pd),
        "new_short": sorted(cs - ps),
        "new_dup_groups": [sorted(g) for g in cg - pg],
    }


def render_md(data: dict, diff: dict, max_list: int) -> str:
    t = data["totals"]
    lines = [
        "# PKOS 库内体检报告",
        "",
        f"> 运行时间（UTC）: {data['run_at']} · 全程只读 · 口径见 pkos-audit/scripts/audit.py 头注",
        "",
        "## 一、核心指标（自动 vs 2026-08-23 手工基线）",
        "",
        "| 指标 | 本次自动 | 手工基线 | 差异说明 |",
        "|---|---|---|---|",

        f"| 总笔记数 | {t['total_notes']} | {BASELINE['total_notes']} | 基线后新增条目计入 |",
        f"| frontmatter 覆盖率 | {t['fm_coverage_pct']}% ({t['fm_present']}/{t['total_notes']}) | {BASELINE['fm_coverage_pct']}% | 口径一致（有 FM 块即计入） |",
        f"| 孤立笔记（零入链） | {t['orphan_notes']} | {BASELINE['orphan_notes']} | 自动口径为全库零入链，手工口径含已建索引豁免 |",
        f"| 完全孤岛（零入链+零出链） | {t['true_islands']} | —（基线用双链修复后=0 的连通口径） | 两口径并列观察 |",
        f"| 悬空 wikilink | {t['dangling_wikilinks']} | ≈{BASELINE['dangling_wikilinks']} | 解析规则=basename 大小写不敏感匹配全库文件 |",
        f"| 悬空图片引用 | {t['dangling_images']} | 0 | 同上 |",
        f"| 空壳笔记(<{HOLLOW_BODY}字) | {t['hollow_notes']} | {BASELINE['hollow_notes']} | |",
        f"| 短笔记(<{SHORT_BODY}字) | {t['short_notes']} | {BASELINE['short_notes']} | |",
        f"| 重复内容组 | {t['duplicate_groups']} | 未统计 | 基线无此项，本次起纳入 |",
        f"| AI 可读性（启发式代理） | {t['readability_proxy_avg']}/5 | 3.7/5（人工） | 代理分≠人工分，差异记盲点账本 |",
        "",
        "## 二、status / type 分布",
        "",
        f"- status: `{json.dumps(data['status_distribution'], ensure_ascii=False)}`",
        f"- type: `{json.dumps(data['type_distribution'], ensure_ascii=False)}`",
        "",
        "## 三、待清理增量建议区",
        "",
    ]
    if diff["baseline_run"]:
        lines.append("- 本次为首轮自动体检（基线运行），以下清单即当前全量待清理项；下轮起只报增量。")
    else:
        lines.append(f"- 新增悬空 wikilink：{len(diff['new_dangling'])} 条")
        lines.append(f"- 新增短笔记：{len(diff['new_short'])} 篇")
        lines.append(f"- 新增重复内容组：{len(diff['new_dup_groups'])} 组")
    lines += ["", "### 悬空 wikilink 清单（截断展示）", ""]
    for s, tg in data["dangling_wikilink_list"][:max_list]:
        lines.append(f"- `{tg}` ← {s}")
    if len(data["dangling_wikilink_list"]) > max_list:
        lines.append(f"- …共 {len(data['dangling_wikilink_list'])} 条，完整清单见同名 .json")
    lines += ["", "### 短笔记样例（截断展示）", ""]
    for r in data["short_list"][:max_list]:
        lines.append(f"- {r}")
    lines += ["", "### 重复内容组（截断展示）", ""]
    for g in data["duplicate_groups_list"][:max_list]:
        lines.append(f"- {' ↔ '.join(g)}")
    lines += ["", "### 完全孤岛样例（截断展示）", ""]
    for r in data["true_island_list"][:max_list]:
        lines.append(f"- {r}")
    lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--prev", default=None)
    ap.add_argument("--blindspot", default=None, help="本次牺牲了什么视角的一句话，追加进盲点账本")
    ap.add_argument("--max-list", type=int, default=30)
    args = ap.parse_args(argv)

    vroot = Path(args.vault)
    if not vroot.is_dir():
        print(json.dumps({"error": f"vault 不存在: {args.vault}"}), file=sys.stderr)
        return 2
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    data = audit(vroot)
    prev = None
    if args.prev and Path(args.prev).is_file():
        prev = json.loads(Path(args.prev).read_text(encoding="utf-8-sig"))
    diff = diff_against_prev(data, prev)

    stamp = data["run_at"][:10]
    json_path = outdir / f"{stamp}_audit.json"
    md_path = outdir / f"{stamp}_audit.md"
    json_path.write_text(json.dumps({**data, "diff": diff}, ensure_ascii=False, indent=1), encoding="utf-8")
    md_path.write_text(render_md(data, diff, args.max_list), encoding="utf-8")

    if args.blindspot:
        bs = outdir / "blindspots.md"
        with open(bs, "a", encoding="utf-8") as f:
            f.write(f"\n## {data['run_at']}\n- 视角牺牲：{args.blindspot}\n")

    print(json.dumps({"md_report": str(md_path), "json_report": str(json_path),
                      "totals": data["totals"], "diff": diff}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
