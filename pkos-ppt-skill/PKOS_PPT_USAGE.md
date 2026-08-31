# pkos-ppt-skill 实操手册（v2.0 原生 PPTX 线）

> 2026-08-31 改版：产物从「每页一张 gptimage2 图片」转为**真·可编辑 PowerPoint**。
> 吸收 ppt-master 设计骨架（design_spec 中间层 + 页型角色 + 字号锚点 + 节奏检查）。

## 快速开始

```bash
cd <套件根>   # C:/Users/18765/AppData/Local/hermes/skills/note-taking/hermes-pkos-skill

# 1. 准备一条 exit=ppt 的路由单（conversion_type ∈ 4 值承接子集）
# 2. 跑 compose.py（比例必问——交互场景先问用户再传 --ratio）
python pkos-ppt-skill/scripts/compose.py --route _PKOS/routes/RT-XXX.yaml --ratio 16:9
```

依赖：`pip install python-pptx`（仅此一项；默认路径零网络）。

## 参数说明

| 参数 | 必填 | 说明 |
|---|---|---|
| `--route` | ✅ | 路由单 YAML 路径（相对或绝对） |
| `--ratio` | ⚠️ | 画布比例：`16:9` / `4:3` / `3:4`；未给且非 `--auto` → ambiguous 决策单 |
| `--slides` | ❌ | 页数；null=按 POL 内容自动（封顶 15） |
| `--auto` | ❌ | 自主轮次：默认 16:9，manifest 留 decision_note |
| `--theme` | ❌ | 强制美学主题（paper-ink/mo-xian/kan-shi/guang-shu/night-desk） |
| `--images` | ❌ | 启用 gptimage2 插图槽位（默认关；需 `PKOS_IMG_API_KEY`） |
| `--out` | ❌ | 输出目录覆盖 |
| `--dry-run` | ❌ | 只输出 design_spec.json，不渲染 |

## 输出结构

```
_PKOS/outputs/<route-id>-deck/
├── <route-id>.pptx        # 原生可编辑演示文稿（文本框/形状/图片）
├── design_spec.json       # 设计规格（deck 唯一事实源，可手改后重渲染）
├── manifest.json          # 可复现记录（sha256 链 + 每页角色/要点/讲稿/插图 provider）
└── illustration-*.png     # 仅 --images 时的插图
```

## 页型角色（deck_spec 确定性分类）

| 角色 | 触发条件 | 版式 |
|---|---|---|
| cover | 固定第 1 页 | 大标题+受众副题+主题色条 |
| bullets | 要点 ≤5 | 标题+两级列表（主点加粗/说明缩进灰） |
| two-column | 要点 ≥6 | 双栏分组 |
| quote | 正文含短引用 | 大引文+竖线锚点 |
| hero-number | 显著数字+短说明 | 居中大数字 |
| image-right | --images 选中的页 | 左文右图（图槽失败画占位框） |
| closing | 固定末页 | 核心结论回显（禁空洞谢谢页） |

规则：单页要点 >5 自动拆页（续页标"（续）"）；连续同版式 ≥3 触发节奏强调；
五维评分卡/R29 实测等质检节不入 deck；EP 编号前缀剥离；「钩子/CTA」映射为「引言/行动建议」。

## 失败三态

| 状态 | 含义 | 处理 |
|---|---|---|
| `not_found` | exit≠ppt / 子集不承接 / status 早于 polished / 源不可达 | 拒绝，返回 rejections |
| `ambiguous` | ratio 未确认且非 auto | 决策单（三选一） |
| `unavailable` | spec 生成失败 / 素材不足 / 渲染或校验门命中 | retry/abort，不出坏产物 |
| `degraded_success` | 仅 --images：deck 完整但插图部分失败 | manifest.degraded=true，prompt 可重放 |
| `success` | 全部就位 | 正常输出 |

## 比例 → 画布/插图尺寸

| 比例 | 画布 | body 锚点 | 插图槽位尺寸（白名单） |
|---|---|---|---|
| 16:9 | 13.33×7.5 in | 18pt | 1536x1024 |
| 4:3 | 10×7.5 in | 17pt | 1536x1024 |
| 3:4 | 7.5×10 in | 15pt | 1024x1536 |

## 美学主题（aesthetics.json v2 双轨）

每主题含 `native`（pptx 渲染 token：色板+中西文字体分工）与 `prompt_tokens`（插图描述，与 html 主题同源）。
纸墨=暖纸底/朱砂条/楷体标题；墨线=深底电蓝；刊式=象牙底金色点缀黑体；光栅=白底蓝橙；夜案=深棕琥珀。

## 精修工作流（spec 手改后重渲染）

```bash
# 1. dry-run 出 spec 或直接改输出目录里的 design_spec.json（改标题/删页/换角色）
# 2. 用 build_pptx 单独重渲染（SKILL.md 实现路径节有一行式命令）
```

## 视觉验收（交付前）

本机装有 PowerPoint 时用 COM 导出逐页 PNG 过一遍（溢出/重叠/字距）：

```python
import win32com.client, os
app = win32com.client.Dispatch("PowerPoint.Application")
pres = app.Presentations.Open(os.path.abspath("<pptx>"), WithWindow=False)
for i, s in enumerate(pres.Slides, 1):
    s.Export(os.path.join("<preview_dir>", f"slide-{i:02d}.png"), "PNG", 1280, 720)
pres.Close()
```

## 环境变量（仅 --images 需要）

| 变量 | 说明 |
|---|---|
| `PKOS_IMG_API_KEY` | gptimage2 密钥 |
| `PKOS_IMG_CONFIG` | image-api config 路径（默认 `pkos-ppt-skill/shared/image-api/config.json`） |

## Agent 集成

```python
import sys; sys.path.insert(0, "pkos-ppt-skill/scripts")
from compose import compose

result = compose(route_path="_PKOS/routes/RT-XXX.yaml", ratio="16:9", with_images=False)
if result["status"] == "success":
    print(f"✅ {result['total_slides']} 页 → {result['pptx']}")
elif result["status"] == "degraded_success":
    print(f"⚠️ deck 完整，{result['images_failed']} 张插图失败（prompt 在 manifest 可重放）")
else:
    print(f"❌ {result['failure_mode']}: {result.get('rejections', result.get('errors'))}")
```
