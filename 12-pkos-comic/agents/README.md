# Agents / 调度说明

> 本目录放 comic skill 的**子 agent 调度说明**，对应 SKILL.md 工序 1-9。
> 每个 agent 是一个**职责清晰、可独立调起**的处理单元。

## 目录

| 文件 | 工序 | 职责 |
|---|---|---|
| `01_intake_validator.md` | 工序 1 | 校验 RT-* + POL-* 前置契约 |
| `02_clarification.md` | 工序 2 | 生成前必问（画风/宫格/封面/人物/大纲） |
| `03_character_anchor.md` | 工序 3 | 角色特征英文锚定（不可变英文短语） |
| `04_storyboard_layout.md` | 工序 4 | 叙事节奏 + 镜头语言（4 宫/6 宫排布） |
| `05_prompt_assembler.md` | 工序 5 | 提示词拼装（prefix + 锚定 + 场景 + 光影 + suffix） |
| `06_chinese_text_mode.md` | 工序 6 | 中文进图三件套（prefix 追加 + 文中文字 + 冗余声明） |
| `07_manifest_writer.md` | 工序 7 | 元数据 manifest.json 写入 |
| `08_artifact_persister.md` | 工序 8 | 归档 _PKOS/outputs/<route-id>-comic-script/ |
| `09_publish_guide.md` | 工序 9 | 拼图与发布指引（含中文失败兜底） |

## 共同不变量

- **A4 公理**：所有 agent 都是无状态能力封装，不成为事实所有者；不修改源 POL-*
- **D-1 公理**：所有 agent 不产生新 truth；只做"已 polished 内容的视觉重排"
- **v0 铁律**：4 套画风不混装 / 4 宫 vs 6 宫二选一 / chinese_text 默认开 / 不擅自换画风不擅自换渠道
