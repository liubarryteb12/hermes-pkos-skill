# 04 - retro_comic (复古美漫)

> 来源:用户 spec 第 3.4 节。

## 适用场景
- 复古/动作/怀旧
- Pop art + halftone 网点
- 参考词:Roy Lichtenstein / 60s Marvel / 80s DC

## Prefix (画风 prefix, 整段直接复制)

```text
Retro vintage American comic book panel, Pop art aesthetic, halftone Ben-Day dots texture, dramatic chiaroscuro lighting, dynamic cinematic action angles, muted 80s print color palette. Clean composition, no watermarks, no signatures, no UI elements, no frame border, no photorealistic, no 3D render. Chinese text in clean sans-serif font (Noto Sans CJK / Source Han Sans style), manga-style speech bubbles with white fill and black outline (2-3px), small triangular tail pointing to the speaker.
```

## Prefix (净图模式, chinese_text=false 时)

```text
Retro vintage American comic book panel, Pop art aesthetic, halftone Ben-Day dots texture, dramatic chiaroscuro lighting, dynamic cinematic action angles, muted 80s print color palette. Clean composition, no text, no speech bubbles, no watermarks, no signatures, no UI elements, no frame border, no photorealistic, no 3D render. Pure halftone art only, all text will be added in post-production.
```

净图模式 suffix 强反向词:在原 suffix 后加 `,text,speech bubbles,Chinese characters,Japanese characters,logos,watermarks`。

## Suffix (按画幅)

| 画幅 | Suffix |
|---|---|
| 6 宫整张 | `--ar 29:47 --stylize 220 --no photorealistic,3D render,watermark,English text,Arabic text,garbled characters` |
| 4 宫整张 | `--ar 1:1 --stylize 220 --no photorealistic,3D render,watermark,English text,Arabic text,garbled characters` |
| 16:9 封面 | `--ar 16:9 --stylize 220 --no photorealistic,3D render,watermark,English text,Arabic text,garbled characters` |
| 4:3 横幅 | `--ar 4:3 --stylize 220 --no photorealistic,3D render,watermark,English text,Arabic text,garbled characters` |
| 3:4 竖版 | `--ar 3:4 --stylize 220 --no photorealistic,3D render,watermark,English text,Arabic text,garbled characters` |

## 渠道替换

- 同 healing
