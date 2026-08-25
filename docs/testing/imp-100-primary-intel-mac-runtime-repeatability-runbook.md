# IMP-100 — Primary Intel Mac local-runtime repeatability runbook

## Status

Preparation only. No repeatability/variance result is accepted by this document.

Do not perform the physical collection until the IMP-100 implementation PR is merged and the follow-up acceptance issue pins one exact approved `main` commit. If `main` advances after that pin, do not silently measure a different commit.

## What is measured

IMP-100 aggregates exactly three separately invoked IMP-098 real-machine reports for the same primary Intel Mac, local Ollama runtime, and exact local model revision.

The three generations already present inside one IMP-098 report are within-session samples. They do not replace the three separate measurement invocations required here.

This remains a warm/current-runtime measurement path. The harness does not restart Ollama, unload/reload the model, or define a cold-start test.

## Preconditions

1. The follow-up acceptance issue has pinned the exact commit SHA to measure.
2. Primary development Mac is Darwin Intel (`x86_64` / `amd64`).
3. The same already-installed local non-cloud Ollama text model is used for all three sessions.
4. Ollama is already running locally.
5. External networking is manually disabled for the full collection period.
6. The tracked checkout is clean and exactly at the pinned commit.
7. No cloud credential is provided to the measurement harness.
8. The operator does not install, pull, update, start, stop, or delete Ollama/models as part of this run.

## Collect three source sessions

From the pinned checkout, set the exact commit and the already-installed native model name locally. The native model name is used only by the local runner and is not written into shareable JSON.

```sh
COMMIT_SHA="<pinned-exact-commit>"
MODEL="<already-installed-local-model>"

uv run python scripts/run_imp_098_local_runtime_resource_measurement.py \
  --commit-sha "$COMMIT_SHA" \
  --evidence-level real-machine \
  --offline-confirmed \
  --local-only-confirmed \
  --model "$MODEL" \
  > ../imp100-session-1.json

uv run python scripts/run_imp_098_local_runtime_resource_measurement.py \
  --commit-sha "$COMMIT_SHA" \
  --evidence-level real-machine \
  --offline-confirmed \
  --local-only-confirmed \
  --model "$MODEL" \
  > ../imp100-session-2.json

uv run python scripts/run_imp_098_local_runtime_resource_measurement.py \
  --commit-sha "$COMMIT_SHA" \
  --evidence-level real-machine \
  --offline-confirmed \
  --local-only-confirmed \
  --model "$MODEL" \
  > ../imp100-session-3.json
```

Each command must exit zero. Do not edit a failed source report into a passing report.

## Manual privacy review of all three sources

Before aggregation, inspect the entire contents of all three source JSON files. Each must contain no:

- absolute local paths;
- usernames;
- hostnames;
- native model name;
- prompt or generated response text;
- process IDs or command lines;
- credentials or secret values;
- workspace or machine identifiers;
- URLs or email addresses.

If any unexpected private content is present, stop. Do not aggregate or upload the affected report.

## Validate each source

```sh
for FILE in \
  ../imp100-session-1.json \
  ../imp100-session-2.json \
  ../imp100-session-3.json
do
  uv run python scripts/validate_imp_098_local_runtime_resource_measurement.py \
    "$FILE" \
    --expected-commit-sha "$COMMIT_SHA" || exit 1
done
```

All three must pass independently.

## Build the repeatability report

Only after the three separate runner invocations and full source privacy review:

```sh
uv run python scripts/build_imp_100_runtime_repeatability_measurement.py \
  --source ../imp100-session-1.json \
  --source ../imp100-session-2.json \
  --source ../imp100-session-3.json \
  --expected-commit-sha "$COMMIT_SHA" \
  --independent-sessions-confirmed \
  --source-privacy-reviewed \
  > ../imp100-local-runtime-repeatability.json
```

The builder fails closed on a mixed commit, platform, Python version, runtime version, model identity/revision, model size, invalid source evidence, duplicate source bytes, or missing operator confirmation.

## Review and validate the aggregate

Manually inspect the entire aggregate JSON for the same privacy exclusions. Then run:

```sh
uv run python scripts/validate_imp_100_runtime_repeatability_measurement.py \
  ../imp100-local-runtime-repeatability.json \
  --expected-commit-sha "$COMMIT_SHA"
```

A passing aggregate still reports:

- `real_machine_repeatability_accepted = false`;
- `repeatability_variance_release_requirement_defined = false`;
- `full_lite_performance_thresholds_defined = false`;
- `phase6_gate_complete = false`;
- `lite_v1_complete = false`;
- `manual_privacy_review_required = true`.

Repository acceptance is a separate follow-up step.

## What this still does not prove

Even accepted repeatability evidence from this path will remain bounded to one primary Intel Mac and one exact local model/runtime identity. It does not by itself establish RAM, total-system/GPU/Metal memory, installation/model-storage, final user-visible latency, cold-start, cross-machine, default-model, accessibility, soak, Phase 6, or Lite v1.0 requirements.
