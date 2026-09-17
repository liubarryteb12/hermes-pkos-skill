#!/usr/bin/env python3
"""
27-pkos-imageapiuse 新增 sensenova provider 测试（v1.1）

测试目标：
  - quirks.endpoint_suffix 正确拼 URL
  - quirks.extra_body 字段自动注入（watermark=false, response_format=b64_json）
  - size_alias 映射正确
  - 无 quirks.extra_body 的 provider 行为不变（gptimage2 回归）

运行: python tests/test_sensenova.py
"""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

_SKILL_DIR = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _SKILL_DIR / "scripts"
_SHARED_DIR = _SKILL_DIR / "shared" / "image-api"

sys.path.insert(0, str(_SCRIPTS_DIR))
sys.path.insert(0, str(_SHARED_DIR))


class TestSensenovaQuirks(unittest.TestCase):
    """sensenova provider quirks 行为测试。"""

    def _build_cfg(self) -> dict:
        return {
            "active_provider": "sensenova",
            "providers": {
                "sensenova": {
                    "kind": "openai-compatible",
                    "endpoint": "https://token.sensenova.cn/v1",
                    "auth_env": "PKOS_IMG_API_KEY",
                    "model": "sensenova-u1.5-lite",
                    "defaults": {
                        "size": "auto",
                        "quality": "auto",
                        "output_format": "png",
                        "background": "auto",
                    },
                    "quirks": {
                        "transparent_bg_param": "background",
                        "size_alias": {
                            "square": "2048x2048",
                            "portrait_9_16": "1536x2720",
                            "landscape_16_9": "2720x1536",
                        },
                        "extra_body": {
                            "response_format": "b64_json",
                            "watermark": False,
                            "prompt_extend": True,
                        },
                        "retry_on_429": True,
                        "response_path": "data[0].b64_json",
                        "endpoint_suffix": "/images/generations",
                    },
                }
            },
            "failure_matrix": {
                "401": "fail-no-retry",
                "429": "retry-backoff",
                "5xx": "retry-once",
                "timeout": "fail-to-fallback",
            },
        }

    @patch.dict("os.environ", {"PKOS_IMG_API_KEY": "sk-test-sensenova"})
    def test_url_with_endpoint_suffix(self):
        """quirks.endpoint_suffix 应覆盖默认路径拼接。"""
        from client import _build_request
        cfg = self._build_cfg()
        url, body, headers = _build_request(cfg, "a cat", "1024x1024")
        self.assertEqual(url, "https://token.sensenova.cn/v1/images/generations")
        # 不应有双后缀
        self.assertNotIn("/v1/images/generations/images/generations", url)

    @patch.dict("os.environ", {"PKOS_IMG_API_KEY": "sk-test-sensenova"})
    def test_extra_body_injected(self):
        """quirks.extra_body 字段应合并进请求体。"""
        from client import _build_request
        cfg = self._build_cfg()
        url, body, headers = _build_request(cfg, "a cat", "1024x1024")
        self.assertEqual(body["response_format"], "b64_json")
        self.assertFalse(body["watermark"])
        self.assertTrue(body["prompt_extend"])
        self.assertEqual(body["model"], "sensenova-u1.5-lite")
        self.assertEqual(body["prompt"], "a cat")

    @patch.dict("os.environ", {"PKOS_IMG_API_KEY": "sk-test-sensenova"})
    def test_size_alias_mapping(self):
        """size_alias 应正确映射。"""
        from client import _build_request
        cfg = self._build_cfg()
        _, body, _ = _build_request(cfg, "a cat", "portrait_9_16")
        self.assertEqual(body["size"], "1536x2720")

        _, body2, _ = _build_request(cfg, "a cat", "landscape_16_9")
        self.assertEqual(body2["size"], "2720x1536")

        _, body3, _ = _build_request(cfg, "a cat", "square")
        self.assertEqual(body3["size"], "2048x2048")

    @patch.dict("os.environ", {"PKOS_IMG_API_KEY": "sk-test-sensenova"})
    def test_auto_quality_not_in_body(self):
        """quality=auto 不下发（上游要求显式传）。"""
        from client import _build_request
        cfg = self._build_cfg()
        _, body, _ = _build_request(cfg, "a cat", "auto")
        self.assertNotIn("quality", body)
        self.assertNotIn("background", body)

    @patch.dict("os.environ", {"PKOS_IMG_API_KEY": "sk-test-sensenova"})
    def test_explicit_quality_in_body(self):
        """quality=hd 应下发。"""
        from client import _build_request
        cfg = self._build_cfg()
        _, body, _ = _build_request(cfg, "a cat", "auto", quality="hd")
        self.assertEqual(body["quality"], "hd")


class TestBackwardCompatibility(unittest.TestCase):
    """原 gptimage2 provider 行为回归测试（无 quirks 改动）。"""

    def _build_gpt_cfg(self) -> dict:
        return {
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

    @patch.dict("os.environ", {"TEST_KEY": "sk-test"})
    def test_default_url_without_suffix(self):
        """无 endpoint_suffix 时应拼默认 /images/generations。"""
        from client import _build_request
        cfg = self._build_gpt_cfg()
        url, body, headers = _build_request(cfg, "a dog", "1024x1024")
        self.assertEqual(url, "http://test/v1/images/generations")

    @patch.dict("os.environ", {"TEST_KEY": "sk-test"})
    def test_no_extra_body_when_absent(self):
        """无 quirks.extra_body 时不应注入额外字段。"""
        from client import _build_request
        cfg = self._build_gpt_cfg()
        _, body, _ = _build_request(cfg, "a dog", "1024x1024")
        self.assertNotIn("watermark", body)
        self.assertNotIn("response_format", body)
        self.assertNotIn("prompt_extend", body)


if __name__ == "__main__":
    unittest.main()
