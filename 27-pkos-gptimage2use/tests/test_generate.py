#!/usr/bin/env python3
"""
27-pkos-gptimage2use 单元测试（v1.0）

测试目标：
  - 输入校验（prompt 空 → ValueError）
  - manifest 结构完整性
  - 失败路径（mock API error → degraded）

运行: python tests/test_generate.py
"""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# 确保能找到 scripts/ 和 shared/image-api/
_SKILL_DIR = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _SKILL_DIR / "scripts"
_SHARED_DIR = _SKILL_DIR / "shared" / "image-api"

sys.path.insert(0, str(_SCRIPTS_DIR))
sys.path.insert(0, str(_SHARED_DIR))


class TestGenerate(unittest.TestCase):
    """测试 27-pkos-gptimage2use 核心逻辑。"""

    def test_empty_prompt_raises(self):
        """prompt 为空应抛 ValueError。"""
        from generate import generate
        with self.assertRaises(ValueError) as ctx:
            generate(prompt="")
        self.assertIn("prompt 不能为空", str(ctx.exception))

    def test_empty_prompt_whitespace_only(self):
        """prompt 全空格也应抛 ValueError。"""
        from generate import generate
        with self.assertRaises(ValueError) as ctx:
            generate(prompt="   ")
        self.assertIn("prompt 不能为空", str(ctx.exception))

    @patch("generate.call_generate")
    @patch("generate.load_config")
    def test_single_generation_success(self, mock_load, mock_call):
        """成功生成一张图应返回正确结果。"""
        mock_load.return_value = {
            "active_provider": "gptimage2",
            "providers": {
                "gptimage2": {
                    "kind": "openai-compatible",
                    "endpoint": "http://test/v1",
                    "auth_env": "TEST_KEY",
                    "model": "gpt-image-2",
                    "defaults": {"size": "1024x1024", "output_format": "png"},
                    "quirks": {"response_path": "data[0].b64_json"},
                }
            },
            "failure_matrix": {"401": "fail-no-retry", "429": "retry-backoff"},
        }
        mock_call.return_value = {
            "file": "/tmp/test.png",
            "prompt": "test prompt",
            "revised_prompt": "test prompt (revised)",
            "size": "1024x1024",
            "hash": "abc123def456",
            "provider": "image-api:gptimage2",
        }

        from generate import generate
        results = generate(prompt="test prompt", route_id="RT-20260828-001")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["prompt"], "test prompt")
        self.assertEqual(results[0]["manifest"]["route_id"], "RT-20260828-001")
        self.assertFalse(results[0]["manifest"]["degraded"])
        self.assertIn("file_hash", results[0]["manifest"])

    @patch("generate.call_generate")
    @patch("generate.load_config")
    def test_api_failure_degraded(self, mock_load, mock_call):
        """API 失败时应标记 degraded=true 并保留 prompt。"""
        mock_load.return_value = {
            "active_provider": "gptimage2",
            "providers": {"gptimage2": {"kind": "openai-compatible", "endpoint": "http://test/v1",
                                         "auth_env": "TEST_KEY", "model": "gpt-image-2",
                                         "defaults": {}, "quirks": {"response_path": "data[0].b64_json"}}},
            "failure_matrix": {},
        }
        mock_call.side_effect = RuntimeError("Connection refused")

        from generate import generate
        results = generate(prompt="test prompt", route_id="RT-20260828-001")

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["manifest"]["degraded"])
        self.assertEqual(results[0]["manifest"]["prompt"], "test prompt")
        self.assertIn("error", results[0]["manifest"])

    @patch("generate.call_generate")
    @patch("generate.load_config")
    def test_multiple_count(self, mock_load, mock_call):
        """count=3 应生成 3 张图，每张 prompt 带 variant 后缀。"""
        mock_load.return_value = {
            "active_provider": "gptimage2",
            "providers": {"gptimage2": {"kind": "openai-compatible", "endpoint": "http://test/v1",
                                         "auth_env": "TEST_KEY", "model": "gpt-image-2",
                                         "defaults": {}, "quirks": {"response_path": "data[0].b64_json"}}},
            "failure_matrix": {},
        }
        mock_call.return_value = {
            "file": "/tmp/test.png",
            "prompt": "test",
            "revised_prompt": "",
            "size": "1024x1024",
            "hash": "hash123",
            "provider": "image-api:gptimage2",
        }

        from generate import generate
        results = generate(prompt="test", count=3)

        self.assertEqual(len(results), 3)
        # call_generate 应被调用 3 次，每次 effective_prompt 带 variant 后缀
        calls = mock_call.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertIn("[variant-1]", calls[0][1]["prompt"])
        self.assertIn("[variant-3]", calls[2][1]["prompt"])
        # 结果 prompt 字段是原始 prompt（manifest 存原始值）
        for r in results:
            self.assertEqual(r["prompt"], "test")


if __name__ == "__main__":
    unittest.main()
