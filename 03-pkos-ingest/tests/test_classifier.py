#!/usr/bin/env python3
"""03-pkos-ingest classifier 测试桩 —— 验证 model-agnostic 行为稳定性。

覆盖 5 类场景：
  1. 单域强信号（考公、生信、AI）
  2. 跨域边界（哲学 vs 传统文化、理财 vs AI 工具）
  3. 匿名标题（Post by @xxx on X）
  4. 无匹配兜底
  5. 批量模式（intake.json 输入）

退出码：0=全过，1=有失败
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "classifier.py"
VAULT = Path("D:/obsidian知识库/obsidian知识库")

TEST_CASES = [
    # (test_name, input_text, expected_domain, min_confidence, expected_tags_subset)
    ("ai-coding-strong",
     "这是一篇关于AI编程助手的使用教程，介绍了如何配置Codex工具和自动化工作流",
     "ai-usage", 0.7, ["AI", "编程"]),
    ("ai-prompt-strong",
     "Midjourney生图提示词技巧，包含人物写真的安全合规指南",
     "ai-usage", 0.7, ["AI"]),
    ("career-interview",
     "公务员面试经验总结，包含结构化面试题和综合分析题的答题框架",
     "career-growth", 0.2, ["职业", "考公"]),
    ("gongkao-strong",
     "公务员行测真题解析，包含言语理解、数量关系、判断推理等模块",
     "gongkao", 0.9, ["考公"]),
    ("humanities-philosophy",
     "儒家哲学思想入门，包含论语、孟子、大学、中庸的核心概念解析",
     "humanities", 0.7, ["哲学", "传统文化"]),
    ("scrn-single-cell",
     "单细胞RNA测序数据分析流程，包含降维聚类和差异基因表达分析",
     "scrn", 0.7, ["生信"]),
    ("rcpm-clinical",
     "R语言构建临床预测模型，ROC曲线和AUC评估分类性能",
     "rcpm", 0.7, ["医学", "生信"]),
    ("invest-finance",
     "股票投资入门指南，基金定投和ETF配置策略详解",
     "invest", 0.7, ["理财"]),
    ("assets-design",
     "PPT排版设计素材合集，包含商务模板和图表配色方案",
     "assets", 0.7, ["素材"]),
    ("anonymous-x-post",
     "Post by @user123 on X - AI Agent workflow automation tips",
     "ai-usage", 0.7, ["AI"]),
]


def run_classify(text: str, source: str = "") -> dict:
    """调用分类器并返回结果。"""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "classify", text, "--source", source],
        capture_output=True, text=True, timeout=15
    )
    if result.returncode != 0:
        raise RuntimeError(f"Classifier failed: {result.stderr}")
    return json.loads(result.stdout)


def test_single_case(name: str, text: str, expected_domain: str,
                     min_confidence: float, expected_tags: list[str]) -> dict:
    """单个测试用例。"""
    result = run_classify(text)
    actual_domain = result.get("suggested_domain")
    actual_conf = result.get("confidence", 0)
    actual_tags = set(result.get("suggested_tags", []))
    
    errors = []
    if actual_domain != expected_domain:
        errors.append(f"domain mismatch: expected={expected_domain}, got={actual_domain}")
    if actual_conf < min_confidence:
        errors.append(f"confidence too low: {actual_conf} < {min_confidence}")
    missing_tags = set(expected_tags) - actual_tags
    if missing_tags:
        errors.append(f"missing tags: {missing_tags}, got: {actual_tags}")
    
    return {
        "name": name,
        "passed": len(errors) == 0,
        "errors": errors,
        "result": result
    }


def test_batch_mode() -> dict:
    """批量模式测试。"""
    # 构造测试 intake.json
    test_inbox = tempfile.mkdtemp()
    # 创建两个测试文件
    test_files = [
        ("test_ai.md", "---\ntitle: \"AI工具测试\"\ntype: clipping\n---\n\n这是一篇关于AI编程助手的文章。"),
        ("test_gongkao.md", "---\ntitle: \"考公笔记\"\ntype: clipping\n---\n\n公务员行测真题总结。"),
    ]
    for fname, content in test_files:
        (Path(test_inbox) / fname).write_text(content, encoding="utf-8")
    
    # 创建 intake manifest
    manifest = {
        "inbox": test_inbox,
        "tickets": [
            {"item": "test_ai.md", "source": ""},
            {"item": "test_gongkao.md", "source": ""},
        ],
        "skipped_sensitive_items": 0
    }
    manifest_path = Path(test_inbox) / "intake.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    
    out_path = Path(test_inbox) / "classified.json"
    
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "batch",
         "--manifest", str(manifest_path),
         "--vault", str(VAULT),
         "--out", str(out_path)],
        capture_output=True, text=True, timeout=30
    )
    
    if result.returncode != 0:
        return {"name": "batch-mode", "passed": False, "errors": [f"exit={result.returncode}: {result.stderr}"]}
    
    if not out_path.exists():
        return {"name": "batch-mode", "passed": False, "errors": ["output file not created"]}
    
    classified = json.loads(out_path.read_text(encoding="utf-8"))
    
    errors = []
    if classified.get("total_items") != 2:
        errors.append(f"total_items mismatch: expected=2, got={classified.get('total_items')}")
    
    results = classified.get("results", [])
    if len(results) != 2:
        errors.append(f"results count mismatch: expected=2, got={len(results)}")
    else:
        # 验证第一个是 AI 域，第二个是考公域
        r1_domain = results[0].get("classification", {}).get("suggested_domain")
        r2_domain = results[1].get("classification", {}).get("suggested_domain")
        if r1_domain != "ai-usage":
            errors.append(f"result[0] domain: expected=ai-usage, got={r1_domain}")
        if r2_domain != "gongkao":
            errors.append(f"result[1] domain: expected=gongkao, got={r2_domain}")
    
    return {"name": "batch-mode", "passed": len(errors) == 0, "errors": errors, "result": classified}


def test_low_confidence_fallback() -> dict:
    """低置信度兜底测试。"""
    text = "这是一段没有明显领域特征的日常文字"
    result = run_classify(text)
    
    errors = []
    # 低置信度应该标记 needs_human_review=True
    if not result.get("needs_human_review"):
        errors.append("low confidence text should trigger needs_human_review=True")
    
    return {"name": "low-confidence-fallback", "passed": len(errors) == 0, "errors": errors, "result": result}


def main() -> int:
    print(f"Testing classifier: {SCRIPT}")
    print(f"Vault: {VAULT}")
    print("=" * 60)
    
    results = []
    
    # 单例测试
    for name, text, exp_domain, min_conf, exp_tags in TEST_CASES:
        r = test_single_case(name, text, exp_domain, min_conf, exp_tags)
        status = "✓ PASS" if r["passed"] else "✗ FAIL"
        print(f"[{status}] {name}")
        if not r["passed"]:
            for e in r["errors"]:
                print(f"         - {e}")
        results.append(r)
    
    # 批量测试
    r = test_batch_mode()
    status = "✓ PASS" if r["passed"] else "✗ FAIL"
    print(f"[{status}] {r['name']}")
    if not r["passed"]:
        for e in r["errors"]:
            print(f"         - {e}")
    results.append(r)
    
    # 低置信度兜底
    r = test_low_confidence_fallback()
    status = "✓ PASS" if r["passed"] else "✗ FAIL"
    print(f"[{status}] {r['name']}")
    if not r["passed"]:
        for e in r["errors"]:
            print(f"         - {e}")
    results.append(r)
    
    # 汇总
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    
    print("=" * 60)
    print(f"Result: {passed}/{total} passed, {failed} failed")
    
    if failed > 0:
        print("\nFailed cases:")
        for r in results:
            if not r["passed"]:
                print(f"  - {r['name']}: {r['errors']}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
