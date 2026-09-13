#!/usr/bin/env python3
"""pkos_paths.py — 套件统一路径解析(v2,09-14 用户裁定「产出根可配置」)。

优先级:环境变量 PKOS_CONFIG > <套件根>/config.json > 内置默认(本机兼容回退)。
所有单元脚本一律经本模块取路径,禁止再硬编码 vault/workspace 绝对路径。

路径职责(09-14 用户裁定):
  - 操作文件(脚本/配置/状态) → 套件根目录(本体,随套件走)
  - 产出产品(文章/图/报告)   → output_root(用户可配置,本机默认 workspace)
"""
from __future__ import annotations
import json
import os
from functools import lru_cache
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path(os.environ.get("PKOS_CONFIG") or (SKILL_ROOT / "config.json"))

# 内置默认 = 本机部署现状(未初始化时的兼容回退,不视为错误)
_DEFAULTS = {
    "vault": r"D:/obsidian知识库/obsidian知识库",
    "workspace": r"D:/00.AIagent/hermesagent/workspace",   # 产出总根(output_root)
    "inboxes": [r"D:/obsidian知识库/obsidian知识库/_PKOS/INBOX"],
}


@lru_cache(maxsize=1)
def _load() -> dict:
    """读 config.json（存在且合法则用之；否则用默认）。坏配置 fail-loud。"""
    if not CONFIG_PATH.exists():
        return dict(_DEFAULTS)
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        raise ValueError(f"config.json 不可解析（{CONFIG_PATH}）: {e}——修复或删除该文件后重试") from e
    if cfg.get("schema") != "pkos-config:1":
        raise ValueError(f"config.json schema 不是 pkos-config:1: {cfg.get('schema')!r}")
    for key in ("vault", "workspace"):
        if not cfg.get(key):
            raise ValueError(f"config.json 缺必填字段: {key}")
    cfg.setdefault("inboxes", [str(Path(cfg["vault"]) / "_PKOS" / "INBOX")])
    return cfg


def get_vault() -> Path:
    return Path(_load()["vault"])


def get_workspace() -> Path:
    """产出总根(output_root)。所有产出产品一律落在此目录下的对应子目录。"""
    return Path(_load()["workspace"])


def get_output_root() -> Path:
    """get_workspace 的语义别名:产出产品根目录(09-14 用户裁定「产出可配置」)。"""
    return get_workspace()


def get_ops_root() -> Path:
    """操作文件根(= 套件根 _ops/)。脚本/配置/状态快照落此,随套件本体走。"""
    return SKILL_ROOT / "_ops"


def get_inboxes() -> list[Path]:
    return [Path(x) for x in _load()["inboxes"]]


def config_exists() -> bool:
    return CONFIG_PATH.exists()


def write_config(vault: str, workspace: str, inboxes: list[str]) -> Path:
    """bootstrap 专用：写入配置（目录存在性校验在 bootstrap 交互层做）。"""
    cfg = {"schema": "pkos-config:1", "vault": str(Path(vault).as_posix()),
           "workspace": str(Path(workspace).as_posix()),
           "inboxes": [str(Path(x).as_posix()) for x in inboxes]}
    from datetime import datetime, timezone
    cfg["created_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    _load.cache_clear()
    return CONFIG_PATH
