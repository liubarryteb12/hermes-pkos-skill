# pkos-ppt-skill 实操手册

## 快速开始

```bash
# 1. 确保 config.json 已配置（复制 config.example.json → config.json，设置 PKOS_IMG_API_KEY 环境变量）
# 2. 准备一条 exit=ppt 的路由单
# 3. 运行 compose.py

python scripts/compose.py --route _PKOS/routes/RT-XXX.yaml --ratio 16:9
```

## 参数说明

| 参数 | 必填 | 说明 |
|---|---|---|
| `--route` | ✅ | 路由单 YAML 路径（相对或绝对） |
| `--ratio` | ❌ | 生图比例：`16:9` / `4:3` / `3:4`；`auto` 模式下可省略 |
| `--slides` | ❌ | 幻灯片数量；null=从 POL 内容自动决定 |
| `--auto` | ❌ | 自主轮次标志；答案取自路由单，不经用户交互 |
| `--theme` | ❌ | 强制指定美学主题（覆盖路由单推断） |
| `--dry-run` | ❌ | 只输出提示词清单，不调 API |

## 比例三选一（v0 锁死铁律）

未指定 `--ratio` 且非 `--auto` 时，脚本会抛出 `RatioRequiredError`，需用户明确选择：

- **16:9** → 1536x1024（推荐，投屏最通用）
- **4:3** → 1536x1024（网关无精确 4:3，用最近横版近似）
- **3:4** → 1024x1536（竖版）

`--auto` 模式下默认 16:9，manifest 中留 `decision_note` 记录决策来源。

## 输出结构

```
_PKOS/outputs/<route-id>-deck-images/
├── slide-01-xxxxxxxx.png   # 每张图
├── slide-02-xxxxxxxx.png
├── ...
├── manifest.json           # 完整可复现记录（prompt/provider/size/ratio/file/hash）
└── README.md               # degraded_success 模式下的占位说明 + prompt 清单
```

## 失败三态

| 状态 | 含义 | 处理 |
|---|---|---|
| `not_found` | 路由单 exit≠ppt / conversion_type 不承接 / 源不可达 | 拒绝执行，返回 rejection 清单 |
| `ambiguous` | ratio=null 且 auto_mode=false | 抛出决策单，需用户交互 |
| `unavailable` | API 全部失败 + prompt 未生成 | retry/abort，返回错误详情 |
| `degraded_success` | API 部分失败或全失败但 prompt 已生成 | manifest.degraded=true，写 README.md 兜底 |
| `success` | 全部出图成功 | 正常输出 |

## 美学主题映射

| html 主题 | ppt 生图风格 |
|---|---|
| paper-ink（纸墨） | 暖纸底色/朱砂点缀/大量留白/扁平插画 |
| mo-xian（墨线） | 深色背景/电蓝线条/高对比信息图 |
| kan-shi（刊式） | 象牙白杂志封面/粗黑标题/高端印刷气质 |
| guang-shu（光栅） | 白底蓝线/橙点列表/明快技术博客风 |
| night-desk（夜案） | 深棕暗调/琥珀锚点/深夜书桌氛围 |

## 常见场景

### 场景 1：手动触发（交互式）
```bash
python scripts/compose.py --route _PKOS/routes/RT-20260827-XXX.yaml
# → 脚本会询问比例选择
```

### 场景 2：自主轮次（定时任务 / agent loop）
```bash
python scripts/compose.py --route _PKOS/routes/RT-20260827-XXX.yaml --auto
# → 自动 16:9，不经用户交互
```

### 场景 3：调试提示词
```bash
python scripts/compose.py --route _PKOS/routes/RT-20260827-XXX.yaml --ratio 16:9 --dry-run
# → 只输出提示词 JSON，不生成图片
```

### 场景 4：指定主题
```bash
python scripts/compose.py --route _PKOS/routes/RT-20260827-XXX.yaml --ratio 3:4 --theme mo-xian
```

## 环境变量

| 变量 | 说明 |
|---|---|
| `PKOS_IMG_API_KEY` | 图像 API 密钥（替代 config.json 中的 auth_env） |
| `PKOS_IMG_CONFIG` | config.json 路径（默认 `shared/image-api/config.json`） |

## 集成到 Agent 工作流

```python
from pkos_ppt.scripts.compose import compose

result = compose(
    route_path="_PKOS/routes/RT-20260827-XXX.yaml",
    ratio="16:9",
    auto_mode=True,
)
if result["status"] == "success":
    print(f"✅ {result['generated']}/{result['total_slides']} 张出图成功")
    print(f"📁 输出目录: {result['output_dir']}")
elif result["status"] == "degraded_success":
    print(f"⚠️ {result['generated']}/{result['total_slides']} 张成功，{result['failed']} 张失败")
    print(f"📋 提示词清单见: {result['output_dir']}/README.md")
else:
    print(f"❌ {result['failure_mode']}: {result.get('rejections', result.get('errors'))}")
```
