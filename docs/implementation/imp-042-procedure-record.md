# IMP-042 — ProcedureRecord v1

## Status

Implemented for review.

## Purpose

Preserve repeatable, inspectable project methods without turning procedure text or capability references into execution authority.

## Implemented boundary

- ProcedureRecord v1 is an authoritative package-format-v2 category;
- each procedure links to one active ProjectRecord and stores purpose, version, prerequisites, ordered steps, required capability IDs, expected outputs, validation steps, rollback steps, platform constraints, sources, verification state, and supersession links;
- domain statuses are `draft`, `approved`, `deprecated`, and `superseded`;
- imported, model-origin, runtime-origin, and system-origin procedures can be created only as draft;
- approval, verification, deprecation, supersession, and archive require the trusted user path;
- approval requires non-empty ordered steps, validation steps, and rollback steps;
- every mutable operation uses an expected record revision;
- supersession preserves the prior procedure and records both predecessor and replacement relations;
- a replacement must be approved, remain in the same project, and use a higher procedure version;
- deterministic JSON export and Doll State Package v2 transfer are supported;
- package format v1 remains unchanged and cannot contain ProcedureRecord members.

## Non-authority rule

A ProcedureRecord describes a method. Its text, ordered steps, capability IDs, source records, and expected outputs are data only. Creating or approving a procedure does not:

- register a capability;
- create a PermissionRecord;
- grant confirmation;
- provide credential scope;
- execute a step;
- permit network or filesystem access;
- bypass current release exclusions.

Execution remains outside this implementation and remains subject to the Capability Broker, PermissionRecord scope, risk tier, exact confirmation, workspace policy, network policy, credential policy, and secret policy.

## Link contract

- `project_id` links to one active ProjectRecord;
- `source_ids` link to active, portable authoritative records;
- `verification_evidence_ids` link to active EvidenceRecords;
- `supersedes_id` and `superseded_by_id` link to ProcedureRecords in the same project with strictly ordered versions;
- all link checks run both in the live repository and during state-package verification before target mutation.

## Preserved guarantees

- local authoritative state;
- optimistic revision protection;
- typed package validation;
- deterministic export;
- secret omission from unencrypted state packages;
- staged package import and failure cleanup;
- model-independent inspection;
- no procedure execution, permission grant, capability registration, credential use, network use, or cloud dependency.

## Tests

The IMP-042 tests prove:

- untrusted procedures remain draft until trusted completion and approval;
- incomplete drafts cannot be approved;
- stale revisions fail closed;
- verification evidence remains typed;
- deprecated and superseded procedures remain inspectable;
- replacement procedures remain same-project and version-ordered;
- capability references do not create permissions or execution authority;
- deterministic export is stable;
- valid procedures survive restart, Doll State Package v2 transfer, and verified state-backup creation;
- hostile package project and supersession links fail before target mutation;
- package format v1 remains free of ProcedureRecord members.

## Deferred work

This implementation does not add:

- procedure execution;
- Capability Broker registration or invocation;
- PermissionRecord creation;
- ProjectCheckpointRecord;
- derived project status;
- Resume Bundle generation;
- final fresh-process or primary-machine evidence for all project-continuity acceptance tests;
- the Phase 4B gate claim.

## Specification mapping

- `docs/spec/03b-project-continuity-and-resumption.md`, section 6
- `docs/spec/08b-project-continuity-acceptance.md`, PROJ-004
- `docs/spec/09-development-roadmap.md`

## Issue

Closes #135.
