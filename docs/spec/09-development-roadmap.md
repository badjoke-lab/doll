# Development roadmap

**Status:** Accepted for implementation  
**Specification version:** 0.2

## 1. Purpose

This roadmap converts the accepted product, continuity, portability, project-continuity, and security specifications into an implementation sequence.

It is a sequencing document, not a promise of exact dates or final pull-request counts.

The governing rule is:

> Prove user-owned continuity first, complete the model-independent safety boundary second, establish canonical AI-environment portability and project-continuity foundations third, then connect models, providers, and useful capabilities without weakening those guarantees.

## 2. Working method

Development proceeds through small, reviewable pull requests.

Each implementation PR must:

- solve one bounded issue;
- cite the accepted specification it implements;
- describe state, portability, project-continuity, permission, secret, trust, network, and migration effects;
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

1. continuity of user-owned state and work, including AI environment portability and project continuity;
2. a model-independent safety boundary.

The implementation phases are:

```text
Phase 0   Specification and principles
Phase 1   Local state foundation
Phase 2   Continuity, transfer, backup, and restore
Phase 3   Safety boundary
Phase 4A  AI environment portability foundation
Phase 4B  Project continuity foundation
Phase 5   Local runtime and model integration
Phase 6   Local AI portability and daily-use integration
Phase 7   Optional cloud and multiple models
Phase 8   Tools and external services
Phase 9   Distribution, encryption, and long-term operation
```

No model adapter, inference request, conversation runtime, or model-initiated capability path may merge before the Phase 3 safety gate passes.

No provider-specific cloud portability path may become the primary portability implementation before the Phase 4A canonical and generic portability gate passes.

No accepted local model integration may begin before Phase 4A and Phase 4B establish the model-independent state contracts that the first runtime will consume.

## 4. Current state

Completed:

- Phase 0 specification baseline, subject to controlled specification changes;
- Phase 1 local state foundation;
- Phase 2 continuity, state-package transfer, backup, restore, and model-independent acceptance;
- Phase 3 model-independent safety boundary;
- Phase 4A AI environment portability foundation;
- IMP-001 through IMP-023;
- IMP-030 through IMP-039;
- local workspace, SQLite state, migrations, managed artifacts, preferences, policies, permissions, confirmed memory, projects, decisions, state-package v2 export with v1 read compatibility and a versioned authoritative record registry, verified backup, restore, continuity acceptance, the model-independent safety boundary, canonical conversation and event state, portability adapter and result records, generic import staging, generic export, reviewed publication, source preservation, idempotency, loss visibility, and Phase 4A acceptance evidence.

Current implementation point:

- Phase 4A passed its generic portability gate on 2026-06-25;
- accepted real-machine evidence is bound to commit `839a4ca7a37753fadf81c3e8e79f140e6d66bc03` on the primary Intel Mac with networking disabled;
- Phase 4B project continuity is now the active foundation phase;
- IMP-038 establishes Doll State Package format v2 for new exports while preserving supported format v1 inspection, verification, planning, and import;
- IMP-039 adds the versioned authoritative record registry used by package export, manifest validation, typed-validator selection, and source-version inventory checks;
- the next bounded Phase 4B implementation issue receives IMP-040;
- local model execution begins only after Phase 4B passes.

Implementation identifier policy:

- merged implementation identifiers never change;
- new implementation identifiers increase monotonically from IMP-030 onward;
- unused legacy reservations IMP-024 through IMP-029 are retired permanently and must not be reused;
- unscheduled roadmap slices do not reserve identifiers and receive the next monotonic identifier only when an implementation issue is opened.

The controlled specification-set 0.2 change does not reopen completed implementation evidence. It changes future requirements and sequencing.

## 5. Phase 0 — Specification and principles

Goal: define product identity, continuity, state ownership, security, portability, project continuity, release evidence, and implementation order before production features.

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
- ADR-006 making AI environment portability and a documented exit path mandatory continuity requirements;
- ADR-007 making model-independent project state and resumption mandatory continuity requirements.

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

Phase 2 is complete. Later portability and project-continuity work extends the preserved state; it does not invalidate completed doll-to-doll continuity evidence.

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

Status: complete.

Implemented:

- bounded best-effort in-memory text scanning;
- structured findings that retain no secret values or reconstruction hints;
- deterministic overlap normalization and typed redaction markers;
- scan-character and finding-count limits with fail-safe output;
- no original text returned after scan-limit or finding-limit exhaustion;
- synthetic detection for selected credential assignments, authorization values, token forms, private-key blocks, cookies, recovery phrases, email addresses, labeled telephone numbers, and private home paths;
- recursive secret-safe diagnostic rendering;
- user-visible CLI exception-detail redaction;
- portability-aware false-positive and false-negative documentation;
- no model, cloud, network, filesystem scan, or secret-store dependency.

### IMP-015 — Secret-Safe Audit and Logging

Status: complete.

Implemented centrally enforced secret-safe audit construction, bounded summaries and metadata,
control-character defenses, private-environment minimization, safe exceptional paths, and
failure-preserving tests.

### IMP-016 — External Secret Store Contract

Status: complete.

Implemented a replaceable secret-store contract with non-secret references, adapter capabilities,
availability and lock state, user-presence requirements, lifecycle operations, validation,
failure isolation, and synthetic in-memory acceptance fixtures.

### IMP-017 — Credential Broker

Status: complete.

Implemented bounded credential use without returning stored values to models or ordinary callers,
with exact reference, destination, scope, purpose, approval, timeout, cancellation, result, audit,
and failure controls.

### IMP-018 — Claim, Evidence, and Trust Model

Status: complete.

Implemented separate confirmed facts, claims, evidence, and inferences with immutable provenance,
confidence, uncertainty, review state, explicit support and contradiction links, and no automatic
import-to-fact promotion.

### IMP-019 — Instruction Origin and Untrusted-Content Boundary

Status: complete.

Implemented immutable source attribution, origin-derived authority classes, data-only treatment
for external, imported, tool, runtime, model, and unknown content, stale durable-policy downgrade,
non-escalating derivation links, structured context channels, and state-package validation.

### IMP-020 — Prompt Injection Defense

Status: complete.

Implemented bounded advisory indicators that retain no matched content, secret-safe
complete-or-fail context packaging, structural origin-channel separation, archive and stale-policy
downgrade preservation, external authorization guards based only on IMP-019, hostile-source and
exfiltration fixtures, unrelated-capability defenses, and no model-only authorization boundary.

### IMP-021 — Capability Taxonomy and Risk Tiers

Status: complete.

Implemented an immutable versioned capability registry, deterministic fingerprints, fixed Tier 0 through Tier 3 classifications, bounded argument and target contracts, exact side-effect and risk matching, target-to-permission binding, resource and timeout limits, read-only permission preflight, explicit network policy, release exclusion, secret-safe audit, Tier 3 denial pending IMP-022, and no unrestricted shell or arbitrary command capability.

### IMP-022 — Mandatory High-Risk Confirmation

Status: complete.

Implemented fresh user-controlled confirmation for every Tier 3 operation, exact binding to capability and side effects, expiry, material-change invalidation, one-time consumption support, and no confirmation from content.

### IMP-023 — Safety Acceptance Test

Status: complete.

Proved secret separation, credential isolation, claim and evidence separation, instruction origin, hostile-content resistance, capability denial, risk enforcement, exact confirmation, audit safety, cross-platform CI, and the primary Intel Mac offline real-process gate.

Accepted Phase 3 evidence:

- merged implementation commit: `22e78b09ba0c144c2cddc918992d52f845c30185`;
- Ubuntu, macOS, and Windows CI passed;
- Windows reported 745 passed, 1 skipped, and 95.25% coverage;
- the primary Intel Mac run passed on Darwin `x86_64` with networking disabled;
- the accepted report returned `phase3_gate_complete = true`;
- SEC-007 remains explicitly deferred because no API listener exists.

Phase 3 gate status: passed on 2026-06-22.

Phase 3 gate:

- IMP-013 through IMP-023 are merged;
- all blocking safety tests pass;
- known limitations are documented;
- no accepted review finding shows a route around the boundary;
- only after this gate may portability adapters, project-continuity proposal adapters, model adapters, or model execution paths accept real untrusted input.

## 9. Phase 4A — AI environment portability foundation

Goal: establish canonical conversation and event state, generic import and export, and adapter contracts before the first runtime, provider, or UI can define Doll State accidentally.

This phase is model-independent and uses synthetic fixtures.

Status: complete through IMP-037.

Completed implementation slices:

- IMP-030 — canonical ConversationRecord and extensible ConversationEventRecord schemas;
- IMP-031 — canonical conversation and event persistence through the generic Doll State record envelope;
- IMP-032 — source and target adapter contracts and SourceEnvironmentRecord;
- IMP-033 — portability batch, mapping, loss, export, and preservation result contracts;
- IMP-034 — generic JSON and JSONL import staging;
- IMP-035 — deterministic generic JSON, JSONL, Markdown, manifest, checksum, and managed-file export;
- IMP-036 — reviewed canonical publication, original-source preservation, deterministic mapping, idempotency, conflict handling, quarantine, loss reporting, and imported-content authority restrictions;
- IMP-037 — PORT-004 through PORT-012 automated and primary Intel Mac acceptance evidence.

Accepted Phase 4A evidence:

- merged implementation commit: `839a4ca7a37753fadf81c3e8e79f140e6d66bc03`;
- Ubuntu, macOS, and Windows CI passed with 859 tests and 95.14% total coverage;
- the primary Intel Mac run passed on Darwin `x86_64`, Python 3.12.13, with networking disabled;
- all declared PORT-004 through PORT-012 checks passed;
- the accepted report returned `phase4a_gate_complete = true`;
- the stored result contains no private path, username, hostname, credential, secret value, fixture content, or personal conversation data;
- PORT-001 through PORT-003 and PORT-013 through PORT-016 remain future portability work;
- stable anti-lock-in remains unclaimed until PORT-015 passes.

Phase 4A gate status: passed on 2026-06-25.

Phase 4A gate:

- canonical state is independent of provider-native and runtime-native response objects;
- provider, application, interface, runtime, and model identity are separate;
- generic export is inspectable without a model or preferred UI;
- repeated import is idempotent for unchanged source objects;
- material transformation and loss are explicit;
- imported content cannot become policy, permission, confirmation, capability, confirmed memory, confirmed fact, approved procedure, confirmed checkpoint, or completed work automatically;
- CI passes on macOS, Windows, and Ubuntu;
- the primary Intel Mac offline acceptance run passes;
- no provider-specific cloud adapter is required.

## 10. Phase 4B — Project continuity foundation

Goal: preserve the work itself before a model is connected to it.

This phase is model-independent and follows `03b-project-continuity-and-resumption.md` and `08b-project-continuity-acceptance.md`.

Status: in progress through IMP-039.

Completed implementation slices:

- IMP-038 — Doll State Package format v2 foundation and supported format v1 read compatibility.
- IMP-039 — versioned authoritative record registry for package validation.

Remaining implementation slices, with identifiers assigned only when scheduled:

1. ProjectRecord v2 while preserving readable ProjectRecord v1;
2. WorkItemRecord lifecycle, dependencies, blockers, acceptance criteria, and verification state;
3. ProcedureRecord lifecycle, versioning, non-authority rule, validation, and rollback description;
4. ProjectCheckpointRecord basis revisions, deterministic fingerprint, confirmation, and stale detection;
5. deterministic `doll project status` view;
6. deterministic project-scoped Resume Bundle with manifest, checksums, machine-readable records, and generated HANDOFF.md;
7. package, backup, restore, fresh-process, hostile-import, and secret-safe output coverage;
8. PROJ-001 through PROJ-012 acceptance evidence.

Implementation rule:

- no new authoritative project-continuity record may become creatable before the same implementation slice preserves it through state package export/import, backup, restore, and fresh-process validation;
- a passing verifier records evidence but does not automatically complete the whole work item in the first implementation;
- generated status and HANDOFF.md remain non-authoritative views.

Phase 4B gate:

- ProjectRecord v2 and all implemented child records survive restart, package transfer, backup, restore, and fresh-process inspection;
- untrusted sources cannot approve procedures, confirm checkpoints, clear blockers, or complete work;
- checkpoint freshness depends on relevant basis revisions rather than unrelated workspace changes;
- project status and reproducible Resume Bundle output are deterministic;
- package v2 validates the new records and supported v1 fixtures remain importable;
- project-continuity output contains no secret values or private host details;
- all blocking PROJ tests pass on the required evidence levels.

## 11. Phase 5 — Local runtime and model integration

Goal: connect useful local inference without allowing the runtime or model to own state, secrets, permissions, trust decisions, portability, project progress, or side effects.

The following work retains its required order but does not reserve implementation identifiers. Each slice receives the next monotonic IMP identifier only after the Phase 4A and Phase 4B gates pass and the slice is scheduled. The unused identifiers IMP-024 through IMP-029 are retired and must not be reused.

### Runtime adapter contract

Implement normalized health, inventory, generation, streaming, cancellation, error, offline, and capability contracts with runtime-independent model identity and no direct authority over state, secrets, files, network, capabilities, or project completion.

### First local runtime adapter

Initial target: Ollama.

Implement local health, inventory mapping, generation, streaming, timeout, cancellation, no silent download, no cloud fallback, and context flow through accepted secret and origin controls.

### Model manifests and bindings

Implement ModelManifestRecord, RuntimeManifestRecord, ModelBindingRecord, provenance, exact revision, checksums, license, compatibility, quarantine, candidate, active, previous, fallback, and rollback state.

### Canonical local conversation path

Implement local API and CLI conversation using only the Phase 4A canonical conversation and event records and Phase 4B project-continuity views where requested.

Required properties:

- scoped state retrieval;
- response provenance;
- separate provider, application, interface, runtime, model, and operation attribution;
- no provider-native object as authoritative state;
- no automatic durable memory creation;
- no direct model capability execution;
- no automatic work completion, procedure approval, blocker clearing, or checkpoint confirmation;
- model proposals pass through the safety boundary.

### Model switch and local fallback

Implement explicit activation, previous binding retention, fallback selection or offer, smoke-test rollback, no unrelated state rewrite, and no cloud request.

### Offline mode and local AI continuity drill

Prove network-disabled startup, outbound-request guard, local conversation, project-state inspection, fallback, model replacement without state loss, and primary-machine evidence.

Phase 5 gate:

- local inference remains optional to state inspection, project status, Resume Bundle export, backup, restore, and recovery;
- model replacement does not rewrite unrelated state;
- canonical conversation and project state survive runtime-private object removal;
- the safety boundary remains the only route to side effects and authoritative project mutation;
- no cloud credential or provider is required.

## 12. Phase 6 — Local AI portability and daily-use integration

Goal: prove that doll can enter from, operate across, and exit to documented formats around real local AI use.

Required sequence, with later non-conflicting implementation identifiers:

1. select one local AI environment actually used by the project owner;
2. implement its source adapter against the Phase 4A contract;
3. import a synthetic and then private real test workspace;
4. verify inventory, source provenance, duplicate prevention, quarantine, and loss reports;
5. retrieve imported context through a different approved model or runtime where practical;
6. remove or disable the original local application and confirm Doll State remains usable;
7. export selected canonical state and one project Resume Bundle generically;
8. pass PORT-001, PORT-003, PORT-013, PORT-015, and applicable PORT-002 evidence;
9. implement the project owner's ChatGPT history adapter only after the local path proves the contract;
10. run the private PORT-014 migration drill without committing personal data.

Daily-use work may then expand writing, editing, summarization, translation, planning, memory review, project and decision workflows, work-item proposals, portability review, accessibility, error clarity, Lite performance, and soak testing.

## 13. Phase 7 — Optional cloud and multiple models

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

Cloud code must remain removable. Removing cloud adapters must not prevent local startup, state access, project status, generic export, Resume Bundle export, restore, local inference, or local migration inspection.

## 14. Phase 8 — Tools and external services

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

Every adapter must declare capability ID, version, risk tier, inputs, outputs, side effects, limits, provenance, instruction origin, credential behavior, project-state effects, and failure isolation.

## 15. Phase 9 — Distribution, encryption, and long-term operation

Goal: make doll maintainable, recoverable, portable, resumable, and distributable over long periods without splitting the core.

Candidate groups:

- installer and package paths;
- signed or verifiable releases where feasible;
- offline recovery kit;
- update staging and rollback;
- standard backup encryption;
- backup rotation and retention;
- long-term schema, package, portability, and project-resumption migration drills;
- support matrix and shareable doctor reports;
- Lite and Heavy measurement;
- richer retrieval, media, verification, and training workflows;
- mobile or remote access only after a separate threat model;
- multi-device synchronization only after conflict and secret-boundary design;
- periodic continuity, portability, project-resumption, and safety drills;
- community verification and release acceptance reports.

The project must not invent custom cryptography.

## 16. Issue and PR discipline

Implementation issues should contain:

- objective;
- accepted specification links;
- in-scope and out-of-scope behavior;
- state and schema changes;
- project-continuity and checkpoint effects;
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

Implementation identifiers follow a monotonic allocation rule:

- the next implementation issue after IMP-037 is IMP-038;
- every later implementation issue receives the next integer greater than all previously assigned IMP identifiers;
- retired identifiers IMP-024 through IMP-029 remain unused permanently;
- roadmap entries do not reserve identifiers before an implementation issue is opened;
- merged issues, pull requests, commits, and implementation records are never renumbered.

Documentation-only sequencing changes must not include implementation code.

## 17. Definition of done for an implementation PR

An implementation PR is done when:

- code matches the accepted boundary;
- tests pass on applicable CI platforms;
- success, denial, malformed input, and recoverable failure are tested;
- security and path failures are tested;
- persisted-state changes include schema and migration handling;
- import or export changes include provenance, idempotency, and loss handling;
- new authoritative record types participate in package, backup, restore, and fresh-process validation in the same merge;
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

## 18. Immediate work

The required order after the Phase 4A gate is:

1. schedule the first bounded Phase 4B package-v2 and project-continuity slice as IMP-038;
2. continue Phase 4B with monotonically increasing identifiers;
3. pass the Phase 4B project-continuity gate;
4. schedule local runtime and model integration slices with the next monotonic identifiers;
5. prove a real local AI migration path before provider-specific cloud portability becomes a primary claim.

## 19. Roadmap change control

The roadmap may change as implementation evidence arrives.

Changes must preserve:

- continuity-first sequencing;
- the safety boundary before model execution;
- canonical and generic portability before provider-specific cloud portability;
- project-continuity foundations before model-owned project workflows;
- local completion before cloud dependence;
- memory and secret separation;
- external and imported content as data rather than authority;
- model-independent permissions, risk, confirmation, work completion, procedure approval, and checkpoint confirmation;
- explicit mapping and loss reporting;
- a documented exit path from doll;
- deterministic and inspectable Resume Bundle output;
- Lite evidence before Heavy hardware commitment;
- test evidence before phase or release claims;
- small PRs;
- explicit migration, rollback, and recoverable failure;
- the project owner's immediate personal-use objective.

Moving model execution before the Phase 3 safety gate or before the required Phase 4 foundations requires a new accepted architecture decision and corresponding security and acceptance-test changes.

Weakening AI environment portability, project continuity, generic inspectable export, source provenance, idempotency, loss visibility, checkpoint freshness, Resume Bundle integrity, trusted completion authority, or the local-first migration priority requires a dedicated architecture decision.
