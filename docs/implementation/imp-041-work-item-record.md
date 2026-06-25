# IMP-041 — WorkItemRecord v1

## Status

Implemented for review.

## Purpose

Add the first project-child authority record so Doll can preserve bounded units of work independently from a large mutable ProjectRecord.

## Implemented boundary

- WorkItemRecord v1 is an authoritative package-format-v2 category;
- each item links to one active ProjectRecord and stores kind, title, description, domain status, priority, dates, dependencies, blockers, acceptance criteria, verification state, evidence, decisions, artifacts, and generic sources;
- accepted kinds are `task`, `milestone`, `investigation`, `maintenance`, and `review`;
- domain statuses are `proposed`, `ready`, `in_progress`, `blocked`, `completed`, and `cancelled`;
- verification states are `not_verified`, `pending`, `passed`, `failed`, and `not_applicable`;
- model, runtime, capability, and system paths may create only proposed items;
- ready creation, promotion, definition updates, lifecycle transitions, completion, cancellation, verification changes, and archive require the trusted user path;
- every mutation uses an expected record revision;
- envelope archive remains separate from domain cancellation;
- blocked work requires at least one current blocker;
- dependency and blocker relations are separate, same-project, non-self, non-duplicate, and type checked;
- dependency cycles are rejected;
- terminal work cannot remain a current blocker;
- acceptance criteria remain deterministic structured data and do not execute anything;
- completion and verification are independent states;
- deterministic JSON export and Doll State Package v2 transfer are supported;
- package format v1 remains unchanged and cannot contain WorkItemRecord members.

## Authority rule

An untrusted proposal never becomes accepted ready work merely because it exists in storage. Non-proposed work with untrusted provenance is treated as malformed unless a trusted mutation has promoted it. Work-item text, criteria, source records, and linked decisions remain data and do not grant execution authority.

## Link contract

- `project_id` links to one active ProjectRecord;
- `depends_on_ids` and `blocked_by_ids` link to active WorkItemRecords in the same project;
- `source_decision_ids` link to active DecisionRecords;
- `verification_evidence_ids` link to active EvidenceRecords;
- `artifact_ids` link to active ArtifactRecords;
- `source_ids` link to active, portable authoritative records;
- all link checks run both in the live repository and during state-package verification before target mutation.

## Preserved guarantees

- local authoritative state;
- optimistic revision protection;
- typed package validation;
- deterministic export;
- secret omission from unencrypted state packages;
- staged package import and failure cleanup;
- model-independent inspection;
- no automatic task execution, capability grant, permission grant, credential use, network use, or cloud dependency.

## Tests

The IMP-041 tests prove:

- trusted lifecycle transitions and stale-revision rejection;
- archived envelope state remains distinct from cancelled work;
- untrusted proposals cannot promote, complete, or cancel themselves;
- an untrusted persisted accepted state fails closed;
- missing, self, duplicate, wrong-type, cross-project, and cyclic relations are rejected;
- blocked state requires an accepted blocker representation;
- completion timestamps, blocker declarations, relation overlap, self-sources, verification evidence, malformed envelopes, read-only repositories, and non-portable source links fail closed;
- decision and verification-evidence links remain typed;
- deterministic export is stable;
- valid work items survive restart, Doll State Package v2 transfer, and verified state-backup creation;
- hostile cross-project package relations fail before target mutation;
- package format v1 remains free of WorkItemRecord members.

## Deferred work

This implementation does not add:

- ProcedureRecord;
- ProjectCheckpointRecord;
- derived project status;
- Resume Bundle generation;
- automatic execution;
- final fresh-process or primary-machine evidence for all project-continuity acceptance tests;
- the Phase 4B gate claim.

## Specification mapping

- `docs/spec/03b-project-continuity-and-resumption.md`, section 5
- `docs/spec/08b-project-continuity-acceptance.md`, PROJ-002, PROJ-003, and PROJ-006
- `docs/spec/09-development-roadmap.md`

## Issue

Closes #133.
