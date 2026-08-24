# Package Verification

- OK: `True`
- Package directory: `D:\deepseekharness\workspace\skills\personal-knowledge-os\pkos-timeline\dist`
- Targets: `1 / 1` adapters present
- Archive present: `True`
- Archive SHA256: `819626f4a2d8d585e66963a09ab502732ce327beed488146a7e970c4fcd4a983`
- Nested SKILL.md entries: `0`
- Failures: `0`
- Warnings: `1`

## Checks

| Check | Status | Detail |
| --- | --- | --- |
| `package-manifest` | `pass` | Package manifest exists: D:\deepseekharness\workspace\skills\personal-knowledge-os\pkos-timeline\dist\manifest.json |
| `generic-adapter` | `pass` | Adapter exists for target: generic |
| `archive-safe-paths` | `pass` | Archive has no absolute or parent-traversal entries |
| `archive-entry-pkos-timeline/SKILL.md` | `pass` | Archive contains pkos-timeline/SKILL.md |
| `archive-entry-pkos-timeline/manifest.json` | `pass` | Archive contains pkos-timeline/manifest.json |
| `archive-entry-pkos-timeline/agents/interface.yaml` | `pass` | Archive contains pkos-timeline/agents/interface.yaml |
| `archive-single-skill-entrypoint` | `pass` | Archive exposes only the root SKILL.md entrypoint |
| `archive-excludes-generated` | `pass` | Archive excludes local caches, platform noise, .yao state, external submission drafts, local evidence pointers, generated dist/, .previews/, and tests/tmp* contents |
| `archive-portable-evidence-index` | `pass` | Archive includes a self-contained portable evidence pointer and verified report index |

## Failures

- None

## Warnings

- Registry audit was not supplied; package verification skipped metadata parity checks.
