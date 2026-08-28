"""PKOS v3.1 共享库：类型守卫 + 物理 Hash 断言 + Telemetry 记录。

被 pkos-html / pkos-ppt-skill / pkos-exit-* 渲染脚本共享 import。
落地位置：pkos-exit-common（新建），所有 exit 包通过 sys.path 共享。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# v3.1 Hook constants
MAX_RETRY = 2
HOOK_VAULT_TTL_DAYS = 30

# v3.3 [Type System TTL]: DerivedDraft 双轨生命周期
#   成功草稿 (_drafts/): 24h 后可清理（Tick 巡检回收）
#   失败/降级隔离 (_quarantine/): 30d 保留归档（诊断上下文，超期由 Tick 提示而非静默删除）
DRAFT_TTL_HOURS = 24
QUARANTINE_TTL_DAYS = 30

# v3.3 [Event Bus]: 事件 schema 版本（消费方据此做兼容解析）
TELEMETRY_SCHEMA_VERSION = "1.0"

# Telemetry: 单写者 jsonl，所有 exit/render/polish 调用都追加
TELEMETRY_PATH = Path(
    os.environ.get("PKOS_TELEMETRY_PATH", "").strip()
    or Path(__file__).resolve().parents[2] / "_PKOS" / "execution" / "telemetry.jsonl"
)


# =====================================================================
# 物理 Hash 断言 (Verification Matrix 核心)
# =====================================================================

def hash_file(p: Path) -> str:
    """SHA256 of file bytes. Empty file = '0' * 64."""
    if not p.exists():
        return "0" * 64
    return hashlib.sha256(p.read_bytes()).hexdigest()


def assert_unchanged(p: Path, pre_hash: str, label: str = "source") -> None:
    """[Self-check A] 物理断言：p 存在且 SHA256 == pre_hash.

    失败立即 sys.exit(5) + 打印 FATAL 错误。"""
    if not p.exists():
        print(
            f"FATAL [Self-check A]: {label} 文件不存在 {p} — "
            f"违反 v3.1 [Verification Matrix]",
            file=sys.stderr,
        )
        sys.exit(5)
    post = hash_file(p)
    if post != pre_hash:
        print(
            f"FATAL [Self-check A]: {label} 哈希变化 {p}\n"
            f"  pre  = {pre_hash}\n"
            f"  post = {post}",
            file=sys.stderr,
        )
        sys.exit(5)


def assert_vault_unchanged(vault_path: Path, baseline: dict[str, str]) -> None:
    """[Self-check A 整库版本] 比对 baseline dict {relpath: sha256}."""
    current: dict[str, str] = {}
    for p in sorted(vault_path.rglob("*.md")):
        rel = str(p.relative_to(vault_path))
        current[rel] = hash_file(p)
    if current != baseline:
        added = set(current) - set(baseline)
        removed = set(baseline) - set(current)
        changed = [
            k for k in current
            if k in baseline and current[k] != baseline[k]
        ]
        print(
            f"FATAL [Self-check A]: vault 完整性破坏\n"
            f"  added:   {sorted(added)[:5]}\n"
            f"  removed: {sorted(removed)[:5]}\n"
            f"  changed: {sorted(changed)[:5]}",
            file=sys.stderr,
        )
        sys.exit(5)


# =====================================================================
# 类型守卫 (Type System)
# =====================================================================

REQUIRED_FIELDS: dict[str, list[str]] = {
    "raw_entry": ["type", "stage", "source", "path"],
    "fact_core": ["type", "stage", "sha256", "path", "status"],
    # entities/facts/numbers 是弱审核的输入材料，契约声明必填 → 守卫强制
    "derived_draft": [
        "type", "target_skill", "derived_from_fact_core",
        "entities", "facts", "numbers",
    ],
    "export_artifact": ["type", "derived_from_derived_draft", "path", "output_location"],
}


def assert_typed(obj: Any, expected_type: str) -> None:
    """[Type Guard] v3.1 强类型校验."""
    if not isinstance(obj, dict):
        raise TypeError(f"expected dict, got {type(obj).__name__}")
    actual = obj.get("type")
    if actual != expected_type:
        raise TypeError(f"type mismatch: expected {expected_type}, got {actual}")
    for field in REQUIRED_FIELDS.get(expected_type, []):
        if field not in obj:
            raise TypeError(
                f"missing required field '{field}' for type {expected_type}"
            )


# =====================================================================
# Telemetry 事件总线 (Event Bus)
# =====================================================================

def emit(cap_id: str, event_type: str | None = None, **fields: Any) -> None:
    """追加一条 telemetry 事件到 jsonl. 失败容错（不允许 telemetry 影响主流程）.

    v3.3.1 收紧（P-15 契约）: event_type 缺省时显式落 "unspecified"（而非字段缺失）——
    dashboard 的 event_type 维度因此总是可聚合；历史 none 数据不再新增。
    """
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "cap_id": cap_id,
        "event_type": event_type or "unspecified",  # v3.3.1: 显式缺省值, 拒绝字段缺失
        "schema_version": TELEMETRY_SCHEMA_VERSION,  # v3.3: 事件 schema 版本化
        **fields,
    }
    try:
        TELEMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TELEMETRY_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError as e:
        # Telemetry 写失败不阻塞主流程，但 stderr 提示
        print(f"WARN: telemetry emit failed: {e}", file=sys.stderr)


def emit_render(
    cap_id: str,
    target_skill: str,
    retry_count: int = 0,
    fallback_triggered: bool = False,
    latency_ms: int = 0,
    **extra: Any,
) -> None:
    """渲染层 telemetry 标准事件."""
    emit(
        cap_id=cap_id,
        target_skill=target_skill,
        retry_count=retry_count,
        fallback_triggered=fallback_triggered,
        latency_ms=latency_ms,
        **extra,
    )


# =====================================================================
# Raw Fallback (Loop)
# =====================================================================

def assert_no_ntfs_ads(path_str: str) -> None:
    """v3.3 [Hook 2 NTFS 防御]: 路径中间段/文件名段含 ':' 即 ADS 注入，拒绝.

    合法盘符冒号只允许出现在首段（如 'D:'）。供自定义 safe_out_fn 复用。
    违规抛 ValueError（调用方决定 exit 码），render.assert_safe_out 内联了同等检查。"""
    segs = path_str.replace("\\", "/").split("/")
    for i, seg in enumerate(segs):
        if not seg:
            continue
        if ":" in seg and not (i == 0 and len(seg) == 2 and seg[1] == ":"):
            raise ValueError(
                f"NTFS ADS colon detected in segment '{seg}' of '{path_str}'"
            )


def quarantine_write(
    target: Path,
    content: str,
    reason: str,
    meta: dict | None = None,
) -> Path:
    """v3.3 [TTL 双轨]: 失败/降级内容落 _quarantine/ 隔离区.

    附带 30d 保留标记 + 诊断上下文（reason/meta/ts），供 Tick 巡检识别归档期。
    只新增文件，永不删除既有文件（P-01 零删除）。"""
    assert_no_ntfs_ads(str(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "<!-- pkos-quarantine\n"
        f"  ts: {datetime.now(timezone.utc).isoformat()}\n"
        f"  ttl_days: {QUARANTINE_TTL_DAYS}\n"
        f"  reason: {reason}\n"
        + ("".join(f"  {k}: {v}\n" for k, v in (meta or {}).items()))
        + "-->\n"
    )
    target.write_text(header + content, encoding="utf-8")
    emit(
        cap_id="pkos.quarantine",
        event="quarantine.write",
        path=str(target),
        ttl_days=QUARANTINE_TTL_DAYS,
        reason=reason,
    )
    return target

def raw_fallback(
    out: Path,
    source_path: Path,
    reason: str,
    cap_id: str,
    safe_out_fn=None,
) -> Path:
    """触发 Raw Fallback：把源 markdown 直出到白名单隔离区（同 .fallback.md 后缀）.

    safe_out_fn: 调用方注入的白名单校验函数（如 render.assert_safe_out）。
    为 None 时退回 render.assert_safe_out（仅 pkos-html 场景可用）。
    返回实际写入的路径。"""
    fallback = out.with_suffix(".fallback.md")
    if safe_out_fn is None:
        from render import assert_safe_out
        safe_out_fn = assert_safe_out
    safe_out_fn(fallback)
    fallback.parent.mkdir(parents=True, exist_ok=True)
    fallback.write_text(
        source_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    emit_render(
        cap_id=cap_id,
        target_skill="raw_fallback",
        fallback_triggered=True,
        reason=reason,
    )
    return fallback


# =====================================================================
# Retry 装饰器 (Loop)
# =====================================================================

def with_max_retry(max_retry: int = MAX_RETRY):
    """装饰器：函数失败时重试 max_retry 次。"""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(max_retry + 1):
                try:
                    return fn(*args, **kwargs)
                except OSError as e:
                    last_err = e
                    if attempt < max_retry:
                        print(
                            f"WARN: {fn.__name__} retry {attempt + 1}/{max_retry}: {e}",
                            file=sys.stderr,
                        )
                        continue
                    raise
            raise last_err  # unreachable
        return wrapper
    return decorator


# =====================================================================
# 写文件 with Retry + Fallback (供 render 脚本使用)
# =====================================================================

def write_with_retry(
    out: Path,
    data: bytes,
    source_path: Path,
    pre_hash: str,
    cap_id: str,
    safe_out_fn=None,
) -> tuple[Path, bool]:
    """写入 out, MAX_RETRY 次失败 → 触发 raw_fallback.

    safe_out_fn: 调用方注入的白名单校验函数；None 时退回 render.assert_safe_out。
    返回 (实际写入路径, 是否降级)."""
    if safe_out_fn is None:
        from render import assert_safe_out
        safe_out_fn = assert_safe_out
    safe_out_fn(out)

    t0 = time.time()
    written = False
    last_err: Exception | None = None
    for attempt in range(MAX_RETRY + 1):
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
            written = True
            break
        except OSError as e:
            last_err = e
            print(
                f"WARN: write failed (retry {attempt + 1}/{MAX_RETRY}) {out}: {e}",
                file=sys.stderr,
            )

    # Self-check A: 写完断言源不变
    assert_unchanged(source_path, pre_hash, label="FactCore")

    if written:
        emit_render(
            cap_id=cap_id,
            target_skill=out.suffix.lstrip("."),
            retry_count=0,
            fallback_triggered=False,
            latency_ms=int((time.time() - t0) * 1000),
        )
        return out, False

    # 失败 → Raw Fallback
    fallback = raw_fallback(
        out, source_path,
        reason=f"write OSError x{MAX_RETRY}: {last_err}",
        cap_id=cap_id,
        safe_out_fn=safe_out_fn,
    )
    # Fallback 也断言源不变
    assert_unchanged(source_path, pre_hash, label="FactCore (post-fallback)")
    return fallback, True
