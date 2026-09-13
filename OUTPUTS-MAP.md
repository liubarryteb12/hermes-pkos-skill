# PKOS 产出物位置总表（权威）

> 生成：2026-09-13 · 来源：实地扫描各单元 SKILL.md 声明 + 磁盘实际内容 + `scripts/pkos_paths.py` 解析
> 用途：你要审核产出时，按本表去对应目录找东西。

---

## 一、三个根（先记这个）

| 根 | 路径 | 装什么 |
|---|---|---|
| **知识库 vault** | `D:\obsidian知识库\obsidian知识库` | 知识条目、索引、分析、审计、路由单、handoff |
| **主 workspace** | `D:\00.AIagent\hermesagent\pkos-outputs` | 公众号、漫画、Gemini 出图/出视频、圆桌 |
| **副 workspace** | `D:\00.AIagent\hermesagent\workspace` | 文章出稿、题词库、PPT/HTML/小说、研究报告 |

⚠️ **注意：workspace 有两个，内容不重叠**（历史原因分叉，见文末）。

---

## 二、按产线找东西（你要审核时主要看这里）

### 公众号文章
| 内容 | 位置 |
|---|---|
| 文章成稿（按母题分目录） | `pkos-outputs\gzh\01-...` 到 `09-AI办公室\` |
| 文章索引 | `pkos-outputs\gzh\00-文章索引.md` |
| 选题规划 | `pkos-outputs\gzh\00-选题规划-母题总表.md` 等 |
| 封面图 | `pkos-outputs\gemini-images\gzh-covers*\` |
| 发表工具 | `pkos-outputs\gzh\_tools\`（wx_api.py 等） |
| **出稿终稿**（13/30 单元产物） | `workspace\pkos-exports\article\<route-id>-article\` |

### 漫画
| 内容 | 位置 |
|---|---|
| 漫画产物（分镜+图） | `pkos-outputs\comic\` |
| 角色卡库 | `pkos-outputs\comic\characters\角色卡库.md` |
| 出图脚本 | `pkos-outputs\comic\_tools\` |
| 出图结果 | `pkos-outputs\comic\images\`、`images-gemini\`、`images-gpt2\` |

### 题词库 / 套图（31、32 单元）
| 内容 | 位置 |
|---|---|
| **题词库（发布镜像）** | 套件内 `31-pkos-imageprompt\references\prompt-library\` |
| **题词库（编辑场）** | `workspace\modelscope-prompts\` |
| 套图示例图 | `workspace\pkos-imageprompts\examples\` |
| 套图出图结果 | `workspace\pkos-imageprompts\out\` |
| 32 套图剧本 | 套件内 `32-pkos-suitegen\references\scripts\` |
| 32 风格 skill 集 | 套件内 `32-pkos-suitegen\references\styles\` |

### Gemini / 出图通道
| 内容 | 位置 |
|---|---|
| Gemini 对话记录 | `pkos-outputs\gemini-chat\` |
| Gemini 出图 | `pkos-outputs\gemini-images\` |
| Gemini 视频 | `pkos-outputs\gemini-videos\` |
| 元宝出图 | `pkos-outputs\yuanbao-images\` |
| ModelScope 出图 | `workspace\ms-images\` |

### PPT / HTML / 小说
| 内容 | 位置 |
|---|---|
| PPT 产物 | `workspace\ppt\<route-id>\` |
| HTML 产物 | `workspace\html\` |
| 小说产物 | `workspace\novel\` |

### 评分 / 研究
| 内容 | 位置 |
|---|---|
| 文章评分卡 | `workspace\article-quality-scoring\scorecards\` |
| 研究报告 | `workspace\research\` |
| 综合报告 | `workspace\report\` |

### 圆桌（三方 AI）
| 内容 | 位置 |
|---|---|
| 圆桌全部 | `pkos-outputs\roundtable-np\{briefs,replies,artifacts,verification}\` |

---

## 三、知识库内部（vault 的 _PKOS）

| 目录 | 装什么 |
|---|---|
| `_PKOS\INBOX\` | 收件箱（待分拣） |
| `_PKOS\entries\` | 入库的知识条目 |
| `_PKOS\analysis\` | 分析产物 AN-*、润色 POL-*、trend-digest |
| `_PKOS\routes\` | 路由单 RT-*.yaml |
| `_PKOS\outputs\` | 出口产物（html/deck/comic-script/image） |
| `_PKOS\manifests\` | 各单元运行清单 |
| `_PKOS\reports\` | 审计/体检/lint 报告（445 文件） |
| `_PKOS\handoffs\` | 会话交接单 |
| `_PKOS\_Export\` | 出口中转（终稿已移到 workspace） |

---

## 四、怎么校验一个产出该在哪

```bash
# 路径系统实际解析
cd <套件根>
python -c "import sys; sys.path.insert(0,'scripts'); import pkos_paths as p; print(p.get_vault(), p.get_workspace(), p.get_inboxes())"
```

当前实际解析：
- vault = `D:\obsidian知识库\obsidian知识库`
- workspace = `D:\00.AIagent\hermesagent\pkos-outputs` ← **注意是这个**
- inboxes = `<vault>\_PKOS\INBOX`

---

## 五、已知问题：workspace 双份分叉

| | `pkos-outputs`（路径系统指向） | `workspace`（副） |
|---|---|---|
| 谁在用 | 12-comic / 24-gemini / 26-video / 圆桌 / 公众号 gzh | 13-wenzhang / 30-scorecard / 31-imageprompt（SKILL.md 硬编码路径） |
| 内容 | 公众号 622、漫画 113、Gemini 图 192 等 | 文章出稿 36、题词库 25、PPT/HTML/小说/研究 |
| 最新活动 | 2026-09-13 | 2026-09-13 |

**根因**：部分单元 SKILL.md 里硬编码了 `workspace\...`，而 `pkos_paths.py` 解析出的是 `pkos-outputs`。两套并存 → 产出分散。

**处置建议**（待你拍板）：
- A）统一到 `pkos-outputs`：改 13/30/31 的硬编码路径 + 迁移现有文件
- B）统一到 `workspace`：改 `pkos_paths.py` 默认值 + 迁移
- C）保持双份，在本表登记"哪类产物去哪边"（零迁移，但永久两套）

---

**本表位置**：`<套件根>\OUTPUTS-MAP.md`
