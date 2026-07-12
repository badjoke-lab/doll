# IMP-062 primary Intel Mac real-machine runbook

## Purpose

Execute the bounded IMP-062 real-machine acceptance after its implementation pull request has merged.

This runbook uses a deterministic non-private synthetic ChatGPT-format source. It does not use personal ChatGPT history, personal Ollama history, or private conversation content.

The result must remain outside the repository until manual privacy review is complete.

## Preconditions

Do not run this drill until all of the following are true:

- the IMP-062 implementation pull request is merged;
- the local checkout is on the exact merged `main` commit;
- the checkout has no uncommitted changes;
- the machine is Darwin on Intel;
- networking has been disabled and this has been confirmed by the operator;
- Ollama is already installed and running locally;
- at least one suitable local model is already installed;
- no model installation, model download, runtime installation, or process launch is required by the drill.

The acceptance runner does not disable networking itself. The `--offline-confirmed` flag records an operator confirmation and must not be used while networking is enabled.

## 1. Synchronize the exact implementation commit

```bash
cd ~/doll

git switch main
git pull --ff-only origin main

git status --short --branch
git rev-parse HEAD
uname -s
uname -m
```

Required state:

- branch is `main`;
- `main` matches `origin/main`;
- there are no modified or untracked repository files;
- operating system is `Darwin`;
- architecture is `x86_64` or `amd64`.

## 2. Confirm the local Ollama model

List the already-installed local models:

```bash
ollama list
```

Enter the exact chosen model name without placing the name directly in shell history:

```bash
printf "Exact installed Ollama model name: "
IFS= read -r MODEL

test -n "$MODEL"
```

The runner does not install or download the model.

## 3. Create an evidence location outside the repository

```bash
EVIDENCE_DIR="$(
  mktemp -d \
    "${TMPDIR:-/tmp}/doll-imp062-evidence.XXXXXX"
)"

RESULT="$EVIDENCE_DIR/result.json"
COMMIT="$(git rev-parse HEAD)"

printf "Evidence directory: %s\n" "$EVIDENCE_DIR"
printf "Exact commit: %s\n" "$COMMIT"
```

Do not place `RESULT` inside the doll repository.

## 4. Disable networking and confirm local-only operation

Disable networking through the operating system before running the command.

Confirm that:

- Wi-Fi and other external network paths are disabled;
- no VPN or remote tunnel is active;
- Ollama remains available only through fixed IPv4 loopback;
- the selected model already exists locally;
- no cloud credential is required.

## 5. Execute the exact-commit drill

```bash
uv run python \
  scripts/run_imp_062_imported_context_replay.py \
  --commit-sha "$COMMIT" \
  --evidence-level real-machine \
  --offline-confirmed \
  --local-only-confirmed \
  --model "$MODEL" \
  > "$RESULT"

STATUS="$?"

unset MODEL

printf "Runner exit status: %s\n" "$STATUS"
printf "Result file: %s\n" "$RESULT"

test "$STATUS" -eq 0
```

The model name is consumed by the process but is not included in the result report.

## 6. Validate the content-free result

```bash
uv run python - "$RESULT" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))

checks = payload.get("checks")
privacy = payload.get("privacy")
evidence = payload.get("evidence")

assert payload.get("result") == "pass"
assert payload.get("evidence_level") == "real-machine"
assert payload.get("operating_system") == "Darwin"
assert payload.get("architecture") in {"x86_64", "amd64"}
assert payload.get("network_mode") == "offline-confirmed"
assert payload.get("real_runtime_used") is True
assert payload.get("external_network_request_used") is False
assert payload.get("cloud_credentials_used") is False
assert payload.get("model_download_used") is False
assert payload.get("runtime_installation_used") is False
assert payload.get("process_launch_used") is False
assert payload.get("tool_execution_used") is False
assert payload.get("capability_execution_used") is False
assert payload.get("context_replay_real_machine_gate") == "pass"
assert payload.get("context_replay_extension_complete") is True
assert payload.get("phase6_gate_complete") is False
assert payload.get("stable_anti_lock_in_claim") is False

assert isinstance(checks, dict) and checks and all(checks.values())
assert isinstance(privacy, dict) and privacy and not any(privacy.values())
assert isinstance(evidence, dict)
assert evidence.get("runtime_mode") == "real-local"
assert evidence.get("selected_event_count") == 2
assert evidence.get("context_instruction_count") == 2
assert evidence.get("target_event_count") == 3
assert evidence.get("authority_record_count") == 0
assert evidence.get("runtime_request_count", 0) >= 4
assert evidence.get("allowed_loopback_socket_attempts", 0) > 0
assert evidence.get("rejected_socket_attempts") == 0

print(json.dumps({
    "result": payload["result"],
    "commit_sha": payload["commit_sha"],
    "operating_system": payload["operating_system"],
    "architecture": payload["architecture"],
    "network_mode": payload["network_mode"],
    "checks_passed": len(checks),
    "privacy_flags_set": sum(value is True for value in privacy.values()),
    "selected_event_count": evidence["selected_event_count"],
    "context_instruction_count": evidence["context_instruction_count"],
    "target_event_count": evidence["target_event_count"],
    "runtime_request_count": evidence["runtime_request_count"],
    "allowed_loopback_socket_attempts": evidence["allowed_loopback_socket_attempts"],
    "rejected_socket_attempts": evidence["rejected_socket_attempts"],
    "phase6_gate_complete": payload["phase6_gate_complete"],
    "stable_anti_lock_in_claim": payload["stable_anti_lock_in_claim"],
}, indent=2, sort_keys=True))
PY
```

## 7. Manual privacy review

Before creating any completion pull request, inspect the JSON and confirm that it contains none of the following:

- native model names;
- source text;
- prompt text;
- model response text;
- source-native conversation or message identifiers;
- absolute paths;
- usernames;
- hostnames;
- account identifiers;
- credentials;
- secret values.

Do not commit the raw result merely because the automated privacy booleans are false. Human review is still required.

A later completion pull request must:

- bind the result to the exact merged IMP-062 implementation commit;
- store only privacy-safe content-free evidence;
- change the context replay extension from `ci-pass` to `pass`;
- add `real-machine` to its accepted evidence levels;
- keep `phase6_gate_complete` false;
- keep `stable_anti_lock_in_claim` false.

## Failure handling

When the runner fails:

- preserve the result outside the repository;
- use only `error_stage` and `error_class` for diagnosis;
- do not add prompt, response, model name, or private source text to the report;
- do not weaken exact-commit, platform, offline, loopback, privacy, authority, or evidence checks;
- do not rerun with networking enabled;
- do not claim real-machine completion.

## Non-claims

A passing result proves only the bounded exact-commit IMP-061 replay path from a deterministic synthetic ChatGPT-format imported source to one explicitly selected already-installed local Ollama model on the primary Intel Mac.

It does not prove native history discovery, automatic retrieval, semantic search, attachments, multimodal fidelity, tools, target-specific export, provider round trips, complete application replacement, the complete Phase 6 gate, or stable general anti-lock-in.
