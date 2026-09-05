# 27-pkos-gptimage2use — gptimage2 图片生成器

调用 gpt-image-2 模型进行图片生成的原子 skill。

## 定位

- **不是**出口层（不做 PPT/漫画/网页）
- **是**工具层（被其他 skill 或用户直接调用）
- 只负责：提示词进 → PNG 出

## 目录结构

```
27-pkos-gptimage2use/
├── SKILL.md                      # 主文档（v2 契约）
├── README.md                     # 本文件
├── agents/
│   └── interface.yaml            # 展示配置 + 触发语
├── scripts/
│   └── generate.py               # CLI + 库函数双入口
└── shared/
    └── image-api/
        ├── client.py             # image-api 客户端（独立副本）
        └── config.json           # 网关配置（无明文密钥）
```

## 快速开始

```bash
# 设置环境变量（只需一次）
export PKOS_IMG_API_KEY="your-api-key-here"

# 基本用法
python scripts/generate.py --prompt "一只橘猫坐在樱花树下，吉卜力风格"

# 指定尺寸
python scripts/generate.py --prompt "..." --size 1792x1024

# 调试（不真正调用 API）
python scripts/generate.py --prompt "..." --dry-run
```

## 尺寸参考

| 需求 | 推荐尺寸 |
|---|---|
| 正方形（头像/图标） | `1024x1024` |
| 竖版（手机壁纸） | `1024x1792` |
| 横版（封面/桌面） | `1792x1024` |
| 自定义 | `<W>x<H>`（如 `1536x864`） |

## 失败处理

| HTTP 状态 | 处理策略 |
|---|---|
| 401 | 不重试，报告凭证问题 |
| 429 | 退避重试 ≤3 次 |
| 5xx | 重试一次 |
| timeout | 不重试，走兜底 |

API 不可用时交付 manifest（含 prompt 原文），可重放。

## 依赖

- Python 3.10+
- `PKOS_IMG_API_KEY` 环境变量
- `11-pkos-ppt-skill/shared/image-api/client.py`（复用）

## 注册清单

- [x] SKILL.md frontmatter `name` = `27-pkos-gptimage2use`
- [x] manifest.json 含版本/所有者
- [x] agents/interface.yaml 含展示名与触发语
- [ ] pipeline/registry.json 登记（需主项目维护）
