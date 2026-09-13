#!/usr/bin/env python3
"""重建 M00 v4：真实数据从 git 旧版恢复，增加 X01 系列列，X02/X03 收进每母题一行紧凑预留。
用法: python _rebuild_m00.py <旧M00文本路径> <新M00输出路径>
"""
import re
import sys
from pathlib import Path

old = Path(sys.argv[1]).read_text(encoding="utf-8")
out = Path(sys.argv[2])

lines = old.splitlines()
matrix = {}  # (Mxx, Sxx) -> dict(name, content, styles, aesthetics)
titles = {}  # Mxx -> 母题名
current_m = None
for line in lines:
    mh = re.match(r"^## (M\d{2}) (.+)$", line.strip())
    if mh:
        current_m = mh.group(1)
        titles[current_m] = mh.group(2)
        continue
    row = re.match(r"^\|\s*S(\d{2})\s+([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|$", line.strip())
    if row and current_m:
        s_num, s_name, content, styles, aes, fname = [x.strip() for x in row.groups()]
        matrix[(current_m, s_num)] = {"name": s_name, "content": content, "styles": styles, "aes": aes}

# 渲染 v4
new_lines = []
new_lines.append("# M00 母题/子题/系列索引 v4")
new_lines.append("")
new_lines.append("> v4（2026-09-13）：在 v2 基础上增加 X 系列层。现有 16 个子题全部归入系列 1（X01，文件名 `Mxx-Sxx-1-子题名.md`）。")
new_lines.append("> X02/X03 为每子题预留扩展位：新建时按登记制追加文件 `Mxx-Sxx-2-*.md` 并在本表补行，编号不回收不复用。")
new_lines.append("> 编号规则：M 母题 / S 子题 / X 系列 / F 风格 / U 用途 / A 审美（六段），模特 Pxx 可选叠加。")
new_lines.append("")
for mx in sorted(titles):
    new_lines.append(f"## {mx} {titles[mx]}")
    new_lines.append("")
    new_lines.append("| 子题 | 内容 | 系列 | 风格五支 | 常配审美 | 文件 |")
    new_lines.append("|---|---|---|---|---|---|")
    for (m, s), info in sorted(matrix.items()):
        if m != mx:
            continue
        new_lines.append(
            f"| S{s} {info['name']} | {info['content']} | X01 | {info['styles']} | {info['aes']} | {m}-S{s}-1-{info['name']}.md |")
    new_lines.append("")
new_lines.append("## 编号规则")
new_lines.append("")
new_lines.append("- M/S/X/F 全部预留到 99；新增先登记本表再使用，编号不回收不复用")
new_lines.append("- 审美后缀约定：`v古`=古风变体 / `v二`=二次元变体 / `v神`=神话工笔变体 / `v诗`=诗意留白变体 / `v幻`=幻想暗夜变体 / `-A简`=极简单色特调")
new_lines.append("- 子题文件内每支风格的**第一段=风格锚点**（文字描述锚点，稳定风格用），题词条目按 `M-S-X-F-U-A` 完整六段编号标注")
new_lines.append("- 组装：锚点 + 题词正文 → S00 消毒 → C00 参数 → 出图")
new_lines.append("")
out.write_text("\n".join(new_lines), encoding="utf-8")
print(f"M00 v4 写入: {out} ({len(new_lines)} 行)")
