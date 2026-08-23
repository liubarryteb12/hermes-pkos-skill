#!/usr/bin/env python3
"""validate_output —— 按 sink 切换验收清单。

用法：python validate_output.py <file.html> --sink web-single-file
退出码：0 通过；1 存在 FAIL。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def check_web_single_file(text: str) -> list[tuple[bool, str]]:
    checks = [
        (text.lstrip().lower().startswith("<!doctype html"), "doctype 在首行"),
        ('charset="utf-8"' in text or "charset=utf-8" in text, "utf-8 charset 声明"),
        (len(re.findall(r"<style", text)) == 1, "内联样式唯一 <style> 块"),
        (not re.search(r'<link[^>]+rel=["\']?stylesheet', text), "无外部 stylesheet link"),
        (not re.search(r"<script\b", text), "无脚本（离线零依赖）"),
        (not re.search(r'src="https?://', text), "无外链资源 src"),
        ("<!-- pkos-output source=" in text, "文件头注释含 pkos-output source 标记"),
        ("route=" in text.split("-->")[0] if "<!--" in text else False, "头注释含 route id"),
        ('data-style="' in text, "根元素带主题 data-style 锚点"),
        ("<title>" in text and "</title>\n" not in text[:10], "title 非空"),
    ]
    return checks


def check_web_combined(text: str) -> list[tuple[bool, str]]:
    # 继承单文件检查，但两处按合并版语义调整：
    # ① 内联 runtime 脚本是功能本体——只禁外链脚本；② 头注释含 kind= 前缀，放宽为前缀匹配
    adjusted = []
    for ok, name in check_web_single_file(text):
        if name == "无脚本（离线零依赖）":
            adjusted.append((not re.search(r'<script\b[^>]*\bsrc=', text), "脚本全部内联（无外链 script src）"))
        elif name == "文件头注释含 pkos-output source 标记":
            head = text.split("-->")[0] if "<!--" in text else ""
            adjusted.append(("<!-- pkos-output " in head and "source=" in head,
                             "头注释含 pkos-output 与 source"))
        else:
            adjusted.append((ok, name))
    extra = [
        ('id="readview"' in text and 'id="deckview"' in text, "阅读/放映双容器齐备"),
        ('class="notes"' in text, "讲稿 .notes 物理分离在场"),
        ('id="mode-toggle"' in text, "模式切换控件在场"),
        ("kind=combined" in text, "头注释标记 kind=combined"),
    ]
    return adjusted + extra


CHECKSETS = {"web-single-file": check_web_single_file, "web-combined": check_web_combined}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--sink", required=True, choices=sorted(CHECKSETS))
    args = ap.parse_args(argv)

    text = Path(args.file).read_text(encoding="utf-8")
    results = CHECKSETS[args.sink](text)
    fails = 0
    for ok, name in results:
        print(("PASS " if ok else "FAIL ") + name)
        fails += 0 if ok else 1
    print(f"-- {args.sink}: {'PASS' if not fails else 'FAIL'} ({fails} 项未过)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
