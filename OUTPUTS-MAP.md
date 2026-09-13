# PKOS 产出物位置总表（权威 v2 — 09-14 迁移后）

> 生成:2026-09-14 · 用途:审核产出时按本表去对应目录找东西。
> **三条铁律(用户裁定)**:① 操作文件(脚本/配置/状态)→ 套件根 `_ops/` ② 产出产品(文章/图/报告)→ `workspace/` 下对应子目录 ③ `workspace` 路径可配置(本机默认 `D:\00.AIagent\hermesagent\workspace`)

---

## 一、两个根 + 一个可配置产出根

| 根 | 本机路径 | 职责 | 进 git? |
|---|---|---|---|
| **知识库 vault** | `D:\obsidian知识库\obsidian知识库` | 知识条目/索引/分析/审计/路由单/handoff | ❌ |
| **操作文件根** | 套件内 `_ops/` | 脚本/配置/状态快照/日志/备份(随套件走) | ❌ |
| **产出总根(output_root)** | `D:\00.AIagent\hermesagent\workspace` | 所有产物:文章/图/报告/PPT/小说/漫画 | ❌ |

路径解析入口: `scripts/pkos_paths.py`(v2,09-14)——所有单元脚本必须经此取路径,禁止硬编码。

---

## 二、按产线找东西(审核时用)

### 公众号文章
| 内容 | 位置 |
|---|---|
| 文章成稿(按母题分目录) | `workspace\gzh\01-...` 到 `09-AI办公室\` |
| 文章索引 | `workspace\gzh\00-文章索引.md` |
| 选题规划 | `workspace\gzh\00-选题规划-*.md` |
| 封面图 | `workspace\gzh-covers-new3\` 或 `workspace\gemini-images\gzh-covers*\` |
| 发表工具(脚本) | `_ops\gzh\_tools\wx_api.py` 等 |
| **出稿终稿**(13/30 单元产物) | `workspace\pkos-exports\article\<route-id>-article\` |

### 漫画
| 内容 | 位置 |
|---|---|
| 漫画原图/对话框 | `workspace\comic\` |
| 角色卡库 | `workspace\comic\characters\` |
| 生成脚本 | `_ops\comic\_tools\gen_6grid_gpt2.py` 等 |

### 套图(32-pkos-suitegen)
| 内容 | 位置 |
|---|---|
| 参考示例图 | `workspace\pkos-imageprompts\examples\` |
| 出图产物 | `workspace\pkos-imageprompts\out\` |
| 题词库(31) | 套件内 `31-pkos-imageprompt\references\prompt-library\` |
| 风格 skill 种子 | 套件内 `32-pkos-suitegen\references\styles\` |

### 其他产线
| 内容 | 位置 |
|---|---|
| PPT/HTML/小说 | `workspace\{ppt,html,novel}\` |
| 评分卡 | `workspace\article-quality-scoring\scorecards\` |
| 研究报告 | `workspace\research\` |
| Gemini 图/视频/对话 | `workspace\gemini-{images,videos,chat}\` |
| 元宝图/对话 | `workspace\yuanbao-{images,chat}\` |
| 圆桌 | `workspace\roundtable-np\` |
| 旧题词镜像 | `workspace\modelscope-prompts\` |

---

## 三、知识库 vault 内部(_PKOS/)

```
_PCOS/
├── INBOX/        收件箱(intake 扫描入口)
├── entries/      已入库条目(按 slug 命名)
├── analysis/     结构化理解产出
├── routes/       路由单(RT-*)
├── outputs/      出口层临时产物(脚本生成)
├── manifests/    路由单 manifest
├── reports/      各类报告
├── audits/       审计 JSON + 趋势
├── fanout/       概念扇出
├── queries/      高价值查询结果
├── _Export/      HTML 出口工作区
└── handoffs/     交接文档
```

---

## 四、迁移日志(09-14)

- **原 `pkos-outputs\`(1046 文件,157MB)拆为两份**:
  - 246 个操作文件 → `_ops\`(gzh 196 / comic 46 / 其他 4)
  - 786 个产出 → `workspace\`(按顶层目录对应:gzh/gemini-images/comic/...)
- **路径系统 v2**: `scripts/pkos_paths.py` 默认 `workspace` 已改为新路径;新增 `get_output_root()` / `get_ops_root()` 访问器
- **gitignore 加 `_ops/`**:操作文件含运营状态快照,不进公开仓库
- **代码引用修复**:`15-pkos-gzhpublish/scripts/upload_weixin_draft.py` 改走 `pkos_paths.get_output_root()`
- **文档同步**:本文档 + SKILL.md 顶部指针 + contracts(如有引用)

---

## 五、新机器/新用户怎么配

`config.json`(schema `pkos-config:1`,由 `00-pkos-init` bootstrap.py 生成):
```json
{
  "schema": "pkos-config:1",
  "vault": "D:/obsidian知识库/obsidian知识库",
  "workspace": "D:/00.AIagent/hermesagent/workspace",
  "inboxes": ["D:/obsidian知识库/obsidian知识库/_PKOS/INBOX"]
}
```
把 `workspace` 改成你的产出根路径即可,无需改代码。
