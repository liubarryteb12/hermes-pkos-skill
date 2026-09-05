# Package Verification

- OK: `True`
- Package directory: `D:\deepseekharness\workspace\skills\personal-knowledge-os\06-pkos-polish\dist`
- Targets: `1 / 1` adapters present
- Archive present: `True`
- Archive SHA256: `6476a868644d464aa0aa0ab90f8e44a6b2f93bc1e608784fd6f0ca850a4118fe`
- Nested SKILL.md entries: `0`
- Failures: `0`
- Warnings: `1`

## Checks

| Check | Status | Detail |
| --- | --- | --- |
| `package-manifest` | `pass` | Package manifest exists: D:\deepseekharness\workspace\skills\personal-knowledge-os\06-pkos-polish\dist\manifest.json |
| `generic-adapter` | `pass` | Adapter exists for target: generic |
| `archive-safe-paths` | `pass` | Archive has no absolute or parent-traversal entries |
| `archive-entry-06-pkos-polish/SKILL.md` | `pass` | Archive contains 06-pkos-polish/SKILL.md |
| `archive-entry-06-pkos-polish/manifest.json` | `pass` | Archive contains 06-pkos-polish/manifest.json |
| `archive-entry-06-pkos-polish/agents/interface.yaml` | `pass` | Archive contains 06-pkos-polish/agents/interface.yaml |
| `archive-single-skill-entrypoint` | `pass` | Archive exposes only the root SKILL.md entrypoint |
| `archive-excludes-generated` | `pass` | Archive excludes local caches, platform noise, .yao state, external submission drafts, local evidence pointers, generated dist/, .previews/, and tests/tmp* contents |
| `archive-portable-evidence-index` | `pass` | Archive includes a self-contained portable evidence pointer and verified report index |

## Failures

- None

## Warnings

- Registry audit was not supplied; package verification skipped metadata parity checks.
