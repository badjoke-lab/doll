# IMP-046 — Project-continuity transfer and recovery coverage

## Status

Implemented for review. Final merge remains gated by cross-platform CI.

## Purpose

Prove that the project-continuity records and derived views implemented through IMP-045 remain usable across package transfer, backup and restore, fresh-process inspection, compatibility boundaries, imported-content claims, and privacy-sensitive failure paths before running the final Phase 4B acceptance gate.

## Implemented boundary

- this slice adds integration coverage rather than a new authoritative record type or production authority path;
- a complete ProjectRecord v2 charter, accepted WorkItemRecords, an approved ProcedureRecord, a confirmed ProjectCheckpointRecord, governing DecisionRecord and PolicyRecord links, and an authoritative artifact are exercised together;
- Doll State Package v2 export, verification, planning, and empty-target import preserve the project charter, work state, procedure, checkpoint basis, checkpoint freshness, typed links, artifact bytes, and derived project status;
- a state backup preserves the same non-secret project-continuity state through verified restore and fresh-process validation while reporting and omitting secret records;
- a workspace backup preserves the authoritative SQLite snapshot, project-continuity records, and artifact bytes through verified restore;
- a separate operating-system process with model adapters disabled and unusable proxy endpoints can derive project status and generate a verified Resume Bundle from restored state;
- a supported package-v1 fixture containing a ProjectRecord v1 remains importable without fabricating WorkItemRecord, ProcedureRecord, ProjectCheckpointRecord, objective, scope, success criteria, or checkpoint state;
- imported content containing completion, approval, blocker-clearing, checkpoint-confirmation, and scope-change statements remains imported data and does not mutate authoritative project, work-item, procedure, or checkpoint records;
- unrelated imported content does not enter the project-scoped Resume Bundle;
- a workspace backup containing secret project-child state fails without publication, inventory registration, or state revision changes;
- a corrupt state package fails before changing an existing target.

## Preserved guarantees

- local-complete and model-independent inspection;
- user authority over project scope, completion, cancellation, procedure approval, blocker clearing, and checkpoint confirmation;
- deterministic typed package validation;
- supported package-v1 compatibility without fabricated state;
- verified state and workspace backup restoration;
- checkpoint freshness based on relevant record revisions;
- generated project status, Resume Bundle, and HANDOFF.md remain non-authoritative;
- secret omission and explicit backup refusal where safe unencrypted publication is impossible;
- no model runtime, provider, cloud account, network request, credential use, capability invocation, procedure execution, or automatic project mutation.

## Tests

The IMP-046 tests prove:

- package-v2 transfer preserves a complete project-continuity fixture and reports one omitted secret WorkItemRecord;
- state-backup restore preserves non-secret project state, artifact bytes, current checkpoint freshness, project status, and Resume Bundle generation;
- workspace-backup restore preserves the exact durable project state and artifact content;
- fresh-process project status and Resume Bundle generation work with model adapters disabled and unusable network proxy endpoints;
- supported package-v1 import keeps ProjectRecord v1 neutral and creates no project-continuity child records;
- imported progress and authority claims remain imported-data events and do not change authoritative project records;
- secret workspace-backup refusal and corrupt-package import leave no partial output or target mutation.

## Deferred work

This implementation does not add or claim:

- the final PROJ-001 through PROJ-012 acceptance result record;
- primary-machine Phase 4B evidence;
- completion of the Phase 4B gate;
- local model integration;
- automatic extraction, approval, confirmation, completion, procedure execution, or blocker clearing.

## Specification mapping

- `docs/spec/03b-project-continuity-and-resumption.md`, sections 9 through 15
- `docs/spec/08b-project-continuity-acceptance.md`, PROJ-001, PROJ-004 through PROJ-012
- `docs/spec/09-development-roadmap.md`

## Issue

Closes #143.
