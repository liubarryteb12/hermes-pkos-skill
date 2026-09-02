# 漫画管线实战经验手册（2026-08-30/31 两期实跑沉淀）

> 来源：RT-20260830-001（收藏≠学会，gptimage2）、小鹿的第一张卡片（4格+6格验证）、RT-20260831-001（番茄工作法，Gemini 全流程发表）。
> 本手册是经验层；操作流程层见 SKILL.md。

## 一、出图通道实测对比（两通道真实数据）

| 维度 | gptimage2 API | Gemini /images（Nano Banana） |
|---|---|---|
| 分辨率 | 1024x1536（竖版上限） | 572x1024（网页 canvas 直读） |
| 中文渲染 | 极稳（图内装饰小字长句也基本全对） | 气泡主文字稳，装饰小字易丢/占位线条化 |
| 角色一致性 | 文字锚定句跨格高度一致 | 同样可靠（锚定句原样复制即可） |
| 单张耗时 | 3-5 分钟 | 约 25 分钟（生成+轮询） |
| 费用 | 按张计费 | 免费（Pro 订阅内） |
| 失败模式 | 524 网关超时→重跑同命令即过 | 发送失败、生成中无超时上限（stop 按钮状态判断） |
| 结论 | 清晰度优先/批量用 | 零成本/单期验证用 |

## 二、通道各自的坑（踩过即记）

### gptimage2
- 524 = 生成超时，重跑同命令即可，重试上限 3 次（第 2 次成功是常态）。
- 长期空转后台任务会被孤儿回收：批量出图用 terminal(background=true, notify=true)，每张落盘后立即确认文件存在。

### Gemini /images（2026-08-31 新版 UI）
- 发送按钮已变：button[aria-label="Send message"] 在 /images 新版不存在；改用 .send-button-container 内的 button（eval 点击）。
- 发送成功信号：div[contenteditable=true].textContent.length 归 0（注入→点击→验证清空，三步缺一不可）。
- 生成中标志：输入框右侧出现黑色方块 stop 按钮；完成标志：stop 消失 + blob 大图计数增长。三点加载动画会转很久（实测 20+ 分钟），不要按旧经验 2-3 分钟判定超时。
- 分辨率固定 572x1024（canvas 直读 blob 的 naturalWidth），无法通过 prompt 提高。
- Chrome 关闭→扩展断桥→open 落 about:blank；cmd //c start chrome 重启后约 20s 重连，然后必须重新 open 目标 URL。
- 上传图片作参考图不可靠，角色一致性只用文字锚定句，不依赖垫图。

## 三、prompt 措辞的实证结论（对照实验）

1. 整图 N 格 vs 逐格：整图 6 格（2列x3排）一次成型，格线/风格/角色由单次推理统一保证，效率与一致性双优；逐格路线只留作单格重抽的补图工具。
2. 版式声明必须放开头：A single tall comic page containing exactly 6 panels arranged in a grid of 2 columns and 3 rows with thin white gutters——Gemini 默认方图倾向，这句是画幅纠正主指令。
3. 五段式分镜（镜头景别→主体事件→表情→道具→氛围）：事件优于状态罗列。Xiao Lu writing at his desk in deep focus 明显优于 Xiao Lu, writing, focused。
4. 媒介锁前置：flat 2D vector illustration 放 prompt 第一句，防滑向写实/3D。
5. 角色统一声明单独成句：The same character appears in every panel: ... 比只在锚定句出现一次更稳。
6. 对白与装饰小字：气泡主文字（≤12字半角标点）是验收底线；图内装饰小字模型会自创，验收时当噪声记录，不当缺陷返工。
7. 拟物角色：具体拟物描述可稳定复现；拟物+主角同框时各自锚定句独立成句。

## 四、发表管线实测（RT-20260831-001 全流程走通）

1. 文案极短化：漫画期正文 5 段短文案（每段 1-3 句），总字数约 400 字——与公众号图文（1500-2200 字）形成差异化。
2. HTML 结构：标题→开场文案段→漫画整图→金句提示块→收尾文案段→END+签名，img 必须 display:block;width:100%;height:auto（消白缝）。
3. 校验：validate_gzh_html.py 过 + audit A 组自查 0 命中（编号只在标题，正文无编号）。
4. 草稿箱：漫画图 upload_permanent_image 拿 media_id（834KB PNG 可传），图 URL 回填 HTML 再 add_draft，回读验证 title/content_len/图域名/digest 四项。
5. 编号规则：草稿标题 02-01-02 · 番茄工作法…（编号进标题）；正文与 digest 无编号（audit A-03 不变）。

## 五、与 Gemini 讨论产出的提示词规范（12 轮，仍有效部分）

- 对白 ≤12 字半角标点；气泡句式固定；正向 prompt 禁 no/without（消除类改肯定短语）。
- 表情安全词库（scratching head/sweat drop/sparkling eyes/closed-eye smile），禁 hysterical/jaw drop。
- prompt 是设计图非命令书：写死版式/角色/对白/画幅/媒介，让渡背景道具与装饰细节。
- 高密度风格词=视觉压缩包（VoxcatAI 实验蒸馏）；角色卡锚定句原样复制禁临场改写。

## 六、系列规划（2026-09-01 用户定稿）

- A 概念粉碎机（打底，3:1）：单概念 6 格叙事节奏=反直觉问题→错误认知→正确机制→生活化类比→一秒记忆点→下期钩子。挂现有母题编号。取材：R临床预测模型（43章）/考公面试题库（95题）/生信知识库/理财16篇/Vibe Hub 术语。
- B 小鹿打工日记（穿插）：连续剧人设漫，真实工作流坑。单开 00-小鹿打工日记。
- 格数铁律：6 格（2列x3排），非特殊要求不出 4 格。
