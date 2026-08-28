#!/usr/bin/env python3
"""单元测试：pkos.exit.ppt.compose 各组件逻辑

覆盖：
- YAML 最小解析器
- 路由单校验（not_found 三条件）
- POL 源解析与 status 校验
- 比例确认（ambiguous vs auto）
- 提示词生成（美学 token 注入、文字截断）
- manifest 结构完整性
"""
import json
import sys
import tempfile
from pathlib import Path

# Windows 沙箱下 /tmp 可能不可写，改用 workspace 下的临时目录
_TMP_ROOT = Path(__file__).resolve().parent.parent.parent / ".tmp-test"
_TMP_ROOT.mkdir(exist_ok=True)

sys.stdout.reconfigure(encoding='utf-8')
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

# 导入被测试模块（需要绕过 __main__ 守卫）
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("compose_sut", _SCRIPTS_DIR / "compose.py")
sut = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(sut)


def test_yaml_parser_basic():
    """最小 YAML 解析器：标量 + 列表"""
    text = """route_id: RT-20260827-001
exit: ppt
conversion_type: 实战操作指南
rationale:
  - "第一条理由"
  - "第二条理由"
"""
    result = sut.yaml_safe_load(text)
    assert result["route_id"] == "RT-20260827-001"
    assert result["exit"] == "ppt"
    assert result["conversion_type"] == "实战操作指南"
    assert result["rationale"] == ["第一条理由", "第二条理由"]
    print("PASS: test_yaml_parser_basic")


def test_yaml_parser_brackets():
    """source_entry 含 [[]] 不会被误解析为数组"""
    text = 'source_entry: "[[POL-2026-08-26-05-01-37-G.md]]"\nexit: ppt\n'
    result = sut.yaml_safe_load(text)
    assert result["source_entry"] == "[[POL-2026-08-26-05-01-37-G.md]]"
    print("PASS: test_yaml_parser_brackets")


def test_validate_route_exit_not_ppt():
    """exit≠ppt → not_found"""
    rejections = sut.validate_route({"exit": "html", "source_entry": "[[POL-xxx.md]]"})
    assert len(rejections) >= 1
    assert "exit=ppt" in rejections[0]
    print("PASS: test_validate_route_exit_not_ppt")


def test_validate_route_conversion_type():
    """conversion_type 不在承接子集 → not_found"""
    rejections = sut.validate_route({
        "exit": "ppt",
        "source_entry": "[[POL-xxx.md]]",
        "conversion_type": "wiki百科条目",  # 实际是接受的，测拒绝的
    })
    assert len(rejections) == 0  # wiki百科条目 在 accepted 中

    rejections2 = sut.validate_route({
        "exit": "ppt",
        "source_entry": "[[POL-xxx.md]]",
        "conversion_type": "公众号漫画",  # 不在接受子集
    })
    assert len(rejections2) >= 1
    print("PASS: test_validate_route_conversion_type")


def test_validate_route_missing_source():
    """缺少 source_entry → not_found"""
    rejections = sut.validate_route({"exit": "ppt"})
    assert any("source_entry" in r for r in rejections)
    print("PASS: test_validate_route_missing_source")


def test_ratio_auto_mode():
    """auto_mode=True 时默认 16:9，不抛异常"""
    ratio, size, note = sut.ask_ratio(None, auto_mode=True)
    assert ratio == "16:9"
    assert size == "1536x1024"
    print("PASS: test_ratio_auto_mode")


def test_ratio_explicit():
    """显式指定比例"""
    for r, s in [("16:9", "1536x1024"), ("3:4", "1024x1536"), ("4:3", "1536x1024")]:
        ratio, size, _ = sut.ask_ratio(r, auto_mode=False)
        assert ratio == r
        assert size == s
    print("PASS: test_ratio_explicit")


def test_ratio_ambiguous():
    """ratio=null 且 auto_mode=false → RatioRequiredError"""
    try:
        sut.ask_ratio(None, auto_mode=False)
        assert False, "应抛出 RatioRequiredError"
    except sut.RatioRequiredError:
        pass
    print("PASS: test_ratio_ambiguous")


def test_build_prompt_injects_aesthetic_tokens():
    """提示词必须包含美学 token"""
    aesthetics = {
        "themes": {"paper-ink": {"prompt_tokens": "warm beige paper, cinnabar accent"}},
        "fallback_theme": {"prompt_tokens": "neutral minimal"},
        "slide_templates": {
            "cover": {"prompt_suffix": "presentation cover slide"},
            "content": {"prompt_suffix": "content slide"},
            "closing": {"prompt_suffix": "closing slide"},
        },
    }
    prompt = sut.build_prompt("paper-ink", 1, 3, "GraphQL 实战", "正文内容", aesthetics, "16:9")
    assert "warm beige paper" in prompt
    assert "cinnabar" in prompt
    assert "presentation cover slide" in prompt
    print("PASS: test_build_prompt_injects_aesthetic_tokens")


def test_build_prompt_truncates_title():
    """标题超过 10 字应截断"""
    aesthetics = {"themes": {}, "fallback_theme": {}, "slide_templates": {}}
    long_title = "这是一个非常长的标题不应该超过十个字"
    prompt = sut.build_prompt("paper-ink", 2, 3, long_title, "some body", aesthetics, "16:9")
    # 截断后应为 10 字
    import re
    m = re.search(r"'([^']+)'", prompt)
    assert m
    assert len(m.group(1)) <= 10
    print("PASS: test_build_prompt_truncates_title")


def test_manifest_structure():
    """manifest.json 必须含 pkos-ppt-deck:1 schema 和五键 slide"""
    out = _TMP_ROOT / "manifest-test"
    out.mkdir(exist_ok=True)
    slides = [
        {"slide": 1, "prompt": "p1", "provider": "image-api:gptimage2",
         "size": "1536x1024", "ratio": "16:9", "file": "slide-01.png", "hash": "abc123"},
    ]
    manifest_path = sut.write_manifest(out, "RT-test-001", slides, "16:9", False)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["schema"] == "pkos-ppt-deck:1"
    assert data["route_id"] == "RT-test-001"
    assert data["ratio"] == "16:9"
    assert data["degraded"] is False
    assert len(data["slides"]) == 1
    s = data["slides"][0]
    assert all(k in s for k in ["slide", "prompt", "provider", "size", "ratio", "file"])
    print("PASS: test_manifest_structure")


def test_classify_slide():
    """首尾页分类正确"""
    assert sut.classify_slide(1, 5) == "cover"
    assert sut.classify_slide(5, 5) == "closing"
    assert sut.classify_slide(3, 5) == "content"
    print("PASS: test_classify_slide")


def test_extract_keywords():
    """关键词提取：去掉 markdown 符号，截取前 N 字"""
    text = "**1. GraphQL 的本质** 是端点 + 查询\n`query { user }`"
    kw = sut.extract_keywords(text, max_len=10)
    assert "GraphQL" in kw or "本质" in kw
    assert len(kw) <= 10
    print("PASS: test_extract_keywords")


def test_parse_pol_content():
    """POL 内容解析：frontmatter + 章节"""
    pol = _TMP_ROOT / "parse-pol-test.md"
    pol.write_text("""---
title: Test Title
status: polished
---

# Main Title

## Section One
Body one here.

## Section Two
Body two here.
""", encoding="utf-8")
    data = sut.parse_pol_content(pol)
    assert data["frontmatter"]["title"] == "Test Title"
    assert data["frontmatter"]["status"] == "polished"
    # 第一个 section 是 # Main Title（H1 在 ## 之前），实际内容从 index 1 开始
    content_sections = [s for s in data["sections"] if s["title"].startswith("Section")]
    assert len(content_sections) == 2
    assert content_sections[0]["title"] == "Section One"
    assert content_sections[1]["title"] == "Section Two"
    print("PASS: test_parse_pol_content")


if __name__ == "__main__":
    tests = [
        test_yaml_parser_basic,
        test_yaml_parser_brackets,
        test_validate_route_exit_not_ppt,
        test_validate_route_conversion_type,
        test_validate_route_missing_source,
        test_ratio_auto_mode,
        test_ratio_explicit,
        test_ratio_ambiguous,
        test_build_prompt_injects_aesthetic_tokens,
        test_build_prompt_truncates_title,
        test_manifest_structure,
        test_classify_slide,
        test_extract_keywords,
        test_parse_pol_content,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"FAIL: {t.__name__}: {e}")
            failed += 1
    print(f"\n{'='*40}")
    print(f"结果: {passed} PASS, {failed} FAIL ({len(tests)} total)")
    sys.exit(0 if failed == 0 else 1)
