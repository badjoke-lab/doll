# IMP-039 — Versioned authoritative record registry

## Status

Implemented for review.

## Purpose

Replace the parallel fixed record-path sets in Doll State Package handling with one versioned authoritative registry. The registry determines which record categories a package format permits, where each category is stored, whether its member is required, and which typed validator must be installed before the category can be accepted.

## Implemented boundary

- package formats 1 and 2 have explicit immutable authoritative record registries;
- each registry category declares `record_type`, `member_path`, `required_member`, and `validator_id`;
- registry construction rejects duplicate record types, duplicate member paths, invalid versions, and unsafe paths;
- v2 export derives accepted record types, JSONL members, record counts, secret omission counts, and manifest categories from the v2 registry;
- package loading resolves the source manifest version before authoritative member inventory validation;
- package inventory validation uses the registry belonging to the source package version;
- every registered validator identity must resolve to an installed typed-record validator;
- `included_categories` must exactly match the versioned authoritative registry plus the fixed package-system categories;
- duplicate, unknown, undeclared, or version-incompatible categories fail closed;
- supported v1 packages continue to use the v1 registry for inspection, verification, planning, and empty-target import.

## Registry contents in this slice

IMP-039 does not add a new authoritative record type. Formats 1 and 2 currently register the same implemented record categories so that the validation boundary exists before ProjectRecord v2 and the first new project-continuity records are added.

A later implementation may extend only the v2 registry with new categories such as work items, procedures, and project checkpoints while leaving the v1 registry unchanged.

## Preserved guarantees

- deterministic v2 ZIP output;
- supported v1 read and import compatibility;
- checksum and size verification;
- path, entry-type, compression-ratio, and JSON limits;
- typed record and cross-record validation;
- secret omission from unencrypted packages;
- staged empty-target import;
- failure cleanup and atomic publication;
- no model, runtime, provider, cloud, capability, or network dependency.

## Tests

The IMP-039 tests prove:

- package formats 1 and 2 resolve to explicit immutable registries;
- malformed, duplicate, or unsafe registry definitions are rejected;
- v2 export inventory and manifest categories are derived from the v2 registry;
- missing, unknown, or duplicate manifest categories are rejected;
- an unknown future authoritative member is rejected before target mutation;
- a registered category without an installed validator fails closed;
- the existing deterministic v2 and supported v1 compatibility tests remain applicable.

## Deferred work

This implementation does not add:

- ProjectRecord v2;
- WorkItemRecord;
- ProcedureRecord;
- ProjectCheckpointRecord;
- project status generation;
- Resume Bundle generation;
- PROJ-001 through PROJ-012 acceptance completion.

## Specification mapping

- `docs/spec/03b-project-continuity-and-resumption.md`, section 10
- `docs/spec/08b-project-continuity-acceptance.md`, PROJ-010
- `docs/spec/09-development-roadmap.md`

## Issue

Closes #129.
