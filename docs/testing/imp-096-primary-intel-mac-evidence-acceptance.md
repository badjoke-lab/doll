# IMP-096 primary Intel Mac evidence acceptance

Status: accepted real-machine evidence for Issue #297.

## Purpose

IMP-096 accepts one privacy-reviewed primary Intel Mac result from the already-implemented IMP-083 Lite client measurement harness. The evidence contract was prepared first so the later physical run could bind to one exact main commit and be checked deterministically.

## Accepted evidence

Measured commit:

`b57ebe6fb4a7620901b95b49f6743b71ae1026f7`

Accepted evidence file:

`docs/testing/results/IMP-096-primary-intel-mac-lite-client-resource-measurement.json`

The physical run satisfied the runbook conditions:

- clean tracked checkout at the exact measured commit;
- `Darwin` on `x86_64`;
- CPython `3.14.6`;
- network manually disabled before measurement and recorded as `offline-confirmed`;
- local-only execution explicitly confirmed;
- no Ollama/model runtime started for the measurement;
- no cloud credentials required;
- evidence runner exited zero.

## Privacy review

The complete raw JSON was manually reviewed before repository acceptance. It contains no absolute local paths, usernames, hostnames, model names, request/prompt/response/source text, credentials or secret values, or workspace identifiers/private machine identifiers.

The fixed report privacy flags are all `false`. This manual review remains part of the acceptance record; validator checks do not replace it.

## Deterministic validation

The acceptance PR adds a CI regression test that invokes:

```sh
python scripts/validate_imp_096_lite_client_measurement.py \
  docs/testing/results/IMP-096-primary-intel-mac-lite-client-resource-measurement.json \
  --expected-commit-sha b57ebe6fb4a7620901b95b49f6743b71ae1026f7
```

Accepted validator output must retain:

- `result = pass`;
- exact validated measured commit SHA;
- `evidence_level = real-machine`;
- `measurement_scope = doll-lite-client-only`;
- performance thresholds undefined;
- Phase 6 incomplete;
- Lite v1 incomplete;
- `manual_privacy_review_required = true`.

The validator fails closed on unknown/missing fields, wrong machine/evidence class, commit mismatch, false checks, reordered steps, invalid measurements, network/process attempts, privacy flags, or release/performance overclaims.

## Accepted measured values

The bounded Lite-client-only workload reports:

- total duration: `256372493 ns`;
- peak process RSS: `41291776 bytes` (`resource-ru_maxrss`);
- workspace disk bytes: `86369`;
- workspace file count: `2`;
- workspace directory count: `7`;
- measured-workload network attempts: `0`;
- measured-workload process-launch attempts: `0`;
- doctor status: `pass`.

These are evidence values from one accepted physical Intel Mac run, not product requirements.

## Non-claims after acceptance

IMP-096 does **not** establish:

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
