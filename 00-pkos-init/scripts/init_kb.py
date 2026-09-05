#!/usr/bin/env python3
"""init_kb —— pkos 知识库工作区初始化：确定路径 + 选架构模式，一键建骨架。

用法：
  python init_kb.py --path "<知识库根目录>" --mode moc|okf|index [--force] [--dry-run]

行为：
  在 <知识库根目录>/_PKOS/ 下创建六大地基目录（INBOX/manifests/analysis/
  routes/outputs/reports，全流程固定名，是各 skill 的接口约定），
  再按所选模式生成条目组织层，写 config.json 与 README.md。

模式（只作用于条目组织层，其余机制不变）：
  moc    MOC 中枢笔记制：entries/<主题域>/ 分夹 + MOC/ 下每域一张中枢笔记
  okf    Open Knowledge Format：entries/ 用数字编号类目（00/10/20/30/90）
  index  INDEX 索引制：entries/ 全扁平不分夹，根部一张 INDEX.md 总目录

退出码：0 成功；1 冲突/参数错误；2 用法错误。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

STAGE_DIRS = ["INBOX", "manifests", "analysis", "routes", "outputs", "reports"]


def load_enabled_units() -> list[str]:
    """读 pipeline/registry.json 的 registered 单元作为实例默认启用集；缺表则回退核心链。"""
    reg = Path(__file__).resolve().parents[2] / "pipeline" / "registry.json"
    try:
        data = json.loads(reg.read_text(encoding="utf-8-sig"))
        ids = [u["id"] for u in data.get("units", []) if u.get("status") == "registered"]
        return ids or ["01-pkos-intake", "03-pkos-ingest", "05-pkos-analysis", "06-pkos-polish",
                       "08-pkos-router", "10-pkos-html", "11-pkos-ppt-skill", "25-pkos-audit",
                       "24-pkos-timeline", "00-pkos-init"]
    except (OSError, json.JSONDecodeError, KeyError):
        return []

MODES = {
    "moc": {
        "label": "MOC 中枢笔记制",
        "dirs": ["entries", "MOC"],
        "entries_note": "entries/ 按主题域分夹（如 entries/方法论/），每域在 MOC/ 有一张 MOC-<域名>.md 中枢笔记做双链汇总",
    },
    "okf": {
        "label": "Open Knowledge Format 编号类目制",
        "dirs": [
            "entries/00_收件暂存",
            "entries/10_方法论",
            "entries/20_工具与技术",
            "entries/30_案例复盘",
            "entries/90_归档",
        ],
        "entries_note": "entries/ 用数字编号类目（Johnny.Decimal 风）：新增类目续编 40_/50_/…，编号即定位",
    },
    "index": {
        "label": "INDEX 索引目录制",
        "dirs": ["entries"],
        "files": {"INDEX.md": None},  # 内容见 make_index_md
        "entries_note": "entries/ 全扁平不分夹，靠根部 INDEX.md 分区总目录导航",
    },
}

README_HEAD = """# _PKOS —— 个人知识库工作区

由 00-pkos-init 生成（{date}）。模式：**{mode_label}**

## 地基目录（固定名，各 skill 的接口约定，勿改名）

| 目录 | 职责 | 负责 skill |
|---|---|---|
| INBOX/ | 收件区：丢 PDF/docx/MD/剪藏进来 | 01-pkos-intake 扫描 |
| manifests/ | ingest/intake 运行清单存档 | 03-pkos-ingest / 01-pkos-intake |
| analysis/ | 分析产物（发现表等） | 05-pkos-analysis |
| routes/ | 路由单 YAML 存档（RT-*.yaml） | 08-pkos-router |
| outputs/ | 出口交付物（HTML/PPT 图组，按 route-id 归档） | 10-pkos-html / 11-pkos-ppt-skill |
| reports/ | 审计报告 JSON + 健康度时间线 | 25-pkos-audit / 24-pkos-timeline |

## 条目组织（当前模式：{mode_label}）

{entries_note}

## 使用入口

1. 往 INBOX/ 丢文件 → 说「处理 INBOX」
2. 对条目说「分析这篇」「润色这段」
3. 说「做成网页 / 出 deck / 发公众号」走出品流水线
"""

INDEX_MD_TEMPLATE = """# INDEX · 全库总目录

> pkos-index 模式：entries/ 扁平存放，本页是唯一导航。新条目入库后在对应分区加一行 `[[条目名]]`。

## 方法论

## 工具与技术

## 案例复盘

## 待整理
"""


def make_readme(mode_key: str) -> str:
    m = MODES[mode_key]
    return README_HEAD.format(date=date.today().isoformat(), mode_label=m["label"],
                              entries_note=m["entries_note"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True, help="知识库根目录")
    ap.add_argument("--mode", required=True, choices=sorted(MODES))
    ap.add_argument("--force", action="store_true", help="已有 _PKOS/config.json 时允许覆盖重建")
    ap.add_argument("--dry-run", action="store_true", help="只打印将创建的清单，不写盘")
    args = ap.parse_args(argv)

    kb = Path(args.path)
    if not kb.is_dir():
        print(f"[ERROR] 知识库根目录不存在: {kb}", file=sys.stderr)
        return 2
    pkos = kb / "_PKOS"
    cfg = pkos / "config.json"
    if cfg.exists() and not args.force:
        print(f"[ERROR] {_norm(cfg)} 已存在（已初始化过）；确认重建请加 --force", file=sys.stderr)
        return 1

    dirs = [f"_PKOS/{d}" for d in STAGE_DIRS]
    for d in MODES[args.mode]["dirs"]:
        dirs.append(f"_PKOS/{d}")
    files = {
        "_PKOS/config.json": lambda: json.dumps({
            "schema": "pkos-config:1",
            "kb_root": str(kb),
            "mode": args.mode,
            "created": date.today().isoformat(),
            "layout": {d.lower(): f"_PKOS/{d}" for d in STAGE_DIRS},
            "modules": {"enabled": load_enabled_units(), "disabled": []},
        }, ensure_ascii=False, indent=2) + "\n",
        "_PKOS/README.md": lambda: make_readme(args.mode),
    }
    files.update({f"_PKOS/{k}": (lambda: v) if v else (lambda: MODES[args.mode]["files"][k])
                  for k, v in MODES[args.mode].get("files", {}).items()})

    tag = "[DRY-RUN] " if args.dry_run else ""
    print(f"{tag}init_kb: root={_norm(kb)} mode={args.mode} ({MODES[args.mode]['label']})")
    for d in dirs:
        print(f"{tag}  mkdir {d}")
    for f in sorted(files):
        print(f"{tag}  write {f}")
    if args.dry_run:
        return 0

    for d in dirs:
        (kb / d).mkdir(parents=True, exist_ok=True)
        gitkeep = kb / d / ".gitkeep"
        if not any((kb / d).iterdir()):
            gitkeep.write_text("", encoding="utf-8")
    for f, maker in files.items():
        p = kb / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(maker(), encoding="utf-8")

    print(json.dumps({"ok": True, "root": str(kb), "mode": args.mode,
                      "config": str(cfg)}, ensure_ascii=False))
    return 0


def _norm(p: Path) -> str:
    return str(p)


if __name__ == "__main__":
    sys.exit(main())
