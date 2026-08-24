# 安装说明 · 567-personal-knowledgedatabase v0.0.1

## 环境要求

- Python 3.12+（全部脚本仅标准库，零第三方依赖）
- 支持 SKILL.md 的技能宿主（如 DeepSeek Harness；技能目录 `~/.dsh/skills/`）

## 安装步骤

1. 把本包内全部 `pkos-*` 目录复制（或 junction）到技能目录：
   ```powershell
   # Windows junction 方式（推荐，源目录更新即时生效）
   $src = "<解压路径>"
   foreach ($s in Get-ChildItem $src -Directory -Filter "pkos-*") {
     New-Item -ItemType Junction -Path "$env:USERPROFILE\.dsh\skills\$($s.Name)" -Target $s.FullName
   }
   ```
2. 重启会话使新技能进入目录。
3. （可选）安装外部依赖：
   - `pkos-ppt` 出图需要图像网关封装（如 567-image-generation）与 API key；
   - 公众号出口需要 `gzh-design` 技能（本包不含）。

## 快速开始

```
「初始化知识库」        ← 首次必做：定路径、选架构模式（MOC/OKF/INDEX）
往 _PKOS/INBOX/ 丢文件 → 「处理 INBOX」
「分析这篇」「润色这段」「做成网页 / 出 deck」
「体检一下知识库」
```

## 自检（安装后建议跑一次）

```bash
python tests/run_tests.py            # 19 组契约测试应全 PASS
python pkos-meta/scripts/meta_gate.py all   # validate + triggers 应 PASS
```

## 版本说明

内部安装登记曾为 pkos v0.1.0（DESIGN.md §4.9，2026-08-23，工单 10 子集）；
本 v0.0.1 为首个完整对外分发版（含 pkos-init 初始化环节与 5 主题 HTML 注册库）。
