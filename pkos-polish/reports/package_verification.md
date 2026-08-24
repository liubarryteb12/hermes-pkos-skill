# Package Verification

- OK: `True`
- Package directory: `D:\deepseekharness\workspace\skills\personal-knowledge-os\pkos-polish\dist`
- Targets: `1 / 1` adapters present
- Archive present: `True`
- Archive SHA256: `c37a74ada675468ea3fb8de70814d169408529d0aeea27e8e379b497a6f98548`
- Nested SKILL.md entries: `0`
- Failures: `0`
- Warnings: `1`

## Checks

| Check | Status | Detail |
| --- | --- | --- |
| `package-manifest` | `pass` | Package manifest exists: D:\deepseekharness\workspace\skills\personal-knowledge-os\pkos-polish\dist\manifest.json |
| `generic-adapter` | `pass` | Adapter exists for target: generic |
| `archive-safe-paths` | `pass` | Archive has no absolute or parent-traversal entries |
| `archive-entry-pkos-polish/SKILL.md` | `pass` | Archive contains pkos-polish/SKILL.md |
| `archive-entry-pkos-polish/manifest.json` | `pass` | Archive contains pkos-polish/manifest.json |
| `archive-entry-pkos-polish/agents/interface.yaml` | `pass` | Archive contains pkos-polish/agents/interface.yaml |
| `archive-single-skill-entrypoint` | `pass` | Archive exposes only the root SKILL.md entrypoint |
| `archive-excludes-generated` | `pass` | Archive excludes local caches, platform noise, .yao state, external submission drafts, local evidence pointers, generated dist/, .previews/, and tests/tmp* contents |
| `archive-portable-evidence-index` | `pass` | Archive includes a self-contained portable evidence pointer and verified report index |

## Failures

- None

## Warnings

- Registry audit was not supplied; package verification skipped metadata parity checks.
