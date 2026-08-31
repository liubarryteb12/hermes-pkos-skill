"""
extract_characters.py — 从 _PKOS/assets/characters/ 抽锚定短语（v3.2 Phase 4）

输入:RT-* options.characters 列表 [{ id, name, character_id }, ...]
输出:characters_with_anchor 列表 [{ id, name, anchor, anchor_hash, short_anchor, short_anchor_hash, source_path }, ...]

规则:
- character_id 形如 "01_主角_小满",对应 _PKOS/assets/characters/01_主角_小满.md
- 详细版锚定短语:读 ## 英文外观描述(出图直接复制,逐字一致!) 段的第一个 ```text``` 块
- 短锚版:详细版取 30-50 词(取前 30-50 词+优先保留标志性配饰/发型/服装关键词)
- sha256 校验:同一人物跨 panel 的 anchor_hash 必须一致(violate 触发 ERR_ANCHOR_MISMATCH)
- 错误码:
  - ERR_CHARACTERS_MISSING: characters=null
  - ERR_CHARACTER_NOT_FOUND: 详细文件不存在
  - ERR_ANCHOR_EXTRACTION_FAIL: 详细文件无英文外观描述段
  - ERR_ANCHOR_TOO_SHORT: 详细版 < 50 词
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
from typing import Any

# === 路径探测 (与 ppt compose.py 同模式) ===
def _find_workspace_root() -> Path:
    # 平铺布局：套件已并入 skill 根，pkos-comic/scripts 的上两级即套件根。
    return Path(__file__).resolve().parents[2]


WORKSPACE_ROOT = _find_workspace_root()
CHARACTERS_DIR = WORKSPACE_ROOT / "_PKOS" / "assets" / "characters"


# === 错误码(对齐 SKILL.md C-4 失败三态) ===
class CharacterExtractError(Exception):
    """角色抽取失败,带 error_code"""

    def __init__(self, error_code: str, message: str, character_id: str | None = None):
        self.error_code = error_code
        self.character_id = character_id
        super().__init__(f"[{error_code}] {message} (character_id={character_id})")


# === 详细文件解析 ===

def _extract_anchor_block(md_text: str) -> str:
    """从详细人物 .md 抽 ## 英文外观描述 段下第一个 ```text``` 块"""
    # 定位 "## 英文外观描述" 段
    m = re.search(
        r"^##\s*英文外观描述[^\n]*\n+",
        md_text,
        re.MULTILINE,
    )
    if not m:
        return ""
    sub = md_text[m.end():]
    # 找下一个 ```text ... ``` 块
    code_m = re.search(r"```text\s*\n(.*?)\n```", sub, re.DOTALL)
    if not code_m:
        return ""
    return code_m.group(1).strip()


def _shorten_anchor(detailed: str, min_words: int = 30, max_words: int = 50) -> str:
    """短锚版:优先保留 age + hair + outfit + 1 个标志性配饰,截到 30-50 词"""
    words = detailed.split()
    if len(words) <= max_words:
        return detailed
    # 保留前 max_words 词
    return " ".join(words[:max_words])


def _read_character_detail(character_id: str, base_dir: Path) -> dict:
    """读详细人物 .md,返回 { source_path, detailed_anchor, detailed_hash }"""
    detail_path = base_dir / f"{character_id}.md"
    if not detail_path.exists():
        raise CharacterExtractError(
            "ERR_CHARACTER_NOT_FOUND",
            f"详细人物文件不存在: {detail_path}",
            character_id,
        )
    text = detail_path.read_text(encoding="utf-8-sig")
    detailed = _extract_anchor_block(text)
    if not detailed:
        raise CharacterExtractError(
            "ERR_ANCHOR_EXTRACTION_FAIL",
            "详细文件无 ## 英文外观描述 ```text``` 块",
            character_id,
        )
    words = detailed.split()
    if len(words) < 50:
        raise CharacterExtractError(
            "ERR_ANCHOR_TOO_SHORT",
            f"详细版 < 50 词 (实际 {len(words)} 词),< 80 词下限或重写详细段",
            character_id,
        )
    short = _shorten_anchor(detailed)
    return {
        "source_path": str(detail_path),
        "detailed_anchor": detailed,
        "detailed_hash": "sha256:" + hashlib.sha256(detailed.encode("utf-8")).hexdigest()[:16],
        "short_anchor": short,
        "short_anchor_hash": "sha256:" + hashlib.sha256(short.encode("utf-8")).hexdigest()[:16],
        "words_count": len(words),
    }


# === 主入口 ===

def extract_characters(
    characters: list[dict[str, Any]] | None,
    characters_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """从 RT-* options.characters 抽锚定短语。

    characters_dir: 默认走全局 CHARACTERS_DIR;测试时可注入临时目录。

    Returns:[
      {
        "id": "char_01", "name": "小满", "character_id": "01_主角_小满",
        "anchor": "A 25-year-old Chinese woman, ...",   # 详细版
        "anchor_hash": "sha256:abc123...",
        "short_anchor": "A 25-year-old Chinese woman, ...",   # 短锚版
        "short_anchor_hash": "sha256:def456...",
        "source_path": "...",
        "words_count": N,
      },
      ...
    ]
    """
    if not characters:
        raise CharacterExtractError(
            "ERR_CHARACTERS_MISSING",
            "characters=null (v0 锁死:本 skill 必填人物清单)",
        )

    target_dir = characters_dir or CHARACTERS_DIR
    out: list[dict[str, Any]] = []
    for c in characters:
        cid = c.get("character_id") or c.get("id")
        name = c.get("name", cid)
        if not cid:
            raise CharacterExtractError(
                "ERR_CHARACTER_NOT_FOUND",
                f"character 项缺 id/character_id: {c}",
            )
        detail = _read_character_detail(cid, base_dir=target_dir)
        out.append({
            "id": c.get("id", cid),
            "name": name,
            "character_id": cid,
            "anchor": detail["detailed_anchor"],
            "anchor_hash": detail["detailed_hash"],
            "short_anchor": detail["short_anchor"],
            "short_anchor_hash": detail["short_anchor_hash"],
            "source_path": detail["source_path"],
            "words_count": detail["words_count"],
        })
    return out


# === CLI 入口(单跑测试) ===

def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(description="抽 _PKOS/assets/characters/ 锚定短语")
    ap.add_argument("--character-id", required=True, help="形如 01_主角_小满")
    args = ap.parse_args(argv)
    try:
        result = extract_characters([{"id": args.character_id, "name": args.character_id, "character_id": args.character_id}])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except CharacterExtractError as e:
        print(json.dumps({"error_code": e.error_code, "message": str(e), "character_id": e.character_id}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
