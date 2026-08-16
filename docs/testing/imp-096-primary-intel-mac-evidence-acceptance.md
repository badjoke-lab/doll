# IMP-096 primary Intel Mac evidence acceptance

Status: preparation for Issue #297; this document does not contain or claim real-machine evidence.

## Purpose

IMP-096 accepts one privacy-reviewed primary Intel Mac result from the already-implemented IMP-083 Lite client measurement harness. The validator added in this preparation slice makes the evidence contract deterministic before the physical-machine run occurs.

This preparation must be merged **before** the accepted measurement is collected. The later measurement therefore binds to one exact main commit that already contains both the runner and its evidence validator.

## Sequence

### 1. Merge the preparation slice

Merge the validator and its tests without closing Issue #297. No real-machine evidence exists at this point.

### 2. On the primary Intel Mac, update to the exact accepted main commit

Use the existing repository and verify that the tracked checkout is clean. Do not make local source edits for the measurement.

Record the commit that will be measured:

```sh
COMMIT_SHA="$(git rev-parse HEAD)"
printf '%s\n' "$COMMIT_SHA"
```

The runner independently verifies that the supplied SHA is the current `HEAD` and that the tracked index/worktree is clean.

### 3. Establish the runbook environment manually

Before running the measurement:

- confirm `uname -s` is `Darwin`;
- confirm `uname -m` is `x86_64` or `amd64`;
- manually disable network connectivity;
- do not provide cloud credentials;
- do not start Ollama or another model/runtime for this measurement;
- keep the output path outside tracked repository content.

These are operator facts. A command-line flag records the confirmation but cannot prove that the physical network was actually disabled.

### 4. Run the existing IMP-083 measurement once

From the clean measured checkout:

```sh
uv run python scripts/run_imp_083_lite_client_measurement.py \
  --commit-sha "$COMMIT_SHA" \
  --evidence-level real-machine \
  --offline-confirmed \
  --local-only-confirmed \
  > ../imp096-lite-client-measurement.json
```

A non-zero exit is not accepted evidence. Do not edit a failed result into a passing result.

### 5. Manually inspect the raw JSON for privacy

Before copying any result into the repository, inspect the complete JSON and confirm that it contains no:

- absolute local paths;
- usernames;
- hostnames;
- model names;
- request, prompt, response, or source text;
- credentials or secret values;
- workspace identifiers or other private machine identifiers.

The validator checks the fixed privacy flags and exact bounded schema, but it does **not** replace this manual review.

If unexpected private content exists, do not commit the file. Fix the measurement/reporting boundary in a separate reviewed change and rerun the measurement.

### 6. Validate the reviewed result against the measured commit

Run:

```sh
uv run python scripts/validate_imp_096_lite_client_measurement.py \
  ../imp096-lite-client-measurement.json \
  --expected-commit-sha "$COMMIT_SHA"
```

Accepted validator output is a small derived summary with:

- `result = pass`;
- the validated measured commit SHA;
- `evidence_level = real-machine`;
- `measurement_scope = doll-lite-client-only`;
- performance thresholds still undefined;
- Phase 6 still incomplete;
- Lite v1 still incomplete;
- `manual_privacy_review_required = true`.

The validator fails closed on unknown/missing fields, wrong machine/evidence class, commit mismatch, false checks, reordered steps, negative/invalid measurements, network/process attempts, privacy flags, or release/performance overclaims.

### 7. Only then prepare the evidence acceptance PR

The acceptance PR may add the reviewed JSON to the repository's testing-results area and update the evidence/status documentation required by Issue #297.

The PR must keep the measured commit SHA unchanged. The acceptance PR's own head SHA will naturally be newer because adding the evidence file is a later repository mutation.

## Non-claims after a passing measurement

A passing IMP-096 measurement does **not** establish:

- minimum RAM;
- maximum disk footprint;
- latency budgets;
- model/Ollama/GPU memory use;
- total-system resource use;
- Lite performance acceptance;
- accessibility acceptance;
- the seven-day release-candidate soak;
- complete Phase 6;
- Lite v1.0 completion;
- stable general anti-lock-in.

Performance-threshold interpretation remains a separate bounded follow-up after accepted measurements exist.