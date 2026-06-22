# IMP-023 — Phase 3 Safety Acceptance Test

## Status

IMP-023 and the Phase 3 safety gate are complete. Cross-platform CI and the primary Intel Mac offline real-process run passed for main commit `22e78b09ba0c144c2cddc918992d52f845c30185`.

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

- classified ordinary-state writes are denied;
- denial does not advance the state revision;
- unknown capabilities are denied;
- release exclusion is applied before confirmation;
- a fresh exact Tier 3 confirmation is accepted only by the confirmation-aware preflight;
- a material session change invalidates that confirmation;
- confirmation cannot bypass release exclusion;
- audit history and confirmation history remain readable after repository close and read-only reopen.

Audit redaction, diagnostic safety, credential non-disclosure, instruction-origin authority, and other SEC requirements remain covered by the executable pytest files mapped in the acceptance matrix. The fresh-process probe supplements those tests rather than duplicating every unit and integration fixture.

The probe performs state, preflight, and persistence validation only. It does not invoke a model runtime, credential operation, network adapter, capability executor, or the synthetic Tier 3 adapter.

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

The accepted primary-machine run completed at `2026-06-22T15:19:43.591791Z` on Darwin `x86_64`, with `network_mode = offline-confirmed`, `primary_intel_mac_gate = pass`, and `phase3_gate_complete = true`. The complete bounded report is stored in `docs/testing/imp-023-primary-intel-mac-result.json`.

## Failure and privacy behavior

Failure output contains only the test identifier, supplied commit SHA, completion time, result, safe failure stage, and exception class. It does not include exception text, absolute paths, usernames, hostnames, secret values, or private fixture content.

The successful report contains bounded platform and acceptance metadata only. All fixtures are synthetic.

## Gate interpretation

Combined cross-platform CI and primary Intel Mac evidence proves that the implemented model-independent Phase 3 boundary passed its accepted gate. This authorizes beginning Phase 4A and Phase 4B foundation work; it does not authorize IMP-024 or model integration before both Phase 4 gates pass.

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
- Future listeners, runtimes, adapters, and executable capabilities require additional acceptance evidence for their newly introduced paths.
