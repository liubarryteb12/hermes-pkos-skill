# 剪藏消化脚本（09-11 修复历史残留专用）

## 用途

批量处理 `_PKOS/INBOX/_processed/` 中残留的半成品剪藏（缺 FM 字段）。

## 用法

```bash
cd D:/00.AIagent/hermesagent
python cn_debug/fix_inbox_processed_20260911.py  # 补 FM + 原子写入域目录
python cn_debug/fix_clip_processed_20260911.py   # 处理 obsidian知识库/_processed/
```

## 核心教训

**原子写入顺序**：
1. 先写目标域目录（`.tmp` + `rename()` 原子操作）
2. `validate_entry.py` 校验通过
3. **成功后**才删除 `_processed/` 中的原件

**禁止**：先移源文件再写 staging —— 这会制造悬空半成品。

## 输出

- `cn_debug/intake_fix_report_20260911.md` - 修复报告
- `cn_debug/dump_126_20260911.py` - 126 件目录（可用于人工裁决）
