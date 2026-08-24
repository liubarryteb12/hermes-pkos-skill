# Package Verification

- OK: `True`
- Package directory: `D:\deepseekharness\workspace\skills\personal-knowledge-os\pkos-html\dist`
- Targets: `1 / 1` adapters present
- Archive present: `True`
- Archive SHA256: `2b0bd0253b48c5b223ab480ddc411a2b8141ec2e0fd077f4458f0394267c5a9d`
- Nested SKILL.md entries: `0`
- Failures: `0`
- Warnings: `1`

## Checks

| Check | Status | Detail |
| --- | --- | --- |
| `package-manifest` | `pass` | Package manifest exists: D:\deepseekharness\workspace\skills\personal-knowledge-os\pkos-html\dist\manifest.json |
| `generic-adapter` | `pass` | Adapter exists for target: generic |
| `archive-safe-paths` | `pass` | Archive has no absolute or parent-traversal entries |
| `archive-entry-pkos-html/SKILL.md` | `pass` | Archive contains pkos-html/SKILL.md |
| `archive-entry-pkos-html/manifest.json` | `pass` | Archive contains pkos-html/manifest.json |
| `archive-entry-pkos-html/agents/interface.yaml` | `pass` | Archive contains pkos-html/agents/interface.yaml |
| `archive-single-skill-entrypoint` | `pass` | Archive exposes only the root SKILL.md entrypoint |
| `archive-excludes-generated` | `pass` | Archive excludes local caches, platform noise, .yao state, external submission drafts, local evidence pointers, generated dist/, .previews/, and tests/tmp* contents |
| `archive-portable-evidence-index` | `pass` | Archive includes a self-contained portable evidence pointer and verified report index |

## Failures

- None

## Warnings

- Registry audit was not supplied; package verification skipped metadata parity checks.
