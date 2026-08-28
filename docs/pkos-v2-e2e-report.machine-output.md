# PKOS v2 e2e report (2026-08-27T06:19:06Z)

- vault: `D:\obsidian知识库\obsidian知识库`
- overall: **PASS**

## 5-step e2e

### maintenance.index (exit=0, 3.21s)

  {
    "total": 560,
    "by_status": {
      "triaged": 522,
      "analyzed": 35,
      "published": 3
    },
    "by_domain_summary": {
      "知识库首页.md": 1,
      "考公备考.md": 1,
      "a-面试题库.md": 1,
      "b-行测与笔记.md": 1,
      "AI与Codex.md": 1,
      "个人办事.md": 1,
      "工作流与Skills.md": 1,
      "素材与图表.md": 1,
      "书籍笔记.md": 1,
      "知识网络分析.md": 1,
      "内容状态总览.md": 1,
      "INDEX.md": 1,

### audit.lint.report-only (exit=0, 0.95s)

  {
    "applied_count": 0,
    "reported_count": 1336,
    "applied": [],
    "reported": [
      {
        "rule": "fm-default-status",
        "path": "D:\\obsidian知识库\\obsidian知识库\\00-知识库首页.md",
        "applied": "status=triaged",
        "dry_run": true
      },
      {
        "rule": "fm-missing-fields",
        "path": "D:\\obsidian知识库\\obsidian知识库\\00-知识库首页.md",
        "missing": [
          "type",
          "status",
          "domain"
        ],
        "applied": {

### capability_runner (exit=1, 5.04s)

  
  === pkos.maintenance.index (12 cases) ===
    FAIL index-include-status-ambiguous: ambiguous 期望非零退出或 v2_failure_mode; out[:200]={
    "total": 0,
    "by_status": {},
    "by_domain_summary": {},
    "cross_domain_edges": 0
  }
  
    FAIL index-incremental-since-ambiguous: ambiguous 期望非零退出或 v2_failure_mode; out[:200]={
    "total": 0,
    "by_status": {},
    "by_domain_summary": {},
    "cross_domain_edges": 0
  }
  
    -> 10/12 passed (0 skip, 2 fail)
  
  === pkos.knowledge_service.commit (14 cases) ===
    FAIL ks-frontmatter-incomplete: not_found 期望非零退出或 v2_failure_mode; out[:200]={

### contract_refs (exit=0, 0.13s)

  
  === 15 SKILL.md 扫描完成，0 错误 ===

### validate_entry (exit=0, 1.13s)

  PASS normalize_url 'HTTPS://X.com/path/?utm_source=x&id=2'
  PASS normalize_url 'https://twitter.com/a/b'
  PASS normalize_url 'https://www.example.com/a/b/'
  PASS normalize_url 'https://example.com?spm=1&b=2&a=1'
  PASS normalize_url 'https://example.com/#frag'
  PASS normalize_url 'https://example.com'
  PASS file key 改名稳定
  PASS valid-clipping exit0
  PASS valid-clipping pass
  PASS valid-clipping 无 ERROR
  PASS legacy-note exit0
  PASS legacy-note 判 legacy
  PASS bad-vocab exit1
  PASS bad-vocab 双词表错误
  PASS missing-title exit1
  PASS missing-title 报 title-missing
  PASS missing-title 有 type/domain 缺失警告
  PASS 未知字段向前兼容
  PASS published 必须有 outputs
  PASS FM 未闭合 fail loud

