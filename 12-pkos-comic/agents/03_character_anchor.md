# Agent 03 - Character Anchor (角色特征英文锚定)

## 职责

从 PKOS 顶层人物资产库 `_PKOS/assets/characters/*.md` 读详细人物文件,抽取**不可变英文锚定短语**。该短语在所有分镜中**逐字复用**,保证跨格一致性。

## 资产库路径（v3.2 增量,评审 round-25 通过）

> **决议**:人物详细文件从原 `_system/人物库/` 迁到 PKOS 顶层 `_PKOS/assets/characters/`,作为 PKOS 体系的"人物资产库"。

- **详细文件位置**:`_PKOS/assets/characters/NN_<角色名>.md`
- **本 skill 读路径**:`_PKOS/assets/characters/`
- **详细文件模板**:见该目录的 README.md 与 Agent 03 文件结构段
- **向后兼容**:旧 `_system/人物库/*.md` 仍保留(只读),但**本 skill v1.0+ 仅读新路径**

## 输入

```yaml
character_id: "01_主角_小满"   # 指向 _PKOS/assets/characters/01_主角_小满.md
short_anchor: false              # token 紧张时 = true(取 30-50 词短锚)
```

## 输出（写入"角色锚定描述"段）

```markdown
- **小满 (anchor_hash: sha256:abc123)**: `A 25-year-old Chinese woman, slim build, 163cm. Short auburn-brown bob with outward-curled ends, deep brown almond eyes with drooping eye corners, oval face, fair warm skin, wearing loose cream knit sweater, dark gray trousers, beige loafers. Small thin silver hoop on right ear. Quiet, gentle, with quiet determination.`
```

## 锚定短语规则（v0 锁死）

1. **80-150 词**:含年龄 / 体型身高 / 发型发色 / 瞳色 / 脸型 / 默认服装 / 配饰
2. **逐字不可变**——同人物跨分镜跨脚本复用,**只改动作/表情/光影/构图**,不改外观
3. **英文输出**——出图 prompt 是英文
4. **可缩写为短锚**（token 紧张时）:
   - 详细版(100+ 词):用于特写/独立角色格
   - 短锚版(30-50 词):仅保留年龄+发型+服装+1 个标志性配饰,用于群像/远景/背景格

## 中文变体（v0 锁死）

如果 chinese_text=true 且人物是国产/亚洲脸:
- 显式加 `Chinese`(不要 `Asian`)
- 肤色用 `fair warm-toned skin` / `warm yellow-toned skin`(避免歧义)
- 服装色用具体颜色词(不要 `light blue` 用 `light blue-gray #B4C7DC`)

## sha256 校验(v3.2 增量)

- **详细版 hash**:`sha256(英文外观描述详细版)` → 写 manifest.characters[].anchor_hash
- **短锚版 hash**:`sha256(短锚版字符串)` → 写 manifest.characters[].short_anchor_hash
- **跨 panel 一致性**:同一人物跨 panel 的 anchor_hash 必须一致
- **不一致处理**:`unavailable(ERR_ANCHOR_MISMATCH)`,abort 不交付

## 不做

- 不改名字/不改性格(性格走"潜台词"字段,不在锚定短语里)
- 不写对白/不写动作
- 不决定服装(默认服装 = 通勤常服;变体在分镜表里临时加)
- 不直接读 `_system/人物库/`(v1.0+ 强制走新路径 `_PKOS/assets/characters/`)
- 不自动迁移旧文件(用户手动 cp/copy)
