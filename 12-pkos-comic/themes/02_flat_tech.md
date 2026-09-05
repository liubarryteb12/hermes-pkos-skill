# 02 - flat_tech (极简扁平科技)

> 来源:用户 spec 第 3.2 节。

## 适用场景
- 科普/清单/技术
- 干净利落,扁平时尚
- 参考词:Noun Project / Dribbble 扁平 / NYT opinion illustration

## Prefix (画风 prefix, 整段直接复制)

```text
Minimalist modern tech vector illustration, clean bold flat lines, 2D flat composition, high contrast, vibrant blue and slate gray palette with cyan accents, sleek UI elements, Dribbble trending vector artwork. Clean composition, no watermarks, no signatures, no UI elements, no frame border, no photorealistic, no 3D render, no gradients. Chinese text in clean sans-serif font (Noto Sans CJK / Source Han Sans style), no speech bubbles (or simple white rectangular callouts with thin black outline if dialogue).
```

## Prefix (净图模式, chinese_text=false 时)

```text
Minimalist modern tech vector illustration, clean bold flat lines, 2D flat composition, high contrast, vibrant blue and slate gray palette with cyan accents, sleek UI elements, Dribbble trending vector artwork. Clean composition, no text, no speech bubbles, no watermarks, no signatures, no UI elements, no frame border, no photorealistic, no 3D render, no gradients. Pure background and shapes only, all text will be added in post-production.
```

净图模式 suffix 强反向词:在原 suffix 后加 `,text,speech bubbles,Chinese characters,Japanese characters,logos,watermarks`。

## Suffix (按画幅)

| 画幅 | Suffix |
|---|---|
| 6 宫整张 | `--ar 29:47 --stylize 150 --no photorealistic,3D render,gradients,watermark,English text,Arabic text,garbled characters` |
| 4 宫整张 | `--ar 1:1 --stylize 150 --no photorealistic,3D render,gradients,watermark,English text,Arabic text,garbled characters` |
| 16:9 封面 | `--ar 16:9 --stylize 150 --no photorealistic,3D render,gradients,watermark,English text,Arabic text,garbled characters` |
| 4:3 横幅 | `--ar 4:3 --stylize 150 --no photorealistic,3D render,gradients,watermark,English text,Arabic text,garbled characters` |
| 3:4 竖版 | `--ar 3:4 --stylize 150 --no photorealistic,3D render,gradients,watermark,English text,Arabic text,garbled characters` |

## 渠道替换

- 同 healing
