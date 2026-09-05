# Package Verification

- OK: `True`
- Package directory: `D:\deepseekharness\workspace\skills\personal-knowledge-os\25-pkos-audit\dist`
- Targets: `1 / 1` adapters present
- Archive present: `True`
- Archive SHA256: `4c4526d4ca2842d3822c59ea767aec6feccb913a23404300409a70b82241028f`
- Nested SKILL.md entries: `0`
- Failures: `0`
- Warnings: `1`

## Checks

| Check | Status | Detail |
| --- | --- | --- |
| `package-manifest` | `pass` | Package manifest exists: D:\deepseekharness\workspace\skills\personal-knowledge-os\25-pkos-audit\dist\manifest.json |
| `generic-adapter` | `pass` | Adapter exists for target: generic |
| `archive-safe-paths` | `pass` | Archive has no absolute or parent-traversal entries |
| `archive-entry-25-pkos-audit/SKILL.md` | `pass` | Archive contains 25-pkos-audit/SKILL.md |
| `archive-entry-25-pkos-audit/manifest.json` | `pass` | Archive contains 25-pkos-audit/manifest.json |
| `archive-entry-25-pkos-audit/agents/interface.yaml` | `pass` | Archive contains 25-pkos-audit/agents/interface.yaml |
| `archive-single-skill-entrypoint` | `pass` | Archive exposes only the root SKILL.md entrypoint |
| `archive-excludes-generated` | `pass` | Archive excludes local caches, platform noise, .yao state, external submission drafts, local evidence pointers, generated dist/, .previews/, and tests/tmp* contents |
| `archive-portable-evidence-index` | `pass` | Archive includes a self-contained portable evidence pointer and verified report index |

## Failures

- None

## Warnings

- Registry audit was not supplied; package verification skipped metadata parity checks.
