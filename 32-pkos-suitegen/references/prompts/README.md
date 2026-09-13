# prompts/ — 套图提示词同步区

> 来源：知识库已分类素材（用户手动点名同步，绝不自动）。
> 同步命令：`python scripts/sync_prompts.py --source <知识库素材目录> --all`

## 规则

1. **手动**：用户点名才同步（09-13 用户裁定）
2. **单向**：知识库 → 此处，不反向写回知识库
3. **粒度**：支持全量 `--all` / 按子题 `--sub M01-S01`
4. **源路径**：`--source` 参数 > `config.json` 的 `suitegen.source`
