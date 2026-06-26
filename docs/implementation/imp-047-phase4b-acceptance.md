# IMP-047 — Phase 4B project-continuity acceptance

## Status

Accepted. The primary Intel Mac offline gate passed on exact merged `main` commit `ddb58d041e505556910930724d0cf2fd03afe7d3` on 2026-06-26.

Accepted evidence:

- `docs/testing/results/IMP-047-primary-intel-mac-2026-06-26.json`

The stored JSON is preserved from the accepted run. Its `limitations` array still contains the pre-storage pending statement emitted by the runner; the updated matrix is the authoritative post-acceptance gate state.

Phase 4B is complete for the model-independent project-continuity foundation covered by PROJ-001 through PROJ-012. This does not connect a local model runtime or establish autonomous project management.

## Verified boundary

The accepted run verified:

- ProjectRecord v2 and implemented child-record continuity;
- deterministic WorkItemRecord, ProcedureRecord, and ProjectCheckpointRecord behavior;
- deterministic read-only project status and project-scoped Resume Bundle generation;
- independent Resume Bundle inspection using only the Python standard library;
- Doll State Package v2 transfer and supported package-v1 neutrality;
- state and workspace backup restoration with artifact preservation;
- fresh-process operation without a model, provider, cloud account, preferred UI, or usable network route;
- imported-content inability to claim authoritative progress;
- secret omission, privacy-safe bounded output, and recoverable cleanup.

## Accepted environment

- commit: `ddb58d041e505556910930724d0cf2fd03afe7d3`;
- operating system: `Darwin`;
- architecture: `x86_64`;
- Python: `3.12.13`;
- network mode: `offline-confirmed`;
- evidence level: `real-machine`;
- completed at: `2026-06-26T12:37:23.396078Z`.

Result:

```text
result = pass
primary_intel_mac_gate = pass
phase4b_gate_complete = true
```

The stored result contains no absolute paths, usernames, hostnames, credentials, secret values, private fixture content, or personal project data.

## CI validation

```bash
python scripts/run_imp_047_project_continuity_acceptance.py \
  --commit-sha "$(git rev-parse HEAD)" \
  --evidence-level ci
```

CI validates the stored real-machine result against the matrix commit, platform, architecture, completion time, offline mode, and passing checks.

## Deliberate limitations

- This proves model-independent project continuity, not autonomous project management.
- No local model runtime, cloud provider, external issue tracker, or multi-user collaboration path is exercised.
- Generated project status, Resume Bundle, and HANDOFF.md remain non-authoritative derived views.
- Later model integration must continue to use the Phase 3 safety boundary and the Phase 4A/4B canonical state contracts.

## Issue

Completion of #145.
