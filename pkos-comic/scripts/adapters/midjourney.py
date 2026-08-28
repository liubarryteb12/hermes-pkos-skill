"""
MidjourneyAdapter (v3.2 Phase 3,评审 round-25 通过)

渠道评估:中文 < 5% 成功率 → 强制 chinese_text=false(净图模式)
"""
from typing import List, Dict, Any
from .base import BaseAdapter, PanelPrompt


class MidjourneyAdapter(BaseAdapter):
    def channel_name(self) -> str:
        return "midjourney"

    def supports_chinese_text(self) -> bool:
        return False   # v3.2 自动切到净图

    def build_requests(self, panels: List[PanelPrompt], metadata: Dict) -> List[Dict[str, Any]]:
        return [
            {
                "prompt": p.prompt,   # manifest 已用 themes/01-04 净图 prefix
                "ar": self._map_ar(p.output_size),
                "stylize": 200,
                "niji": 6 if metadata.get("art_style") == "healing" else None,
                "no": ["text", "speech bubbles", "watermark", "Chinese characters"],
                "metadata": {
                    "panel_id": p.panel_id,
                    "route_id": metadata.get("route_id"),
                    "force_chinese_text_false": True
                }
            }
            for p in panels
        ]

    def _map_ar(self, size: str) -> str:
        if "1880" in size:
            return "29:47"
        if "1240" in size:
            return "1:1"
        if "675" in size:
            return "16:9"
        if "900" in size:
            return "4:3"
        if "1200" in size and "1200" in size.split("x")[1]:
            return "3:4"
        return "1:1"
