# 出图渠道适配器 (v3.2 Phase 3)

> 评审 round-25 通过:在 `scripts/adapters/` 下补出图渠道适配器接口定义 + 两个实现(伪代码/接口)。
> 真实 API 调用留给 round-26 接入(prototype 阶段不跳)。

## 设计原则

- **本 skill 不直接出图**——出图是调用方的事
- **adapter 只做 prompt → 该渠道 API 的格式转换**——把 12-pkos-comic 产出的 prompt 块,转成 Nano Banana / gptimage2 / 可灵 等能直接调用的请求体
- **adapter 不调 API**——只输出请求体给调用方,或由调用方自己用 gptimage2 之类工具跑
- **不锁死渠道**——adapter 是可插拔的(评审要求:不擅自换渠道,但允许添加新 adapter)

## 接口定义 (`adapters/base.py`)

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class PanelPrompt:
    panel_id: int          # 1, 2, 3, ...
    prompt: str            # 完整可粘贴 prompt(从 manifest.prompts/panel-N.txt 读)
    chinese_text: str      # 该 panel 的中文文字(用于校验)
    output_size: str       # "1200x1880" / "1200x1240" / "1200x675" 等

@dataclass
class AdapterRequest:
    panels: List[PanelPrompt]
    metadata: Dict[str, Any]   # art_style / grid / route_id / chinese_text
    dry_run: bool              # True=只生成请求体不调 API

class BaseAdapter(ABC):
    @abstractmethod
    def build_requests(self, panels: List[PanelPrompt], metadata: Dict) -> List[Dict[str, Any]]:
        """把 panel prompts 转成该渠道的 API 请求体(返回 JSON 列表)"""
        raise NotImplementedError

    @abstractmethod
    def channel_name(self) -> str:
        """返回渠道 ID,例如 'nano-banana' / 'gptimage2' / 'kling'"""
        raise NotImplementedError

    @abstractmethod
    def supports_chinese_text(self) -> bool:
        """返回 True/False —— 渠道是否支持中文文字渲染"""
        raise NotImplementedError
```

## Nano Banana Adapter (`adapters/nano_banana.py`)

> 渠道评估:中文约 80% 成功率 → 默认开 chinese_text=true

```python
class NanoBananaAdapter(BaseAdapter):
    def channel_name(self) -> str:
        return "nano-banana"

    def supports_chinese_text(self) -> bool:
        return True   # 默认开

    def build_requests(self, panels, metadata):
        chinese = metadata.get("chinese_text", True)
        return [
            {
                "model": "nano-banana-v1",
                "prompt": p.prompt,
                "size": p.output_size,   # "1200x1880" → 拆为 1200/1880
                "n": 1,                  # 1 出 1(成本最优,失败再单格重出)
                "response_format": "url",
                "negative_prompt": self._build_negative(chinese),
                "metadata": {
                    "panel_id": p.panel_id,
                    "route_id": metadata["route_id"],
                    "chinese_text_enabled": chinese
                }
            }
            for p in panels
        ]

    def _build_negative(self, chinese: bool) -> str:
        if chinese:
            return "garbled characters, broken Chinese strokes, illegible text"
        return "text, speech bubbles, Chinese characters, watermarks"
```

## gptimage2 Adapter (`adapters/gptimage2.py`)

> 渠道评估:中文约 80% 成功率 → 默认开 chinese_text=true(同 Nano Banana)

```python
class GPTImage2Adapter(BaseAdapter):
    def channel_name(self) -> str:
        return "gptimage2"

    def supports_chinese_text(self) -> bool:
        return True

    def build_requests(self, panels, metadata):
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
                    "route_id": metadata["route_id"]
                }
            }
            for p in panels
        ]

    def _map_size(self, size: str) -> str:
        # gptimage2 只接 1024x1024/1024x1792/1792x1024 → 提示错误让人工选
        return "1024x1024"  # 默认方;6 宫 1200x1880 不支持,需调用方手动 clip
```

## Midjourney Adapter(`adapters/midjourney.py`)

> 渠道评估:中文<5% 成功率 → 强制 chinese_text=false

```python
class MidjourneyAdapter(BaseAdapter):
    def channel_name(self) -> str:
        return "midjourney"

    def supports_chinese_text(self) -> bool:
        return False   # v3.2 自动切到净图

    def build_requests(self, panels, metadata):
        # 强制净图
        return [
            {
                "prompt": p.prompt,   # manifest 已用 themes/01-04 净图 prefix
                "ar": self._map_ar(p.output_size),
                "stylize": 200,
                "niji": 6 if metadata["art_style"] == "healing" else None,
                "no": ["text", "speech bubbles", "watermark"]
            }
            for p in panels
        ]
```

## 可灵 / 通义 Adapter(占位)

> v3.2 prototype 阶段仅放接口与 TODO,真实 API 接入 round-26。

```python
# adapters/kling.py    -- TODO: round-26
# adapters/tongyi.py   -- TODO: round-26
# adapters/sd_comfyui.py -- TODO: round-26
```

## 不做(本轮明确不做)

- 不实现任何真实 API 调用(`BaseAdapter` 用 ABC 抽象)
- 不做 prompt 优化/翻译(出图 prompt 已由 12-pkos-comic 拼装好,adapter 只做格式转换)
- 不做 cost tracking / retry(留给 round-26)
- 不写 tests(本轮未实现,等 round-26 实跑)

## 验收

- 4 个 adapter 文件(2 实 + 2 占位)就位
- `adapters/base.py` 接口完整
- channel_name 字符串与 RT-* route_id 元数据可对齐
- supports_chinese_text() 返回值与 v3.2 决策一致(Nano Banana/gptimage2=True, Midjourney=False)
