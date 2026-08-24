# Package Verification

- OK: `True`
- Package directory: `D:\deepseekharness\workspace\skills\personal-knowledge-os\pkos-ingest\dist`
- Targets: `1 / 1` adapters present
- Archive present: `True`
- Archive SHA256: `a5059142cc2dc1f76cda7cd1ee42d2fd333c88888d50c0c1df9d74ed610625a8`
- Nested SKILL.md entries: `0`
- Failures: `0`
- Warnings: `1`

## Checks

| Check | Status | Detail |
| --- | --- | --- |
| `package-manifest` | `pass` | Package manifest exists: D:\deepseekharness\workspace\skills\personal-knowledge-os\pkos-ingest\dist\manifest.json |
| `generic-adapter` | `pass` | Adapter exists for target: generic |
| `archive-safe-paths` | `pass` | Archive has no absolute or parent-traversal entries |
| `archive-entry-pkos-ingest/SKILL.md` | `pass` | Archive contains pkos-ingest/SKILL.md |
| `archive-entry-pkos-ingest/manifest.json` | `pass` | Archive contains pkos-ingest/manifest.json |
| `archive-entry-pkos-ingest/agents/interface.yaml` | `pass` | Archive contains pkos-ingest/agents/interface.yaml |
| `archive-single-skill-entrypoint` | `pass` | Archive exposes only the root SKILL.md entrypoint |
| `archive-excludes-generated` | `pass` | Archive excludes local caches, platform noise, .yao state, external submission drafts, local evidence pointers, generated dist/, .previews/, and tests/tmp* contents |
| `archive-portable-evidence-index` | `pass` | Archive includes a self-contained portable evidence pointer and verified report index |

## Failures

- None

## Warnings

- Registry audit was not supplied; package verification skipped metadata parity checks.
