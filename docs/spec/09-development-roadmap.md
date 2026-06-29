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
- Phase 4B project continuity foundation;
- Phase 5 local runtime and model integration;
- IMP-001 through IMP-023;
- IMP-030 through IMP-057;
- local workspace, SQLite state, migrations, managed artifacts, canonical conversation and project state, State Package v2, backup and restore, the model-independent safety boundary, AI-environment portability, project continuity, runtime-independent adapter contracts, a loopback-only Ollama adapter, authoritative runtime and model manifests, explicit bindings, canonical local conversation and streaming, explicit fallback switching, exact rollback, and accepted primary Intel Mac offline continuity evidence through IMP-054, the offline Ollama API session source adapter through IMP-055, explicit loopback Ollama chat capture through IMP-056, and the deterministic local-portability migration harness through IMP-057.

Current implementation point:

- Phase 4A passed its generic portability gate on 2026-06-25;
- accepted real-machine evidence is bound to commit `839a4ca7a37753fadf81c3e8e79f140e6d66bc03` on the primary Intel Mac with networking disabled;
- Phase 4B passed its project-continuity gate on 2026-06-26;
- accepted Phase 4B real-machine evidence is bound to commit `ddb58d041e505556910930724d0cf2fd03afe7d3` on the primary Intel Mac with networking disabled;
- IMP-038 through IMP-047 establish package-v2 continuity, authoritative project records, deterministic status and Resume Bundles, transfer and recovery coverage, and accepted PROJ-001 through PROJ-012 evidence;
- Phase 5 passed its local-runtime continuity gate on 2026-06-28;
- accepted real-machine evidence is bound to commit `1a5b66b2417d6f3e1eafcd14d2769e9c15d7f96c` on the primary Intel Mac with networking disabled;
- IMP-048 through IMP-054 establish the runtime contract, loopback-only Ollama adapter, authoritative manifests and bindings, canonical local conversation and streaming, explicit fallback switching, exact rollback, State Package v2 transfer, backup restore, and accepted LRUN-001 through LRUN-012 evidence;
- Phase 6 local AI portability and daily-use integration is in progress through IMP-057;
- IMP-055 adds an offline source adapter for a documented caller-retained Ollama API session bundle, with exact JSON validation, content-free inventory, original-source hashing, deterministic normalization, explicit attachment-metadata loss, and reuse of the accepted generic staging and reviewed-publication boundary;
- IMP-056 adds an explicit non-streaming text-only capture path through fixed IPv4 loopback, resolves one opaque already-installed local model through the filtered inventory, and returns an IMP-055-valid session bundle without reading application databases, logs, shell history, or unrelated sessions;
- IMP-057 merged at commit `7b63ff512e20d1d6ae65da8938486b093e14b6c6` and composes explicit capture, reviewed canonical import, idempotency and conflict checks, generic export, State Package v2 transfer, backup restore, and alternate fresh-process inspection without the capture component;
- IMP-057 extends State Package v2 conditionally for portability publication records and managed original-source artifacts while preserving the previous package surface when those records are absent;
- accepted primary Intel Mac evidence is bound to exact IMP-057 implementation commit `7b63ff512e20d1d6ae65da8938486b093e14b6c6` and stored at `docs/testing/results/IMP-057-primary-intel-mac-2026-06-29.json`;
- PORT-001, PORT-003, and the bounded IMP-057 portion of PORT-013 pass at both `ci` and `real-machine` evidence levels;
- the bounded IMP-057 local-portability gate is complete, but this does not establish native Ollama history migration, target-specific export, general application replacement, PORT-015, the complete Phase 6 gate, or a stable general anti-lock-in property;
- Issue #178 is completed by the privacy-reviewed evidence pull request;
- this evidence-only completion allocates no implementation identifier; the next bounded implementation receives IMP-058 only when a new implementation issue is opened;
- later local migration, cloud, and tool work must continue through the Phase 3 safety boundary and the Phase 4A/4B canonical state contracts.

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

Status: complete through IMP-047.

Completed implementation slices:

- IMP-038 — Doll State Package format v2 foundation and supported format v1 read compatibility.
- IMP-039 — versioned authoritative record registry for package validation.
- IMP-040 — ProjectRecord v2 with neutral ProjectRecord v1 read compatibility.
- IMP-041 — WorkItemRecord v1 lifecycle and dependency integrity.
- IMP-042 — ProcedureRecord v1 lifecycle and non-authority guarantees.
- IMP-043 — ProjectCheckpointRecord v1 confirmation and freshness.
- IMP-044 — deterministic read-only derived project status.
- IMP-045 — deterministic project-scoped Resume Bundle.
- IMP-046 — project-continuity transfer and recovery coverage.
- IMP-047 — automated PROJ-001 through PROJ-012 acceptance evidence, independent Resume Bundle inspection, and an exact-commit primary Intel Mac offline runner.

Accepted Phase 4B evidence:

- merged implementation commit: `ddb58d041e505556910930724d0cf2fd03afe7d3`;
- Ubuntu, macOS, and Windows CI passed before the accepted real-machine run;
- the primary Intel Mac run passed on Darwin `x86_64`, Python 3.12.13, with networking disabled;
- all declared PROJ-001 through PROJ-012 checks passed;
- the accepted report returned `phase4b_gate_complete = true`;
- the stored result contains no private path, username, hostname, credential, secret value, fixture content, or personal project data.

Phase 4B gate status: passed on 2026-06-26.

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

Status: complete through IMP-054.

The remaining work retains its required order and receives monotonically increasing implementation identifiers only when scheduled. The unused identifiers IMP-024 through IMP-029 are retired and must not be reused.

### IMP-048 — Runtime adapter contract

Status: complete.

Implemented normalized runtime declaration, health, inventory, generation, bounded streaming transcript, cancellation, timeout, closed failure, offline, and descriptive-capability contracts with runtime-independent identities and no direct authority over state, secrets, files, network, capabilities, or project completion. Synthetic adapters prove the contract without a model, runtime service, provider, cloud account, credential, preferred UI, network request, process launch, or persistent state change.

### IMP-049 — First local Ollama runtime adapter

Status: complete; accepted real-machine evidence is provided by IMP-054.

Implemented loopback-only health, inventory, generation, bounded NDJSON streaming, timeout, cancellation, opaque model identifiers, explicit local-only confirmation, cloud-model exclusion, and closed failure mapping. Tests use an injected fake transport. No runtime or model is persistently bound and no authoritative state is added.

### IMP-050 — Model manifests and explicit bindings

Status: complete.

Implemented authoritative RuntimeManifestRecord v1, ModelManifestRecord v1, and ModelBindingRecord v1 records with user-controlled provenance, exact revision and checksum identity, license review, compatibility, quarantine, candidate, active, previous, fallback, disabled, and scope-local rollback state. Schema version 3, typed optional State Package v2 categories, package-v1 neutrality, backup and restore, fresh-process validation, audit history, optimistic revision checks, and one-active-binding-per-scope enforcement are covered. No runtime or model is connected and no installation, download, inference, automatic activation, or capability execution occurs.

### IMP-051 — Canonical local conversation execution

Status: complete; accepted real-machine evidence is provided by IMP-054.

Implemented one model-independent, non-streaming local turn through `LocalRuntimeBoundary.generate`. The service resolves exactly one explicit active binding, revalidates exact runtime and model manifest revisions and the registered adapter declaration, creates the current user instruction outside the model, packages selected context through prompt-injection and secret controls, and renders one bounded deterministic runtime input.

The turn persists managed user, context-snapshot, and assistant artifacts plus canonical `user_message`, `system_context_snapshot`, and `assistant_message` or bounded `error` events. Runtime output is also stored as an immutable data-only instruction-origin record and cannot become policy, permission, memory, confirmation, project progress, or a capability request. Duplicate operation IDs fail closed, invalid runtime results do not become assistant messages, and persistence failures roll back newly created records and managed files.

The existing schema version 3 and State Package v2 remain sufficient. Tests use injected synthetic adapters only and perform no network request, process launch, model download, runtime installation, cloud access, credential retrieval, tool execution, or authoritative project mutation.

### IMP-052 — Explicit model switching and fallback rollback

Status: complete; accepted real-machine evidence is provided by IMP-054.

Implemented `ModelSwitchService` for explicit switching to one chosen binding in an exact scope. It lists valid switch targets and explicitly configured fallback candidates, revalidates exact binding and manifest revisions plus the registered local adapter declaration, and runs deterministic bounded preflight and post-activation probes only through `LocalRuntimeBoundary.generate`.

A failed preflight records bounded failure state and leaves the current active binding unchanged. A successful preflight activates the selected target through the existing transaction, preserves the exact previous binding, and verifies the new active binding. Failed post-activation verification rolls back to that exact previous binding and marks the rejected target failed. Fallbacks are ordered deterministically by user-configured priority and binding ID but are never selected automatically.

Probe input contains no canonical conversation, memory, project, credential, or private-path content. Probe output remains transient and is not persisted as conversation, instruction-origin, memory, project, capability, or other authoritative state. Public results and switch audit metadata expose bounded identifiers, hashes, outcomes, and failure codes only. Schema version 3 and State Package v2 remain unchanged. CI uses injected synthetic adapters and requires no user-side local or offline work.

### IMP-053 — Bounded local streaming conversation path

Status: complete; accepted real-machine evidence is provided by IMP-054.

Implemented `LocalStreamingConversationService` above the accepted `LocalRuntimeBoundary.stream` contract. The service resolves one exact active binding, revalidates runtime and model manifests plus the adapter declaration, packages the current user instruction and selected context through the existing authority, prompt-injection, and secret controls, and returns a bounded presentation-only stream transcript that is excluded from object representation.

Partial deltas are never persisted. Only a terminally valid, identity-matched, non-blank, secret-safe completed stream is committed through the existing IMP-051 canonical user, context-snapshot, and assistant artifact/event path. Failed, cancelled, timed-out, malformed, blank, identity-mismatched, resource-limited, or secret-bearing results create no assistant artifact, assistant event, or runtime-output instruction-origin record. Duplicate operation IDs fail closed and persistence failure removes every record and managed file created by the attempted turn.

Schema version 3 and State Package v2 remain unchanged. CI uses injected synthetic adapters only and requires no user-side local or offline work. No browser, terminal, desktop live-rendering transport, real runtime, real model, runtime installation, process launch, model download, cloud request, credential retrieval, tool execution, capability execution, or project mutation is added.

### IMP-054 — Network-disabled real-runtime continuity drill

Status: accepted; primary Intel Mac offline evidence stored.

Implemented an exact-commit acceptance runner that exercises the accepted Ollama adapter with deterministic injected transport in CI. The drill covers loopback health and exact inventory, canonical non-streaming and bounded streaming conversation, explicit switching to a configured fallback, forced post-activation failure and exact rollback, preservation of memory, project, portability, conversation, runtime/model manifest, and binding state, State Package v2 transfer, state-backup restore, and fresh-process inspection with adapters disabled. State Package v2 now registers the already-existing canonical `conversation` and `conversation_event` records as optional members, validates conversation ownership and parent-event graph integrity, keeps package v1 unchanged, and remains compatible with earlier v2 packages that omit those members.

Real-machine mode accepts only Darwin x86_64 or amd64, the fixed IPv4 loopback Ollama transport, an explicit local port, two distinct preinstalled model names, the exact checked-out commit, and explicit offline and local-only confirmations. A socket guard rejects every non-loopback destination, and evidence output excludes native model names, prompts, responses, paths, usernames, hostnames, credentials, and secrets.

The accepted run used the exact merged implementation commit on Darwin `x86_64` with networking disabled, two preinstalled local model revisions, and explicit local-only confirmation. It did not install or start Ollama, download or delete models, use cloud providers, retrieve credentials, execute tools or capabilities, migrate schema, or change State Package v2.

### Accepted Phase 5 evidence

- implementation commit: `1a5b66b2417d6f3e1eafcd14d2769e9c15d7f96c`;
- the primary Intel Mac run passed on Darwin `x86_64`, Python 3.12.13, with networking disabled;
- the accepted local runtime was Ollama 0.30.11 through adapter `ollama.local` 1.0.0;
- all declared LRUN-001 through LRUN-012 checks passed;
- explicit fallback switching, exact rollback, State Package v2 transfer, backup restore, and fresh-process continuity passed;
- the accepted report returned `phase5_gate_complete = true`;
- the stored result contains no native model names, prompt or response text, private paths, usernames, hostnames, credentials, secret values, or private fixture content.

Phase 5 gate status: passed on 2026-06-28.

Phase 5 gate:

- local inference remains optional to state inspection, project status, Resume Bundle export, backup, restore, and recovery;
- model replacement does not rewrite unrelated state;
- canonical conversation and project state survive runtime-private object removal;
- the safety boundary remains the only route to side effects and authoritative project mutation;
- no cloud credential or provider is required.

## 12. Phase 6 — Local AI portability and daily-use integration

Goal: prove that doll can enter from, operate across, and exit to documented formats around real local AI use.

Status: in progress from IMP-055.

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

### IMP-055 — Offline Ollama API session source adapter

Status: implemented with synthetic CI evidence; real local-environment migration evidence remains pending.

Implemented a source-specific parser for the documented doll-defined `ollama-api-chat-session` version 1 JSON format. The adapter accepts explicit caller-provided bytes only, declares `network_behavior = none`, rejects duplicate keys, non-finite constants, invalid UTF-8, malformed exact shapes, unsupported versions, invalid timestamps and identifiers, and bounded resource violations, and produces a content-free inventory plus the SHA-256 of the exact original bundle.

Supported conversations, user, assistant, system, and tool-role messages, parent relationships, tool calls, and attachment metadata normalize deterministically into the existing generic portability object model. Imported model identifiers remain non-authoritative source metadata. Attachment bytes are not read, and metadata-only handling produces explicit material loss. Unknown roles, conflicting duplicates, missing parents, and cycles use the accepted quarantine and loss paths.

The adapter reuses the Phase 4A generic staging, preview, exact-plan approval, source mapping, unchanged-source idempotency, changed-source conflict, original-source preservation, atomic publication, and failure-cleanup boundaries. It introduces no authoritative record type, schema migration, State Package format change, runtime request, process launch, credential path, cloud access, tool execution, capability execution, or automatic authority promotion.

Synthetic tests prove deterministic inventory and mappings, canonical publication, managed source preservation, unchanged re-import reuse, changed-source conflict without overwrite, malformed and hostile-input handling, and absence of network or runtime dependencies. IMP-055 does not establish a native Ollama export, live capture, tested round trip, PORT-013 completion, or the Phase 6 gate.

### IMP-056 — Explicit loopback Ollama chat session capture

Status: implemented with deterministic injected-transport CI evidence; real primary Intel Mac migration evidence remains pending.

Implemented a typed service that starts or appends one explicit text-only local Ollama conversation turn. The caller supplies exact source-environment, conversation, message, operation, and timestamp identities plus one opaque model ID. The service requires explicit local-only confirmation, resolves the opaque model through the existing cloud-filtered local inventory, reads the local runtime version, and permits only `GET /api/tags`, `GET /api/version`, and non-streaming `POST /api/chat` on fixed IPv4 loopback.

Existing source bytes must first pass IMP-055 validation. The selected conversation must be unique, text-only, within limits, and a single linear parent chain; duplicate identifiers, unsupported roles, attachments, tool calls, wrong source identity, and runtime-version mismatch fail before chat. Unrelated conversations remain preserved. The response must use the exact selected native model, assistant role, bounded non-blank content, supported completion state and reason, and a valid timestamp, with no images, tools, thinking payload, duplicate keys, invalid UTF-8, or undeclared message members.

On success, the service appends one user event and one assistant event to the source bundle, records the resolved native model only as imported source metadata, updates runtime and export metadata, and revalidates the complete returned bytes through IMP-055. It writes no Doll State and creates no policy, memory, permission, credential, capability, model binding, confirmation, procedure, checkpoint, blocker, or project-completion authority.

Synthetic tests prove the exact inventory/version/chat sequence, new and appended sessions, preserved unrelated conversations, cloud-model exclusion, cancellation, timeout, malformed response, source-history rejection, bounded failure privacy, and absence of State, credential, capability, process, remote HTTP, model-download, or tool dependencies. IMP-056 does not provide automatic/background capture, private application discovery, streaming, multimodal or tool fidelity, target-specific export, tested round trip, application replacement, PORT-013 completion, or the Phase 6 gate.

### IMP-057 — Local-portability migration harness

Status: implementation and bounded evidence complete with deterministic synthetic CI and accepted primary Intel Mac real-machine evidence.

Implemented an integrated migration scenario that composes IMP-056 capture, IMP-055 validation and staging, reviewed canonical publication, unchanged-source idempotency, changed-source conflict protection, generic export, State Package v2 transfer, verified backup restore, and alternate fresh-process inspection after the capture component is absent from the execution path.

The implementation also adds conditional State Package v2 support for source environments, import batches, mapping reports, portability losses, source mappings, quarantines, original-source snapshot records, and managed original-source files. Imported content remains data-only, relationships and hashes are revalidated after transfer, and packages without portability records keep the previous v2 category surface.

Deterministic CI passes on Linux, macOS, and Windows. The accepted primary Intel Mac run used Darwin `x86_64`, networking disabled, fixed IPv4 loopback Ollama, and one explicitly selected already-installed local model. PORT-001, PORT-003, and the bounded IMP-057 portion of PORT-013 now pass at both `ci` and `real-machine` evidence levels.

The accepted result is bound to exact merged implementation commit `7b63ff512e20d1d6ae65da8938486b093e14b6c6` and stored at `docs/testing/results/IMP-057-primary-intel-mac-2026-06-29.json`. Privacy review confirmed that the result contains no native model names, prompts, responses, personal conversations, paths, usernames, hostnames, credentials, or secrets.

IMP-057 does not complete PORT-015, target-specific export, ChatGPT history migration, native Ollama history discovery, multimodal or tool fidelity, a second runtime migration, the full Phase 6 gate, or a stable anti-lock-in claim.

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

The required order after accepted IMP-057 real-machine evidence is:

1. keep the accepted claim limited to PORT-001, PORT-003, and the bounded IMP-057 portion of PORT-013;
2. do not extend the result to native Ollama history discovery, target-specific export, general application replacement, PORT-015, the complete Phase 6 gate, or a stable general anti-lock-in claim;
3. open the next bounded Phase 6 implementation issue only when its objective, acceptance boundary, and real-machine requirements are defined; the next bounded implementation receives IMP-058 only when a new implementation issue is opened;
4. continue local-first daily-use and migration work through the Phase 3 safety boundary and the Phase 4A/4B canonical state contracts;
5. keep ChatGPT history, provider-specific cloud portability, credentials, tools, automatic cloud fallback, multimodal capture, and target-specific export outside the completed IMP-057 boundary.

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
