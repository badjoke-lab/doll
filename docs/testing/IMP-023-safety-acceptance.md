# IMP-023 — Phase 3 Safety Acceptance Test

## Status

Automated CI acceptance is implemented on Issue #78. The Phase 3 gate remains open until the exact final commit also passes the primary Intel Mac real-process run with networking disabled.

## Purpose

IMP-023 validates the model-independent safety boundary implemented by IMP-013 through IMP-022 before any model adapter, inference path, or capability execution path may merge.

This acceptance work adds no model integration and performs no real filesystem mutation outside a synthetic temporary workspace, network request, process adapter execution, credential operation, account action, financial action, message delivery, or external-service side effect.

## Evidence structure

`docs/testing/phase-3-safety-matrix.json` maps SEC-001 through SEC-023 to executable pytest files and evidence levels.

The matrix is checked by `scripts/run_imp_023_safety_acceptance.py`. The runner rejects:

- missing, duplicate, reordered, or unknown SEC identifiers;
- a blocking implemented requirement without executable pytest evidence;
- a referenced test file that is absent or contains no tests;
- an unexplained `not_applicable` result;
- removal of the required primary Intel Mac gate.

SEC-007 is currently `not_applicable` because doll has an application factory but no API listener or server-launch path. The localhost-binding requirement becomes blocking when such a listener is introduced.

## Fresh-process probe

The runner starts a separate Python process with a synthetic temporary workspace and verifies:

- secret-bearing ordinary-state writes are denied;
- denial does not advance the state revision;
- secret-shaped audit input is redacted;
- unknown capabilities are denied;
- release exclusion is applied before confirmation;
- a fresh exact Tier 3 confirmation is accepted only by the confirmation-aware preflight;
- a material session change invalidates that confirmation;
- confirmation cannot bypass release exclusion;
- state, audit history, and confirmation history remain readable after repository close and read-only reopen;
- no model runtime, cloud credential, network path, or live side-effect adapter is used.

The probe performs preflight and persistence validation only. It never invokes the synthetic Tier 3 adapter.

## CI execution

Run against the exact checked-out commit:

```text
python scripts/run_imp_023_safety_acceptance.py \
  --commit-sha "$(git rev-parse HEAD)" \
  --evidence-level ci
```

A passing CI report deliberately contains:

```text
primary_intel_mac_gate = pending
phase3_gate_complete = false
```

CI evidence must pass on Ubuntu, macOS, and Windows together with the repository dependency-lock, Ruff, formatting, strict mypy, generated-specification, coverage, CLI, and module-CLI checks.

## Primary Intel Mac execution

On the exact final PR commit, with networking disabled independently by the operator, run:

```text
python scripts/run_imp_023_safety_acceptance.py \
  --commit-sha "$(git rev-parse HEAD)" \
  --evidence-level real-machine \
  --offline-confirmed
```

The runner rejects real-machine claims unless the operating system is macOS, the architecture is Intel-compatible, the checked-out SHA matches exactly, and offline operation is explicitly confirmed.

A passing report from this command is the remaining machine-level evidence required before the roadmap may mark IMP-023 and Phase 3 complete.

## Failure and privacy behavior

Failure output contains only the test identifier, supplied commit SHA, completion time, result, and exception class. It does not include exception text, absolute paths, usernames, hostnames, secret values, or private fixture content.

The successful report contains bounded platform and acceptance metadata only. All fixtures are synthetic.

## Gate interpretation

Automated CI success proves that the implemented model-independent boundary is internally consistent across the supported CI operating systems. It does not by itself authorize Phase 4 or IMP-024.

Phase 3 may be declared complete only when:

- the complete final CI matrix passes;
- the exact final commit passes the primary Intel Mac offline real-process run;
- coverage remains above the accepted threshold without blanket exclusions;
- review finds no direct route from a future model adapter around permission, secret, origin, capability, confirmation, network, filesystem, process, credential, or audit boundaries;
- known limitations remain documented.

## Known limitations

- No model adapter or model execution path exists.
- No live capability execution adapter exists.
- No API listener exists, so SEC-007 remains deferred rather than falsely passed.
- No live Web retrieval, credential, account, financial, posting, email, or process operation is exercised.
- The primary Intel Mac result cannot be supplied by GitHub-hosted CI and must be recorded separately on the exact final commit.
