# Security Trust Report

- OK: `True`
- Scanned files: `8`
- Scripts: `5`
- Internal script modules: `0`
- Secret findings: `0`
- Network-capable scripts: `0`
- Network policy covered scripts: `0`
- Network policy missing scripts: `0`
- File-write scripts: `3`
- Permission approvals: `0 / 1`
- Permission approval gaps: `1`
- CLI help smoke checked: `3`
- CLI help smoke failures: `0`
- Interactive scripts: `0`
- Package hash scope: `source-contract-without-generated-reports`
- Package hash files: `8`
- Package SHA256: `a552126149000d44b56aa024ec8945a0b2198ae70446d1a17bb961051147940d`

## Failures

- None

## Warnings

- No dependency or lock file detected
- CLI scripts without argparse/help surface: scripts\build_themes.py, scripts\lint_theme.py
- Permission approvals missing: file_write

## Dependency Evidence

- Files: `none`
- Pinned entries: `0`
- Unpinned entries: `0`

## Network Policy

- Policy file: `security/network_policy.json`
- Present: `False`
- Covered scripts: `0`
- Missing scripts: `none`
- Mismatches: `0`

## Permission Governance

- Policy file: `security/permission_policy.json`
- Present: `False`
- Required capabilities: `file_write`
- Approved capabilities: `none`
- Missing approvals: `file_write`
- Invalid approvals: `none`
- Expired approvals: `none`

## CLI Help Smoke

- Enabled: `True`
- Timeout seconds: `5.0`
- Checked scripts: `3`
- Passed scripts: `3`
- Failed scripts: `none`

## Script Surface

| Script | Interface | Declared | Argparse | Main Guard | Input | Network | File Write | Subprocess | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| scripts\build_themes.py | cli | False | False | True | False | False | True | False | Default CLI classification; add SCRIPT_INTERFACE for internal modules. |
| scripts\lint_theme.py | cli | False | False | True | False | False | False | False | Default CLI classification; add SCRIPT_INTERFACE for internal modules. |
| scripts\render.py | cli | False | True | True | False | False | True | False | Default CLI classification; add SCRIPT_INTERFACE for internal modules. |
| scripts\render_combined.py | cli | False | True | True | False | False | True | False | Default CLI classification; add SCRIPT_INTERFACE for internal modules. |
| scripts\validate_output.py | cli | False | True | True | False | False | False | False | Default CLI classification; add SCRIPT_INTERFACE for internal modules. |
