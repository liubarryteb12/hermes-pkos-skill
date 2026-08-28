"""
GPTImage2Adapter (v3.2 Phase 3,评审 round-25 通过)

渠道评估:中文约 80% 成功率 → 默认开 chinese_text=true

注:gptimage2 只接 1024x1024/1024x1792/1792x1024 固定尺寸。pkos-comic 6 宫
1200x1880 / 4 宫 1200x1240 / 16:9 封面 1200x675 需调用方手动 clip。
"""
from typing import List, Dict, Any
from .base import BaseAdapter, PanelPrompt


class GPTImage2Adapter(BaseAdapter):
    def channel_name(self) -> str:
        return "gptimage2"

    def supports_chinese_text(self) -> bool:
        return True

    def build_requests(self, panels: List[PanelPrompt], metadata: Dict) -> List[Dict[str, Any]]:
        chinese = metadata.get("chinese_text", True)
        return [
            {
                "model": "gpt-image-2",
                "prompt": p.prompt,
                "size": self._map_size(p.output_size),
                "n": 1,
                "quality": "hd",
                "metadata": {
                    "panel_id": p.panel_id,
                    "route_id": metadata.get("route_id"),
                    "chinese_text_enabled": chinese,
                    "note": "gptimage2 size 不支持 pkos-comic 1200x1880 整图,需调用方手动 clip"
                }
            }
            for p in panels
        ]

    def _map_size(self, size: str) -> str:
        # gptimage2 固定尺寸枚举
        if size in ("1024x1024", "1024x1792", "1792x1024"):
            return size
        # pkos-comic 默认尺寸映射
        if "1880" in size or "1240" in size:  # 6 宫或 4 宫 → 用 1024x1792(竖)
            return "1024x1792"
        if "675" in size or "900" in size:  # 16:9 封面或 4:3 → 用 1792x1024(横)
            return "1792x1024"
        return "1024x1024"  # 兜底方
