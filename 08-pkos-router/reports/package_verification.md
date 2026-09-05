# Package Verification

- OK: `True`
- Package directory: `D:\deepseekharness\workspace\skills\personal-knowledge-os\08-pkos-router\dist`
- Targets: `1 / 1` adapters present
- Archive present: `True`
- Archive SHA256: `91d1ed8b8a73a71476815af66f33ec38c1c8014c7bc9e4084e9bdad4ed42fc6a`
- Nested SKILL.md entries: `0`
- Failures: `0`
- Warnings: `1`

## Checks

| Check | Status | Detail |
| --- | --- | --- |
| `package-manifest` | `pass` | Package manifest exists: D:\deepseekharness\workspace\skills\personal-knowledge-os\08-pkos-router\dist\manifest.json |
| `generic-adapter` | `pass` | Adapter exists for target: generic |
| `archive-safe-paths` | `pass` | Archive has no absolute or parent-traversal entries |
| `archive-entry-08-pkos-router/SKILL.md` | `pass` | Archive contains 08-pkos-router/SKILL.md |
| `archive-entry-08-pkos-router/manifest.json` | `pass` | Archive contains 08-pkos-router/manifest.json |
| `archive-entry-08-pkos-router/agents/interface.yaml` | `pass` | Archive contains 08-pkos-router/agents/interface.yaml |
| `archive-single-skill-entrypoint` | `pass` | Archive exposes only the root SKILL.md entrypoint |
| `archive-excludes-generated` | `pass` | Archive excludes local caches, platform noise, .yao state, external submission drafts, local evidence pointers, generated dist/, .previews/, and tests/tmp* contents |
| `archive-portable-evidence-index` | `pass` | Archive includes a self-contained portable evidence pointer and verified report index |

## Failures

- None

## Warnings

- Registry audit was not supplied; package verification skipped metadata parity checks.
