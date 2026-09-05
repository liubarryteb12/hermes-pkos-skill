# Agent 05 - Prompt Assembler (提示词拼装)

## 职责

把 `画风 prefix + 角色锚定 + 本格场景/动作/光影 + 画风 suffix` 按公式拼成完整可粘贴 prompt。

## 通用公式（v0 锁死）

```text
完整可出图 Prompt =
  [画风 prefix (来自 themes/<art_style>.md)]
  + ", " + [本格出场角色锚定短语 (来自 Agent 03)]
  + ", " + [本格动作/道具/场景环境描述 (来自 Agent 04)]
  + ", " + [光影/构图/景深描述 (来自 Agent 04 的 shot 字段)]
  + " " + [画风 suffix (来自 themes/<art_style>.md, 按画幅改 --ar)]
```

## 中文进图三件套（v0 锁死，chinese_text=true 时）

在公式末尾追加：

```text
+ ", " + [气泡/文字描述] contains clearly printed Chinese text "原文"
+ ", the text \"原文\" should be clearly printed in clean sans-serif Chinese font, no missing strokes"
```

且画风 prefix 已内嵌：`Chinese text in clean sans-serif font (Noto Sans CJK / Source Han Sans style), manga-style speech bubbles with white fill and black outline (2-3px), small triangular tail pointing to the speaker.`

气泡描述词表：

| 气泡类型 | 英文描述 |
|---|---|
| 无气泡 | (不写气泡字段) |
| 白底圆角对白气泡 | `a manga-style speech bubble with white fill and black outline, small triangular tail pointing to [人物名]` |
| 云朵形独白泡 | `a cloud-shaped thought bubble with white fill and black outline, no tail, soft scalloped edge` |
| 画面顶端旁白 | `a small line of Chinese text at the top of the panel, no bubble` |
| 画面底端旁白 | `a small line of Chinese text at the bottom of the panel, no bubble` |
| 招牌/屏幕字 | `a [类型] with Chinese text "原文" clearly printed on it` |

## --ar 按画幅选

| 画幅 | --ar |
|---|---|
| 6 宫整张 | 29:47 |
| 4 宫整张 | 1:1 |
| 16:9 封面 | 16:9 |
| 4:3 横幅 | 4:3 |
| 3:4 竖版 | 3:4 |

## 输出形态

每格是**独立可粘贴**的整段（不是公式分解）。例：

```text
[画风 prefix]
, [角色锚定]
, [本格场景]
, [光影]
, [气泡+中文]
, [冗余声明]
[--ar 29:47 --stylize ... --no ...]
```

## 长度限制（v0 锁死）

- 单格完整 prompt ≤ 600 词（超过 600 模型会丢信息）
- 中文原文 ≤ 12 字/段
- 英文 prompt 80-150 词

## 不做

- 不写中文对白原文（脚本主表层给）
- 不选画风（上游已选）
- 不出图
