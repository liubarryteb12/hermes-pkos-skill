# Package Verification

- OK: `True`
- Package directory: `D:\deepseekharness\workspace\skills\personal-knowledge-os\05-pkos-analysis\dist`
- Targets: `1 / 1` adapters present
- Archive present: `True`
- Archive SHA256: `cf0bdc7ce6f83a81c081b670b8fe655aa45b65916232cb782bb02efc786ee202`
- Nested SKILL.md entries: `0`
- Failures: `0`
- Warnings: `1`

## Checks

| Check | Status | Detail |
| --- | --- | --- |
| `package-manifest` | `pass` | Package manifest exists: D:\deepseekharness\workspace\skills\personal-knowledge-os\05-pkos-analysis\dist\manifest.json |
| `generic-adapter` | `pass` | Adapter exists for target: generic |
| `archive-safe-paths` | `pass` | Archive has no absolute or parent-traversal entries |
| `archive-entry-05-pkos-analysis/SKILL.md` | `pass` | Archive contains 05-pkos-analysis/SKILL.md |
| `archive-entry-05-pkos-analysis/manifest.json` | `pass` | Archive contains 05-pkos-analysis/manifest.json |
| `archive-entry-05-pkos-analysis/agents/interface.yaml` | `pass` | Archive contains 05-pkos-analysis/agents/interface.yaml |
| `archive-single-skill-entrypoint` | `pass` | Archive exposes only the root SKILL.md entrypoint |
| `archive-excludes-generated` | `pass` | Archive excludes local caches, platform noise, .yao state, external submission drafts, local evidence pointers, generated dist/, .previews/, and tests/tmp* contents |
| `archive-portable-evidence-index` | `pass` | Archive includes a self-contained portable evidence pointer and verified report index |

## Failures

- None

## Warnings

- Registry audit was not supplied; package verification skipped metadata parity checks.
