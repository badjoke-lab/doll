# IMP-098 — Primary Intel Mac local-runtime/model resource runbook

## Status

Preparation only. No real-machine result is accepted by this document.

The physical run must be performed only after the IMP-098 preparation PR is merged. Use the exact then-current approved `main` commit. Do not reuse an older SHA after `main` advances without first re-evaluating the target.

## What this run measures

The harness measures one explicitly selected, already-installed local Ollama text model on the primary Intel Mac through doll's existing fixed-loopback runtime path.

It records:

- local Ollama version;
- opaque Doll-facing model ID and exact model revision;
- provider-reported installed model bytes from local inventory;
- four sampled aggregate RSS values for the local Ollama listener process tree: one before generation and one after each of three fixed generations;
- corresponding runtime process counts without process IDs or command lines;
- doll-process RSS;
- three end-to-end generation durations;
- generated output character counts only.

The fixed fabricated prompt and generated text are never included in the shareable JSON.

This is not a cold-start measurement. The harness does not unload a model or restart Ollama.

## Preconditions

1. Primary development Mac is Darwin Intel (`x86_64` / `amd64`).
2. The selected Ollama model is already installed locally.
3. The selected model is a local text model, not an Ollama cloud model.
4. Ollama is already running on the local machine.
5. `lsof` and `ps` are available from the normal macOS environment.
6. No cloud credential is provided to the harness.
7. External networking is manually disabled for the measurement period.
8. The tracked checkout is clean.

The harness never installs, starts, stops, updates, pulls, or deletes Ollama or a model.

## Select the local model

Outside the shareable report, inspect the already-installed local models:

```sh
ollama list
```

Choose one already-installed general text model suitable for ordinary local conversation. Do not install a model merely to satisfy this run unless a separate project decision explicitly chooses to do so.

The native model name is passed only to the local command. The generated JSON stores an opaque model ID and revision instead.

## Physical run

From the repository:

```sh
git fetch origin
git checkout main
git pull --ff-only origin main
git status --short
uname -s
uname -m

COMMIT_SHA="$(git rev-parse HEAD)"
MODEL="<already-installed-local-model>"

uv run python scripts/run_imp_098_local_runtime_resource_measurement.py \
  --commit-sha "$COMMIT_SHA" \
  --evidence-level real-machine \
  --offline-confirmed \
  --local-only-confirmed \
  --model "$MODEL" \
  > ../imp098-local-runtime-resource-measurement.json
```

A non-zero exit is not acceptable evidence. Do not edit a failed result into a passing result.

## Manual privacy review

Before committing or uploading the JSON, inspect the entire file and confirm it contains no:

- absolute local paths;
- usernames;
- hostnames;
- native model name;
- prompt or generated response text;
- process IDs;
- process command lines;
- credentials or secret values;
- workspace or machine identifiers.

The report may contain the public-safe opaque model ID, model revision digest, runtime version, platform class, architecture, Python version, numeric resource measurements, and fixed non-claim flags.

If unexpected private content exists, do not commit or upload the result.

## Deterministic validation

After manual privacy review:

```sh
uv run python scripts/validate_imp_098_local_runtime_resource_measurement.py \
  ../imp098-local-runtime-resource-measurement.json \
  --expected-commit-sha "$COMMIT_SHA"
```

Accepted validation for collection must report:

- `result = pass`;
- exact commit binding;
- `evidence_level = real-machine`;
- `measurement_scope = doll-local-runtime-single-model`;
- repeat count `3`;
- `real_machine_measurement_accepted = false`;
- full Lite performance thresholds false;
- Phase 6 complete false;
- Lite v1.0 complete false;
- manual privacy review still required.

The `accepted = false` state is intentional. Physical collection and repository acceptance are separate steps.

## What this run still does not prove

Even a passing physical result does not by itself establish:

- minimum system RAM;
- continuous or total-system peak memory;
- exact GPU, Metal, or shared-memory requirements;
- full Lite installation/model-storage requirements across all supported models;
- final user-visible latency requirements;
- cold-start performance;
- cross-machine performance;
- supported/default model selection;
- complete Lite performance acceptance;
- accessibility acceptance;
- the release-candidate soak;
- Phase 6 completion;
- Lite v1.0 completion.

A separate evidence-acceptance PR is required after the physical JSON is reviewed and validated.
