# Agent 07 - Manifest Writer (元数据 manifest.json 写入)

## 职责

把本次生成的全部决策写入 `_PKOS/outputs/<route-id>-comic-script/manifest.json`，作为 v2 契约 C-3 完整性门槛的依据。

## manifest schema（v0 锁死）

```json
{
  "schema": "pkos-comic-script:1",
  "route_id": "RT-YYYYMMDD-NNN",
  "generated_at": "YYYY-MM-DDTHH:MM:SSZ",
  "art_style": "healing | flat_tech | comic_strip | retro_comic",
  "grid": "4-grid | 6-grid | custom",
  "cover": "16:9 | none",
  "chinese_text": true,
  "panels_count": 7,
  "chinese_text_segments": 5,
  "degraded": false,
  "degraded_reason": null,
  "decision_source": "interactive | auto_mode",
  "characters": [
    { "id": "char_01", "name": "小满", "anchor_hash": "sha256:xxx" }
  ],
  "panels": [
    {
      "panel": 1,
      "row": 1,
      "col": 1,
      "shot": "中景(膝盖以上), 背后平视",
      "chinese_text": null,
      "prompt_hash": "sha256:xxx"
    }
  ],
  "integrity": {
    "panel_count_match": true,
    "chinese_text_segments_match": true,
    "character_anchor_consistent": true,
    "art_style_in_vocab": true
  }
}
```

## 完整性自检（v0 锁死）

- `art_style` ∈ 四值词表
- `grid` ∈ {4-grid, 6-grid, custom}
- `cover` ∈ {16:9, none}
- `chinese_text` 是 bool
- `panels_count` = 4 / 6 / (grid==custom 时 N)
- `chinese_text_segments` = 顶部【全篇对白】的段数
- 每个 panel 的 prompt_hash 用 sha256(完整 prompt 字符串) 取前 16 位
- 同一人物的 anchor_hash 跨 panel 一致

## 失败映射

| 自检失败 | 影响 |
|---|---|
| 词表越界 | unavailable |
| panels_count 与分镜表行数不一致 | unavailable |
| chinese_text_segments 与【全篇对白】段数不一致 | unavailable |
| 同一人物跨 panel anchor_hash 不一致 | unavailable（v0 锁死：跨格必须一致）|

## 不做

- 不写脚本正文（脚本主表层写）
- 不出图
- 不修改 RT-* 路由单（只读）
