# IMP-064 primary Intel Mac local-writing runbook

## Purpose

Run the bounded IMP-063 local-writing workflow through one already-installed local Ollama model on the primary Intel Mac and produce a content-free IMP-064 result for later privacy review.

This runbook does not accept evidence by itself. The result must be reviewed and committed through a separate completion pull request.

The drill requires networking operator-confirmed disabled. The runner writes the result outside the repository and requires manual privacy review before acceptance.

## Required conditions

Before starting:

- the IMP-064 implementation pull request has been merged;
- the checkout is the exact merged implementation commit;
- `git status --porcelain` is empty;
- the machine reports `Darwin` and `x86_64` or `amd64`;
- Ollama is already installed and running;
- at least one suitable local model is already installed;
- no runtime or model installation or download will occur during the drill;
- no cloud provider, provider account, credential, VPN, proxy, or remote model is used;
- the result destination is outside the repository and outside the doll workspace.

## Privacy boundary

The runner uses deterministic non-private writing requests and source material.

The result must not contain:

- a native model name;
- request text;
- source text;
- prompt text;
- model response text;
- conversation titles or source identifiers;
- an absolute path;
- a username;
- a hostname;
- a credential;
- a secret value;
- private fixture content.

The selected model name is supplied interactively and is not written into the result.

## Execution

First synchronize the exact merged implementation commit while networking is still available:

```bash
cd ~/doll

git switch main
git pull --ff-only origin main

git status --short --branch
git rev-parse HEAD
uname -s
uname -m
ollama list
```

Record the exact merged implementation commit shown by `git rev-parse HEAD`.

Create an external result location:

```bash
EVIDENCE_DIR="$(
  mktemp -d \
    "${TMPDIR:-/tmp}/doll-imp064-evidence.XXXXXX"
)"
RESULT="$EVIDENCE_DIR/result.json"
```

Read the model name without placing it directly in the command line:

```bash
printf "Enter the exact installed Ollama model name: "
IFS= read -r MODEL

test -n "$MODEL"

ollama list \
  | awk 'NR > 1 {print $1}' \
  | grep -Fx -- "$MODEL" \
  >/dev/null
```

Disable Wi-Fi, VPN, and every other external network path manually. Keep the already-running local Ollama service available.

Confirm that the checkout is clean and bind the run to the exact merged commit:

```bash
COMMIT="$(git rev-parse HEAD)"
test -z "$(git status --porcelain)"
```

Run the acceptance:

```bash
uv run python \
  scripts/run_imp_064_local_writing.py \
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

Re-enable networking only after the runner has exited.

## Required result checks

The JSON result must satisfy all of the following:

```text
result = pass
evidence_level = real-machine
operating_system = Darwin
architecture = x86_64 or amd64
network_mode = offline-confirmed
real_runtime_used = true
external_network_request_used = false
cloud_credentials_used = false
model_download_used = false
runtime_installation_used = false
process_launch_used = false
tool_execution_used = false
capability_execution_used = false
writing_workflow_real_machine_gate = pass
local_writing_workflow_complete = true
phase6_gate_complete = false
stable_anti_lock_in_claim = false
```

Every value in `checks` must be `true`.

Every value in `privacy` must be `false`.

The evidence must also show:

```text
runtime_mode = real-local
workflow_mode_count = 3
completed_workflow_count = 3
source_instruction_count_total = 2
prompt_untrusted_counts = [0, 1, 1]
prompt_injection_finding_count >= 1
secret_redaction_count = 0
target_event_count = 9
runtime_request_count >= 8
allowed_loopback_socket_attempts > 0
rejected_socket_attempts = 0
authority_record_count = 0
```

## Manual privacy review

Open the result locally and verify that it contains only:

- fixed field names;
- booleans;
- bounded counts;
- platform facts;
- timestamps;
- the exact implementation commit;
- opaque hashes;
- documented limitations and non-claim flags.

Do not commit the file when any native model name, writing content, prompt content, response content, local path, username, hostname, credential, secret, or private material appears.

## Separate evidence acceptance

After privacy review:

1. open a separate completion issue or evidence issue;
2. create a new branch from the current `main`;
3. add only the reviewed content-free result under `docs/testing/results/`;
4. bind the matrix gate to the exact implementation commit and completion timestamp;
5. promote the bounded workflow from `ci-pass` to `pass` at `ci` and `real-machine` evidence levels;
6. keep `phase6_gate_complete = false`;
7. keep `stable_anti_lock_in_claim = false`;
8. run the focused acceptance, related tests, quality checks, public-status check, generated-specification check, and full CI before merge.

## Non-claims

A passing IMP-064 result does not establish personal writing quality, automatic retrieval, memory or project context selection, translation, attachments, multimodal input, streaming workflow output, tools, cloud fallback, target-specific export, complete Phase 6, or stable general anti-lock-in.
