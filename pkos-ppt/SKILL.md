---
name: pkos-ppt
description: PPT 出口层（v0.2 出图制）：消费路由单，把每页幻灯片与材料用 gptimage2 直接生成投屏演示图片——提示词即版式，统一美学 token，文字极简。图像经 shared/image-api 可配置；不可用时交付提示词清单兜底。触发语：「做成幻灯片」「出个 deck」「演示版」「出图版 PPT」。
---

# 前置契约

与 pkos-html 相同：必须持有合法路由单（`exit: ppt`）。**两出口形态不混装**
（用户 2026-08-23 裁定）：html=中规中矩的阅读网页；ppt=直接出图。
前代 HTML deck 渲染器已 deprecated。

## 职责边界

只做：按路由单把已有内容转成图像提示词并出图、记 manifest。

1. 不做：不改写原意、不新增观点（文案以 polished 素材为准）；
2. 不做：不出网页版 deck、不做放映模式页面（那是被裁定的废弃形态）；
3. 不做：不擅自更换模型或网关配置（铁律：provider 走 manifest 声明）。

# 工序

1. 读路由单 → 从 polished/AN 素材提炼每页「一句话标题 + 画面构思」；
2. 写图像提示词：统一美学 token 写进每条 prompt（如纸墨系=暖纸底色/朱砂点缀/
   大量留白/扁平插画），每图文字 ≤2 处短句防乱码，尺寸横版 1536x1024；
3. 调 shared/image-api（本机实例：`~/.dsh/skills/567-image-generation`，
   `scripts/generate.py --prompt … --size 1536x1024`）逐张生成；
4. 每张记 manifest：`{slide, prompt 原文, provider, size, file}`——可复现；
5. 图片归档 `_PKOS/outputs/<route-id>-deck-images/slide-N-*.png`。

# 兜底

API 不可用时不再产网页替代品：交付完整提示词清单 + 占位说明，网关恢复后按单重放。
宁要无图的完整方案，不要临场编造的替代品。

# 生成前三问（一次问完）

受众 / 风格映射（继承 html 出口主题美学）/ 张数与节奏。
自主轮次走逃生口：答案取自路由单并在 manifest 留痕。

### 实录（2026-08-23，RT-20260823-002）

7 页全经 gptimage2 出图成功（横版），成品见
`_PKOS/outputs/RT-20260823-002-deck-images/`；prompt 原文存于该批调用记录。
