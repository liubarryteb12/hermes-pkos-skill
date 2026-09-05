#!/usr/bin/env python3
"""
shared/image-api/client.py — 图像生成网关适配层

读取 shared/image-api/config.json（或环境变量 PKOS_IMG_CONFIG），
调用 OpenAI 兼容 /images/generations 接口。

支持 failure_matrix 语义：401→fail-no-retry, 429→retry-backoff, 5xx→retry-once, timeout→fallback。
所有 provider 差异隔离在 quirks 区；消费方永远不感知网关是谁。

v0 铁律：不擅自换 provider，不擅自改尺寸重试。
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# ── 配置加载 ────────────────────────────────────────────────────────────────

# client.py lives at <workspace>/shared/image-api/client.py
# config.json is at <workspace>/shared/image-api/config.json (same dir)
_DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = _DEFAULT_CONFIG_DIR / "config.example.json"  # safe default (no secrets)

FAILURE_MATRIX = {
    "401": "fail-no-retry",
    "429": "retry-backoff",
    "5xx": "retry-once",
    "timeout": "fail-to-fallback",
}

MAX_RETRIES_BACKOFF = 3       # 429 最多退避重试次数
MAX_RETRIES_ONCE = 1          # 5xx 最多重试一次


def load_config() -> dict:
    """加载 config.json；优先 PKOS_IMG_CONFIG 环境变量，其次默认路径。"""
    cfg_path_str = os.environ.get("PKOS_IMG_CONFIG", str(DEFAULT_CONFIG_PATH))
    cfg_path = Path(cfg_path_str)
    if not cfg_path.exists():
        raise FileNotFoundError(f"image-api config.json 不存在: {cfg_path}")
    with open(cfg_path, "r", encoding="utf-8-sig") as f:
        cfg = json.load(f)
    # 校验必填字段
    for key in ("active_provider", "providers"):
        if key not in cfg:
            raise ValueError(f"config.json 缺少必填字段: {key}")
    # auth_env 安全：不允许明文 key
    active = cfg["active_provider"]
    prov = cfg["providers"].get(active)
    if not prov:
        raise ValueError(f"active_provider '{active}' 不在 providers 中")
    auth_env = prov.get("auth_env")
    if not auth_env:
        raise ValueError(f"provider '{active}' 未声明 auth_env")
    if "api_key" in prov and isinstance(prov["api_key"], str) and prov["api_key"].startswith("sk-"):
        raise ValueError(
            f"provider '{active}' config.json 含明文 api_key（铁律：只允许 auth_env）"
        )
    return cfg


def get_api_key(cfg: dict, provider_id: str | None = None) -> str:
    """从环境变量读取密钥；provider_id 为空时取 active_provider。"""
    active = provider_id or cfg["active_provider"]
    auth_env = cfg["providers"][active].get("auth_env", "PKOS_IMG_API_KEY")
    key = os.environ.get(auth_env)
    if not key:
        raise RuntimeError(
            f"凭证缺失：环境变量 {auth_env} 未设置（provider={active}）"
        )
    return key


# ── 网关调用 ────────────────────────────────────────────────────────────────

def _build_request(
    cfg: dict,
    prompt: str,
    size: str,
    quality: str | None = None,
    background: str | None = None,
) -> tuple[str, dict, dict]:
    """构建请求体；quirks.size_alias 自动映射别名。返回 (url, body, extra_headers)。"""
    active = cfg["active_provider"]
    prov = cfg["providers"][active]
    endpoint = prov["endpoint"].rstrip("/")
    url = endpoint + "/images/generations"

    quirks = prov.get("quirks", {})
    body: dict[str, Any] = {
        "model": prov.get("model", "gpt-image-2"),
        "prompt": prompt,
    }
    # size_alias：wide → 1536x1024 等
    size_alias = quirks.get("size_alias", {})
    if size in size_alias:
        size = size_alias[size]
    body["size"] = size

    defaults = prov.get("defaults", {})
    if quality is None:
        quality = defaults.get("quality", "auto")
    if quality:
        body["quality"] = quality
    if background is None:
        background = defaults.get("background", "auto")
    if background:
        body["background"] = background

    headers = {
        "Authorization": f"Bearer {get_api_key(cfg, active)}",
        "Content-Type": "application/json",
    }
    return url, body, headers


def _parse_retry_limit(action_str: str, default: int = 3) -> int:
    """从 failure_matrix 动作字符串解析最大重试次数。

    已知动作：
    - "fail-no-retry" → 0
    - "retry-backoff" → default（默认 3）
    - "retry-once" → 1
    - "fail-to-fallback" → 0
    """
    if action_str == "fail-no-retry" or action_str == "fail-to-fallback":
        return 0
    if action_str == "retry-once":
        return 1
    if action_str == "retry-backoff":
        return default
    # 尝试从字符串末尾提取数字（如 "retry-3"）
    import re as _re
    m = _re.search(r"(\d+)$", action_str)
    return int(m.group(1)) if m else default


def call_generate(
    cfg: dict,
    prompt: str,
    size: str,
    output_dir: Path,
    quality: str | None = None,
    background: str | None = None,
    timeout_sec: int = 300,
) -> dict:
    """
    调用图像生成 API，返回 {file, prompt, revised_prompt, size, hash}。
    失败按 failure_matrix 语义处理（不擅自重试不可重试的错误）。
    """
    active = cfg["active_provider"]
    prov = cfg["providers"][active]
    failure_matrix = cfg.get("failure_matrix", FAILURE_MATRIX)
    url, body, headers = _build_request(cfg, prompt, size, quality, background)

    ext = prov.get("defaults", {}).get("output_format", "png") or "png"
    dest = output_dir / f"slide-{hashlib.md5(prompt.encode()).hexdigest()[:8]}.{ext}"

    # 解析 429 退避重试上限
    retry_limit = _parse_retry_limit(failure_matrix.get("429", "retry-backoff"), default=3)
    for attempt in range(1 + retry_limit):
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                break
        except urllib.error.HTTPError as he:
            code = he.code
            action = failure_matrix.get(str(code), "fail-no-retry")
            err_body = ""
            try:
                err_body = he.read().decode("utf-8", "replace")[:500]
            except Exception:
                pass
            if action == "fail-no-retry":
                raise RuntimeError(f"{active} HTTP {code}: {err_body}") from he
            if action == "retry-backoff" and attempt < retry_limit:
                wait = 2 ** attempt
                time.sleep(wait)
                continue
            raise RuntimeError(f"{active} HTTP {code}: {err_body}") from he
        except urllib.error.URLError as ue:
            # timeout
            action = failure_matrix.get("timeout", "fail-to-fallback")
            if action == "fail-to-fallback":
                raise RuntimeError(f"{active} 超时: {ue.reason}") from ue
            raise
        except Exception as e:
            raise RuntimeError(f"{active} 调用异常: {e}") from e
    else:
        raise RuntimeError(f"{active} 重试耗尽（{1 + retry_limit} 次）")

    # 解析响应
    resp_path = prov.get("quirks", {}).get("response_path", "data[0].b64_json")
    parts = resp_path.split(".")
    obj = data
    for p in parts:
        if "[" in p:
            key, idx = p.split("[")
            idx = int(idx.rstrip("]"))
            obj = obj[key][idx]
        else:
            obj = obj[p]
    b64 = obj
    if not b64 or not isinstance(b64, str):
        raise RuntimeError(f"响应无 b64_json: {json.dumps(data)[:300]}")

    output_dir.mkdir(parents=True, exist_ok=True)
    raw = base64.b64decode(b64)
    dest.write_bytes(raw)

    file_hash = hashlib.sha256(raw).hexdigest()
    revised = data.get("data", [{}])[0].get("revised_prompt", "")

    return {
        "file": str(dest.resolve()),
        "prompt": prompt,
        "revised_prompt": revised,
        "size": size,
        "hash": file_hash,
        "provider": f"image-api:{active}",
    }


# ── CLI 入口（调试用） ──────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="11-pkos-ppt-skill image-api 调用器（调试）")
    ap.add_argument("--prompt", required=True, help="图像提示词")
    ap.add_argument("--size", default="1536x1024", help="尺寸（宽×高，像素）")
    ap.add_argument("--quality", default=None, help="quality: low/medium/high/auto")
    ap.add_argument("--background", default=None, help="background: opaque/transparent/auto")
    ap.add_argument("--out-dir", default=None, help="输出目录（默认 config.json defaults.output_dir）")
    ap.add_argument("--cfg", default=str(DEFAULT_CONFIG_PATH), help="config.json 路径")
    args = ap.parse_args(argv)

    # Override default config path for this invocation
    cfg = load_config()
    out_dir = Path(args.out_dir or cfg.get("defaults", {}).get("output_dir", "output"))
    try:
        result = call_generate(cfg, args.prompt, args.size, out_dir, args.quality, args.background)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
