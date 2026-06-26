# IMP-045 — Deterministic Resume Bundle

## Status

Implemented for review. Final verification runs through the repository quality and cross-platform CI gates.

## Purpose

Provide a deterministic, project-scoped handoff package that can be inspected without a model, preferred user interface, cloud account, or network connection.

## Implemented boundary

- `ResumeBundleService` derives one versioned ZIP bundle from current authoritative project records through a read-only repository;
- the bundle contains `manifest.json`, project and checkpoint views, active, next, and blocked work-item views, decisions, procedures, governing policies, validation requirements, artifact references, source references, generated `HANDOFF.md`, and `checksums.json`;
- output is scoped to one active non-secret project;
- canonical JSON, deterministic record ordering, and deterministic ZIP metadata make repeated exports byte-for-byte identical for the same accepted state and selection options;
- the manifest records the source workspace identity, source state revision, selection options, included and omitted counts, omission reasons, checkpoint identity and freshness, and checksum algorithm;
- `HANDOFF.md` is explicitly generated and non-authoritative;
- artifact bytes and external source content are not copied into bundle format v1;
- artifact and source records are represented by bounded references that state whether content is included, unavailable, omitted, or requires a separate approved export;
- normal export omits secret-sensitivity records and reports omission counts without exposing their values;
- output publication uses a temporary file, verifies the completed bundle, and atomically replaces the final path;
- failed generation or verification removes temporary and partial output;
- bundle generation requires a read-only repository and does not mutate state, records, audit events, or artifacts;
- no model, provider, capability, credential, network, or cloud component is required.

## CLI

```text
doll project resume export PROJECT_ID --output BUNDLE.zip --workspace WORKSPACE
```

The output path must be outside the doll workspace and must not already exist.

## Bundle layout

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

## Non-authority rule

A Resume Bundle is derived output. Generating or reading it does not:

- create or update an authoritative record;
- confirm or supersede a checkpoint;
- change project scope or objective;
- clear a blocker;
- complete or cancel work;
- approve or execute a procedure;
- grant capability, permission, credential, filesystem, or network authority;
- make `HANDOFF.md` an authoritative state source.

## Integrity and privacy rules

- every required member is listed in the fixed bundle inventory;
- `checksums.json` covers every other bundle member with SHA-256 and byte length;
- verification rejects duplicate, missing, extra, unsafe, unreadable, or checksum-mismatched members;
- generated output contains relative managed artifact paths only;
- artifact content, external source content, secret values, absolute local paths, usernames, hostnames, and unrelated project records are excluded from normal bundle output;
- unsupported, unavailable, and omitted information remains explicit.

## Tests

The IMP-045 tests prove:

- repeated exports of the same accepted state are byte-for-byte identical;
- required bundle members, manifest fields, checkpoint freshness, human-readable handoff sections, and checksums are present;
- output is limited to one project and excludes secret child-record text;
- artifact references are included while artifact bytes are not copied;
- service and CLI generation preserve state revision, record revisions, audit count, and managed artifacts;
- a fresh operating-system process can generate the same bundle with model adapters disabled;
- checksum tampering is rejected;
- partial output is not published on a failed export.

## Deferred work

This implementation does not add:

- artifact-byte inclusion;
- external source fetching;
- automatic project, work-item, checkpoint, or procedure mutation;
- model-assisted handoff interpretation;
- the final PROJ-001 through PROJ-012 acceptance gate evidence;
- the Phase 4B completion claim.

## Specification mapping

- `docs/spec/03b-project-continuity-and-resumption.md`, section 9
- `docs/spec/08b-project-continuity-acceptance.md`, PROJ-008, PROJ-009, and PROJ-012
- `docs/spec/09-development-roadmap.md`

## Issue

Closes #141.
