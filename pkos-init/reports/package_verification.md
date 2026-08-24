# Package Verification

- OK: `True`
- Package directory: `D:\deepseekharness\workspace\skills\personal-knowledge-os\pkos-init\dist`
- Targets: `1 / 1` adapters present
- Archive present: `True`
- Archive SHA256: `be67a9dbe8605539c090a09bfe6ca5f00ff1f19f73c718d2d5072caab68cf1fb`
- Nested SKILL.md entries: `0`
- Failures: `0`
- Warnings: `1`

## Checks

| Check | Status | Detail |
| --- | --- | --- |
| `package-manifest` | `pass` | Package manifest exists: D:\deepseekharness\workspace\skills\personal-knowledge-os\pkos-init\dist\manifest.json |
| `generic-adapter` | `pass` | Adapter exists for target: generic |
| `archive-safe-paths` | `pass` | Archive has no absolute or parent-traversal entries |
| `archive-entry-pkos-init/SKILL.md` | `pass` | Archive contains pkos-init/SKILL.md |
| `archive-entry-pkos-init/manifest.json` | `pass` | Archive contains pkos-init/manifest.json |
| `archive-entry-pkos-init/agents/interface.yaml` | `pass` | Archive contains pkos-init/agents/interface.yaml |
| `archive-single-skill-entrypoint` | `pass` | Archive exposes only the root SKILL.md entrypoint |
| `archive-excludes-generated` | `pass` | Archive excludes local caches, platform noise, .yao state, external submission drafts, local evidence pointers, generated dist/, .previews/, and tests/tmp* contents |
| `archive-portable-evidence-index` | `pass` | Archive includes a self-contained portable evidence pointer and verified report index |

## Failures

- None

## Warnings

- Registry audit was not supplied; package verification skipped metadata parity checks.
