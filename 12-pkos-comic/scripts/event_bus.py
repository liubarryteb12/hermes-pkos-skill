"""
event_bus.py — 12-pkos-comic EventBus 包装（v3.2 Phase 4,评审 round-25 通过）

复用 10-pkos-html/scripts/pkos_v31_lib.py 的 emit/emit_render:
- export.success  : 正常交付(脚本完整 + manifest 完整)
- export.fallback : degraded_success(出图渠道不可用,交付 prompt 清单)
- export.degraded : 系统级降级(IO/数据问题)
- anchor.mismatch : 人物跨 panel anchor_hash 不一致(ERR_ANCHOR_MISMATCH)

参考:ppt 用了 img_client (shared/image-api),comic 暂不调真实出图 API,
所有事件写到 _PKOS/execution/telemetry.jsonl 唯一单写者。
"""
from __future__ import annotations

import importlib.util as _ilu
import sys
from pathlib import Path
from typing import Any

# === 加载 v3.1 共享库 (与 render_deck.py 同模式) ===
_V31_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "10-pkos-html"
    / "scripts"
    / "pkos_v31_lib.py"
)
_spec = _ilu.spec_from_file_location("pkos_v31_lib", _V31_PATH)
_pkos_v31 = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_pkos_v31)

emit = _pkos_v31.emit  # type: ignore[attr-defined]
emit_render = _pkos_v31.emit_render  # type: ignore[attr-defined]
MAX_RETRY = _pkos_v31.MAX_RETRY  # type: ignore[attr-defined]

CAP_ID_COMIC = "pkos.exit.comic.compose"


# === comic 出口语义事件 (按 v3.1 EventBus schema) ===

def emit_export_success(
    route_id: str,
    panels_count: int,
    art_style: str,
    chinese_text: bool,
    style_adapter: str | None = None,
    **extra: Any,
) -> None:
    """正常交付事件。"""
    emit(
        cap_id=CAP_ID_COMIC,
        event_type="export.success",
        route_id=route_id,
        panels_count=panels_count,
        art_style=art_style,
        chinese_text=chinese_text,
        style_adapter=style_adapter,
        target_skill="comic_storyboard" if style_adapter == "comic_storyboard" else "comic",
        **extra,
    )


def emit_export_fallback(
    route_id: str,
    reason: str,
    panels_count: int,
    **extra: Any,
) -> None:
    """degraded_success: 脚本完整,出图渠道不可用。"""
    emit(
        cap_id=CAP_ID_COMIC,
        event_type="export.fallback",
        route_id=route_id,
        reason=reason,
        panels_count=panels_count,
        fallback_triggered=True,
        target_skill="comic_fallback",
        **extra,
    )


def emit_export_degraded(
    route_id: str,
    reason: str,
    error_code: str,
    **extra: Any,
) -> None:
    """系统级降级:IO/数据问题导致未能交付完整产物。"""
    emit(
        cap_id=CAP_ID_COMIC,
        event_type="export.degraded",
        route_id=route_id,
        reason=reason,
        error_code=error_code,
        degraded=True,
        target_skill="comic_degraded",
        **extra,
    )


def emit_anchor_mismatch(
    route_id: str,
    character_id: str,
    panel_a: int,
    panel_b: int,
    **extra: Any,
) -> None:
    """人物锚定不一致(ERR_ANCHOR_MISMATCH)"""
    emit(
        cap_id=CAP_ID_COMIC,
        event_type="anchor.mismatch",
        route_id=route_id,
        character_id=character_id,
        panel_a=panel_a,
        panel_b=panel_b,
        error_code="ERR_ANCHOR_MISMATCH",
        target_skill="comic",
        **extra,
    )


def emit_validation_fail(
    route_id: str,
    error_code: str,
    rejected_fields: list[str],
    **extra: Any,
) -> None:
    """gate_1/gate_2 失败"""
    emit(
        cap_id=CAP_ID_COMIC,
        event_type="validation.fail",
        route_id=route_id,
        error_code=error_code,
        rejected_fields=rejected_fields,
        target_skill="comic",
        **extra,
    )


if __name__ == "__main__":
    # smoke test
    emit_export_success("RT-TEST-001", panels_count=7, art_style="healing", chinese_text=True)
    print("event_bus smoke test OK")
