# IMP-040 — ProjectRecord v2

## Status

Implemented for review.

## Purpose

Add a durable project-charter schema without rewriting or fabricating charter content for existing ProjectRecord v1 records.

## Implemented boundary

- ProjectRecord schema versions 1 and 2 are readable;
- the existing `ProjectService.create` and `ProjectService.update` methods remain the v1 compatibility path;
- `ProjectService.create_v2` creates an explicit v2 charter through the trusted user path;
- `ProjectService.update_v2` updates v2 records and may explicitly upgrade a readable v1 record to v2;
- v2 adds `objective`, `in_scope`, `out_of_scope`, `success_criteria`, and `governing_policy_ids`;
- v1 reads expose neutral values for v2-only fields: `objective=None` and empty tuples;
- v1 description or linked records are never inferred into v2 charter fields;
- v2 governing policy IDs must reference active, valid PolicyRecords;
- deterministic project export identifies and emits the actual project schema version;
- state-package typed-link validation enforces v2 governing policy links;
- archive operations preserve the existing project schema version.

## Compatibility rule

ProjectRecord v1 remains readable, exportable, package-transferable, and updateable through its existing compatibility path. The v1 path cannot edit a v2 record because doing so would drop v2-only charter fields. An explicit v2 update is required.

Upgrading v1 to v2 is a trusted mutation that requires all accepted v2 charter values to be supplied. Doll does not construct an objective, scope, success criterion, or policy link from the v1 description, a model summary, imported text, or conversation history.

## Preserved guarantees

- user authority for project mutation;
- optimistic record revision checks;
- active/archived envelope separation;
- typed decision, memory, artifact, and policy links;
- deterministic JSON export;
- secret exclusion from normal export and unencrypted packages;
- package path, checksum, size, and atomic-import protections;
- no model, runtime, provider, cloud credential, capability, or network dependency.

## Tests

The IMP-040 tests prove:

- ProjectRecord v1 remains readable with neutral v2-only values;
- v1 deterministic export remains schema-correct;
- a complete ProjectRecord v2 survives restart and Doll State Package v2 transfer;
- deterministic v2 export contains the accepted charter fields;
- a v1 record can be explicitly upgraded to v2 without inferring content from its description;
- missing, archived, and wrong-type governing policy links are rejected;
- a package with a tampered missing governing policy link fails before target mutation;
- existing v1 project and decision behavior remains covered by the full test suite.

## Deferred work

This implementation does not add:

- WorkItemRecord;
- ProcedureRecord;
- ProjectCheckpointRecord;
- deterministic project status;
- Resume Bundle generation;
- final PROJ-001 fresh-process or primary-machine evidence;
- the Phase 4B gate claim.

## Specification mapping

- `docs/spec/03b-project-continuity-and-resumption.md`, section 4
- `docs/spec/08b-project-continuity-acceptance.md`, PROJ-001 and PROJ-010
- `docs/spec/09-development-roadmap.md`

## Issue

Closes #131.
