# IMP-043 — ProjectCheckpointRecord v1

## Status

Implemented for review.

## Purpose

Preserve one explicitly confirmed project position without confusing it with a live mutable status object.

## Implemented boundary

- ProjectCheckpointRecord v1 is an authoritative package-format-v2 category;
- confirmation states are `proposed`, `confirmed`, and `superseded`;
- untrusted model, runtime, importer, and system origins may create only proposed checkpoints;
- confirmation, supersession, and archive require the trusted user path;
- checkpoint content preserves project identity, as-of time, summary, current phase, current goal, active work, next work, blocked work, completed milestones, required validation records, and additional basis records;
- confirmation captures the exact revision of every declared basis record;
- basis record IDs are sorted deterministically before fingerprinting;
- the basis fingerprint is SHA-256 over canonical JSON containing the accepted checkpoint fields and basis revisions;
- the checkpoint record itself is excluded from its basis so confirmation does not make it immediately stale;
- freshness is derived without mutating state as `current`, `stale`, or `superseded`;
- a proposed checkpoint has no derived freshness until confirmation;
- missing, revision-changed, archived, wrong-state, wrong-type, or cross-project relevant records make a confirmed checkpoint stale;
- unrelated workspace mutations do not make a checkpoint stale;
- stale and superseded checkpoints remain inspectable;
- deterministic JSON export and Doll State Package v2 transfer are supported;
- package format v1 remains unchanged and cannot contain ProjectCheckpointRecord members.

## Basis contract

The confirmation basis contains exactly:

- the ProjectRecord;
- every work item listed as active, next, blocked, or completed milestone;
- every required validation record;
- every explicitly supplied additional basis record.

Each basis ID maps to the authoritative record revision observed during trusted confirmation. The fingerprint excludes host names, user names, absolute local paths, secrets, workspace-wide state revision, and nondeterministic timestamps outside accepted record fields.

## Freshness rule

A confirmed checkpoint is current only when:

- every basis record still exists;
- every basis record has the recorded revision;
- the ProjectRecord remains active and valid;
- active, next, blocked, and completed-milestone work items still satisfy their typed same-project role contract;
- required validation and additional basis records remain active and portable;
- the stored basis fingerprint still matches the canonical basis description.

Changing an unrelated preference, memory, audit entry, or another project does not affect freshness merely because the workspace state revision advanced.

## Package rule

The state package validates checkpoint structure and fingerprint unconditionally. A checkpoint whose basis is still revision-current must also satisfy its typed link contract. A checkpoint with missing or changed basis records remains transferable as an inspectable stale checkpoint rather than being silently rewritten or discarded.

## Preserved guarantees

- local authoritative state;
- optimistic revision protection;
- typed package validation;
- deterministic export and fingerprinting;
- secret omission from unencrypted state packages;
- staged package import and failure cleanup;
- model-independent inspection;
- no derived status command, procedure execution, permission grant, capability invocation, credential use, network use, or cloud dependency.

## Tests

The IMP-043 tests prove:

- an untrusted proposal cannot confirm itself;
- trusted confirmation captures sorted basis revisions and a deterministic fingerprint;
- a checkpoint is current immediately after confirmation;
- unrelated preference mutation leaves it current;
- changing or removing a relevant basis record makes it stale;
- same-revision typed-role tampering also makes it stale;
- stale checkpoint data and its original fingerprint remain inspectable;
- superseded checkpoints remain inspectable with superseded freshness;
- invalid work-item roles, cross-project links, duplicate roles, malformed envelopes, non-portable basis links, and stale revisions fail closed;
- read-only mutation and transactional create or update failures leave no partial checkpoint state;
- valid checkpoints survive restart, Doll State Package v2 transfer, and verified state-backup creation;
- fingerprint tampering fails before target mutation;
- package format v1 remains free of ProjectCheckpointRecord members.

## Deferred work

This implementation does not add:

- `doll project status`;
- Resume Bundle generation;
- automatic checkpoint creation or confirmation;
- procedure execution;
- final fresh-process or primary-machine evidence for all project-continuity acceptance tests;
- the Phase 4B gate claim.

## Specification mapping

- `docs/spec/03b-project-continuity-and-resumption.md`, section 7
- `docs/spec/08b-project-continuity-acceptance.md`, PROJ-005
- `docs/spec/09-development-roadmap.md`

## Issue

Closes #137.
