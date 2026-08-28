"""
BaseAdapter 接口定义（v3.2 Phase 3,评审 round-25 通过）

注:本文件是伪代码/接口定义,prototype 阶段未实跑。
round-26 接入真实 API 时,把 ABC 抽象方法实现完整。
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class PanelPrompt:
    panel_id: int          # 1, 2, 3, ...
    prompt: str            # 完整可粘贴 prompt（从 manifest.prompts/panel-N.txt 读）
    chinese_text: str      # 该 panel 的中文文字（用于校验）
    output_size: str       # "1200x1880" / "1200x1240" / "1200x675"


@dataclass
class AdapterRequest:
    panels: List[PanelPrompt]
    metadata: Dict[str, Any]   # art_style / grid / route_id / chinese_text
    dry_run: bool              # True=只生成请求体不调 API


class BaseAdapter(ABC):
    @abstractmethod
    def build_requests(self, panels: List[PanelPrompt], metadata: Dict) -> List[Dict[str, Any]]:
        """把 panel prompts 转成该渠道的 API 请求体（返回 JSON 列表）"""
        raise NotImplementedError

    @abstractmethod
    def channel_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def supports_chinese_text(self) -> bool:
        raise NotImplementedError
