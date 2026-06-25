# IMP-037 Phase 4A portability acceptance

## Status

Automated evidence implemented. The primary Intel Mac offline gate remains pending, so Phase 4A is not complete.

## Scope

This acceptance slice covers PORT-004 through PORT-012 using the merged IMP-030 through IMP-036 contracts and implementations.

It verifies:

- generic JSON import staging and reviewed publication;
- deterministic canonical conversation and event persistence;
- deterministic generic JSON, JSONL, Markdown, manifest, and checksum export;
- source environment, adapter, object, batch, and content-hash provenance;
- unchanged repeated-import idempotency;
- explicit quarantine, mapping, material-loss, and source-preservation evidence;
- imported-content authority restrictions;
- hostile parser and publication failure handling;
- doll-independent export inspection in a separate process;
- exact commit binding and bounded result output.

## Files

- `docs/testing/phase-4a-portability-matrix.json`
- `scripts/run_imp_037_portability_acceptance.py`
- `scripts/imp_037_fresh_probe.py`
- `scripts/imp_037_export_inspector.py`
- `tests/test_portability_acceptance.py`
- `tests/test_portability_acceptance_static.py`

## CI command

```bash
python scripts/run_imp_037_portability_acceptance.py \
  --commit-sha "$(git rev-parse HEAD)" \
  --evidence-level ci
```

Expected foundation result before primary-machine evidence:

```text
result = pass
primary_intel_mac_gate = pending
phase4a_gate_complete = false
stable_anti_lock_in_claim = false
```

## Fresh-process boundary

The runner starts `imp_037_fresh_probe.py` in a separate Python process with a disposable synthetic workspace. The probe imports, publishes, reopens, and exports canonical state. It then starts `imp_037_export_inspector.py` in another process after removing `PYTHONPATH`.

The inspector uses only the Python standard library. It does not import doll or a third-party package. It verifies the exact file set, SHA-256 declarations, manifest, JSON/JSONL consistency, non-authoritative Markdown notice, authority notice, record counts, and preserved source identity.

No model, runtime, preferred UI, running doll service, network request, cloud account, or credential is used.

## Primary Intel Mac command

Run only from the exact merged `main` commit on the project owner's primary Intel Mac after networking has been disabled:

```bash
python scripts/run_imp_037_portability_acceptance.py \
  --commit-sha "$(git rev-parse HEAD)" \
  --evidence-level real-machine \
  --offline-confirmed
```

The output is a single bounded JSON object. Review it before storing it. Do not commit terminal history, absolute paths, usernames, hostnames, source archives, fixture text, or other machine-specific details.

A separate completion PR must:

1. store the accepted JSON result under `docs/testing/results/`;
2. change the matrix real-machine gate from `pending` to `pass`;
3. bind the result to the exact merged commit, platform, architecture, completion time, and offline mode;
4. set `phase4a_gate_complete` to `true`;
5. update the roadmap and generated specification;
6. rerun CI and confirm the accepted stored evidence is preserved.

## Deliberate limitations

- PORT-001 through PORT-003 and PORT-013 through PORT-016 are not completed here.
- The generic export covers canonical conversations and conversation events only.
- No provider-specific, local-application, runtime, model, cloud, or private-history adapter is exercised.
- This does not establish a local migration claim or stable anti-lock-in claim.
