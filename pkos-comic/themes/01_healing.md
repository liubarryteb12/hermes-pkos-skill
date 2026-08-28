# 01 - healing (日系治愈,默认推荐)

> 来源:用户 spec 第 3.1 节。

## 适用场景
- 治愈/情感/故事
- 公众号读者接受度最高,温暖、生活化、读者零负担
- 参考词:夏目友人帐 / 深夜食堂 / 萤火虫之墓

## Prefix (画风 prefix, 整段直接复制)

```text
A warm, gentle Japanese healing-style manga panel. Soft watercolor-like digital painting with delicate hand-drawn line art in deep brown (3D2E26) instead of pure black. Color palette limited to warm beige (F5EFE6), soft yellow (F4D58D), sakura pink (F5C6C6), mint green (B8D8B8), light gray-blue (B4C7DC), and milk coffee (C8A789). Diffused side-back lighting like late afternoon sun through a window, no harsh highlights, soft feathered edges. Semi-transparent layered color washes, plenty of breathing space, subtle paper grain texture (5-10% noise). Style references: Natsume's Book of Friends, Midnight Diner, Grave of the Fireflies. Clean composition, no watermarks, no signatures, no UI elements, no frame border, no photorealistic, no 3D render. Chinese text in clean sans-serif font (Noto Sans CJK / Source Han Sans style), manga-style speech bubbles with white fill and black outline (2-3px), small triangular tail pointing to the speaker.
```

## Prefix (净图模式, chinese_text=false 时)

> 当 `chinese_text=false` 时,去掉中文字体/气泡声明,改用强反向词锁定"无文字"。

```text
A warm, gentle Japanese healing-style manga panel. Soft watercolor-like digital painting with delicate hand-drawn line art in deep brown (3D2E26) instead of pure black. Color palette limited to warm beige (F5EFE6), soft yellow (F4D58D), sakura pink (F5C6C6), mint green (B8D8B8), light gray-blue (B4C7DC), and milk coffee (C8A789). Diffused side-back lighting like late afternoon sun through a window, no harsh highlights, soft feathered edges. Semi-transparent layered color washes, plenty of breathing space, subtle paper grain texture (5-10% noise). Style references: Natsume's Book of Friends, Midnight Diner, Grave of the Fireflies. Clean composition, no text, no speech bubbles, no watermarks, no signatures, no UI elements, no frame border, no photorealistic, no 3D render. Pure background and characters only, all text will be added in post-production.
```

净图模式 suffix 强反向词:在原 suffix 后加 `,text,speech bubbles,Chinese characters,Japanese characters,logos,watermarks`。

## Suffix (按画幅)

| 画幅 | Suffix |
|---|---|
| 6 宫整张 | `--ar 29:47 --style raw --stylize 200 --no English text,Arabic text,garbled characters,broken Chinese strokes,illegible text,misplaced text` |
| 4 宫整张 | `--ar 1:1 --style raw --stylize 200 --no English text,Arabic text,garbled characters,broken Chinese strokes,illegible text,misplaced text` |
| 16:9 封面 | `--ar 16:9 --style raw --stylize 200 --no English text,Arabic text,garbled characters,broken Chinese strokes,illegible text,misplaced text` |
| 4:3 横幅 | `--ar 4:3 --style raw --stylize 200 --no English text,Arabic text,garbled characters,broken Chinese strokes,illegible text,misplaced text` |
| 3:4 竖版 | `--ar 3:4 --style raw --stylize 200 --no English text,Arabic text,garbled characters,broken Chinese strokes,illegible text,misplaced text` |

## 渠道替换

- **Nano Banana / gptimage2**:直接粘贴
- **可灵/即梦**:把 `--ar` 换成"自定义宽高 1200x1880",`--no` 里的词塞"反向提示词"框
- **通义万相**:把 `--no` 里的词塞"反向提示词"框
- **SD/ComfyUI**:把 `Style references:` 之前的部分作为正向 prompt,`--no` 里的作为负面 prompt
