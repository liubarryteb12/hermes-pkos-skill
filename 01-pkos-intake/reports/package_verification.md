# Package Verification

- OK: `True`
- Package directory: `D:\deepseekharness\workspace\skills\personal-knowledge-os\01-pkos-intake\dist`
- Targets: `1 / 1` adapters present
- Archive present: `True`
- Archive SHA256: `1df976978adb938cf65c368338c6f875cf06d04b790d72a3193944d29d28b9e4`
- Nested SKILL.md entries: `0`
- Failures: `0`
- Warnings: `1`

## Checks

| Check | Status | Detail |
| --- | --- | --- |
| `package-manifest` | `pass` | Package manifest exists: D:\deepseekharness\workspace\skills\personal-knowledge-os\01-pkos-intake\dist\manifest.json |
| `generic-adapter` | `pass` | Adapter exists for target: generic |
| `archive-safe-paths` | `pass` | Archive has no absolute or parent-traversal entries |
| `archive-entry-01-pkos-intake/SKILL.md` | `pass` | Archive contains 01-pkos-intake/SKILL.md |
| `archive-entry-01-pkos-intake/manifest.json` | `pass` | Archive contains 01-pkos-intake/manifest.json |
| `archive-entry-01-pkos-intake/agents/interface.yaml` | `pass` | Archive contains 01-pkos-intake/agents/interface.yaml |
| `archive-single-skill-entrypoint` | `pass` | Archive exposes only the root SKILL.md entrypoint |
| `archive-excludes-generated` | `pass` | Archive excludes local caches, platform noise, .yao state, external submission drafts, local evidence pointers, generated dist/, .previews/, and tests/tmp* contents |
| `archive-portable-evidence-index` | `pass` | Archive includes a self-contained portable evidence pointer and verified report index |

## Failures

- None

## Warnings

- Registry audit was not supplied; package verification skipped metadata parity checks.
