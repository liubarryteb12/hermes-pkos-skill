# Install Simulation

- OK: `False`
- Package directory: `D:\deepseekharness\workspace\skills\dist\pkos-v0.0.1-packages\pkos-audit`
- Archive extracted: `True`
- Nested SKILL.md entries: `0`
- Entrypoint loaded: `True`
- Manifest loaded: `True`
- Interface loaded: `True`
- Adapters readable: `1`
- Installer permissions enforced: `0`
- Installer permission failures: `3`
- Failures: `3`
- Warnings: `0`

## Checks

| Check | Status | Detail |
| --- | --- | --- |
| `archive-present` | `pass` | Package archive exists: D:\deepseekharness\workspace\skills\dist\pkos-v0.0.1-packages\pkos-audit\pkos-audit.zip |
| `archive-safe-paths` | `pass` | Archive has no absolute or parent-traversal entries |
| `single-skill-entrypoint` | `pass` | Installed package exposes only the root SKILL.md entrypoint |
| `single-top-level` | `pass` | Archive top-level directory is pkos-audit |
| `entrypoint-load` | `pass` | Installed SKILL.md frontmatter is readable |
| `entrypoint-name` | `pass` | Installed SKILL.md name matches package directory |
| `entrypoint-description` | `pass` | Installed SKILL.md description is present |
| `manifest-load` | `pass` | Installed manifest.json is readable |
| `manifest-name` | `pass` | Installed manifest name matches package manifest |
| `manifest-version` | `pass` | Installed manifest version matches package manifest |
| `interface-load` | `pass` | Installed agents/interface.yaml is readable |
| `overview-report` | `pass` | Installed overview report is present |
| `review-studio-report` | `pass` | Installed Review Studio report is present |
| `adapter-generic` | `pass` | generic adapter is readable after package install simulation |
| `adapter-generic-name` | `pass` | generic adapter name matches package manifest |
| `permission-policy-load` | `fail` | Installed permission policy is readable |
| `permission-generic-contract` | `pass` | generic adapter exposes target permission contract for installer enforcement |
| `permission-generic-file_write-approved` | `fail` | generic capability file_write has active reviewer approval |
| `permission-generic-file_write-target-enforcement` | `fail` | generic capability file_write has target enforcement note |

## Failures

- Installed permission policy is readable
- generic capability file_write has active reviewer approval
- generic capability file_write has target enforcement note

## Warnings

- None
