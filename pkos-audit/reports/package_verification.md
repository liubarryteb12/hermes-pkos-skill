# Package Verification

- OK: `True`
- Package directory: `D:\deepseekharness\workspace\skills\personal-knowledge-os\pkos-audit\dist`
- Targets: `1 / 1` adapters present
- Archive present: `True`
- Archive SHA256: `17f04f436330ee5bab336de9c49335907fe71fa1f5af09c4497445a04f5224de`
- Nested SKILL.md entries: `0`
- Failures: `0`
- Warnings: `1`

## Checks

| Check | Status | Detail |
| --- | --- | --- |
| `package-manifest` | `pass` | Package manifest exists: D:\deepseekharness\workspace\skills\personal-knowledge-os\pkos-audit\dist\manifest.json |
| `generic-adapter` | `pass` | Adapter exists for target: generic |
| `archive-safe-paths` | `pass` | Archive has no absolute or parent-traversal entries |
| `archive-entry-pkos-audit/SKILL.md` | `pass` | Archive contains pkos-audit/SKILL.md |
| `archive-entry-pkos-audit/manifest.json` | `pass` | Archive contains pkos-audit/manifest.json |
| `archive-entry-pkos-audit/agents/interface.yaml` | `pass` | Archive contains pkos-audit/agents/interface.yaml |
| `archive-single-skill-entrypoint` | `pass` | Archive exposes only the root SKILL.md entrypoint |
| `archive-excludes-generated` | `pass` | Archive excludes local caches, platform noise, .yao state, external submission drafts, local evidence pointers, generated dist/, .previews/, and tests/tmp* contents |
| `archive-portable-evidence-index` | `pass` | Archive includes a self-contained portable evidence pointer and verified report index |

## Failures

- None

## Warnings

- Registry audit was not supplied; package verification skipped metadata parity checks.
