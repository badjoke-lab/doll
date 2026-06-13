# Development roadmap

**Status:** Draft for acceptance  
**Specification version:** 0.1

## 1. Purpose

This roadmap converts the accepted product and engineering specifications into an implementation sequence.

It is a sequencing document, not a promise of exact dates or pull-request counts.

The governing rule is:

> Prove continuity first, then add useful local capabilities, then expand performance and access.

## 2. Working method

Development proceeds through small, reviewable pull requests.

Each implementation PR should:

- solve one bounded problem;
- cite the accepted specification it implements;
- describe state, permission, network, and migration effects;
- include tests;
- avoid unrelated refactoring;
- state what was not tested on real hardware;
- preserve a working main branch.

The intended division of work is:

- GPT: architecture, specification, task decomposition, review, and release-gate checking;
- Codex: implementation, tests, migrations, documentation updates, and PR preparation;
- project owner: priorities, real-machine validation, final merge, release, license, and hardware decisions.

## 3. Current phase

### Phase 0 — Specification and repository baseline

Status at completion of PR-005:

- product identity defined;
- Continuity Contract defined;
- architecture and Doll State defined;
- security and permission model defined;
- Model Vault and recovery defined;
- release scope defined;
- acceptance tests defined;
- roadmap defined.

Remaining Phase 0 work after PR-005:

1. generate a combined specification document;
2. run a contradiction and completeness audit;
3. normalize requirement wording where needed;
4. freeze specification version 0.1 for implementation;
5. create the initial implementation issue and PR queue.

No production feature should bypass this baseline.

## 4. Phase 1 — Repository and continuity kernel

Goal: establish a cross-platform Python package, private workspace, versioned state, and safe write boundary.

### Proposed PR sequence

#### IMP-001 — Python package and CI skeleton

- Python 3.12 project metadata;
- `uv` lock and development commands;
- `src/doll/` package;
- Typer CLI entry point;
- FastAPI application factory;
- pytest, lint, and type-check configuration;
- GitHub Actions for macOS, Windows, and Ubuntu;
- no model or external tool dependency.

Acceptance focus:

- PLAT-001;
- imports and CLI help on all CI platforms;
- no private data created in repository.

#### IMP-002 — Platform paths and workspace initialization

- platform-aware default directories;
- `doll init`;
- WorkspaceRecord;
- workspace configuration;
- repository-checkout protection;
- path canonicalization primitives;
- synthetic fixtures.

Acceptance focus:

- CONT-P001;
- PLAT-002;
- Japanese and non-ASCII path tests.

#### IMP-003 — SQLite state repository and migrations

- initial schema;
- common record envelope;
- schema version table;
- migration runner;
- transactions and revision fields;
- read-only recovery opening path.

Acceptance focus:

- STATE-001;
- STATE-002;
- STATE-005 foundation.

#### IMP-004 — Audit service

- append-oriented audit schema;
- operation IDs;
- actor and result records;
- secret-safe error summaries;
- CLI audit listing.

Acceptance focus:

- CONT-P015 foundation;
- SEC-012.

#### IMP-005 — Workspace file service

- managed artifact paths;
- safe create-new semantics;
- content hashing;
- atomic writes;
- traversal and link-escape defenses;
- size limits.

Acceptance focus:

- CONT-P008;
- CONT-P009;
- SEC filesystem tests.

## 5. Phase 2 — Minimal Doll State and recovery

Goal: make durable user state inspectable, exportable, restorable, and independent from a model.

### Proposed PR sequence

#### IMP-006 — Preferences, policies, and permissions

- PreferenceRecord;
- PolicyRecord;
- PermissionRecord;
- denied, allow-once, ask, and scoped modes;
- no global allow-all;
- management CLI.

#### IMP-007 — Confirmed memory

- confirmed MemoryRecord only for the first slice;
- create, list, inspect, update, archive, export;
- provenance and sensitivity;
- no automatic conversation-to-memory conversion.

Acceptance focus:

- CONT-P005.

#### IMP-008 — Projects and decisions

- ProjectRecord;
- DecisionRecord;
- links to memory and artifacts;
- revision-safe updates.

Acceptance focus:

- CONT-P006.

#### IMP-009 — Doll State export and import

- package manifest;
- JSON/JSONL records;
- checksums;
- package version;
- staged validation;
- conflict reporting;
- no code execution.

Acceptance focus:

- STATE-003;
- STATE-004;
- STATE-008.

#### IMP-010 — Backup create and verify

- state backup;
- full workspace backup;
- manifest and SHA-256 checks;
- completion only after verification;
- backup inventory.

Acceptance focus:

- CONT-P010;
- STATE-007 foundation.

#### IMP-011 — Restore and post-restore validation

- restore to empty target;
- staged extraction;
- unsafe-path rejection;
- workspace identity preservation;
- doctor validation;
- restore audit event.

Acceptance focus:

- CONT-P011;
- CONT-P012;
- STATE-007;
- STATE-008.

## 6. Phase 3 — Local model path and first continuity proof

Goal: connect local inference without letting the runtime own Doll State.

### Proposed PR sequence

#### IMP-012 — Runtime adapter contract

- adapter protocol;
- normalized health, inventory, generation, cancellation, and error models;
- mocked adapter tests;
- runtime-independent model IDs.

#### IMP-013 — Ollama adapter

- local health check;
- installed model inventory mapping;
- local generation and streaming;
- timeouts and cancellation;
- no model download;
- no cloud path.

#### IMP-014 — Model manifests and bindings

- ModelManifestRecord;
- RuntimeManifestRecord;
- ModelBindingRecord;
- manual registration;
- active, previous, fallback status;
- checksum and provenance fields.

#### IMP-015 — Local conversation path

- session orchestration;
- local API chat path;
- CLI conversation path for recovery;
- scoped state retrieval;
- response provenance;
- no automatic memory creation.

Acceptance focus:

- CONT-P002;
- CONT-P004.

#### IMP-016 — Model switch and local fallback

- explicit activation;
- previous binding retention;
- fallback selection;
- rollback on failed smoke test;
- degraded-state reporting;
- no cloud request.

Acceptance focus:

- CONT-P013;
- CONT-P014;
- MODEL-006 through MODEL-010.

#### IMP-017 — Offline mode and first continuity drill

- network-disabled startup setting;
- outbound-request guard for core paths;
- offline doctor checks;
- scripted manual drill instructions;
- first real-machine continuity report.

Acceptance focus:

- CONT-P003;
- first complete Personal Lite proof.

### Phase 3 gate

Do not begin broad feature expansion until all Personal Lite continuity proof tests pass on the primary macOS machine.

## 7. Phase 4 — Capability Broker and local documents

Goal: add useful local tools without bypassing security.

### Proposed PR sequence

#### IMP-018 — Capability Broker core

- versioned capability registry;
- schema validation;
- permission checks;
- operation approval records;
- allow and deny audit events;
- timeouts and cancellation.

Acceptance focus:

- SEC-001 through SEC-005.

#### IMP-019 — Approved local document read

- user-selected external text and Markdown;
- managed copy option;
- DocumentRecord;
- path and size validation;
- extraction provenance.

Acceptance focus:

- CONT-P007.

#### IMP-020 — Artifact service completion

- artifact versions;
- project links;
- source links;
- export path through a user-controlled action;
- no silent overwrite.

#### IMP-021 — Local full-text search

- SQLite FTS5;
- index rebuild;
- authoritative versus reproducible separation;
- search without a model.

Acceptance focus:

- STATE-010.

## 8. Phase 5 — Lite general-purpose capabilities

Goal: make Lite useful for daily personal work while preserving the passed continuity proof.

Candidate PR groups:

- writing, editing, summarization, and translation workflows;
- PDF text extraction adapter;
- OCR adapter;
- CSV inspection and simple transformation;
- optional local speech-to-text;
- Open WebUI compatibility integration;
- usability improvements for memory, projects, artifacts, backup, and model switching.

Each optional adapter must fail independently and be visible through `doll doctor`.

## 9. Phase 6 — Minimal Web research

Goal: add current-information research without requiring cloud-model inference.

Proposed slices:

1. source and research-session records;
2. explicit search-provider adapter;
3. safe URL retrieval with SSRF-oriented controls;
4. content extraction;
5. local cache and retention policy;
6. citation records;
7. local-model synthesis;
8. hostile-source and prompt-injection tests;
9. offline retained-source mode.

Web research may remain experimental until all tests in the accepted suite pass.

## 10. Phase 7 — Lite release hardening

Goal: satisfy the Lite v1.0 gate.

Required work:

- complete CI matrix;
- installer or package path suitable for the release claim;
- migration drills;
- backup corruption and restore tests;
- shareable doctor report;
- support matrix;
- known limitations;
- release acceptance report;
- seven-day primary-machine soak;
- release candidate continuity drill;
- documentation review.

### Lite schedule direction

For one person using GPT for specification and review and Codex for implementation, a realistic target remains approximately:

- Personal Lite proof: several focused weeks;
- Lite v1.0: roughly 10 to 14 weeks at sustained part-time development;
- weekend-only work: potentially four to six months.

These are planning ranges, not commitments.

## 11. Phase 8 — Heavy foundation

Goal: extend performance without splitting the core.

Before hardware purchase:

- profile and role abstractions;
- embedding and reranker interfaces;
- verifier workflow design;
- media adapter contracts;
- evaluation suite expansion;
- hardware measurement schema;
- training dataset manifests;
- mocked Heavy integration tests.

After hardware purchase:

- large-model validation;
- GPU runtime validation;
- multi-role local routing;
- richer retrieval;
- vision and long-audio pipelines;
- controlled video extraction;
- LoRA or SFT experiments;
- real-machine failure and recovery drills;
- Heavy soak and release report.

### Heavy schedule direction

Heavy v1.0 is expected after Lite, with total project time likely in the range of eight to twelve months under sustained part-time work. Real completion depends on hardware and test results.

## 12. Phase 9 — Optional cloud gateway

Cloud work begins only after local release gates are stable.

Suggested order:

1. generic outbound package contract;
2. preview and redaction;
3. operating-system credential storage;
4. Ask Every Time mode;
5. one generic OpenAI-compatible adapter;
6. audit and local response storage;
7. provider-specific adapters only when justified;
8. allowlisted task mode;
9. cost and retention reporting where available.

Cloud code must remain removable.

## 13. Phase 10 — Mobile

Suggested order:

1. separate remote-access threat model;
2. mobile browser companion to the user's own PC;
3. PWA;
4. Android hybrid mode;
5. iOS hybrid mode;
6. standalone mobile Lite feasibility work.

PC continuity remains the authority for state and recovery until mobile-specific state synchronization is designed.

## 14. Issue and PR discipline

Implementation issues should contain:

- objective;
- accepted specification links;
- in-scope and out-of-scope behavior;
- data changes;
- permission and network effects;
- migration requirements;
- test IDs;
- real-machine work required;
- rollback plan.

A PR should normally implement one issue or one tightly related slice.

## 15. Definition of done for an implementation PR

An implementation PR is done when:

- code matches the accepted boundary;
- tests pass on applicable CI platforms;
- security and path failures are tested;
- persisted-state changes include schema and migration handling;
- documentation is updated;
- no private fixture is committed;
- optional dependencies fail cleanly;
- PR description states real-hardware gaps;
- review comments are resolved;
- main remains recoverable.

## 16. Specification follow-up after PR-005

The immediate next repository work is:

1. add deterministic specification generation;
2. generate `DOLL_FINAL_SPEC.md`;
3. run contradiction and requirement audit;
4. update documents where contradictions are found;
5. mark specification set 0.1 accepted for implementation;
6. open IMP-001.

## 17. Roadmap change control

The roadmap may change as measurements arrive.

Changes must preserve:

- continuity-first sequencing;
- local completion before cloud dependence;
- Lite before Heavy hardware commitment;
- test evidence before release claims;
- small PRs;
- explicit migration and rollback;
- the project owner's immediate personal-use objective.
