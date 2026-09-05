# Security Trust Report

- OK: `True`
- Scanned files: `4`
- Scripts: `1`
- Internal script modules: `0`
- Secret findings: `0`
- Network-capable scripts: `0`
- Network policy covered scripts: `0`
- Network policy missing scripts: `0`
- File-write scripts: `1`
- Permission approvals: `0 / 1`
- Permission approval gaps: `1`
- CLI help smoke checked: `1`
- CLI help smoke failures: `0`
- Interactive scripts: `0`
- Package hash scope: `source-contract-without-generated-reports`
- Package hash files: `4`
- Package SHA256: `0de09d9146c39f012e61399fe475fa66d7afc4df27477c4cb29069e8497aa8b1`

## Failures

- None

## Warnings

- No dependency or lock file detected
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
- Checked scripts: `1`
- Passed scripts: `1`
- Failed scripts: `none`

## Script Surface

| Script | Interface | Declared | Argparse | Main Guard | Input | Network | File Write | Subprocess | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| scripts\init_kb.py | cli | False | True | True | False | False | True | False | Default CLI classification; add SCRIPT_INTERFACE for internal modules. |
