"""
NanoBananaAdapter (v3.2 Phase 3,评审 round-25 通过)

渠道评估:中文约 80% 成功率 → 默认开 chinese_text=true
"""
from typing import List, Dict, Any
from .base import BaseAdapter, PanelPrompt


class NanoBananaAdapter(BaseAdapter):
    def channel_name(self) -> str:
        return "nano-banana"

    def supports_chinese_text(self) -> bool:
        return True

    def build_requests(self, panels: List[PanelPrompt], metadata: Dict) -> List[Dict[str, Any]]:
        chinese = metadata.get("chinese_text", True)
        return [
            {
                "model": "nano-banana-v1",
                "prompt": p.prompt,
                "size": p.output_size,
                "n": 1,
                "response_format": "url",
                "negative_prompt": self._build_negative(chinese),
                "metadata": {
                    "panel_id": p.panel_id,
                    "route_id": metadata.get("route_id"),
                    "chinese_text_enabled": chinese
                }
            }
            for p in panels
        ]

    def _build_negative(self, chinese: bool) -> str:
        if chinese:
            return "garbled characters, broken Chinese strokes, illegible text, misplaced text"
        return "text, speech bubbles, Chinese characters, watermarks, signatures"
