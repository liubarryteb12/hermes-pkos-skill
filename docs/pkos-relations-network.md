# PKOS 关系网络全景（Relations Network Map）

> **版本**: 1.0 (v3.3) | **date**: 2026-08-28
> **数据来源**: pipeline/registry.json 31 units 的 consumes/produces/depends_on 字段 + round-27 五 skill 联通实测
> **用途**: 一张文档看全 PKOS 的单元分层、依赖边、产物流向、治理横切面与外部边界
> **姊妹文档**: `contracts/skill-dispatch-catalog.md`（出口层能力卡片，router 阅读版）· `contracts/external-capability-boundary.md`（内外边界）

---

## 1. 分层主轴（stage 0→9 数据流）

```
stage 0   收集                stage 5   内容出口（四槽位）
   intake.scan ──┐                    exit.html.render    单文件HTML
   gptimage2use* │                    exit.ppt.compose    逐页出图PPT
                 ▼                    exit.comic.compose  漫画分镜+格prompt
stage 1   抽取                 exit.gzhxiaoshuo     小说三层结构
   ingest.extract
                 │                    (*gptimage2use 是 utility，常驻被出口调用)
                 ▼
stage 2   理解                stage 6   裁决与验证
   analysis.structure ──► POL            knowledge_service.commit（唯一写入口, D-6）
   intake.query（检索）          weak_check.verify（独立弱审, ≥0.9）
                 │
                 ▼                    stage 7   维护
stage 3   净化                   maintenance.index（MASTER_INDEX）
   polish.refine ──► DerivedDraft        maintenance.fanout.concept（概念展开）
                 │                      maintenance.timeline（健康趋势）
                 ▼
stage 4   决策                stage 8   治理
   router.decide ──► RT-*.yaml           governance.bootstrap（初始化）
                 │                      governance.audit（全库体检）
                 ▼                      governance.tick（心跳巡检, v3.3）
stage 5→6  出口消费（见上）
                                      stage 9   深度维护
                                         audit.lint（lint 修复）
```

**主数据流一句话**：intake 分拣 → ingest 抽取 → analysis 理解（产 POL）→ polish 净化（产 DerivedDraft）→ weak_check 放行 → router 决策（产 RT）→ 四出口之一产出 ExportArtifact → 全程 telemetry 记录。

## 2. 依赖边明细（registry depends_on 实测，共 16 条）

| 依赖方 → 被依赖方 | 边的含义 |
|---|---|
| ingest.extract → intake.scan | 抽取消费分拣单 |
| analysis.structure → ingest.extract | 理解消费已抽取条目 |
| analysis.structure → maintenance.index | 需要 MASTER_INDEX 做关联推荐 |
| polish.refine → analysis.structure | 净化消费发现表（AN-*） |
| router.decide → polish.refine | 决策消费 POL-*（status=polished） |
| router.decide → governance.bootstrap | 需要 config.json 的 modules.enabled |
| **四出口 → router.decide** | 消费 RT-*.yaml（by_route_artifact） |
| **四出口 → polish.refine** | 消费 POL 源内容 |
| exit.ppt → exit.html.render | 主题映射复用（paper-ink 等同源主题） |
| exit.gzhxiaoshuo → weak_check.verify | 三层结构出厂前过弱审 |
| weak_check → polish.refine / router.decide | 输入 = DerivedDraft + RT 上下文 |
| intake.query → maintenance.index / fanout / intake.scan | 检索聚合三方 |
| maintenance.index → bootstrap / commit | 索引基于地基与提交易 |
| fanout.concept → maintenance.index | 概念展开需要索引 |
| maintenance.timeline → governance.audit | 趋势页消费审计报告 |
| audit.lint → maintenance.index / commit | lint 基于索引定位 + 原子写 |
| governance.tick → audit.lint | 心跳巡检内嵌增量 lint |

**入度最高的三个枢纽**：`polish.refine`（被 router/四出口/weak_check 共 6 处依赖）、`router.decide`（被四出口+weak_check 依赖）、`maintenance.index`（被 analysis/query/fanout/lint 依赖）——**这三个是关系网的承重墙，改动需全量回归**。

## 3. 产物 → 消费者矩阵（谁产什么、谁吃）

| 产物 | 生产者 | 消费者 | 物理位置 |
|---|---|---|---|
| 分拣单 *-intake.json | intake.scan | ingest.extract | _PKOS/manifests/ |
| 合规条目（status=raw） | ingest.extract | commit（入库 vault） | vault entries/ |
| 发现表 AN-* | analysis.structure | polish.refine | _PKOS/analysis/ |
| 净化稿 POL-*（status=polished） | polish.refine | router / 四出口 | _PKOS/analysis/ |
| DerivedDraft | polish.refine | weak_check / 出口 | 内存→_drafts(24h TTL) |
| 路由单 RT-*.yaml | router.decide | 四出口 | _PKOS/routes/ |
| 弱审报告 {pass,score} | weak_check.verify | router 策略 / 出口闸门 | stdout + telemetry |
| ambiguous-*.yaml | weak_check（降级时） | **人工裁决** → tick 清点 | _PKOS/_quarantine/(30d) |
| 单文件 HTML | exit.html.render | 用户/公众号 | _PKOS/_Export/html/ |
| slide prompt JSON → PNG | exit.ppt.compose → gptimage2use | 用户演示 | outputs/<RT>-deck-images/ |
| comic 脚本+格prompt+manifest → PNG | exit.comic.compose → gptimage2use | 公众号漫画 | outputs/<RT>-comic-script/ |
| chapter.json + 正文.md + slice | exit.gzhxiaoshuo | 用户 / comic·video 复用 slice | _Export/gzhxiaoshuo/ |
| gen-<hash>.png + manifest | gptimage2use | 调用方出口 | outputs/image/ 或指定目录 |
| MASTER_INDEX.md/json | maintenance.index | analysis/query/人 | _PKOS/ |
| 审计报告 audit.{md,json} | governance.audit | timeline / 人 | _PKOS/reports/ |
| lint 报告 | audit.lint | tick 巡检 / 人 | _PKOS/reports/lint/ |
| 提交记录 commits/*.json | knowledge_service.commit | index / 审计 | _PKOS/reports/commits/ |
| telemetry.jsonl | **全单元经 lib.emit 单写者** | telemetry_dashboard / tick | _PKOS/execution/ |

## 4. 类型状态机（横向约束，贯穿所有数据流）

```
RawEntry ──commit──► FactCore ──analysis/polish──► DerivedDraft ──出口──► ExportArtifact
(可变)              (SHA256锚定,只读)              (EPHEMERAL,           (白名单,
                                                    24h/30d TTL)         不可逆)
                        ▲                                                    │
                        └──────────── 严禁逆流（B1 铁律）────────────────────┘
```

- 每个箭头都有物理守卫：commit 门（D-6 单点）、SHA256 断言（assert_unchanged, exit 5）、类型守卫（assert_typed, exit 2）、双重白名单（assert_safe_out, exit 4）
- 失败传播链：弱审不过×2 → raw_fallback（.fallback.md）→ _quarantine 决策单 → **governance.tick 30d 清点 → 人工裁决**（闭环）

## 5. Provider 依赖表

| Provider | 服务对象 | 用途 | 凭证 |
|---|---|---|---|
| hy3（hunyuan-direct, 47.108.25.114:1519/v1） | intake.query / fanout.concept / 各出口 LLM 轮 | 对话推理（含 reasoning_content） | HUNYUAN_API_KEY（.env） |
| gpt-image-2（同网关 /images/generations） | gptimage2use → ppt/comic 出图 | 图像生成 | PKOS_IMG_API_KEY（.env, **与聊天 key 不同分组**） |
| filesystem / atomic_writer / yaml_writer | commit / lint / comic 等 | 本地 IO 原子性 | — |
| self-degrade | intake.query / fanout | LLM 不可达时降级路径 | — |

⚠️ **registry 陈旧登记**：`exit.ppt.compose.depends_on_providers` 仍写 `image-api:567-image-generation`（v2.8 时代）——实测出图通道是 gptimage2use（gpt-image-2）。下轮 registry 修订时更正为 `gptimage2-image`。

## 6. 治理与观测横切面（不产内容，约束内容）

| 横切机制 | 覆盖范围 | 物理执行点 |
|---|---|---|
| EventBus 单写者 | 全部 31 单元 | pkos_v31_lib.emit() → telemetry.jsonl（schema_version 1.0） |
| MAX_RETRY=2 | 全部 LLM/出图/写入重试 | pkos_v31_lib 常量 |
| 双重白名单 | 全部落盘 | render.assert_safe_out + lib（ADS 冒号/大小写归一化） |
| DerivedDraft TTL | _drafts 24h / _quarantine 30d | lib 常量 + tick.py 清点 |
| vault 零写入 | 除 commit/index/审计报告外全部 | render_layer_safety 8 向量 + tick |
| PITFALLS 前置读取 | 一切代码修改 | docs/PITFALLS.md（Hook 1） |

## 7. 双重身份与外部边界（网络的外沿）

- **v0 兼容层**（pkos-init/-intake/-ingest/-analysis/-polish/-router/-comic/-html/-audit/-timeline 等 8+ 个）：deprecated 入口，仅映射到 v2 capability_id，新会话一律用 v2/v3 名
- **外部辅助**（不占网络节点）：gzh-design（排版美化）、khazix-writer（长文写作）、567-image-generation（出图 API 封装，其 config 明文 key 待清）、素材目录（微信公众号文章生成等）——**可读 PKOS 产物，无写权限，契约输入不得来自它们**

## 8. 一屏总结

```
                 ┌────────── 治理横切面：EventBus / MAX_RETRY / 白名单 / TTL / PITFALLS ──────────┐
                 │                                                                               │
外部输入 → intake → ingest → [commit] ⇒ FactCore ⇒ analysis ⇒ polish ⇒ weak_check ⇒ router ⇒ {html|ppt|comic|novel}
                                        （D-6 唯一写入）                    （10/24 矩阵）      │
                                                                                                 ▼
             maintenance(index/fanout/timeline) + governance(tick/audit/lint) ← 全程观测    ExportArtifact
                                                                                                 
             provider: hy3(聊天) · gpt-image-2(出图) ；外部：gzh-design/khazix-writer（只读外沿）
```

**承重墙（改动需全量回归）**：polish.refine · router.decide · maintenance.index · knowledge_service.commit · pkos_v31_lib
