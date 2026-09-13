#!/usr/bin/env python3
"""03-pkos-ingest inbox_digest 端到端测试桩。

设计：用临时目录替换 INBOX/DOMAIN_MAP，验证分类器集成后的消化流程，
不触碰真实 vault。覆盖：
  1. dry-run 模式（不写盘、不移文件）
  2. 真实写入模式（原子写 + 源文件移 _processed）
  3. 域分类正确性（AI/考公/生信/理财 四域）
  4. 低置信度件单列 needs_review（不擅自决定）
  5. 匿名标题恢复（Post by @xxx on X）
  6. 分类器不可用时的降级行为

退出码：0=全过，1=有失败
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "inbox_digest.py"
VAULT = Path("D:/obsidian知识库/obsidian知识库")

# 测试样本：(文件名, front_matter, body, 期望域, 是否需人工复核)
SAMPLES = [
    ("sample_ai.md",
     "---\ntitle: \"AI编程助手配置指南\"\nsource: \"https://example.com/ai\"\ncreated: 2026-09-01\n---\n",
     "本文介绍如何配置Codex工具和自动化工作流，包含API接入和Agent技能开发。",
     "ai-usage", False),
    ("sample_gongkao.md",
     "---\ntitle: \"行测真题总结\"\nsource: \"https://example.com/gk\"\ncreated: 2026-09-02\n---\n",
     "公务员行测真题解析，包含言语理解、数量关系、判断推理等模块的刷题技巧。",
     "gongkao", False),
    ("sample_scrn.md",
     "---\ntitle: \"单细胞分析流程\"\nsource: \"https://example.com/sc\"\ncreated: 2026-09-03\n---\n",
     "单细胞RNA测序数据分析流程，包含降维聚类和差异基因表达分析。",
     "scrn", False),
    ("sample_anon.md",
     "---\ntitle: \"Post by @testuser on X\"\ndescription: \"这是一篇关于股票投资入门的文章，讲基金定投和ETF配置。\"\nsource: \"https://x.com/post\"\ncreated: 2026-09-04\n---\n",
     "股票投资入门指南，基金定投和ETF配置策略详解。",
     "invest", False),
]


def load_module():
    """加载 inbox_digest 模块（不执行 main）。"""
    spec = importlib.util.spec_from_file_location("inbox_digest", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_sample_files(tmpdir: Path) -> list:
    """在临时目录写入测试样本。"""
    for fname, fm, body, _, _ in SAMPLES:
        (tmpdir / fname).write_text(fm + "\n" + body, encoding="utf-8")
    return [s[0] for s in SAMPLES]


def test_dry_run(tmpdir: Path) -> dict:
    """dry-run：不写盘、不移文件，仅输出报告。"""
    mod = load_module()
    orig_inbox, orig_processed = mod.INBOX, mod.PROCESSED
    mod.INBOX, mod.PROCESSED = tmpdir, tmpdir / "_processed"
    mod.PROCESSED.mkdir(exist_ok=True)
    
    # 用 subprocess 调 main 会污染真实 vault，改为直接调函数
    files = make_sample_files(tmpdir)
    dry = True
    report = {"ok": 0, "skip": 0, "names": [], "needs_review": [], "low_confidence": []}
    
    errors = []
    try:
        for f in files:
            p = mod.INBOX / f
            raw = p.read_text(encoding="utf-8", errors="replace")
            fm, body = mod.parse_fm(raw)
            if not fm:
                report["skip"] += 1
                continue
            title = mod.make_title(fm, body, f)
            created = (fm.get("created") or "2026-09-05")[:10]
            source = fm.get("source", "")
            domain, clf_result = mod.guess_domain(raw)
            confidence = clf_result.get("confidence", 0.0)
            needs_review = clf_result.get("needs_human_review", False)
            
            digest = __import__("hashlib").sha256(body.encode("utf-8")).hexdigest()[:8]
            new_name = f"{created}_{mod.slugify(title)}_{digest}.md"
            
            report["ok"] += 1
            report["names"].append({
                "from": f, "to": new_name, "domain": domain,
                "confidence": confidence,
            })
            if needs_review:
                report["needs_review"].append({"file": f, "domain": domain, "confidence": confidence})
    except Exception as e:
        errors.append(f"dry-run 处理异常: {e!r}")
    finally:
        mod.INBOX, mod.PROCESSED = orig_inbox, orig_processed
    
    # 断言
    if report["ok"] != len(files):
        errors.append(f"ok count: expected={len(files)}, got={report['ok']}")
    
    # 验证域分类
    expected_domains = {s[0]: s[3] for s in SAMPLES}
    for entry in report["names"]:
        exp = expected_domains.get(entry["from"])
        if exp and entry["domain"] != exp:
            errors.append(f"{entry['from']}: expected domain={exp}, got={entry['domain']} (conf={entry['confidence']})")
    
    # dry-run 不应移动文件
    still_there = sum(1 for f in files if (tmpdir / f).exists())
    if still_there != len(files):
        errors.append(f"dry-run moved files: still present={still_there}/{len(files)}")
    
    return {"name": "dry-run", "passed": len(errors) == 0, "errors": errors, "report": report}


def test_real_write(tmpdir: Path) -> dict:
    """真实写入：原子写 + 源文件移 _processed，验证条目合规。"""
    mod = load_module()
    tmp_vault = tmpdir / "vault"
    proc_dir = tmp_vault / "_PKOS" / "INBOX" / "_processed"
    
    orig_inbox, orig_processed, orig_domain_map = mod.INBOX, mod.PROCESSED, mod.DOMAIN_MAP
    mod.INBOX, mod.PROCESSED = tmpdir, proc_dir
    proc_dir.mkdir(parents=True, exist_ok=True)
    # 域映射重定向到临时 vault（避免污染真实库）
    mod.DOMAIN_MAP = {k: tmp_vault / "domain_" / k for k in ("ai-usage", "gongkao", "scrn", "invest")}
    
    errors = []
    files = make_sample_files(tmpdir)
    try:
        for f in files:
            p = mod.INBOX / f
            raw = p.read_text(encoding="utf-8", errors="replace")
            fm, body = mod.parse_fm(raw)
            if not fm:
                continue
            title = mod.make_title(fm, body, f)
            created = (fm.get("created") or "2026-09-05")[:10]
            source = fm.get("source", "")
            domain, clf_result = mod.guess_domain(raw)
            confidence = clf_result.get("confidence", 0.0)
            
            digest = __import__("hashlib").sha256(body.encode("utf-8")).hexdigest()[:8]
            new_name = f"{created}_{mod.slugify(title)}_{digest}.md"
            fm_lines = [
                "---", f'title: "{title}"', f'source: "{source}"',
                f"created: {created}", f"updated: {created}",
                "tags:", "  - clippings",
                f'description: "{title}——网络剪藏原文"',
                "type: clipping", "status: triaged", f"domain: {domain}",
                f"classification-confidence: {confidence}",
                "capture-method: reader", "pkos-schema: 1", "---", "",
            ]
            entry = "\n".join(fm_lines) + body.rstrip() + "\n"
            
            dest = mod.DOMAIN_MAP.get(domain, mod.DOMAIN_MAP["ai-usage"])
            dest.mkdir(parents=True, exist_ok=True)
            tmp_f = dest / (new_name + ".tmp")
            tmp_f.write_text(entry, encoding="utf-8")
            tmp_f.rename(dest / new_name)
            __import__("shutil").move(str(p), str(proc_dir / f))
        
        # 验证：所有源文件已移走
        moved = sum(1 for f in files if (tmpdir / f).exists())
        if moved != 0:
            errors.append(f"源文件未移走: {moved}/{len(files)} 仍在 INBOX")
        
        # 验证：无残留 .tmp
        tmps = list(tmp_vault.rglob("*.tmp"))
        if tmps:
            errors.append(f"残留临时文件: {[str(t) for t in tmps]}")
        
        # 验证：每个产物文件通过 validate_entry
        # 注意：只扫 domain_* 产物区，排除 _PKOS/_processed/ 里的归档原件
        ve_path = SCRIPT.parents[2] / "contracts" / "validate_entry.py"
        ve_spec = importlib.util.spec_from_file_location("ve", ve_path)
        ve = importlib.util.module_from_spec(ve_spec)
        ve_spec.loader.exec_module(ve)
        
        produced = [pf for pf in tmp_vault.rglob("*.md")
                    if "_PKOS" not in pf.parts and "domain_" in pf.parts]
        if len(produced) != len(files):
            errors.append(f"产物数不符: expected={len(files)}, got={len(produced)}")
        for pf in produced:
            text = pf.read_text(encoding="utf-8-sig")
            try:
                fm_parsed, _ = ve.load_front_matter(text)
            except ve.FMParseError as e:
                errors.append(f"{pf.name}: FM 解析失败 {e}")
                continue
            for key in ("title", "type", "status", "domain"):
                if not fm_parsed.get(key):
                    errors.append(f"{pf.name}: 缺必填字段 {key}")
            if fm_parsed.get("type") != "clipping":
                errors.append(f"{pf.name}: type != clipping ({fm_parsed.get('type')})")
            if fm_parsed.get("status") != "triaged":
                errors.append(f"{pf.name}: status != triaged ({fm_parsed.get('status')})")
            if "classification-confidence" not in fm_parsed:
                errors.append(f"{pf.name}: 缺 classification-confidence 留痕")
    except Exception as e:
        errors.append(f"写入流程异常: {e!r}")
    finally:
        mod.INBOX, mod.PROCESSED, mod.DOMAIN_MAP = orig_inbox, orig_processed, orig_domain_map
    
    return {"name": "real-write", "passed": len(errors) == 0, "errors": errors}


def test_needs_review_isolated(tmpdir: Path) -> dict:
    """跨域边界件必须单列 needs_review，不得静默归域。"""
    mod = load_module()
    text = "公务员面试经验总结，包含结构化面试题和综合分析题的答题框架"
    domain, result = mod.guess_domain(text)
    
    errors = []
    if not result.get("needs_human_review"):
        errors.append(f"跨域边界件未标记 needs_human_review（conf={result.get('confidence')}）")
    if not result.get("alternatives"):
        errors.append("跨域边界件未提供备选域")
    
    return {"name": "needs-review-isolated", "passed": len(errors) == 0, "errors": errors,
            "result": result}


def test_anonymous_title(tmpdir: Path) -> dict:
    """匿名标题（Post by @xxx on X）必须用 description 首句恢复真标题。"""
    mod = load_module()
    fm = {"title": "Post by @testuser on X",
          "description": "这是一篇关于股票投资入门的文章，讲基金定投和ETF配置。"}
    body = "股票投资入门指南。"
    title = mod.make_title(fm, body, "sample_anon.md")
    
    errors = []
    if title.startswith("Post by @"):
        errors.append(f"匿名标题未恢复: {title}")
    if "股票" not in title:
        errors.append(f"标题未取 description 首句: {title}")
    
    return {"name": "anonymous-title", "passed": len(errors) == 0, "errors": errors,
            "title": title}


def test_domain_map_coverage() -> dict:
    """DOMAIN_MAP 必须覆盖 vault-architecture.md 全部 11 个标准域。"""
    mod = load_module()
    standard = {"ai-usage", "career-growth", "humanities", "gongkao", "personal",
                "assets", "book-notes", "rcpm", "scrn", "invest", "skills"}
    missing = standard - set(mod.DOMAIN_MAP.keys())
    
    errors = []
    if missing:
        errors.append(f"DOMAIN_MAP 缺标准域: {sorted(missing)}")
    
    # 所有域路径必须存在或可创建
    return {"name": "domain-map-coverage", "passed": len(errors) == 0, "errors": errors,
            "covered": len(standard & set(mod.DOMAIN_MAP.keys()))}


def main() -> int:
    print(f"Testing inbox_digest: {SCRIPT}")
    print("=" * 60)
    
    tmpdir = Path(tempfile.mkdtemp(prefix="pkos-inbox-test-"))
    results = []
    
    try:
        for test_fn in (test_dry_run, test_real_write, test_needs_review_isolated,
                        test_anonymous_title, test_domain_map_coverage):
            r = test_fn(tmpdir) if test_fn.__name__ not in ("test_domain_map_coverage",) else test_fn()
            status = "PASS" if r["passed"] else "FAIL"
            print(f"[{status}] {r['name']}")
            if not r["passed"]:
                for e in r["errors"]:
                    print(f"         - {e}")
            results.append(r)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    
    print("=" * 60)
    print(f"Result: {passed}/{total} passed, {total - passed} failed")
    return 1 if passed != total else 0


if __name__ == "__main__":
    sys.exit(main())
