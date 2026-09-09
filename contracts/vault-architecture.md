# 知识库架构规范（vault-architecture:1，2026-09-05 方案 A 定稿）

> 权威落点：用户 vault `D:\obsidian知识库\obsidian知识库` 采用本规范。任何新单元/新脚本涉及 vault 目录结构、type/domain 词表、FM 字段时，以本文件为唯一真相。

## 1. 目录架构（权威）

```
<vault>/
├── 00-知识库首页.md / INDEX.md / 98-知识网络分析.md / 99-内容状态总览.md / 知识体系总览.md   ← 库级导航 MOC（根）
├── 01-考公备考/        题库/（exempt-zone 练习状态机）  笔记/  域 MOC 入内（01-考公备考.md 等）
├── 02-AI与Codex/       使用相关/（7 子域）  agentskill/  agentmcp/  02-AI与Codex.md
├── 03-个人办事/
├── 04-工作流与Skills/  第三方技能文档（exempt-zone）
├── 05-素材与图表/      350种排版图鉴  图片存放/  Excalidraw/
├── 06-书籍笔记/        笔记/  PDF/
├── 07-生信分析/        R临床预测模型/  单细胞基因调控网络/
├── 08-理财投资/
├── 90-归档/            作者/（原 _作者）  悬空wiki索引/  grn调研staging/  research-github/ 杂件
├── Vibe Hub/           独立域（术语词典，不入编号轨）
├── obsidian知识库/     剪藏输入点（第二 INBOX，见规则 3'）
├── _PKOS/              系统地基（永不作为内容域）
└── 账户密码/           敏感区（永不入索引/审计）
```

规则：
1. 编号只留给「域目录」；域 MOC 文件移入域内，库级 MOC 留根。
2. `_` 前缀 = 归档/系统/暂存语义，与编号域分开；顶层不再允许出现 `_作者` 类活动内容目录（归 90-归档/作者）。
3. **禁止出现嵌套库**：vault 内不得存在名为库根名（`obsidian知识库`）的子目录——剪藏工具输出路径若指向 `D:\obsidian知识库\obsidian知识库\obsidian知识库` 即配置错误，X 帖一律收 `02-AI与Codex/使用相关/_X帖子收藏/`。
3'. **`obsidian知识库/`（库根同名子目录）= 剪藏输入点（第二 INBOX），2026-09-05 用户裁定收编**：剪藏工具（浏览器插件等）配置的输出路径 `...\obsidian知识库\obsidian知识库\obsidian知识库\` 持续写入，与其反复手动归位，不如登记为正式输入通道。它与 `_PKOS/INBOX/` 同级：intake 扫描范围 = `_PKOS/INBOX/` + `obsidian知识库/` + 该通道；文件按规则 5 路由归位后，原件移入 `obsidian知识库/_processed/`（与 INBOX 惯例一致）。**工具侧不改配置也成立**——本目录的存在是预期，不是残留。
4. X 帖文件名消歧惯例：`Post by @<user> on X (<tweetid>).md`（推文 ID 后缀，遇撞名必加）。
5. 新内容路由：网页/X 剪藏 → `02-AI与Codex/使用相关/<子域>/`；技能/MCP 文档 → `04-工作流与Skills/`；生信 → `07-生信分析/`；其余按域对号入座；不确定 → 90-归档。

## 2. type 词表（权威，与 validate_entry.py TYPE_VOCAB 一致）

`moc / concept / method / case / clipping / term / tool / person / index`

| type | 适用 |
|---|---|
| `clipping` | 外部剪藏（网页/X 帖）原文 |
| `concept` | 概念/章节/一般笔记（原 note 默认去向） |
| `person` | 人物页（原 `_作者`） |
| `tool` | 工具/技能/MCP 描述 |
| `index` | INDEX*.md 索引入口 |
| `moc` | 总览/首页型导航（含 98/99/知识体系总览） |
| `case` | 案例复盘 |
| `method` | 方法论（自写笔记） |
| `term` | 术语条目 |

**豁免区私有词**（validate 不扫，不入全局词表）：`面试题目/整套真题/待作答/已作答`（考公题库练习状态机）；`题号/题型` 为题库 FM 键。豁免区登记：`_PKOS/exempt-zones.json`（段级路径）。

## 3. domain 规则

- 值必须 slug：`^[a-z0-9][a-z0-9-]*$`，**严禁空格/中文**（`domain: Vibe Hub` 会被解析器截断成 `Vibe` 造成数据损坏）。
- 中文域 slug 映射表（权威）：知识库导航→`kb-nav`、AI使用相关→`ai-usage`、书籍笔记→`book-notes`、R临床预测模型→`rcpm`、单细胞基因调控网络→`scrn`、Vibe(Hub)→`vibe-hub`、_作者→`authors`、_悬空wiki索引→`dangling-wiki`、书籍PDF→`book-pdfs`、图片存放→`images`、理财投资→`invest`、考公笔记→`gongkao-notes`、考公刷题→`gongkao`、03-个人办事→`personal`、05-素材与图表→`assets`、Excalidraw→`excalidraw`、obsidian知识库(嵌套残留)→`legacy-vault`。
- 新增域 slug：优先用英文短词，登记回本表。

## 4. FM 必填/推荐字段

必填：`title` `type` `status` `domain`。
推荐：`description` `tags`（YAML 列表）`created` `updated` `published` `source`（URL 去重主键）`capture-method` `pkos-schema: 1`。

## 5. OKF 对齐（吸收式，非照搬）

借鉴 Google Open Knowledge Format v0.2（GCP/open-knowledge-format SPEC）的元数据设计，**不照搬结构**（OKF 的 index.md/log.md 保留名、开放 type 词表、Attested Computation 与 PKOS 冲突）。

采纳：
- `generated: { by: agent/hermes-pkos-skill, at: <ISO8601 UTC> }`（Agent 产出物必带）
- `verified: { by: human:<id>, at: ... }` / `process:<id>`（人审/机审签名）
- `stale_after: <ISO8601>`（时效件如羊毛/模型动态，3-6 个月）
- `source-id:` / `source-title:`（结构化溯源标量键）
- `status` 折叠映射仅导出时用（raw/analyzed→draft；polished/routed/exported/published→stable），库内永远保留 PKOS 六态。

**⚠️ PKOS 受限 YAML 解析器硬约束（validate_entry.py）**：
- 不支持「列表项内嵌 mapping」（`sources:\n  - id: ...` → FMParseError「意外缩进」）
- 不支持 flow mapping 作值（`{a: b}`）
- 因此 OKF 的 `sources:` 块状写法在 PKOS 条目里**禁用**；结构化溯源用标量键 `source-id` + `source-title`。
- 详见 `contracts/okf-alignment.md`（pkos-okf:1 契约）。

## 6. 双 FM 头修复（历史债，2026-09-05）

症状：文件出现 `---\ntitle: ...\n---\nstatus: ...\ntype: ...\ndomain: ...\n---\n`（两个 FM 块）或 body 以键值行开头。
根因：空 FM 块结构（`---\n---\nfields\n---`）被非状态机感知的重写脚本破坏；实测全库 936 件。
修复算法（状态机合并）：
1. 文件以 `---` 开头，逐行扫描头部；`---` 行前瞻下一非空行——若是键值行则继续收块，否则闭合。
2. 收集所有键值行（含 `- ` 列表项、缩进子键），**后键覆盖前键**（`status: analyzed` 覆盖 `triaged`），`title` 保留第一个。
3. body 从闭合 `---` 之后去前导空行。
4. 顺带修 `domain: <slug> 残留文字` → 取 slug 段。

```python
def is_kv_line(s):
    if re.match(r'^[\w\u4e00-\u9fff-]+:\s*\S?', s): return True
    if re.match(r'^\s*-\s*\S', s): return True
    if re.match(r'^\s+\S+:\s*\S', s): return True
    return False

def rebuild_fm(text):
    if not text.startswith('---'): return text, False
    lines = text.split('\n'); i = 1; fm_lines = []
    while i < len(lines):
        s = lines[i].strip()
        if s == '---':
            j = i + 1
            while j < len(lines) and not lines[j].strip(): j += 1
            if j < len(lines) and is_kv_line(lines[j]): i += 1; continue
            break
        elif is_kv_line(lines[i]): fm_lines.append(lines[i].rstrip()); i += 1
        else: break
    if i >= len(lines): return text, False
    body = '\n'.join(lines[i+1:]).lstrip('\n')
    merged, pos = [], {}
    for l in fm_lines:
        m = re.match(r'^([\w\u4e00-\u9fff-]+):', l)
        if m:
            k = m.group(1)
            if k == 'title' and k in pos: continue
            if k in pos: merged[pos[k]] = l
            else: pos[k] = len(merged); merged.append(l)
        else: merged.append(l)
    new_fm = '\n'.join(merged)
    new_fm = re.sub(r'^domain:\s*([\w-]+)\s+\S.*$', r'domain: \1', new_fm, flags=re.M)
    return f'---\n{new_fm}\n---\n\n{body}', True
```

## 7. 迁移记录与回滚

- FM sidecar 全量备份：`_PKOS/_rollback/okf-align-backup-20260905-210524/fm_sidecar.json`（1108 件，动 FM 前先存同款）
- 目录移动清单：`workspace/research/vault-digest/dir_moves.json`
- 双 FM 清单：`workspace/research/vault-digest/double_fm_list.json`
- **动 FM 前必存 sidecar**（上次教训：重建索引读文件 status，动后比对恢复）；index 是只读投影，永远以文件为准。
