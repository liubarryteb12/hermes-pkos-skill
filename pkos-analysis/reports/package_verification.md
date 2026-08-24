# Package Verification

- OK: `True`
- Package directory: `D:\deepseekharness\workspace\skills\personal-knowledge-os\pkos-analysis\dist`
- Targets: `1 / 1` adapters present
- Archive present: `True`
- Archive SHA256: `f3596bd3d1a0781b61b16a2dde7b277995432d0a7d88f73e901abf81335b0397`
- Nested SKILL.md entries: `0`
- Failures: `0`
- Warnings: `1`

## Checks

| Check | Status | Detail |
| --- | --- | --- |
| `package-manifest` | `pass` | Package manifest exists: D:\deepseekharness\workspace\skills\personal-knowledge-os\pkos-analysis\dist\manifest.json |
| `generic-adapter` | `pass` | Adapter exists for target: generic |
| `archive-safe-paths` | `pass` | Archive has no absolute or parent-traversal entries |
| `archive-entry-pkos-analysis/SKILL.md` | `pass` | Archive contains pkos-analysis/SKILL.md |
| `archive-entry-pkos-analysis/manifest.json` | `pass` | Archive contains pkos-analysis/manifest.json |
| `archive-entry-pkos-analysis/agents/interface.yaml` | `pass` | Archive contains pkos-analysis/agents/interface.yaml |
| `archive-single-skill-entrypoint` | `pass` | Archive exposes only the root SKILL.md entrypoint |
| `archive-excludes-generated` | `pass` | Archive excludes local caches, platform noise, .yao state, external submission drafts, local evidence pointers, generated dist/, .previews/, and tests/tmp* contents |
| `archive-portable-evidence-index` | `pass` | Archive includes a self-contained portable evidence pointer and verified report index |

## Failures

- None

## Warnings

- Registry audit was not supplied; package verification skipped metadata parity checks.
