# -*- coding: utf-8 -*-
"""frontmatter 解析行为契约探针。只验行为，不管实现；函数名自动适配。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pkos_kb import parser as P

fn = next((getattr(P, n) for n in ("parse_frontmatter", "parse_fm", "frontmatter")
           if hasattr(P, n)), None)
if fn is None:
    print("找不到 parse_frontmatter"); sys.exit(1)

def call(t):
    r = fn(t)
    return r[0] if isinstance(r, tuple) else r

CASES = [
    ("块级列表 tags", "---\ntitle: T\ntags:\n  - alpha\n  - beta\n---\n正文",
     lambda d: d.get("tags") == ["alpha", "beta"]),
    ("行内列表 tags", "---\ntitle: T\ntags: [alpha, beta]\n---\n正文",
     lambda d: d.get("tags") == ["alpha", "beta"]),
    ("多行块标量", "---\ntitle: T\nsummary: |\n  第一行\n  第二行\n---\n正文",
     lambda d: d.get("summary", "").strip() == "第一行\n第二行"),
    ("引号含冒号", '---\ntitle: "PKOS: 实验"\n---\n正文',
     lambda d: d.get("title") == "PKOS: 实验"),
    ("嵌套字典", "---\ntitle: T\nmeta:\n  author: me\n  year: 2026\n---\n正文",
     lambda d: d.get("meta") == {"author": "me", "year": 2026}),
    ("布尔真值", "---\ntitle: T\ndraft: true\n---\n正文",
     lambda d: d.get("draft") is True),
    ("整数", "---\ntitle: T\nver: 4\n---\n正文",
     lambda d: d.get("ver") == 4 and not isinstance(d.get("ver"), bool)),
    ("浮点", "---\ntitle: T\nscore: 1.5\n---\n正文",
     lambda d: d.get("score") == 1.5),
    ("版本号不当数字", "---\ntitle: T\nver: 4.9.10\n---\n正文",
     lambda d: d.get("ver") == "4.9.10"),
    ("前导零不当数字", "---\ntitle: T\nid: 007\n---\n正文",
     lambda d: d.get("id") == "007"),
    ("八进制陷阱", "---\ntitle: T\nzip: 01003\n---\n正文",
     lambda d: d.get("zip") == "01003"),
    ("六十进制陷阱", "---\ntitle: T\noffset: 1:30\n---\n正文",
     lambda d: d.get("offset") == "1:30"),
    ("CJK 值", "---\ntitle: 知识管理\nstage: raw\n---\n正文",
     lambda d: d.get("title") == "知识管理"),
    ("BOM 开头", "\ufeff---\ntitle: T\nstage: raw\n---\n正文",
     lambda d: d.get("title") == "T"),
    ("CRLF 换行", "---\r\ntitle: T\r\nstage: raw\r\n---\r\n正文",
     lambda d: d.get("title") == "T"),
    ("正文含分隔符", "---\ntitle: T\n---\n正文\n---\n后面",
     lambda d: d.get("title") == "T" and "后面" not in str(d)),
    ("无 frontmatter", "只有正文\n没有头",
     lambda d: d == {}),
    ("空 frontmatter", "---\n---\n正文",
     lambda d: d == {} or d is None),
    ("空值键不存空串", "---\ntitle: T\ntags:\n---\n正文",
     lambda d: d.get("tags", "__absent__") in (None, "__absent__", [])),
]

print(f"{'用例':16} {'结果':6} 值")
print("-" * 72)
ok = bad = 0
for name, text, pred in CASES:
    try:
        d = call(text) or {}
        good = pred(d)
        detail = repr(d)[:44]
    except Exception as e:
        good, detail = False, f"{type(e).__name__}: {e}"[:44]
    ok, bad = ok + good, bad + (not good)
    print(f"{name:16} {'PASS' if good else 'FAIL':6} {detail}")

print("-" * 72)
print("坏 YAML 是否 fail-loud（不静默返回空）:", end=" ")
try:
    d = call("---\ntitle: [unclosed\n  bad: : :\n---\n正文")
    print(f"FAIL 静默返回 {d!r} —— 应抛 ValueError")
    bad += 1
except Exception as e:
    print(f"PASS 抛出 {type(e).__name__}")
    ok += 1

print(f"\n通过 {ok}/{ok+bad}   失败 {bad}")
print("满足 frontmatter 行为契约" if bad == 0 else "存在契约缺口")
