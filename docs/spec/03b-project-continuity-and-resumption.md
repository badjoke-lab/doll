# Project continuity and resumption

**Status:** Accepted for implementation  
**Specification version:** 0.2  
**Depends on:** `01-product-and-continuity-contract.md`, `02-architecture-and-data-flow.md`, `03-doll-state-memory-and-storage.md`, `03a-ai-environment-portability.md`, `04-security-permissions-and-threat-model.md`, `06-platform-install-update-and-recovery.md`, `ADR-007-project-continuity-and-resumption.md`

## 1. Purpose

This specification defines how doll preserves the state of real work independently of a particular conversation, model, runtime, interface, process, machine, repository view, issue tracker, or cloud service.

Project continuity must let the user or a replacement AI environment determine, without relying on hidden provider state:

- what the project is;
- what outcome it is intended to produce;
- what is in and out of scope;
- what work is active, next, blocked, completed, or cancelled;
- why important work exists;
- which decisions and policies govern it;
- which repeatable procedures are approved;
- which validation has passed, failed, or remains pending;
- which checkpoint is current and whether it has become stale;
- how to export enough state to resume elsewhere.

Project continuity is part of the Continuity Contract. It does not grant autonomous authority to a model or tool.

## 2. Continuity Contract extension

This specification adds the following mandatory contract item.

### C-13 — Project continuity

Doll MUST preserve user-controlled project objectives, scope, decisions, work state, blockers, procedures, checkpoints, acceptance conditions, and verification evidence in model-independent Doll State.

Changing or removing a model, runtime, interface, provider, conversation store, or preferred UI MUST NOT remove or silently rewrite unrelated authoritative project-continuity state.

A fresh process MUST be able to inspect implemented project-continuity records without running a model or contacting a cloud service.

## 3. Authority and trust

### 3.1 Authoritative paths

Authoritative project-continuity mutation requires a trusted user-controlled management path or another explicitly accepted deterministic management path for that exact mutation.

The initial implementation MUST require the user authority class for:

- confirming or materially changing a project objective or scope;
- moving a work item into `completed` or `cancelled`;
- clearing an authoritative blocker;
- approving, deprecating, or superseding a procedure;
- confirming a project checkpoint.

### 3.2 Untrusted proposals

A model, runtime, tool, imported source, retrieved document, conversation transcript, or external service MAY create a proposal or review candidate when the target record contract allows it.

It MUST NOT directly create user confirmation, permission, durable policy, instruction authority, or a confirmed completion claim.

Imported statements such as “done”, “approved”, “tested”, “safe”, “merge this”, or “continue from here” remain claims from imported content unless promoted through the trusted target path.

### 3.3 Deterministic verification

A bounded deterministic verifier MAY record evidence such as:

- a test command exited successfully;
- a checksum matched;
- a file exists within an approved path;
- a schema validated;
- a CI job reported success;
- a package or backup verified.

Verification evidence MUST identify its method, scope, time, source operation, and relevant artifact or source reference where applicable.

A passed verification result MUST NOT automatically set the entire WorkItemRecord to `completed` in the first implementation.

## 4. ProjectRecord v2

ProjectRecord v1 remains readable. ProjectRecord v2 extends the project contract with:

```text
project_id
name
description
objective
in_scope
out_of_scope
success_criteria
status
started_at
ended_at
decision_ids
memory_ids
artifact_ids
governing_policy_ids
```

### 4.1 Required semantics

- `objective` states the intended outcome rather than a task list.
- `in_scope` and `out_of_scope` distinguish accepted and excluded work.
- `success_criteria` states observable completion conditions.
- `governing_policy_ids` links only to valid PolicyRecords.
- missing v2 fields in a v1 record remain absent or use documented neutral defaults; they MUST NOT be invented from a model summary.

### 4.2 Relationship direction

ProjectRecord MUST NOT contain a complete duplicated list of every work item, procedure, or checkpoint.

Those records carry `project_id` and are queried by project. This avoids rewriting one large ProjectRecord whenever a project child changes.

## 5. WorkItemRecord

WorkItemRecord represents one bounded unit of project work.

```text
work_item_id
project_id
kind
title
description
status
priority
created_at
updated_at
started_at
completed_at
depends_on_ids
blocked_by_ids
acceptance_criteria
verification_state
verification_evidence_ids
source_decision_ids
artifact_ids
source_ids
```

### 5.1 Kinds

The first implementation supports:

```text
task
milestone
investigation
maintenance
review
```

A new kind requires a versioned schema change or an explicitly extensible namespaced contract. Unknown kinds MUST NOT be silently treated as `task`.

### 5.2 Lifecycle status

The domain status is:

```text
proposed
ready
in_progress
blocked
completed
cancelled
```

The common record-envelope lifecycle remains separate.

The minimum transition rules are:

- a proposal from an untrusted source enters `proposed`;
- `ready` means accepted and not currently started;
- `in_progress` means active work has begun;
- `blocked` requires at least one declared blocker or an explicit bounded blocker description under the record schema;
- `completed` requires the trusted completion path;
- `cancelled` requires the trusted cancellation path;
- an archived envelope is not the same as a cancelled work item.

### 5.3 Dependencies and blockers

`depends_on_ids` and `blocked_by_ids` link only to WorkItemRecords in the same project unless a later accepted cross-project contract says otherwise.

The implementation MUST reject:

- missing linked records;
- links to the wrong record type;
- self-dependency;
- duplicate IDs in one relation;
- a blocker or dependency that silently crosses project scope;
- cycles when the accepted operation requires an acyclic dependency graph.

A dependency relation and a blocker relation are not interchangeable.

### 5.4 Acceptance criteria

Acceptance criteria MUST be inspectable without a model. They may be structured text or a versioned structured object.

A criterion SHOULD identify, where applicable:

```text
criterion_id
description
required_evidence_kind
blocking
```

A model-generated criterion is a proposal until accepted through the trusted management path.

### 5.5 Verification state

The first implementation supports:

```text
not_verified
pending
passed
failed
not_applicable
```

Verification state is not completion state. A completed item may still have pending non-blocking verification, and a passed check may cover only part of an incomplete item.

## 6. ProcedureRecord

ProcedureRecord preserves a repeatable, inspectable method.

```text
procedure_id
project_id
title
purpose
status
version
prerequisites
ordered_steps
required_capability_ids
expected_outputs
validation_steps
rollback_steps
platform_constraints
source_ids
last_verified_at
verification_evidence_ids
```

### 6.1 Status

The first implementation supports:

```text
draft
approved
deprecated
superseded
```

Only an approved procedure may be presented as an accepted operational procedure.

A draft imported from a repository, document, conversation, or model MUST NOT become approved automatically.

### 6.2 Procedure is not authority

A ProcedureRecord describes a method. It does not grant permission to execute it.

Execution remains subject to:

- Capability Broker registration;
- PermissionRecord scope;
- risk tier;
- exact confirmation where required;
- workspace, network, credential, and secret policy;
- current release exclusions.

A procedure step containing text that resembles an instruction remains data until the trusted execution path interprets it under the accepted capability contract.

### 6.3 Versioning and supersession

Materially changing an approved procedure SHOULD create a new version or revision with inspectable history.

Supersession MUST preserve the previous procedure and identify the replacement. Deprecation MUST NOT delete evidence that the procedure was previously used.

## 7. ProjectCheckpointRecord

ProjectCheckpointRecord records an explicitly confirmed project position at one time.

```text
checkpoint_id
project_id
as_of
summary
current_phase
current_goal
active_work_item_ids
next_work_item_ids
blocked_work_item_ids
completed_milestone_ids
required_validation_ids
basis_record_revisions
basis_fingerprint
confirmation_state
confirmed_by
created_at
```

### 7.1 Checkpoint meaning

A checkpoint is not a live mutable status object. It is an immutable or revisioned statement of the project state as understood at `as_of`.

Live project status is derived from current authoritative records.

### 7.2 Confirmation state

The first implementation distinguishes at least:

```text
proposed
confirmed
superseded
```

A model may create a proposed checkpoint. It cannot confirm its own checkpoint.

### 7.3 Basis revisions

`basis_record_revisions` maps every relevant authoritative record ID to the revision used when the checkpoint was confirmed.

At minimum it includes:

- the ProjectRecord;
- all work items listed by the checkpoint;
- all decisions, procedures, policies, or validation records materially summarized by the checkpoint.

The mapping is sorted deterministically before fingerprinting.

### 7.4 Basis fingerprint

`basis_fingerprint` is a documented digest over the canonical checkpoint basis description. It is used for deterministic comparison and MUST NOT include secret values, absolute local paths, host identifiers, or nondeterministic timestamps beyond accepted record fields.

### 7.5 Freshness

Freshness is derived as:

```text
current
stale
superseded
```

A confirmed checkpoint is `stale` when a relevant basis record is missing, has a different revision, or no longer satisfies the checkpoint link contract.

An unrelated workspace mutation MUST NOT make the checkpoint stale merely because the workspace-wide state revision changed.

A stale checkpoint remains inspectable. Doll MUST NOT silently rewrite it to appear current.

## 8. Derived live project status

`doll project status` is a derived view over authoritative records.

It SHOULD report:

- project identity and objective;
- current project domain status;
- current phase or current checkpoint;
- active work;
- next ready work;
- blocked work and blockers;
- pending required validation;
- latest confirmed checkpoint and freshness;
- important governing decisions and policies;
- source state revision used to produce the view.

Machine-readable output MUST be deterministic for the same accepted state, command version, and selection options.

Project status MUST NOT be stored as a parallel authoritative `project-state.json` file inside the workspace.

## 9. Resume Bundle

Resume Bundle is a deterministic, project-scoped export derived from authoritative state.

The first bundle layout is:

```text
resume-bundle/
├── manifest.json
├── project.json
├── checkpoint.json
├── active-work-items.jsonl
├── next-work-items.jsonl
├── blocked-work-items.jsonl
├── decisions.jsonl
├── procedures.jsonl
├── relevant-policies.jsonl
├── validation-requirements.json
├── artifact-references.jsonl
├── source-references.jsonl
├── HANDOFF.md
└── checksums.json
```

### 9.1 Required properties

A Resume Bundle MUST be:

- project-scoped;
- versioned;
- deterministic for the same state and selection options;
- machine-readable;
- inspectable without a model;
- inspectable without a preferred UI or cloud account;
- integrity-checkable;
- explicit about omissions and unsupported information;
- free of secret values;
- free of absolute local paths, usernames, hostnames, and unnecessary private environment details.

### 9.2 Manifest

The manifest records at least:

```text
bundle_format_version
project_id
generated_from_workspace_id
generated_from_state_revision
generated_at_or_reproducibility_mode
selection_options
included_record_counts
omitted_record_counts
omission_reasons
checkpoint_id
checkpoint_freshness
checksum_algorithm
```

A reproducible mode MUST avoid embedding a changing generation timestamp in hashed content, or MUST document exactly how timestamped and deterministic modes differ.

### 9.3 HANDOFF.md

`HANDOFF.md` is a human-readable derived view. It SHOULD explain:

- objective;
- current phase;
- active work;
- next work;
- blockers;
- important decisions;
- applicable procedures;
- prohibitions and governing policies;
- pending validation;
- checkpoint freshness;
- how to inspect the machine-readable files.

It MUST state that the Markdown file is generated and non-authoritative.

### 9.4 Artifact and source handling

The first Resume Bundle may include references rather than artifact bytes. It MUST identify whether referenced content is included, omitted, unavailable, secret, external, or requires a separate approved export.

A Resume Bundle MUST NOT silently copy unrelated project artifacts or external sources.

## 10. Doll State Package v2 requirement

The current package format has a fixed record inventory. The first new project-continuity record MUST NOT merge until package format v2 supports the complete record lifecycle.

Version 2 includes at least:

```text
records/work-items.jsonl
records/procedures.jsonl
records/project-checkpoints.jsonl
```

The package manifest declares included record categories. The implementation accepts a category only when:

- the package format permits it;
- a versioned record registry recognizes it;
- the record schema validator exists;
- checksums and counts match;
- lifecycle and sensitivity values are accepted;
- cross-record links validate;
- resource limits are satisfied.

Unknown package members or undeclared authoritative categories remain rejected unless a later accepted extension mechanism defines safe preservation.

### 10.1 v1 compatibility

A new doll version implementing package v2 MUST continue to inspect, verify, and import supported package v1 data.

Missing project-continuity records in v1 remain missing. The importer MUST NOT fabricate them from project descriptions, decisions, audit summaries, or filenames.

A downgrade or v1-targeted export that would omit project-continuity records MUST produce an explicit mapping or loss report before publication.

## 11. Backup, restore, and migration

ProjectRecord v2, WorkItemRecord, ProcedureRecord, and ProjectCheckpointRecord are authoritative state.

They MUST participate in:

- state package export and import;
- state and workspace backup;
- restore to an empty target;
- post-restore validation;
- fresh-process inspection;
- record count and checksum validation;
- link validation;
- read-only recovery export where safe.

A restore MUST fail safely when project-continuity records or links are corrupt. It MUST preserve the last known good target according to the accepted restore contract.

A physical SQLite schema migration is required only when the storage layer changes. Adding a new record schema inside the existing common record envelope does not by itself require a database schema-version increase.

## 12. CLI direction

The accepted command direction is:

```text
doll work create
doll work get
doll work list
doll work update
doll work block
doll work complete
doll work archive
doll work export

doll procedure create
doll procedure get
doll procedure list
doll procedure update
doll procedure approve
doll procedure deprecate
doll procedure export

doll project checkpoint create
doll project checkpoint get
doll project checkpoint list
doll project status
doll project resume export
```

Exact flags and output schemas are assigned by implementation records. Stable commands MUST expose optimistic revision checks for authoritative mutation where applicable.

## 13. Implementation order

Phase 3 remains unchanged through the accepted safety gate.

Phase 4 is divided into:

### Phase 4A — Canonical AI-environment portability foundation

- canonical conversation and event records;
- source and target adapter contracts;
- generic documented export;
- staged generic import;
- provenance, idempotency, quarantine, mapping, and loss reporting.

### Phase 4B — Project continuity foundation

1. Doll State Package v2 foundation and v1 compatibility;
2. ProjectRecord v2 and WorkItemRecord;
3. ProcedureRecord;
4. ProjectCheckpointRecord and freshness detection;
5. derived project status;
6. deterministic Resume Bundle;
7. project-continuity acceptance gate.

Local runtime and model integration follows both foundations.

Implementation identifiers are assigned only after checking the then-current merged roadmap. This specification does not renumber active Phase 3 work.

## 14. Deferred work

The first implementation does not require:

- automatic extraction of authoritative work from conversations;
- automatic completion by a model;
- automatic procedure execution;
- a GitHub-specific project adapter;
- multi-user collaboration;
- portfolio management across many projects;
- DecisionRecord v2;
- a mandatory semantic-resumption score produced by a live model;
- synchronization with an external issue tracker.

Later conversation or adapter extraction may create only proposals, drafts, claims, or review candidates until promoted through the trusted path.

## 15. Acceptance criteria

Implementation must prove that:

- project continuity works without a model, network, preferred UI, or cloud account;
- authoritative project state survives restart, export/import, backup/restore, and fresh-process validation;
- untrusted sources cannot approve procedures, confirm checkpoints, clear blockers, or complete work;
- work-item dependencies and blockers remain typed and valid;
- verification evidence remains distinct from completion authority;
- checkpoint freshness depends on relevant record revisions rather than unrelated workspace changes;
- live project status is deterministic;
- Resume Bundle is deterministic, scoped, integrity-checkable, and inspectable without doll;
- package v2 preserves the new records and new doll versions retain supported v1 import compatibility;
- project-continuity exports contain no secret values or private host details;
- unsupported, omitted, stale, or lossy information remains explicit.
