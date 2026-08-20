# IMP-096 — Primary Intel Mac Lite client evidence acceptance

Status: accepted real-machine evidence for Issue #297.

## Scope

IMP-096 accepts one privacy-reviewed primary Intel Mac execution of the already-implemented IMP-083 Lite client resource-measurement harness. The accepted evidence is bound to exact measured commit:

`b57ebe6fb4a7620901b95b49f6743b71ae1026f7`

Evidence file:

`docs/testing/results/IMP-096-primary-intel-mac-lite-client-resource-measurement.json`

The physical run used Darwin `x86_64`, CPython `3.14.6`, a clean tracked checkout, explicit offline/local-only operator confirmation, no model runtime, and no cloud credentials. The evidence runner exited zero.

## Accepted measurements

The deterministic result reports:

- `result = pass`;
- `evidence_level = real-machine`;
- `measurement_scope = doll-lite-client-only`;
- total bounded workload duration: `256372493 ns`;
- process peak RSS: `41291776 bytes` from `resource-ru_maxrss`;
- measured workspace bytes: `86369`;
- measured workspace files: `2`;
- measured workspace directories: `7`;
- measured-workload network attempts: `0`;
- measured-workload process-launch attempts: `0`;
- doctor status: `pass`.

Every required evidence check is true. Every fixed privacy flag is false. The raw JSON was also manually reviewed before acceptance for absolute paths, usernames, hostnames, model names, request/prompt/response/source text, credentials, secrets, and workspace identifiers.

CI re-runs `scripts/validate_imp_096_lite_client_measurement.py` against the committed evidence and the exact measured SHA so schema drift, altered evidence, false checks, wrong machine class, privacy flags, or release/performance overclaims fail closed.

## Acceptance boundary

IMP-096 establishes only that one privacy-safe primary Intel Mac Lite-client-only measurement has been accepted through the deterministic validator.

It does **not** establish minimum RAM, a maximum disk footprint, latency budgets, model/Ollama/GPU memory use, total-system resource use, Lite performance acceptance, accessibility acceptance, the seven-day release-candidate soak, complete Phase 6, Lite v1.0, or stable general anti-lock-in.

Performance-threshold interpretation remains separate work.
