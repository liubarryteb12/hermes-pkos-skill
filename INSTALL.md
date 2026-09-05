# 安装说明 · hermes-pkos-skill v4.9.21

> 五岁小孩版：把玩具箱搬回家，插上电，问它一句话，它就开始干活。

## 环境要求

- **Windows 10/11**（开发与测试平台；其他系统理论可跑但未验证）
- **Python 3.11+**（全部脚本仅标准库，零第三方依赖）
- 一个 **Obsidian 仓库（vault）**——系统管理的就是这个文件夹
- （可选）[Hermes Agent](https://hermes-agent.nousresearch.com/docs) —— 作为技能宿主体验最完整

## 安装到 Hermes Agent

```powershell
# 1. 克隆到 Hermes 技能目录
cd "$env:LOCALAPPDATA\hermes\skills\note-taking"
git clone https://github.com/liubarryteb12/hermes-pkos-skill.git

# 2. 初始化你的知识库（对 AI 说）：
#    "初始化 PKOS，库在 D:\我的知识库"
#    → governance.bootstrap 会建好 _PKOS/ 地基 + config.json

# 3. 体检确认 29 个单元全部到岗
cd hermes-pkos-skill
python scripts/upgrade_check.py            # 期望: ALL PASS
python scripts/registry_schema_check.py    # 期望: PASS (29 单元, 0 警告)
```

## 安装到其他技能宿主（非 Hermes）

本包是标准的 `SKILL.md` 技能集：把仓库克隆到任何支持 SKILL.md 的宿主技能目录即可。
宿主只需能：读文件、跑 Python 脚本、执行 shell 命令。

```bash
git clone https://github.com/liubarryteb12/hermes-pkos-skill.git
python hermes-pkos-skill/scripts/upgrade_check.py   # 验证
```

## 首次使用三件事

1. **初始化**：对 AI 说「初始化 PKOS，库在 <你的 vault 路径>」
2. **喂资料**：把网页/PDF/笔记扔进 `00_收件暂存/`（或你定义的 INBOX）
3. **说人话**：「整理一下我的知识库」——AI 会走完整消化流水线并报进度

## 可选外部能力

| 能力 | 需要什么 |
|---|---|
| 生图（gptimage2 通道） | 环境变量 `PKOS_IMG_API_KEY` + OpenAI 兼容图像端点 |
| 生图（Gemini 通道） | 已登录 Gemini 的浏览器（浏览器驱动方案） |
| 公众号发表 | `wx_gzh_config.json`（app_id/app_secret）+ `gzh-design` 排版技能 |
| PPT 出图 | 图像通道同上（默认走原生渲染，无需出图） |

**凭证纪律**：所有密钥只从环境变量 / `.env` 读取（`.gitignore` 已排除），
绝不出现在代码、日志、回复里。仓库内 config 文件只含占位符。

## 验证安装

```bash
# 全量自检（全部只读，跑不坏任何东西）
python tests/run_tests.py            # 19 项检查
python tests/contract_refs.py        # 28 SKILL.md 契约引用
python tests/capability_runner.py    # 37 能力契约用例
cd pkos-knowledge-service-commit/scripts && python probe_p2.py   # 行为探针
```

全绿 = 小工人们全部到岗，可以开工。

## 升级

```bash
git pull
python scripts/sync_to_main.py --check   # 若你维护本地 SSOT 副本
python scripts/upgrade_check.py          # 升级后体检
```

升级守卫会自动检查：账本计数、覆盖率、测试基线、旧路径残留、主库漂移。
