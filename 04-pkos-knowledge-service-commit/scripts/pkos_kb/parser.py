"""
parser.py — 解析层：frontmatter / wikilink / CJK bigram

要点:
  - frontmatter 只读前 4KB，禁止全文件 read()（T-3 二级短路）
  - 抽链接前先剔除围栏代码块与行内代码，否则代码里的 [[x]] 会污染图谱
  - CJK bigram：unicode61 对中文整段成词，必须预切分（T-4）
"""
from __future__ import annotations

import hashlib
import re
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── 正则 ────────────────────────────────────────────────────────────
FM_RE = re.compile(rb"^---\r?\n(.*?)\r?\n---[ \t]*\r?\n", re.S)
FENCE_RE = re.compile(r"^[ \t]*(```|~~~).*?^[ \t]*\1", re.S | re.M)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
WIKILINK_RE = re.compile(r"(!?)\[\[([^\[\]\|\n\r#]+)(#[^\[\]\|\n\r]*)?(?:\|[^\[\]\n\r]*)?\]\]")
MDLINK_RE = re.compile(r"(!?)\[[^\]\n]*\]\(\s*<?([^)>\s]+?\.md)>?(?:#([^)\s]+))?\s*\)")
_FM_SCALAR = re.compile(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$")

FM_HEAD_BYTES = 4096


def _coerce_yaml_scalar(v: str) -> Any:
    """YAML 标量字面量类型转换：纯十进制 int / float / bool / null → 真类型。
    前导零（007/01003/0755）一律保留字符串——YAML 1.1 八进制歧义，入库不可逆失真。"""
    if not v:
        return v
    low = v.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "~"):
        return None
    # 前导零拒绝转 int（007→'007' 而非 7；01003→'01003' 而非 1003/515）
    if re.fullmatch(r"[-+]?0[0-9]+", v):
        return v
    try:
        if re.fullmatch(r"[-+]?\d+", v):
            return int(v)
        if re.fullmatch(r"[-+]?(?:\d+\.\d*|\.\d+)(?:[eE][-+]?\d+)?", v) or \
           re.fullmatch(r"[-+]?\d+[eE][-+]?\d+", v):
            return float(v)
    except ValueError:
        pass
    return v


_YAML_STRUCT_RE = re.compile(r"(?m)^\s+\S|^\s*-\s|[|>]\s*$|[\"']")

_yaml_available_cache: Optional[bool] = None
_warned_no_yaml = False


def yaml_available() -> bool:
    """PyYAML 是否可用（模块级缓存）。降级落痕判定用。"""
    global _yaml_available_cache
    if _yaml_available_cache is None:
        try:
            import yaml  # type: ignore  # noqa: F401
            _yaml_available_cache = True
        except ImportError:
            _yaml_available_cache = False
    return _yaml_available_cache


def needs_degraded(raw: "bytes | str") -> bool:
    """该文件解析是否降级（无 PyYAML 且 frontmatter 含结构字符）。
    调用方据此写 index_state='DEGRADED'，事后可 SQL 捞出重扫。"""
    if yaml_available():
        return False
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    m = FM_RE.match(raw)
    if not m:
        return False
    try:
        block = m.group(1).decode("utf-8", "ignore")
    except Exception:
        return False
    return has_yaml_structure(block)


def has_yaml_structure(block: str) -> bool:
    """frontmatter 块是否含 YAML 结构字符（缩进/列表/块标量/引号）。
    无 PyYAML 时这类文件解析会降级——调用方据此打 index_state='DEGRADED'。"""
    return any(_YAML_STRUCT_RE.search(l) for l in block.splitlines())


def _warn_no_yaml_once() -> None:
    global _warned_no_yaml
    if not _warned_no_yaml:
        _warned_no_yaml = True
        warnings.warn(
            "PyYAML 未安装：frontmatter 复杂结构（列表/多行块/嵌套）将被跳过，"
            "入库后 index_state='DEGRADED'，可安装 pyyaml 后按 DEGRADED 清单重扫。",
            RuntimeWarning, stacklevel=3)


def _load_yaml(block: str) -> Dict[str, Any]:
    """yaml.safe_load + YAML 1.1 陷阱拦截：八进制/六十进制隐式转换会静默失真
    （01003→515、1:30→90、007→7），前导零/冒号值在入库场景必须保留字符串。
    add_implicit_resolver 是追加不是替换（默认 int 解析器先匹配，永远轮不到新正则），
    所以直接覆写 int constructor：只把纯十进制转 int，其余原样返回字符串。
    布尔/浮点/列表/字典等其余解析行为继承 SafeLoader，不受影响。"""
    import yaml  # type: ignore

    class _PkosLoader(yaml.SafeLoader):
        pass

    _PkosLoader.add_constructor("tag:yaml.org,2002:int", _yaml_int_keep_leading_zero)
    try:
        loaded = yaml.load(block, Loader=_PkosLoader) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"frontmatter YAML 解析失败: {e}") from e
    if not isinstance(loaded, dict):
        raise ValueError(f"frontmatter 顶层应为映射，得到 {type(loaded).__name__}")
    return loaded


def _yaml_int_keep_leading_zero(loader: Any, node: Any) -> Any:
    """int constructor：纯十进制（可带正负号）→ int；前导零/冒号/八进制十六进制 → 字符串。
    YAML 1.1 默认 007→7、01003→515、1:30→90 是静默不可逆失真，入库场景必须拦。"""
    v = loader.construct_scalar(node)
    if re.fullmatch(r"[-+]?(?:0|[1-9][0-9_]*)(?:_[0-9]+)*", v):
        try:
            return int(v.replace("_", ""))
        except ValueError:
            return v
    return v

def parse_frontmatter(head: "bytes | str") -> Dict[str, Any]:
    """frontmatter → dict。分级解析（v5.3 评估第③处修复）：
      简单 kv（无 YAML 结构字符/标量字面量）走正则快路径；
      出现缩进/列表/块标量/引号 → yaml.safe_load（正确性零妥协）；
      YAML 解析失败 fail-loud（不静默返回空/错值）。
      兼容 str/bytes 输入；自动剥 UTF-8 BOM（Windows 笔记常见，\ufeff 会卡死 ^--- 匹配）。
    静默存错值比崩溃危险：tags 块级列表被正则吞成空串 = 标签永久丢失且看不出丢过。"""
    if isinstance(head, str):
        head = head.encode("utf-8")
    if head.startswith(b"\xef\xbb\xbf"):
        head = head[3:]           # UTF-8 BOM
    m = FM_RE.match(head)
    if not m:
        return {}
    try:
        block = m.group(1).decode("utf-8", "ignore")
    except Exception:
        return {}
    # 快筛：只有非空行且全部是简单 `key: scalar` 才走快路径
    lines = [l for l in block.splitlines() if l.strip()]
    if lines and all(_FM_SCALAR.match(l) and not _YAML_STRUCT_RE.search(l) for l in lines):
        out: Dict[str, Any] = {}
        for line in lines:
            mm = _FM_SCALAR.match(line)
            k, v = mm.group(1), mm.group(2).strip()
            if not v:
                continue              # 空值键不存（宁缺勿错：存 "" 看不出是丢过还是本来空）
            if v.startswith("[") and v.endswith("]"):
                out[k] = [x.strip().strip("\"'") for x in v[1:-1].split(",") if x.strip()]
            else:
                out[k] = _coerce_yaml_scalar(v.strip("\"'"))
        return out
    # 有 YAML 结构 → 真解析。可选依赖：无 yaml 模块时退回避让（不静默存错值）
    try:
        import yaml  # type: ignore
    except ImportError:
        _warn_no_yaml_once()
        # 环境无 PyYAML：只收非空简单 kv；空值/结构父键（tags: 后跟列表）宁缺勿错——
        # 存 `tags: ""` 比不存更糟（标签静默丢失且看不出丢过）
        out = {}
        for line in lines:
            if line[0] in " \t-#" or _YAML_STRUCT_RE.search(line):
                continue
            mm = _FM_SCALAR.match(line)
            if mm and mm.group(2).strip() and not mm.group(2).strip().endswith(":"):
                out[mm.group(1)] = mm.group(2).strip().strip("\"'")
        return out
    try:
        loaded = _load_yaml(block)
    except ValueError as e:
        raise e
    if not isinstance(loaded, dict):
        raise ValueError(f"frontmatter 顶层应为映射，得到 {type(loaded).__name__}")
    return loaded


def read_frontmatter_only(path: Path) -> Dict[str, Any]:
    """T-3 二级短路：只读前 4KB。"""
    with open(path, "rb") as f:
        return parse_frontmatter(f.read(FM_HEAD_BYTES))


def split_frontmatter(raw: bytes) -> Tuple[Dict[str, Any], str]:
    fm = parse_frontmatter(raw[:FM_HEAD_BYTES])
    m = FM_RE.match(raw)
    body = raw[m.end():] if m else raw
    return fm, body.decode("utf-8", "ignore")


def strip_code(text: str) -> str:
    return INLINE_CODE_RE.sub(" ", FENCE_RE.sub(" ", text))


def extract_links(body: str) -> List[Tuple[str, Optional[str], str]]:
    """→ [(target_title, anchor, link_type)]，已剔除代码块内伪链接。"""
    clean = strip_code(body)
    out: List[Tuple[str, Optional[str], str]] = []
    seen = set()
    for bang, title, anchor in WIKILINK_RE.findall(clean):
        t = title.strip()
        if not t:
            continue
        a = (anchor or "").lstrip("#").strip() or None
        key = (t, a, bool(bang), "wiki")
        if key in seen:
            continue
        seen.add(key)
        out.append((t, a, "embed" if bang else "wiki"))
    for bang, target, anchor in MDLINK_RE.findall(clean):
        t = Path(target.replace("\\", "/")).stem
        if not t:
            continue
        a = (anchor or "").strip() or None
        key = (t, a, bool(bang), "md")
        if key in seen:
            continue
        seen.add(key)
        out.append((t, a, "embed" if bang else "md"))
    return out


# ── CJK bigram ──────────────────────────────────────────────────────
_CJK_RUN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002a6df]+")


def cjk_bigram(text: str) -> str:
    """连续 CJK 切成重叠二元组；英文数字原样。写入侧与查询侧都要切。"""
    out: List[str] = []
    last = 0
    for m in _CJK_RUN.finditer(text):
        out.append(text[last:m.start()])
        s = m.group()
        out.append(" ".join(s[i:i + 2] for i in range(len(s) - 1)) if len(s) > 1 else s)
        last = m.end()
    out.append(text[last:])
    return " ".join(out)


def fts_query(q: str) -> str:
    """把用户查询转成 FTS5 短语查询（保证词序）。"""
    tok = cjk_bigram(q).strip()
    tok = tok.replace('"', " ")
    tok = re.sub(r"\s+", " ", tok).strip()
    return '"' + tok + '"' if tok else ""


def make_snippet(body: str, query: str, width: int = 60) -> str:
    """P-7：FTS 只做定位，展示回读原文。绝不能把 bigram 文本给人看。"""
    if not body:
        return ""
    flat = re.sub(r"\s+", " ", body).strip()
    i = flat.find(query)
    if i < 0 and query:
        for probe in (query[:2], query[:1]):
            if probe:
                i = flat.find(probe)
                if i >= 0:
                    break
    if i < 0:
        return flat[:width * 2] + ("…" if len(flat) > width * 2 else "")
    s = max(0, i - width)
    e = min(len(flat), i + len(query) + width)
    return ("…" if s else "") + flat[s:e] + ("…" if e < len(flat) else "")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, buf: int = 1 << 18) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(buf), b""):
            h.update(chunk)
    return h.hexdigest()
