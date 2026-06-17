# Development roadmap

**Status:** Accepted for implementation  
**Specification version:** 0.1

## 1. Purpose

This roadmap converts the accepted product, continuity, and security specifications into an implementation sequence.

It is a sequencing document, not a promise of exact dates or pull-request counts.

The governing rule is:

> Prove user-owned continuity first, complete the model-independent safety boundary second, then add model execution and useful capabilities without weakening either pillar.

## 2. Working method

Development proceeds through small, reviewable pull requests.

Each implementation PR must:

- solve one bounded issue;
- cite the accepted specification it implements;
- describe state, permission, secret, trust, network, and migration effects;
- include tests for success and denial or failure paths;
- avoid unrelated refactoring;
- distinguish CI evidence from real-machine evidence;
- preserve a working and recoverable `main` branch;
- avoid private data, credentials, secret values, personal paths, usernames, hostnames, and home-directory details.

The normal unit of work is:

```text
1 Issue → 1 Branch → 1 Pull Request
```

The intended division of work is:

- GPT: architecture, specification, task decomposition, review, and release-gate checking;
- Codex or equivalent implementation assistance: code, tests, migrations, documentation updates, and PR preparation;
- project owner: priorities, real-machine validation, final merge, release, license, and hardware decisions.

## 3. Governing implementation order

Doll has two co-equal architectural pillars:

1. continuity of user-owned state;
2. a model-independent safety boundary.

The implementation phases are:

```text
Phase 0  Specification and principles
Phase 1  Local state foundation
Phase 2  Continuity, transfer, backup, and restore
Phase 3  Safety boundary
Phase 4  Local AI
Phase 5  Cloud and multiple models
Phase 6  Tools and external services
Phase 7  Daily use
Phase 8  Distribution, encryption, and long-term operation
```

No model adapter, inference request, conversation runtime, or model-initiated capability path may merge before the Phase 3 safety gate passes.

## 4. Current state

Completed:

- Phase 0 specification baseline;
- IMP-001 through IMP-010;
- local workspace, SQLite state, migrations, audit, managed artifacts, preferences, policies, permissions, confirmed memory, projects, decisions, state-package export/import, and verified backup creation.

Current implementation point:

- Phase 2;
- IMP-011 is the next code issue;
- IMP-011 adds backup restore and post-restore validation;
- IMP-012 will run the model-independent Continuity Acceptance Test;
- IMP-013 through IMP-023 implement and validate the safety boundary;
- local model execution begins at IMP-024 or later.

## 5. Phase 0 — Specification and principles

Goal: define product identity, continuity, state ownership, security, release evidence, and implementation order before production features.

Status: complete, subject to controlled specification changes.

Completed specification work includes:

- product identity and Continuity Contract;
- local-complete, cloud-optional architecture;
- Doll State and storage model;
- default-deny permissions and trust boundaries;
- Model Vault direction;
- platform and recovery direction;
- release scope and acceptance evidence;
- deterministic `DOLL_FINAL_SPEC.md` generation;
- ADR-005 sequencing the safety boundary before model execution.

No implementation PR may silently contradict this baseline.

## 6. Phase 1 — Local state foundation

Goal: establish a cross-platform package, private workspace, versioned authoritative state, explicit user control, and safe writes without any model dependency.

Status: complete through IMP-008.

### IMP-001 — Python package and CI skeleton

Implemented:

- Python package metadata;
- `uv` lock and development commands;
- `src/doll/` package;
- Typer CLI entry point;
- FastAPI application factory;
- pytest, lint, type-check, and coverage configuration;
- macOS, Windows, and Ubuntu CI;
- no model or external tool dependency.

### IMP-002 — Platform paths and workspace initialization

Implemented:

- platform-aware data locations;
- `doll init`;
- WorkspaceRecord;
- repository-checkout protection;
- path canonicalization;
- synthetic and Unicode fixtures.

### IMP-003 — SQLite state repository and migrations

Implemented:

- schema versioning;
- common record envelope;
- migration runner;
- transactions and revisions;
- read-only recovery opening path.

### IMP-004 — Append-oriented audit service

Implemented:

- operation IDs;
- actor and result records;
- secret-safe summaries;
- audit listing;
- append-oriented persistence.

### IMP-005 — Workspace file service

Implemented:

- managed artifact paths;
- create-new semantics;
- content hashing;
- atomic writes;
- traversal and link-escape defenses;
- size limits.

### IMP-006 — Preferences, policies, and permissions

Implemented:

- PreferenceRecord;
- PolicyRecord;
- PermissionRecord;
- denied, allow-once, ask, and scoped modes;
- no global allow-all;
- explicit management path;
- model or content text cannot count as approval.

### IMP-007 — Confirmed memory

Implemented:

- confirmed MemoryRecord management;
- provenance and sensitivity;
- archive and export;
- no automatic conversation-to-memory conversion.

### IMP-008 — Projects and decisions

Implemented:

- ProjectRecord;
- DecisionRecord;
- typed links;
- revision-safe updates;
- archive and export.

## 7. Phase 2 — Continuity, transfer, backup, and restore

Goal: make durable state inspectable, transferable, restorable, and verifiable without a model, runtime, network connection, cloud account, or preferred UI.

### IMP-009 — Doll State package export and import

Status: complete.

Implemented:

- versioned package manifest;
- JSON and JSONL records;
- checksums;
- staged validation;
- conflict reporting;
- empty-target import;
- no package-content execution.

Acceptance focus:

- STATE-003;
- STATE-004;
- STATE-008.

### IMP-010 — Backup creation and verification

Status: complete.

Implemented:

- state backup;
- workspace backup;
- SQLite snapshot;
- artifact-byte preservation;
- manifest and SHA-256 verification;
- tamper detection;
- atomic no-clobber publication;
- secret-containing unencrypted workspace-backup rejection;
- backup inventory and audit.

Acceptance focus:

- CONT-P010;
- STATE-007 foundation;
- cross-platform backup safety.

### IMP-011 — Backup restore and post-restore validation

Status: next code implementation.

Required scope:

- state-backup restore into an empty target;
- workspace-backup restore into an empty target;
- complete verification before extraction;
- staging outside the final target;
- safe path and member validation;
- SQLite integrity validation;
- workspace identity and revision validation;
- record and typed-link validation;
- artifact hash and byte validation;
- atomic publication without overwrite;
- cleanup of staging and partial output on failure;
- fresh-process post-restore validation;
- normal output without absolute local path disclosure;
- no model execution and no network access.

Acceptance focus:

- CONT-P011;
- CONT-P012;
- STATE-007;
- STATE-008;
- PLAT-005;
- PLAT-007.

### IMP-012 — Continuity Acceptance Test

Goal: prove the complete Phase 1 and Phase 2 continuity foundation before any safety-boundary or model work depends on it.

Required evidence:

- clean workspace creation;
- confirmed memory, preferences, policies, permissions, projects, decisions, typed links, audit history, and artifacts persist across process restart;
- Doll State export and import preserve implemented authoritative records;
- state backup restores into an empty target;
- workspace backup restores into an empty target;
- restored workspace identity, schema, revision, records, links, audit history, and artifact bytes match the verified source contract;
- corrupt, tampered, unsafe, mismatched, existing, or non-empty targets fail closed;
- a fresh process validates and inspects restored state without a model;
- no cloud credentials or network access are required;
- no absolute path, username, hostname, home-directory detail, secret, or personal fixture appears in shareable output;
- CI passes on macOS, Windows, and Ubuntu;
- the complete drill passes on the primary Intel Mac.

Phase 2 gate:

- IMP-011 is merged;
- required continuity and state tests pass;
- the real-machine continuity report records the tested commit and limitations;
- restore failure does not damage the last known good workspace;
- no model execution path exists.

## 8. Phase 3 — Safety boundary

Goal: implement the authority, secret, trust, instruction, capability, and confirmation boundary before any model is allowed to execute.

The safety boundary is model-independent. Tests use synthetic callers, hostile fixtures, malformed requests, and explicit management commands rather than a live model.

### IMP-013 — Secret Classification Policy

Define:

- secret classes and sensitivity levels;
- ordinary-state prohibition for secret values;
- SecretReference requirements;
- allowed metadata and prohibited value fields;
- input, output, persistence, export, backup, and diagnostic handling;
- fail-closed behavior for uncertain secret-bearing operations.

### IMP-014 — Secret Detection and Redaction

Implement:

- bounded best-effort detectors;
- structured redaction results;
- false-positive and false-negative documentation;
- redaction for user-visible errors and diagnostics;
- no broad secret-search permission;
- tests for common credential, token, key, cookie, recovery phrase, and personal-data patterns using synthetic fixtures only.

### IMP-015 — Secret-Safe Audit and Logging

Implement:

- centrally enforced audit and log sanitization;
- structured safe summaries;
- rejection or redaction of secret-bearing fields;
- path, username, hostname, and home-directory minimization;
- tests proving allowed, denied, failed, and exceptional operations do not leak secret values.

### IMP-016 — External Secret Store Contract

Define a portable contract for operating-system or compatible external secret stores:

- reference creation and lookup metadata;
- availability and locked-state reporting;
- user-presence requirements;
- create, replace, revoke, and delete semantics;
- no ordinary-state secret-value persistence;
- platform-specific adapters remain replaceable;
- unavailable secret storage cannot block non-secret core startup.

### IMP-017 — Credential Broker

Implement a narrow broker that:

- accepts SecretReference, capability, destination, scope, and operation metadata;
- obtains required user approval or presence;
- uses a credential only inside the bounded operation;
- does not return the stored secret value to a model or ordinary caller by default;
- returns a structured operation result;
- redacts errors and audit events;
- supports cancellation, timeout, and fail-closed behavior.

### IMP-018 — Claim, Evidence, and Trust Model

Implement distinct records and links for:

- confirmed facts;
- claims;
- supporting or contradicting evidence;
- inferences;
- provenance, source, confidence, uncertainty, and review status.

Required rule:

- model, tool, document, website, import, or runtime assertions do not become confirmed facts automatically.

### IMP-019 — Instruction Origin and Untrusted-Content Boundary

Implement:

- instruction-origin metadata;
- authority classes;
- immutable source attribution for imported and retrieved content;
- separation of system policy, user instruction, durable policy, content, tool result, and model proposal;
- content cannot grant permission, confirmation, or policy changes;
- unknown origin fails to the least-authoritative classification.

### IMP-020 — Prompt Injection Defense

Implement defense in depth:

- context packaging that preserves origin and authority;
- prompt-injection indicators and warnings;
- unrelated-capability and exfiltration-request detection;
- policy and permission enforcement outside the model;
- hostile document, website, metadata, OCR, transcript, and tool-result fixtures;
- no reliance on model classification as the authorization boundary.

### IMP-021 — Capability Taxonomy and Risk Tiers

Implement:

- versioned capability registry;
- input and output schemas;
- declared targets, side effects, and resource limits;
- permission and network checks;
- risk tiers;
- unknown or malformed capability denial;
- no unrestricted shell or arbitrary command-string capability;
- allow and deny audit events.

Initial risk direction:

- Tier 0: pure computation with no side effect;
- Tier 1: bounded managed read or reversible creation;
- Tier 2: scoped modification or explicit external read;
- Tier 3: destructive, externally visible, credential-bearing, account-affecting, or process-execution action;
- Prohibited: actions outside accepted release scope regardless of confirmation.

### IMP-022 — Mandatory High-Risk Confirmation

Implement:

- trusted user-controlled confirmation channel;
- fresh confirmation for every Tier 3 operation;
- exact capability, target, destination, side-effect, and credential-class preview;
- expiry and one-operation binding;
- material-change invalidation;
- no confirmation from model text, documents, websites, imports, or tool results;
- no persistent broad confirmation for high-risk operations;
- confirmation does not override policy or make a prohibited capability available.

### IMP-023 — Safety Acceptance Test

Goal: prove the complete safety boundary before model execution.

Required evidence includes:

- secret values are absent from ordinary state, logs, audit, exports, backups, fixtures, diagnostics, and model-context packages;
- SecretReference remains non-secret and portable;
- credential-broker tests complete bounded synthetic operations without exposing stored values;
- confirmed facts, claims, evidence, and inferences remain distinct through restart and export;
- instruction origin and authority survive persistence and context assembly;
- hostile content cannot grant approval, alter policy, raise authority, or trigger a capability;
- unknown and malformed capabilities fail closed;
- risk tiers are enforced;
- high-risk operations fail without fresh exact confirmation;
- changed targets, arguments, destinations, side effects, or credential classes invalidate confirmation;
- denial and failure preserve the last known good state;
- security-relevant events are auditable without leaking sensitive data;
- CI passes on macOS, Windows, and Ubuntu;
- applicable real-process checks pass on the primary Intel Mac.

Phase 3 gate:

- IMP-013 through IMP-023 are merged;
- all blocking safety tests pass;
- open known limitations are documented;
- no accepted review finding shows a route around the boundary;
- only after this gate may IMP-024 introduce a model adapter contract.

## 9. Phase 4 — Local AI

Goal: connect useful local inference without allowing the runtime or model to own state, secrets, permissions, trust decisions, or side effects.

Expected sequence begins at IMP-024.

### IMP-024 — Runtime adapter contract

- normalized health, inventory, generation, streaming, cancellation, and error contracts;
- runtime-independent model IDs;
- no direct state, secret-store, filesystem, network, or capability access;
- mocked adapter tests.

### IMP-025 — First local runtime adapter

Initial target: Ollama.

- local health check;
- installed model inventory mapping;
- local generation and streaming;
- timeout and cancellation;
- no silent model download;
- no cloud fallback;
- all context passes through accepted origin and secret controls.

### IMP-026 — Model manifests and bindings

- ModelManifestRecord;
- RuntimeManifestRecord;
- ModelBindingRecord;
- source, revision, checksum, license, and compatibility;
- quarantine, candidate, active, previous, fallback, and rollback state.

### IMP-027 — Local conversation path

- local API and CLI conversation;
- scoped state retrieval;
- response provenance;
- no automatic durable memory creation;
- no direct model capability execution;
- model proposals pass through the safety boundary.

### IMP-028 — Model switch and local fallback

- explicit activation;
- previous binding retention;
- fallback selection or offer;
- rollback after failed smoke test;
- no unrelated state rewrite;
- no cloud request.

### IMP-029 — Offline mode and local AI continuity drill

- network-disabled startup;
- outbound-request guard;
- local conversation and fallback offline;
- model replacement without state loss;
- primary-machine continuity evidence.

Phase 4 gate:

- local inference remains optional to state inspection, export, backup, restore, and recovery;
- model replacement does not rewrite unrelated state;
- the safety boundary remains the only route to side effects;
- no cloud credential is required.

## 10. Phase 5 — Cloud and multiple models

Goal: add optional performance and role expansion without making cloud access authoritative or mandatory.

Cloud work begins only after the local path and safety boundary are stable.

Expected slices:

1. generic bounded outbound-package contract;
2. exact preview, minimization, and redaction;
3. provider-independent cloud adapter interface;
4. one optional OpenAI-compatible adapter;
5. multiple local-model role routing;
6. local/cloud selection policy with no automatic cloud fallback;
7. cost, retention, destination, and audit reporting where available;
8. provider-specific adapters only when justified.

Cloud code must remain removable. Removing cloud adapters must not prevent local startup, state access, restore, or local inference.

## 11. Phase 6 — Tools and external services

Goal: add useful capabilities through the accepted Capability Broker rather than direct model authority.

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

Every adapter must:

- declare capability ID, version, risk tier, inputs, outputs, side effects, limits, and provenance;
- fail independently;
- avoid unrestricted shell execution;
- preserve instruction origin for returned content;
- use the credential broker when a credential is required;
- remain visible through doctor and audit;
- keep experimental features outside stable release claims.

## 12. Phase 7 — Daily use

Goal: make the continuity and safety foundations useful for ordinary personal work.

Candidate work:

- writing and editing;
- summarization and translation;
- planning and research workflows;
- memory review and confirmation flows;
- project and decision workflows;
- backup and restore usability;
- source, claim, evidence, and inference inspection;
- capability and confirmation usability;
- optional Open WebUI compatibility;
- accessibility and error clarity;
- performance measurement on Lite hardware;
- seven-day primary-machine soak before a Lite stable claim.

Daily-use convenience must not hide model, network, credential, permission, or risk state.

## 13. Phase 8 — Distribution, encryption, and long-term operation

Goal: make doll maintainable, recoverable, and distributable over long periods without splitting the core.

Candidate groups:

- installer and package paths;
- signed or verifiable releases where feasible;
- offline recovery kit;
- update staging and rollback;
- standard backup encryption;
- backup rotation and retention;
- long-term schema migration drills;
- support matrix and shareable doctor reports;
- Lite and Heavy profile measurement;
- Heavy hardware selection only after Lite evidence;
- richer retrieval, media, verification, and training workflows;
- mobile companion or remote access only after a separate threat model;
- multi-device synchronization only after conflict and secret-boundary design;
- periodic continuity and safety drills;
- community verification and release acceptance reports.

The project must not invent custom cryptography. Encryption work must use established operating-system or library primitives and must not make unencrypted recovery impossible without an explicit accepted product decision.

## 14. Issue and PR discipline

Implementation issues should contain:

- objective;
- accepted specification links;
- in-scope and out-of-scope behavior;
- state and schema changes;
- secret and credential effects;
- trust, evidence, and instruction-origin effects;
- permission, capability, risk, and confirmation effects;
- network and process effects;
- migration requirements;
- test IDs;
- real-machine work required;
- rollback or failure-preservation plan.

A PR should normally implement one issue or one tightly related slice.

Documentation-only sequencing changes must not include implementation code.

## 15. Definition of done for an implementation PR

An implementation PR is done when:

- code matches the accepted boundary;
- tests pass on applicable CI platforms;
- success, denial, malformed input, and recoverable failure are tested;
- security and path failures are tested;
- persisted-state changes include schema and migration handling;
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

## 16. Immediate work

The required order from the current repository state is:

1. merge the documentation change adopting ADR-005 and this roadmap;
2. return to `impl/imp-011-restore-post-validation`;
3. rebase that branch onto the updated `main`;
4. implement IMP-011 only;
5. pass CI, review, and Intel Mac real-process restore validation;
6. squash-merge IMP-011;
7. implement IMP-012 as the Continuity Acceptance Test;
8. begin IMP-013 only after the Phase 2 gate passes;
9. complete IMP-013 through IMP-023;
10. begin model work at IMP-024 or later only after the Phase 3 gate passes.

## 17. Roadmap change control

The roadmap may change as implementation evidence arrives.

Changes must preserve:

- continuity-first sequencing;
- the safety boundary before model execution;
- local completion before cloud dependence;
- memory and secret separation;
- external content as data rather than authority;
- model-independent permissions, risk, and confirmation;
- Lite evidence before Heavy hardware commitment;
- test evidence before phase or release claims;
- small PRs;
- explicit migration, rollback, and recoverable failure;
- the project owner's immediate personal-use objective.

A change that moves model execution before the Phase 3 safety gate requires a new accepted architecture decision and corresponding security and acceptance-test changes.
