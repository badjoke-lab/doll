# Development roadmap

**Status:** Accepted for implementation  
**Specification version:** 0.1

## 1. Purpose

This roadmap converts the accepted product, continuity, portability, and security specifications into an implementation sequence.

It is a sequencing document, not a promise of exact dates or final pull-request counts.

The governing rule is:

> Prove user-owned continuity first, complete the model-independent safety boundary second, establish the portability foundation third, then connect models, providers, and useful capabilities without weakening those guarantees.

## 2. Working method

Development proceeds through small, reviewable pull requests.

Each implementation PR must:

- solve one bounded issue;
- cite the accepted specification it implements;
- describe state, portability, permission, secret, trust, network, and migration effects;
- include tests for success and denial or failure paths;
- avoid unrelated refactoring;
- distinguish CI evidence from real-machine evidence;
- preserve a working and recoverable `main` branch;
- avoid private data, credentials, secret values, personal paths, usernames, hostnames, and home-directory details.

The normal unit of work is:

```text
1 Issue -> 1 Branch -> 1 Pull Request
```

The intended division of work is:

- GPT: architecture, specification, task decomposition, review, and release-gate checking;
- Codex or equivalent implementation assistance: code, tests, migrations, documentation updates, and PR preparation;
- project owner: priorities, real-machine validation, final merge, release, license, and hardware decisions.

## 3. Governing implementation order

Doll has two co-equal architectural pillars:

1. continuity of user-owned state, including AI environment portability;
2. a model-independent safety boundary.

The implementation phases are:

```text
Phase 0  Specification and principles
Phase 1  Local state foundation
Phase 2  Continuity, transfer, backup, and restore
Phase 3  Safety boundary
Phase 4  AI environment portability foundation
Phase 5  Local runtime and model integration
Phase 6  Local AI portability and daily-use integration
Phase 7  Optional cloud and multiple models
Phase 8  Tools and external services
Phase 9  Distribution, encryption, and long-term operation
```

No model adapter, inference request, conversation runtime, or model-initiated capability path may merge before the Phase 3 safety gate passes.

No provider-specific cloud portability path may become the primary portability implementation before the Phase 4 canonical and generic portability gate passes.

## 4. Current state

Completed:

- Phase 0 specification baseline;
- Phase 1 local state foundation;
- Phase 2 continuity, state-package transfer, backup, restore, and model-independent acceptance;
- IMP-001 through IMP-013;
- local workspace, SQLite state, migrations, audit, managed artifacts, preferences, policies, permissions, confirmed memory, projects, decisions, state-package export/import, verified backup, restore, continuity acceptance, and secret-classification enforcement.

Current implementation point:

- Phase 3 is in progress;
- IMP-013 is complete;
- IMP-014 is the next implementation item;
- IMP-014 through IMP-023 complete and validate the remaining safety boundary;
- Phase 4 portability work begins only after the Phase 3 gate;
- local model execution begins after both the Phase 3 gate and the required Phase 4 contracts that prevent the first runtime from becoming the canonical state format.

The controlled documentation change adopting ADR-006 does not reopen Phase 0 or change completed implementation evidence. It changes future requirements and sequencing.

## 5. Phase 0 — Specification and principles

Goal: define product identity, continuity, state ownership, security, portability, release evidence, and implementation order before production features.

Status: complete, subject to controlled specification changes.

Accepted specification work includes:

- product identity and Continuity Contract;
- local-complete, cloud-optional architecture;
- Doll State and storage model;
- default-deny permissions and trust boundaries;
- Model Vault direction;
- platform and recovery direction;
- release scope and acceptance evidence;
- deterministic `DOLL_FINAL_SPEC.md` generation;
- ADR-005 sequencing the safety boundary before model execution;
- ADR-006 making AI environment portability and a documented exit path mandatory continuity requirements.

No implementation PR may silently contradict this baseline.

## 6. Phase 1 — Local state foundation

Goal: establish a cross-platform package, private workspace, versioned authoritative state, explicit user control, and safe writes without model dependency.

Status: complete through IMP-008.

### IMP-001 — Python package and CI skeleton

Implemented package metadata, `src/doll/`, CLI and API foundations, tests, lint, typing, coverage, and macOS, Windows, and Ubuntu CI without a model dependency.

### IMP-002 — Platform paths and workspace initialization

Implemented platform-aware private workspace creation, stable WorkspaceRecord identity, repository-checkout protection, path canonicalization, and synthetic Unicode fixtures.

### IMP-003 — SQLite state repository and migrations

Implemented schema versions, common record envelopes, transactions, revisions, migrations, and read-only recovery opening.

### IMP-004 — Append-oriented audit service

Implemented operation IDs, actor and result records, bounded summaries, listing, and append-oriented persistence.

### IMP-005 — Workspace file service

Implemented managed artifact paths, create-new semantics, hashing, atomic writes, traversal and link-escape defenses, and size limits.

### IMP-006 — Preferences, policies, and permissions

Implemented PreferenceRecord, PolicyRecord, PermissionRecord, explicit modes, no universal allow-all, and a management path that cannot treat model or content text as approval.

### IMP-007 — Confirmed memory

Implemented confirmed MemoryRecord management, provenance, sensitivity, archive, export, and no automatic conversation-to-memory conversion.

### IMP-008 — Projects and decisions

Implemented ProjectRecord, DecisionRecord, typed links, revision-safe updates, archive, and export.

## 7. Phase 2 — Continuity, transfer, backup, and restore

Goal: make durable state inspectable, transferable, restorable, and verifiable without a model, runtime, network connection, cloud account, or preferred UI.

Status: complete through IMP-012.

### IMP-009 — Doll State package export and import

Implemented versioned manifests, JSON and JSONL records, checksums, staged validation, conflict reporting, empty-target import, and no package-content execution.

### IMP-010 — Backup creation and verification

Implemented state and workspace backups, SQLite snapshots, artifact-byte preservation, manifest and SHA-256 verification, tamper detection, atomic publication, backup inventory, audit, and secret-policy rejection for unsafe unencrypted backups.

### IMP-011 — Backup restore and post-restore validation

Implemented verified empty-target restore, pre-extraction validation, staging, path and member defenses, SQLite and record validation, artifact verification, atomic publication, failure cleanup, fresh-process validation, privacy-safe output, and no model or network dependency.

### IMP-012 — Continuity Acceptance Test

Proved restart persistence, state transfer, backup restore, fresh-process inspection, failure preservation, model independence, network independence, cross-platform CI, and the primary Intel Mac continuity drill.

Phase 2 is complete. Later portability work extends transfer beyond doll-native packages; it does not invalidate the completed doll-to-doll continuity evidence.

## 8. Phase 3 — Safety boundary

Goal: implement the authority, secret, trust, instruction, capability, and confirmation boundary before any model is allowed to execute.

The safety boundary is model-independent. Tests use synthetic callers, hostile fixtures, malformed requests, imported-content fixtures, and explicit management commands rather than a live model.

### IMP-013 — Secret Classification Policy

Status: complete.

Implemented:

- closed secret and credential classes;
- ordinary-state prohibition for secret values;
- validated non-secret SecretReference metadata;
- explicit handling decisions for input, state, audit, logs, export, backup, diagnostics, model context, output, external stores, and bounded operations;
- fail-closed behavior for uncertain requests;
- enforcement in generic state create and update paths before transaction start;
- tests proving rejected writes do not advance record, state, or workspace revisions.

### IMP-014 — Secret Detection and Redaction

Status: next.

Implement:

- bounded best-effort detectors;
- structured redaction results;
- false-positive and false-negative documentation;
- redaction for user-visible errors and diagnostics;
- detection coverage for future imported conversation, attachment, and configuration content;
- no broad secret-search permission;
- synthetic credential, token, key, cookie, recovery phrase, and personal-data fixtures.

### IMP-015 — Secret-Safe Audit and Logging

Implement centrally enforced sanitization, safe summaries, rejection or redaction of secret-bearing fields, private-environment minimization, and exceptional-path tests.

### IMP-016 — External Secret Store Contract

Define a replaceable operating-system or compatible secret-store contract with non-secret references, availability and lock state, user-presence requirements, lifecycle operations, and failure isolation.

### IMP-017 — Credential Broker

Implement bounded credential use without returning stored values to models or ordinary callers, with destination, scope, approval, timeout, cancellation, result, and audit controls.

### IMP-018 — Claim, Evidence, and Trust Model

Implement separate confirmed facts, claims, evidence, and inferences with provenance, confidence, uncertainty, and review state. Imports do not create confirmed facts directly.

### IMP-019 — Instruction Origin and Untrusted-Content Boundary

Implement immutable source attribution and authority classes for system policy, user instruction, durable policy, external content, imported data, tool results, and model proposals.

### IMP-020 — Prompt Injection Defense

Implement context packaging that preserves origin, policy enforcement outside the model, hostile source fixtures, exfiltration and unrelated-capability defenses, and no model-only authorization boundary.

### IMP-021 — Capability Taxonomy and Risk Tiers

Implement a versioned capability registry, schemas, targets, side effects, limits, permission and network checks, risk tiers, denial of malformed requests, and no unrestricted shell.

### IMP-022 — Mandatory High-Risk Confirmation

Implement fresh user-controlled confirmation for every Tier 3 operation, exact binding to capability and side effects, expiry, material-change invalidation, and no confirmation from content.

### IMP-023 — Safety Acceptance Test

Prove secret separation, credential isolation, claim and evidence separation, instruction origin, hostile-content resistance, capability denial, risk enforcement, exact confirmation, audit safety, cross-platform CI, and applicable primary-machine checks.

Phase 3 gate:

- IMP-013 through IMP-023 are merged;
- all blocking safety tests pass;
- known limitations are documented;
- no accepted review finding shows a route around the boundary;
- only after this gate may portability adapters, model adapters, or model execution paths accept real untrusted input.

## 9. Phase 4 — AI environment portability foundation

Goal: establish canonical conversation and event state, generic import and export, and adapter contracts before the first runtime, provider, or UI can define Doll State accidentally.

This phase is model-independent and uses synthetic fixtures.

Required implementation slices, with identifiers assigned only when scheduled:

1. canonical ConversationRecord and extensible ConversationEventRecord schemas;
2. SourceEnvironmentRecord, ImportBatchRecord, MappingReportRecord, PortabilityLossRecord, and ExportBatchRecord;
3. source-adapter and target-adapter contracts;
4. generic JSON or JSONL import staging;
5. generic JSON, JSONL, Markdown, manifest, checksum, and managed-file export;
6. original-source hash and optional managed snapshot;
7. deterministic mapping, provenance, idempotency, conflict, and quarantine behavior;
8. mapping and loss reports;
9. imported-content authority restrictions;
10. PORT-004 through PORT-012 acceptance evidence.

Phase 4 gate:

- canonical state is independent of provider-native and runtime-native response objects;
- provider, application, interface, runtime, and model identity are separate;
- generic export is inspectable without a model or preferred UI;
- repeated import is idempotent for unchanged source objects;
- material transformation and loss are explicit;
- imported content cannot become policy, permission, confirmation, capability, confirmed memory, or confirmed fact automatically;
- CI passes on macOS, Windows, and Ubuntu;
- no provider-specific cloud adapter is required.

## 10. Phase 5 — Local runtime and model integration

Goal: connect useful local inference without allowing the runtime or model to own state, secrets, permissions, trust decisions, portability, or side effects.

Existing implementation identifiers remain unchanged.

### IMP-024 — Runtime adapter contract

Implement normalized health, inventory, generation, streaming, cancellation, error, offline, and capability contracts with runtime-independent model identity and no direct authority over state, secrets, files, network, or capabilities.

### IMP-025 — First local runtime adapter

Initial target: Ollama.

Implement local health, inventory mapping, generation, streaming, timeout, cancellation, no silent download, no cloud fallback, and context flow through accepted secret and origin controls.

### IMP-026 — Model manifests and bindings

Implement ModelManifestRecord, RuntimeManifestRecord, ModelBindingRecord, provenance, exact revision, checksums, license, compatibility, quarantine, candidate, active, previous, fallback, and rollback state.

### IMP-027 — Canonical local conversation path

Implement local API and CLI conversation using only the Phase 4 canonical conversation and event records.

Required properties:

- scoped state retrieval;
- response provenance;
- separate provider, application, interface, runtime, model, and operation attribution;
- no provider-native object as authoritative state;
- no automatic durable memory creation;
- no direct model capability execution;
- model proposals pass through the safety boundary.

### IMP-028 — Model switch and local fallback

Implement explicit activation, previous binding retention, fallback selection or offer, smoke-test rollback, no unrelated state rewrite, and no cloud request.

### IMP-029 — Offline mode and local AI continuity drill

Prove network-disabled startup, outbound-request guard, local conversation, fallback, model replacement without state loss, and primary-machine evidence.

Phase 5 gate:

- local inference remains optional to state inspection, export, backup, restore, and recovery;
- model replacement does not rewrite unrelated state;
- canonical conversation state survives runtime-private object removal;
- the safety boundary remains the only route to side effects;
- no cloud credential is required.

## 11. Phase 6 — Local AI portability and daily-use integration

Goal: prove that doll can enter from, operate across, and exit to documented formats around real local AI use.

Required sequence, with later non-conflicting implementation identifiers:

1. select one local AI environment actually used by the project owner;
2. implement its source adapter against the Phase 4 contract;
3. import a synthetic and then private real test workspace;
4. verify inventory, source provenance, duplicate prevention, quarantine, and loss reports;
5. retrieve imported context through a different approved model or runtime where practical;
6. remove or disable the original local application and confirm Doll State remains usable;
7. export selected canonical state generically;
8. pass PORT-001, PORT-003, PORT-013, PORT-015, and applicable PORT-002 evidence;
9. implement the project owner's ChatGPT history adapter only after the local path proves the contract;
10. run the private PORT-014 migration drill without committing personal data.

Daily-use work may then expand writing, editing, summarization, translation, planning, memory review, project and decision workflows, portability review, accessibility, error clarity, Lite performance, and soak testing.

## 12. Phase 7 — Optional cloud and multiple models

Goal: add optional performance and role expansion without making cloud access authoritative, mandatory, or the canonical portability path.

Expected slices:

1. generic bounded outbound-package contract;
2. exact preview, minimization, and redaction;
3. provider-independent cloud adapter interface;
4. one optional provider adapter, potentially OpenAI-compatible;
5. multiple local-model role routing;
6. local and cloud selection policy with no automatic cloud fallback;
7. cost, retention, destination, and audit reporting where available;
8. provider-specific import or export adapters only after generic and local portability gates;
9. additional providers only when justified.

Cloud code must remain removable. Removing cloud adapters must not prevent local startup, state access, generic export, restore, local inference, or local migration inspection.

## 13. Phase 8 — Tools and external services

Goal: add useful capabilities through the accepted Capability Broker rather than direct model or adapter authority.

Candidate groups:

- approved local document read;
- artifact versioning and export;
- local full-text search;
- safe URL retrieval and Web research;
- PDF extraction;
- OCR;
- CSV inspection and transformation;
- image, audio, and video adapters;
- optional speech-to-text;
- narrowly scoped external-service integrations.

Every adapter must declare capability ID, version, risk tier, inputs, outputs, side effects, limits, provenance, instruction origin, credential behavior, and failure isolation.

## 14. Phase 9 — Distribution, encryption, and long-term operation

Goal: make doll maintainable, recoverable, portable, and distributable over long periods without splitting the core.

Candidate groups:

- installer and package paths;
- signed or verifiable releases where feasible;
- offline recovery kit;
- update staging and rollback;
- standard backup encryption;
- backup rotation and retention;
- long-term schema and portability migration drills;
- support matrix and shareable doctor reports;
- Lite and Heavy measurement;
- richer retrieval, media, verification, and training workflows;
- mobile or remote access only after a separate threat model;
- multi-device synchronization only after conflict and secret-boundary design;
- periodic continuity, portability, and safety drills;
- community verification and release acceptance reports.

The project must not invent custom cryptography.

## 15. Issue and PR discipline

Implementation issues should contain:

- objective;
- accepted specification links;
- in-scope and out-of-scope behavior;
- state and schema changes;
- import, export, mapping, and loss effects;
- secret and credential effects;
- trust, evidence, provenance, and instruction-origin effects;
- permission, capability, risk, and confirmation effects;
- network and process effects;
- migration requirements;
- test IDs;
- real-machine work required;
- rollback or failure-preservation plan.

A PR should normally implement one issue or one tightly related slice.

Documentation-only sequencing changes must not include implementation code.

## 16. Definition of done for an implementation PR

An implementation PR is done when:

- code matches the accepted boundary;
- tests pass on applicable CI platforms;
- success, denial, malformed input, and recoverable failure are tested;
- security and path failures are tested;
- persisted-state changes include schema and migration handling;
- import or export changes include provenance, idempotency, and loss handling;
- secret-bearing paths are classified and tested;
- audit and user-visible output are checked for leakage;
- documentation is updated;
- no private or secret fixture is committed;
- coverage does not fall below the accepted threshold;
- blanket coverage exclusions are not used to hide untested logic;
- optional dependencies fail cleanly;
- PR description states real-hardware gaps;
- review comments are resolved;
- `main` remains recoverable.

## 17. Immediate work

The required order from `main` commit `14724d2cab328bafc398ea2beac2f23a176ee4fd` is:

1. merge the documentation-only change adopting ADR-006, the portability specification, PORT tests, and this revised roadmap;
2. confirm the generated combined specification and all documentation checks;
3. return to Phase 3 without starting portability implementation;
4. create and implement IMP-014 only;
5. continue IMP-015 through IMP-023 in order;
6. pass the Phase 3 safety gate;
7. schedule Phase 4 portability-foundation issues with new non-conflicting identifiers;
8. pass the Phase 4 portability gate;
9. begin IMP-024 through IMP-029 local model work;
10. prove a real local AI migration path before provider-specific cloud portability becomes a primary claim.

## 18. Roadmap change control

The roadmap may change as implementation evidence arrives.

Changes must preserve:

- continuity-first sequencing;
- the safety boundary before model execution;
- canonical and generic portability before provider-specific cloud portability;
- local completion before cloud dependence;
- memory and secret separation;
- external and imported content as data rather than authority;
- model-independent permissions, risk, and confirmation;
- explicit mapping and loss reporting;
- a documented exit path from doll;
- Lite evidence before Heavy hardware commitment;
- test evidence before phase or release claims;
- small PRs;
- explicit migration, rollback, and recoverable failure;
- the project owner's immediate personal-use objective.

Moving model execution before the Phase 3 safety gate requires a new accepted architecture decision and corresponding security and acceptance-test changes.

Weakening AI environment portability, generic inspectable export, source provenance, idempotency, loss visibility, or the local-first migration priority requires a dedicated architecture decision.
