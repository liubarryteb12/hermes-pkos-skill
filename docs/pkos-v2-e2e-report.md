# PKOS v2 e2e report (2026-08-31T15:27:49Z)

- vault: `D:\obsidian`
- overall: **PASS**

## 5-step e2e

### maintenance.index (exit=0, 0.12s)

  {
    "total": 0,
    "by_status": {},
    "by_domain_summary": {},
    "cross_domain_edges": 0
  }

### audit.lint.report-only (exit=0, 0.13s)

  {
    "applied_count": 0,
    "reported_count": 0,
    "applied": [],
    "reported": []
  }

### capability_runner (exit=1, 6.34s)

  
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

### contract_refs (exit=0, 0.15s)

  
  === 26 SKILL.md 扫描完成，0 错误 ===

### validate_entry (exit=0, 1.3s)

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

