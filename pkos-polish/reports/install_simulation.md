# Install Simulation

- OK: `False`
- Package directory: `D:\deepseekharness\workspace\skills\dist\pkos-v0.0.1-packages\pkos-polish`
- Archive extracted: `True`
- Nested SKILL.md entries: `0`
- Entrypoint loaded: `True`
- Manifest loaded: `True`
- Interface loaded: `True`
- Adapters readable: `1`
- Installer permissions enforced: `0`
- Installer permission failures: `1`
- Failures: `3`
- Warnings: `0`

## Checks

| Check | Status | Detail |
| --- | --- | --- |
| `archive-present` | `pass` | Package archive exists: D:\deepseekharness\workspace\skills\dist\pkos-v0.0.1-packages\pkos-polish\pkos-polish.zip |
| `archive-safe-paths` | `pass` | Archive has no absolute or parent-traversal entries |
| `single-skill-entrypoint` | `pass` | Installed package exposes only the root SKILL.md entrypoint |
| `single-top-level` | `pass` | Archive top-level directory is pkos-polish |
| `entrypoint-load` | `pass` | Installed SKILL.md frontmatter is readable |
| `entrypoint-name` | `pass` | Installed SKILL.md name matches package directory |
| `entrypoint-description` | `pass` | Installed SKILL.md description is present |
| `manifest-load` | `pass` | Installed manifest.json is readable |
| `manifest-name` | `pass` | Installed manifest name matches package manifest |
| `manifest-version` | `pass` | Installed manifest version matches package manifest |
| `interface-load` | `pass` | Installed agents/interface.yaml is readable |
| `overview-report` | `fail` | Installed overview report is present |
| `review-studio-report` | `fail` | Installed Review Studio report is present |
| `adapter-generic` | `pass` | generic adapter is readable after package install simulation |
| `adapter-generic-name` | `pass` | generic adapter name matches package manifest |
| `permission-policy-load` | `fail` | Installed permission policy is readable |
| `permission-generic-contract` | `pass` | generic adapter exposes target permission contract for installer enforcement |

## Failures

- Installed overview report is present
- Installed Review Studio report is present
- Installed permission policy is readable

## Warnings

- None
