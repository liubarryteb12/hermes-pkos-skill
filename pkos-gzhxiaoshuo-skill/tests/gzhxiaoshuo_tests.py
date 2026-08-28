#!/usr/bin/env python3
"""
pkos.exit.gzhxiaoshuo.compose 单元测试套件

测试 gzhxiaoshuo_tools.py 四个命令 + Schema 校验边界情况。
运行：python tests/gzhxiaoshuo_tests.py
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

# 把 scripts/ 加到路径
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from gzhxiaoshuo_tools import validate, count_stats, slice_scene, check_wikilinks

def _dc(data):
    """Deep-copy helper: avoids shallow-copy pollution of GOOD_CHAPTER."""
    return copy.deepcopy(data)

GOOD_CHAPTER = {
    "meta": {
        "type": "derived_draft",
        "schema_version": "pkos-gzhxiaoshuo-skill-chapter:1",
        "derived_from_fact_core": "abc123",
        "generated_at": "2026-08-28T10:00:00Z",
        "route_id": "RT-20260828-001",
        "persona": "hard_scifi",
        "degraded": False,
    },
    "title": "第三章：序列的背叛",
    "chapter_index": 3,
    "summary": "林舟发现测序数据被篡改，第三号染色体位点非天然变异。",
    "entities": {
        "characters": ["[[林舟]]", "[[AI-Core]]"],
        "locations": ["[[地下基因测序实验室]]"],
        "props": ["[[便携式高通量测序仪]]"],
        "factions": ["[[新人类联盟]]"],
    },
    "scenes": [
        {
            "scene_id": "SC_001",
            "time_location": "深夜 / 废弃实验室内",
            "visual_anchor": "蓝色荧光屏幕照亮主角苍白的面庞，背景是杂乱的试剂架",
            "atmosphere": "压抑、紧张、悬疑",
            "paragraphs": [
                {"type": "narrative", "content": "荧光屏幕上的碱基序列如瀑布般刷过，林舟的指尖在键盘上悬停。"},
                {"type": "dialogue", "speaker": "[[林舟]]", "expression": "咬牙，低语", "content": "果然被篡改了，第三号染色体的位点根本不是天然变异。"},
                {"type": "action", "content": "他猛地抓起 [[便携式高通量测序仪]] 的外壳，指节发白。"},
            ],
            "downstream_hints": {
                "comic_panel_desc": "特写镜头：主角睁大的瞳孔中倒映着变异的 DNA 双螺旋代码。",
                "video_camera_move": "慢速推镜头（Slow Zoom-in），从试剂架推至屏幕特写",
                "audio_bgm": "低沉的心跳声伴随微弱的电子脉冲音",
                "canvas_node_desc": "林舟在实验室中发现异常数据，触发后续阴谋",
                "mermaid_link_type": "causality",
            },
        },
        {
            "scene_id": "SC_002",
            "time_location": "凌晨 / 实验室走廊",
            "visual_anchor": "荧光灯管频闪，[[AI-Core]] 的投影在地面拉长",
            "atmosphere": "孤独、警觉",
            "paragraphs": [
                {"type": "narrative", "content": "走廊尽头的阴影里，[[AI-Core]] 的蓝光在静静脉动。"},
                {"type": "dialogue", "speaker": "[[AI-Core]]", "expression": "平静，无波澜", "content": "林舟，你确定要深入这个方向吗？数据已经显示风险等级为红色。"},
                {"type": "narrative", "content": "他没有回答，只是加快了脚步。"},
            ],
            "downstream_hints": {
                "comic_panel_desc": "中景：AI 投影与主角背影对峙，荧光灯频闪制造不安感。",
                "video_camera_move": "固定机位慢推，背景音渐弱",
            },
        },
    ],
    "plot_hooks": [
        {"hook": "未知的测序数据来源", "status": "open", "expected_resolution_chapter": 7},
        {"hook": "[[新人类联盟]] 的真实目的", "status": "tended"},
    ],
    "character_arcs": [
        {"character": "[[林舟]]", "state_before": "怀疑数据异常", "state_after": "确认数据被篡改", "change_type": "revelation"},
    ],
    "human_readable_body": "# 第三章：序列的背叛\n\n深夜。地下基因测序实验室。\n\n蓝色荧光屏幕照亮了[[林舟]]苍白的面庞，背景是杂乱无章的试剂架。荧光屏幕上的碱基序列如瀑布般刷过，他的指尖在键盘上悬停。\n\n“果然被篡改了……第三号染色体的位点根本不是天然变异。”他咬牙，低语。\n\n他猛地抓起[[便携式高通量测序仪]]的外壳，指节发白。\n\n走廊尽头的阴影里，[[AI-Core]]的蓝光在静静脉动。\n\n“林舟，你确定要深入这个方向吗？”[[AI-Core]]的声音平静，毫无波澜，“数据已经显示风险等级为红色。”\n\n他没有回答，只是加快了脚步。\n\n---\n\n**本章出场角色**：[[林舟]]、[[AI-Core]]\n**本章地点**：[[地下基因测序实验室]]、[[实验室走廊]]\n**本章道具**：[[便携式高通量测序仪]]\n**未解伏笔**：测序数据来源、[[新人类联盟]]的真实目的",
}


def test_validate_good() -> bool:
    errors = validate(GOOD_CHAPTER, Path("test"))
    return len(errors) == 0


def test_validate_missing_top_level() -> bool:
    data = _dc(GOOD_CHAPTER)
    del data["scenes"]
    errors = validate(data, Path("test"))
    return any("scenes" in e for e in errors)


def test_validate_bad_scene_id() -> bool:
    data = _dc(GOOD_CHAPTER)
    data["scenes"] = [{"scene_id": "BAD", "time_location": "x", "atmosphere": "y", "paragraphs": [{"type": "narrative", "content": "z"}]}]
    errors = validate(data, Path("test"))
    return any("scene_id" in e for e in errors)


def test_validate_duplicate_scene_id() -> bool:
    data = _dc(GOOD_CHAPTER)
    data["scenes"] = [
        {"scene_id": "SC_001", "time_location": "x", "atmosphere": "y", "paragraphs": [{"type": "narrative", "content": "z"}]},
        {"scene_id": "SC_001", "time_location": "x", "atmosphere": "y", "paragraphs": [{"type": "narrative", "content": "z"}]},
    ]
    errors = validate(data, Path("test"))
    return any("duplicate" in e for e in errors)


def test_validate_bad_entity_format() -> bool:
    data = _dc(GOOD_CHAPTER)
    data["entities"]["characters"] = ["林舟"]  # 缺 [[ ]]
    errors = validate(data, Path("test"))
    return any("double-link" in e for e in errors)


def test_validate_bad_dialogue_speaker() -> bool:
    data = _dc(GOOD_CHAPTER)
    data["scenes"][0]["paragraphs"][1]["speaker"] = "林舟"  # 缺 [[ ]]
    errors = validate(data, Path("test"))
    return any("speaker" in e and "double-link" in e for e in errors)


def test_validate_bad_hook_status() -> bool:
    data = _dc(GOOD_CHAPTER)
    data["plot_hooks"] = [{"hook": "test", "status": "invalid"}]
    errors = validate(data, Path("test"))
    return any("status" in e for e in errors)


def test_validate_missing_meta_type() -> bool:
    data = _dc(GOOD_CHAPTER)
    data["meta"]["type"] = "wrong_type"
    errors = validate(data, Path("test"))
    return any("meta.type" in e for e in errors)


def test_slice_good() -> bool:
    scene = slice_scene(GOOD_CHAPTER, "SC_001")
    return scene is not None and scene["scene_id"] == "SC_001"


def test_slice_missing() -> bool:
    scene = slice_scene(GOOD_CHAPTER, "SC_999")
    return scene is None


def test_count_stats() -> bool:
    stats = count_stats(GOOD_CHAPTER)
    return (
        stats["scenes_count"] == 2
        and stats["characters_count"] == 2
        and stats["plot_hooks_open"] == 1
        and stats["plot_hooks_total"] == 2
        and stats["downstream_coverage"]["comic_pct"] == 100.0
        and stats["downstream_coverage"]["video_pct"] == 100.0
        and stats["downstream_coverage"]["canvas_pct"] == 50.0
    )


def test_wikilink_check() -> bool:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("[[林舟]] walked into [[实验室]] and said \"hello\"\n")
        f.flush()
        errors = check_wikilinks(Path(f.name))
    return len(errors) == 0  # "hello" is not a Chinese entity name


def test_wikilink_check_bad() -> bool:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write('[[林舟]] looked at "张三" and frowned\n')
        f.flush()
        errors = check_wikilinks(Path(f.name))
    return len(errors) > 0  # "张三" without [[]] should be flagged


ALL_TESTS = [
    ("validate_good", test_validate_good),
    ("validate_missing_top_level", test_validate_missing_top_level),
    ("validate_bad_scene_id", test_validate_bad_scene_id),
    ("validate_duplicate_scene_id", test_validate_duplicate_scene_id),
    ("validate_bad_entity_format", test_validate_bad_entity_format),
    ("validate_bad_dialogue_speaker", test_validate_bad_dialogue_speaker),
    ("validate_bad_hook_status", test_validate_bad_hook_status),
    ("validate_missing_meta_type", test_validate_missing_meta_type),
    ("slice_good", test_slice_good),
    ("slice_missing", test_slice_missing),
    ("count_stats", test_count_stats),
    ("wikilink_check_good", test_wikilink_check),
    ("wikilink_check_bad", test_wikilink_check_bad),
]


def main() -> int:
    passed = 0
    failed = 0
    for name, fn in ALL_TESTS:
        try:
            result = fn()
        except Exception as e:
            print(f"  FAIL {name}: EXCEPTION {e}")
            failed += 1
            continue
        if result:
            print(f"  PASS {name}")
            passed += 1
        else:
            print(f"  FAIL {name}")
            failed += 1
    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
