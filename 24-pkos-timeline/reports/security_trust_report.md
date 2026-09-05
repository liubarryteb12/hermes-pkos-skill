# Security Trust Report

- OK: `True`
- Scanned files: `4`
- Scripts: `1`
- Internal script modules: `0`
- Secret findings: `0`
- Network-capable scripts: `0`
- Network policy covered scripts: `0`
- Network policy missing scripts: `0`
- File-write scripts: `0`
- Permission approvals: `0 / 0`
- Permission approval gaps: `0`
- CLI help smoke checked: `1`
- CLI help smoke failures: `0`
- Interactive scripts: `0`
- Package hash scope: `source-contract-without-generated-reports`
- Package hash files: `4`
- Package SHA256: `67b0b2873939791bfa7997bc2b65bee1f9dbe22bd3100d8942db03d1b8551f81`

## Failures

- None

## Warnings

- No dependency or lock file detected

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
- Required capabilities: `none`
- Approved capabilities: `none`
- Missing approvals: `none`
- Invalid approvals: `none`
- Expired approvals: `none`

## CLI Help Smoke

- Enabled: `True`
- Timeout seconds: `5.0`
- Checked scripts: `1`
- Passed scripts: `1`
- Failed scripts: `none`

## Script Surface

| Script | Interface | Declared | Argparse | Main Guard | Input | Network | File Write | Subprocess | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| scripts\build_timeline.py | cli | False | True | True | False | False | False | False | Default CLI classification; add SCRIPT_INTERFACE for internal modules. |
