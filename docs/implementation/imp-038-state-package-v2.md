# IMP-038 — Doll State Package v2 foundation

## Status

Implemented for review.

## Purpose

Begin Phase 4B without introducing project-continuity records before their transfer boundary exists. Newly exported Doll State packages use format version 2, while supported version 1 packages remain inspectable, verifiable, plannable, and importable.

## Implemented boundary

- `PACKAGE_FORMAT_VERSION` advances from 1 to 2 for new exports.
- Supported read versions are declared explicitly as 1 and 2.
- Package inspection reports the source package version rather than the current writer version.
- Version-specific manifest requirements are selected before the shared integrity and typed-record validation path runs.
- Existing version 1 inventory, record paths, checksums, security limits, and empty-target import behavior remain supported.
- Import audit metadata records the actual source package version.
- The generated package README identifies writer format version 2.
- Deterministic output is preserved for identical accepted state and export time.

## Compatibility rule

Version 2 is intentionally a foundation format in this slice. It retains the current authoritative record inventory and member paths. The next bounded Phase 4B slice may add the versioned authoritative record registry and then extend version 2 validation without changing how version 1 packages are identified.

Version 1 support is read compatibility only. New exports are always version 2.

## Preserved guarantees

- read-only export;
- deterministic ZIP metadata and member order;
- complete checksum inventory;
- path, entry-type, size, compression-ratio, and JSON limits;
- typed record and cross-record validation;
- secret-record omission from unencrypted packages;
- no package-content execution;
- staged empty-target import;
- failure cleanup and atomic publication behavior;
- no model, runtime, provider, cloud credential, or network dependency.

## Tests

The IMP-038 tests prove:

- new exports report format version 2;
- repeated exports with the same state and timestamp are byte-identical;
- a deterministic synthetic version 1 fixture remains inspectable and verifiable;
- the version 1 fixture can be planned and imported into an empty target;
- imported version 1 audit evidence retains source version 1;
- unsupported versions fail before target mutation;
- missing version-required manifest fields fail closed.

Existing state-package unit, integration, defensive, coverage, CLI, and cross-platform CI tests remain applicable.

## Deferred work

This implementation does not add:

- the authoritative record registry;
- ProjectRecord v2;
- WorkItemRecord;
- ProcedureRecord;
- ProjectCheckpointRecord;
- project status generation;
- Resume Bundle generation;
- PROJ-001 through PROJ-012 acceptance completion.

## Specification mapping

- `docs/spec/03b-project-continuity-and-resumption.md`
- `docs/spec/08b-project-continuity-acceptance.md`
- `docs/spec/09-development-roadmap.md`

## Issue

Closes #126.
