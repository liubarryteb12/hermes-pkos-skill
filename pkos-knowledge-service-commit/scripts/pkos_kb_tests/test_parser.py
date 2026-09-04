"""解析层：代码块伪链接、frontmatter 4KB、bigram"""
from pkos_kb.parser import (cjk_bigram, extract_links, parse_frontmatter,
                            read_frontmatter_only, split_frontmatter)

DOC = """正文 [[真链接A]] 和 [[真链接B|别名]] 与 [[带锚点#章节]]
![[嵌入图]] 还有 [md链接](某笔记.md) 和 [带锚](另一篇.md#节)
```python
# [[代码块假链接]]
x = 1
```
~~~
[[波浪号代码块假链接]]
~~~
行内 `[[行内假链接]]` 结束
"""


def titles():
    return [t for t, _, _ in extract_links(DOC)]


def test_wikilink():
    assert "真链接A" in titles() and "真链接B" in titles()


def test_alias_stripped():
    assert not any("|" in t for t in titles())


def test_anchor_separated():
    assert ("带锚点", "章节") in [(t, a) for t, a, _ in extract_links(DOC)]


def test_embed_type():
    assert ("嵌入图", None, "embed") in extract_links(DOC)


def test_md_link():
    assert "某笔记" in titles() and "另一篇" in titles()


def test_fenced_code_excluded():
    assert "代码块假链接" not in titles()
    assert "波浪号代码块假链接" not in titles()


def test_inline_code_excluded():
    assert "行内假链接" not in titles()


def test_frontmatter_basic():
    fm = parse_frontmatter(b"---\ntitle: T\nstatus: raw\ntags: [a, b]\n---\n\nbody")
    assert fm["title"] == "T" and fm["status"] == "raw" and fm["tags"] == ["a", "b"]


def test_frontmatter_only_reads_head(tmp_path):
    p = tmp_path / "big.md"
    p.write_text("---\ntitle: T\n---\n\n" + "字" * 500000, encoding="utf-8")
    assert read_frontmatter_only(p)["title"] == "T"


def test_frontmatter_absent():
    fm, body = split_frontmatter(b"no frontmatter here")
    assert fm == {} and body == "no frontmatter here"


def test_crlf_frontmatter():
    fm, _ = split_frontmatter(b"---\r\ntitle: T\r\n---\r\n\r\nbody")
    assert fm["title"] == "T"


def test_bigram():
    assert cjk_bigram("知识图谱") == " 知识 识图 图谱 "
    assert "FTS5" in cjk_bigram("知识FTS5图谱")


def test_bigram_single_char():
    assert "我" in cjk_bigram("我")


def test_no_duplicate_links():
    out = extract_links("[[A]] [[A]] [[A]]")
    assert len(out) == 1


# ── v5.3 评估第③处回归：frontmatter 结构字符不得静默存错值 ──────────────
def test_fm_block_list_not_silently_dropped():
    """块级列表 tags 曾静默存成空串（第二个标签永久丢失）——修复后必须完整保留。"""
    fm = parse_frontmatter(b"---\ntitle: T\ntags:\n  - alpha\n  - beta\n---\n\nbody")
    assert fm.get("tags") == ["alpha", "beta"], f"块级列表被静默吞掉: {fm!r}"


def test_fm_multiline_block():
    fm = parse_frontmatter("---\ntitle: T\nsummary: |\n  第一行\n  第二行\n---\n".encode("utf-8"))
    assert fm.get("summary") == "第一行\n第二行", f"多行块存错: {fm!r}"


def test_fm_yaml_scalar_types():
    """布尔/数字必须转真类型，不得存字符串。"""
    fm = parse_frontmatter("---\ntitle: T\npublished: true\nrating: 4\n---\n".encode("utf-8"))
    assert fm.get("published") is True, f"布尔存成字符串: {fm!r}"
    assert fm.get("rating") == 4, f"数字存成字符串: {fm!r}"


def test_fm_nested_dict():
    fm = parse_frontmatter("---\ntitle: T\nauthor:\n  name: me\n  year: 2026\n---\n".encode("utf-8"))
    assert fm.get("author") == {"name": "me", "year": 2026}, f"嵌套字典存错: {fm!r}"


def test_fm_needs_degraded_flag():
    """无 PyYAML 时复杂结构文件必须落 index_state='DEGRADED'（可对账，非静默缺失）。"""
    import builtins
    import warnings
    from pkos_kb.parser import needs_degraded

    # 有 yaml 的环境 → 不降级
    assert needs_degraded(b"---\ntags:\n  - a\n---\n") is False

    real_import = builtins.__import__
    def fake_import(name, *a, **k):
        if name == "yaml":
            raise ImportError("no yaml")
        return real_import(name, *a, **k)

    builtins.__import__ = fake_import
    try:
        for m in list(__import__("sys").modules):
            if m.startswith("pkos_kb"):
                del __import__("sys").modules[m]
        from pkos_kb import parser as p2
        # 复杂结构 → DEGRADED
        assert p2.needs_degraded(b"---\ntags:\n  - a\n  - b\n---\n") is True
        # 简单 kv → 不降级
        assert p2.needs_degraded(b"---\ntitle: T\nstage: raw\n---\n") is False
        # 告警一次性
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            p2.parse_frontmatter(b"---\ntags:\n  - a\n---\n")
            p2.parse_frontmatter(b"---\ntags:\n  - a\n---\n")
            n_warn = sum(1 for x in w if "PyYAML" in str(x.message))
        assert n_warn <= 1, f"告警应一次性，实际 {n_warn}"
    finally:
        builtins.__import__ = real_import


def test_fm_yaml_octal_blocked():
    """YAML 1.1 八进制/六十进制隐式转换必须拦截（007/01003/1:30 保字符串）。"""
    fm = parse_frontmatter(
        "---\ntitle: T\nid: 007\nzip: 01003\noffset: 1:30\nver: 4.9.10\n---\n正文".encode("utf-8"))
    assert fm.get("id") == "007", f"前导零被转: {fm!r}"
    assert fm.get("zip") == "01003", f"八进制被转: {fm!r}"
    assert fm.get("offset") == "1:30", f"六十进制被转: {fm!r}"
    assert fm.get("ver") == "4.9.10", f"版本号被转: {fm!r}"
