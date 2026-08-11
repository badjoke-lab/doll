# IMP-083 primary Intel Mac Lite client measurement runbook

## Purpose

Run the exact IMP-083 doll-client-only resource measurement on the primary Intel Mac after the implementation commit is fixed. This runbook does not measure Ollama, model weights, GPU memory, model latency, or total-system resource use.

## Preconditions

- use the primary development Mac;
- operating system reports Darwin;
- architecture reports `x86_64` or `amd64`;
- check out the exact implementation commit to be measured;
- tracked index must match HEAD and the tracked working tree must match the index;
- untracked evidence output is permitted, so the JSON redirection below does not invalidate the tracked-source guard;
- networking is manually disabled for the measurement run;
- no cloud credential is required;
- no Ollama process or model is required by this measurement;
- run from the repository root with the locked project environment available.

## Command

Record the exact checked-out commit, then run:

```bash
COMMIT_SHA="$(git rev-parse HEAD)"
uv run python scripts/run_imp_083_lite_client_measurement.py \
  --commit-sha "$COMMIT_SHA" \
  --evidence-level real-machine \
  --offline-confirmed \
  --local-only-confirmed \
  > imp083-lite-client-measurement.json
```

The runner independently checks that `--commit-sha` matches the current checkout, rejects staged or unstaged tracked changes before measurement, and rejects real-machine evidence on non-Darwin or non-Intel architectures.

## Expected result

The JSON result must have:

- `result = "pass"`;
- `evidence_level = "real-machine"`;
- `network_mode = "offline-confirmed"`;
- all `checks` equal to `true`;
- fixed five-step measurement order;
- non-negative timing values;
- positive workspace byte/file/directory counts;
- process peak RSS available and non-negative;
- `measured_workload_network_attempt_count = 0`;
- `measured_workload_process_attempt_count = 0`;
- `performance_thresholds_defined = false`;
- `external_runtime_memory_measured = false`;
- `model_memory_measured = false`;
- `lite_performance_gate_complete = false`;
- `phase6_gate_complete = false`;
- `lite_v1_complete = false`;
- every privacy flag equal to `false`.

## Evidence handling

Before committing any real-machine result, inspect the JSON manually for privacy. Do not commit a result containing an absolute path, username, hostname, workspace identifier, private fixture content, model name, request/source text, credential, or secret.

A successful run establishes one exact-machine doll-client overhead measurement only. It does not by itself define minimum hardware requirements or complete Lite performance acceptance. Measurement interpretation and thresholds require a separate controlled implementation after enough evidence exists.
