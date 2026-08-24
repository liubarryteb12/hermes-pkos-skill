# Package Verification

- OK: `True`
- Package directory: `D:\deepseekharness\workspace\skills\personal-knowledge-os\pkos-intake\dist`
- Targets: `1 / 1` adapters present
- Archive present: `True`
- Archive SHA256: `9aa4cf77fe583d590341cd8f215824d0615a29d8a35b9ced71471c21e4a423b3`
- Nested SKILL.md entries: `0`
- Failures: `0`
- Warnings: `1`

## Checks

| Check | Status | Detail |
| --- | --- | --- |
| `package-manifest` | `pass` | Package manifest exists: D:\deepseekharness\workspace\skills\personal-knowledge-os\pkos-intake\dist\manifest.json |
| `generic-adapter` | `pass` | Adapter exists for target: generic |
| `archive-safe-paths` | `pass` | Archive has no absolute or parent-traversal entries |
| `archive-entry-pkos-intake/SKILL.md` | `pass` | Archive contains pkos-intake/SKILL.md |
| `archive-entry-pkos-intake/manifest.json` | `pass` | Archive contains pkos-intake/manifest.json |
| `archive-entry-pkos-intake/agents/interface.yaml` | `pass` | Archive contains pkos-intake/agents/interface.yaml |
| `archive-single-skill-entrypoint` | `pass` | Archive exposes only the root SKILL.md entrypoint |
| `archive-excludes-generated` | `pass` | Archive excludes local caches, platform noise, .yao state, external submission drafts, local evidence pointers, generated dist/, .previews/, and tests/tmp* contents |
| `archive-portable-evidence-index` | `pass` | Archive includes a self-contained portable evidence pointer and verified report index |

## Failures

- None

## Warnings

- Registry audit was not supplied; package verification skipped metadata parity checks.
