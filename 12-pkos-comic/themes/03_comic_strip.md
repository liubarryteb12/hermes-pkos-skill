# 03 - comic_strip (职场黑白条漫)

> 来源:用户 spec 第 3.3 节。

## 适用场景
- 职场/段子/反转
- 黑白极简,强对比,报纸漫画感
- 参考词:Dilbert / 纽约客漫画 / 加菲猫

## Prefix (画风 prefix, 整段直接复制)

```text
Modern black-and-white comic strip panel, crisp expressive ink linework, dynamic screentone shading, high contrast, clean newspaper comic style, emotive character expressions and humorous tension. Clean composition, no watermarks, no signatures, no UI elements, no frame border, no color, no photorealistic, no 3D render. Chinese text in clean sans-serif font (Noto Sans CJK / Source Han Sans style), manga-style speech bubbles with white fill and black outline (2-3px), small triangular tail pointing to the speaker.
```

## Prefix (净图模式, chinese_text=false 时)

```text
Modern black-and-white comic strip panel, crisp expressive ink linework, dynamic screentone shading, high contrast, clean newspaper comic style, emotive character expressions and humorous tension. Clean composition, no text, no speech bubbles, no watermarks, no signatures, no UI elements, no frame border, no color, no photorealistic, no 3D render. Pure black-and-white line art only, all text will be added in post-production.
```

净图模式 suffix 强反向词:在原 suffix 后加 `,text,speech bubbles,Chinese characters,Japanese characters,logos,watermarks`。

## Suffix (按画幅)

| 画幅 | Suffix |
|---|---|
| 6 宫整张 | `--ar 29:47 --stylize 120 --no color,photorealistic,3D render,watermark,English text,Arabic text,garbled characters` |
| 4 宫整张 | `--ar 1:1 --stylize 120 --no color,photorealistic,3D render,watermark,English text,Arabic text,garbled characters` |
| 16:9 封面 | `--ar 16:9 --stylize 120 --no color,photorealistic,3D render,watermark,English text,Arabic text,garbled characters` |
| 4:3 横幅 | `--ar 4:3 --stylize 120 --no color,photorealistic,3D render,watermark,English text,Arabic text,garbled characters` |
| 3:4 竖版 | `--ar 3:4 --stylize 120 --no color,photorealistic,3D render,watermark,English text,Arabic text,garbled characters` |

## 渠道替换

- 同 healing
