# IMP-047 — Phase 4B project-continuity acceptance

## Status

Automated evidence implemented. The primary Intel Mac offline gate remains pending, so Phase 4B is not complete.

## Scope

This acceptance slice covers PROJ-001 through PROJ-012 using the merged IMP-038 through IMP-046 contracts and implementations.

It verifies:

- ProjectRecord v2 charter continuity;
- WorkItemRecord authority, lifecycle, dependencies, blockers, acceptance criteria, and decision traceability;
- ProcedureRecord continuity and non-authority;
- ProjectCheckpointRecord deterministic basis, fingerprint, confirmation, and freshness;
- deterministic read-only project status;
- deterministic project-scoped Resume Bundle generation and independent inspection;
- Doll State Package v2 transfer and supported package-v1 neutrality;
- state and workspace backup restoration;
- fresh-process operation with model adapters disabled and no usable network route;
- imported-content inability to claim authoritative progress;
- secret-safe scoped output and failure cleanup;
- exact commit binding and bounded privacy-safe result output.

## Files

- `docs/testing/phase-4b-project-continuity-matrix.json`
- `scripts/run_imp_047_project_continuity_acceptance.py`
- `scripts/imp_047_fresh_probe.py`
- `scripts/imp_047_bundle_inspector.py`
- `tests/test_project_continuity_acceptance.py`
- `tests/test_project_continuity_acceptance_static.py`

## CI command

```bash
python scripts/run_imp_047_project_continuity_acceptance.py \
  --commit-sha "$(git rev-parse HEAD)" \
  --evidence-level ci
```

Expected result before primary-machine evidence:

```text
result = pass
primary_intel_mac_gate = pending
phase4b_gate_complete = false
```

## Fresh-process and independent-inspection boundary

The runner starts `imp_047_fresh_probe.py` in a separate Python process with a disposable synthetic workspace. The probe exercises deterministic status and Resume Bundle output, package-v2 transfer, state-backup restoration, checkpoint freshness, secret omission, and fresh CLI processes with model adapters disabled and unusable proxy endpoints.

The probe starts `imp_047_bundle_inspector.py` in another process after removing `PYTHONPATH`. The inspector uses only the Python standard library. It verifies the fixed ZIP inventory, safe member paths, SHA-256 declarations, manifest and project identity, current checkpoint, explicit omissions, generated non-authoritative HANDOFF.md notice, and absence of private absolute paths and the synthetic secret marker.

No model, runtime, preferred UI, running doll service, network request, cloud account, or credential is used.

## Primary Intel Mac command

Run only from the exact merged `main` commit on the project owner's primary Intel Mac after networking has been disabled:

```bash
python scripts/run_imp_047_project_continuity_acceptance.py \
  --commit-sha "$(git rev-parse HEAD)" \
  --evidence-level real-machine \
  --offline-confirmed
```

The output is one bounded JSON object. Review it before storing it. Do not commit terminal history, absolute paths, usernames, hostnames, private project text, fixture archives, or machine-specific details.

A separate completion PR must:

1. store the accepted JSON result under `docs/testing/results/`;
2. change the matrix real-machine gate from `pending` to `pass`;
3. bind the result to the exact merged commit, Darwin x86_64 or amd64 architecture, completion time, and offline mode;
4. set `phase4b_gate_complete` to `true`;
5. update the roadmap, combined specification, and public project status;
6. rerun CI and confirm the stored evidence remains valid;
7. only then permit the first bounded Phase 5 local-runtime issue to receive the next implementation identifier.

## Deliberate limitations

- This proves model-independent project continuity, not autonomous project management.
- No local model runtime, cloud provider, external issue tracker, or multi-user collaboration path is exercised.
- Generated project status, Resume Bundle, and HANDOFF.md remain non-authoritative derived views.
- Model integration remains blocked until the separate primary-machine completion PR passes.

## Issue

Refs #145.
