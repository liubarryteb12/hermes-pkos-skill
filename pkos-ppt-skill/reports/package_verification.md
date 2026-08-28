# Package Verification

- OK: `True`
- Package directory: `D:\deepseekharness\workspace\skills\personal-knowledge-os\pkos-ppt\dist`
- Targets: `1 / 1` adapters present
- Archive present: `True`
- Archive SHA256: `fb5c997fc6e0cb6a9517b3da82b4d037f3a8d6cbdcff6ba8248c32d07f4554cc`
- Nested SKILL.md entries: `0`
- Failures: `0`
- Warnings: `1`

## Checks

| Check | Status | Detail |
| --- | --- | --- |
| `package-manifest` | `pass` | Package manifest exists: D:\deepseekharness\workspace\skills\personal-knowledge-os\pkos-ppt\dist\manifest.json |
| `generic-adapter` | `pass` | Adapter exists for target: generic |
| `archive-safe-paths` | `pass` | Archive has no absolute or parent-traversal entries |
| `archive-entry-pkos-ppt/SKILL.md` | `pass` | Archive contains pkos-ppt/SKILL.md |
| `archive-entry-pkos-ppt/manifest.json` | `pass` | Archive contains pkos-ppt/manifest.json |
| `archive-entry-pkos-ppt/agents/interface.yaml` | `pass` | Archive contains pkos-ppt/agents/interface.yaml |
| `archive-single-skill-entrypoint` | `pass` | Archive exposes only the root SKILL.md entrypoint |
| `archive-excludes-generated` | `pass` | Archive excludes local caches, platform noise, .yao state, external submission drafts, local evidence pointers, generated dist/, .previews/, and tests/tmp* contents |
| `archive-portable-evidence-index` | `pass` | Archive includes a self-contained portable evidence pointer and verified report index |

## Failures

- None

## Warnings

- Registry audit was not supplied; package verification skipped metadata parity checks.
