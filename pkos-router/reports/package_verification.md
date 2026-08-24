# Package Verification

- OK: `True`
- Package directory: `D:\deepseekharness\workspace\skills\personal-knowledge-os\pkos-router\dist`
- Targets: `1 / 1` adapters present
- Archive present: `True`
- Archive SHA256: `6e708beccb0f95abb629f3d822bd7d3f299eb6b8b3c6ce01d9986fd58e612bfc`
- Nested SKILL.md entries: `0`
- Failures: `0`
- Warnings: `1`

## Checks

| Check | Status | Detail |
| --- | --- | --- |
| `package-manifest` | `pass` | Package manifest exists: D:\deepseekharness\workspace\skills\personal-knowledge-os\pkos-router\dist\manifest.json |
| `generic-adapter` | `pass` | Adapter exists for target: generic |
| `archive-safe-paths` | `pass` | Archive has no absolute or parent-traversal entries |
| `archive-entry-pkos-router/SKILL.md` | `pass` | Archive contains pkos-router/SKILL.md |
| `archive-entry-pkos-router/manifest.json` | `pass` | Archive contains pkos-router/manifest.json |
| `archive-entry-pkos-router/agents/interface.yaml` | `pass` | Archive contains pkos-router/agents/interface.yaml |
| `archive-single-skill-entrypoint` | `pass` | Archive exposes only the root SKILL.md entrypoint |
| `archive-excludes-generated` | `pass` | Archive excludes local caches, platform noise, .yao state, external submission drafts, local evidence pointers, generated dist/, .previews/, and tests/tmp* contents |
| `archive-portable-evidence-index` | `pass` | Archive includes a self-contained portable evidence pointer and verified report index |

## Failures

- None

## Warnings

- Registry audit was not supplied; package verification skipped metadata parity checks.
