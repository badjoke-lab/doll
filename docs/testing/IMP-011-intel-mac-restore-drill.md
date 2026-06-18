# IMP-011 Intel Mac Restore Drill

**Status:** Required before IMP-011 merge  
**Evidence level:** Real machine / real process  
**Target:** Primary Intel Mac

## Purpose

This drill proves that both supported backup kinds can be restored on the primary Intel Mac without a model runtime, cloud credentials, or network access.

The drill creates only synthetic temporary state and removes its temporary workspace when complete. Its JSON report contains no absolute paths, username, hostname, secret value, or private source content.

## Preconditions

1. Check out the exact PR #34 head to be evaluated.
2. Install the locked development environment with `uv sync --frozen`.
3. Disable Wi-Fi, Ethernet, VPN, and any other network connection.
4. Confirm that no cloud credential or model runtime is required for the commands below.
5. Record the exact 40-character commit SHA.

## Command

Run from the repository root, replacing the placeholder with the exact commit SHA:

```text
uv run python scripts/run_imp_011_intel_mac_drill.py \
  --commit-sha 0000000000000000000000000000000000000000 \
  --offline-confirmed \
  > imp-011-intel-mac-restore-drill.json
```

Then confirm the command succeeded:

```text
echo $?
```

The exit code must be `0`.

## Required report checks

The JSON report must contain:

- `test_id` equal to `IMP-011-INTEL-MAC-RESTORE-DRILL`;
- `result` equal to `pass`;
- the exact evaluated commit SHA;
- `evidence_level` equal to `real-machine`;
- `operating_system` equal to `Darwin`;
- Intel architecture reported as `x86_64` or `amd64`;
- `network_mode` equal to `disabled-confirmed-by-operator`;
- `model_runtime_used` equal to `false`;
- `cloud_credentials_used` equal to `false`;
- every entry under `checks` equal to `true`;
- state restore revision equal to the state-backup source revision plus one;
- workspace restore revision equal to the workspace-backup source revision;
- privacy flags all indicating that private environment data is absent.

## Evidence handling

Attach the generated JSON file to PR #34 or paste its complete one-line JSON content into a PR comment.

Do not attach temporary workspaces, backup archives, local configuration, home-directory paths, terminal history, credentials, or unrelated diagnostics.

## Failure handling

A nonzero exit code or `result: fail` blocks the merge.

Record only the error class shown by the script. Do not paste private paths or local environment details. Fix the implementation or drill environment, rerun from a clean checkout of the same commit, and retain only the passing report used for the merge decision.
