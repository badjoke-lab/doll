# IMP-044 — Deterministic derived project status

## Status

Implemented for review.

## Purpose

Provide one model-independent, read-only view of current project state without creating a competing authoritative ProjectStatusRecord or mutable `project-state.json` file.

## Implemented boundary

- `ProjectStatusService` derives status from current authoritative ProjectRecord, WorkItemRecord, ProcedureRecord, ProjectCheckpointRecord, DecisionRecord, and PolicyRecord data;
- the selected ProjectRecord must be active and non-secret for normal status output;
- output includes project identity, objective availability, domain status, current phase and goal, active work, next ready work, blocked work and blockers, pending required validation, latest confirmed checkpoint and freshness, accepted governing decisions, governing policies, approved procedures, omitted secret-record counts, and source state revision;
- active work means `in_progress` WorkItemRecords;
- next work means accepted `ready` WorkItemRecords, including ready blocker records that are themselves valid next candidates;
- blocked work means `blocked` WorkItemRecords and preserves current blocker IDs;
- pending required validation means non-cancelled accepted work with at least one blocking acceptance criterion whose verification state is not `passed` or `not_applicable`;
- work items are ordered by priority, case-folded title, and record ID;
- the latest checkpoint is selected deterministically by accepted `as_of`, creation time, and record ID;
- accepted decisions include explicitly linked project decisions and active accepted decisions whose `project_id` matches the selected project;
- applicable procedures are active approved procedures in the selected project;
- governing policies are the ProjectRecord's explicit active policy links;
- every list uses deterministic ordering and canonical JSON uses sorted keys with compact separators;
- human-readable and JSON CLI forms open the repository read-only;
- normal output omits secret child records and reports deterministic omission counts;
- no model, provider, network, capability, credential, or cloud component is required.

## CLI

```text
doll project status PROJECT_ID --workspace WORKSPACE
doll project status PROJECT_ID --json --workspace WORKSPACE
```

The text form is an inspectable summary. The JSON form uses schema identifier `doll.project-status.v1` and is byte-for-byte deterministic for the same accepted state and selection options.

## Non-authority rule

Project status is derived output only. Generating or reading it does not:

- create or update an authoritative record;
- change project, work-item, procedure, checkpoint, decision, policy, permission, memory, or artifact state;
- append an audit event;
- confirm a checkpoint;
- clear a blocker;
- complete or cancel work;
- approve or execute a procedure;
- grant capability, permission, credential, filesystem, or network authority.

## Read-only invariants

Status generation through the service or CLI preserves:

- workspace state revision;
- every authoritative record revision;
- audit-event count;
- managed artifact bytes.

No generation timestamp is embedded. `source_state_revision` identifies the authoritative snapshot observed by the derived view.

## Tests

The IMP-044 tests prove:

- canonical JSON is identical for repeated reads of the same accepted state;
- project identity, objective, active work, ready work, blocked work, blocker IDs, pending validation, latest checkpoint, checkpoint freshness, decisions, policies, and procedures are present;
- unrelated project work is excluded;
- secret child records are omitted and counted without exposing their text;
- service, text CLI, JSON CLI, and a fresh operating-system process operate through read-only state;
- state revision, record revisions, audit count, and artifact bytes remain unchanged;
- status works with model adapters disabled and without a network dependency;
- missing, archived, or secret selected projects fail closed;
- output does not contain the workspace path.

## Deferred work

This implementation does not add:

- Resume Bundle generation;
- `HANDOFF.md`;
- automatic checkpoint creation or confirmation;
- automatic work transition or validation;
- final PROJ-001 through PROJ-012 gate evidence;
- the Phase 4B completion claim.

## Specification mapping

- `docs/spec/03b-project-continuity-and-resumption.md`, section 8
- `docs/spec/08b-project-continuity-acceptance.md`, PROJ-007 and PROJ-009
- `docs/spec/09-development-roadmap.md`

## Issue

Closes #139.
