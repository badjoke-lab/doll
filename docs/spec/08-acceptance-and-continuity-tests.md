# Acceptance and Continuity Test Suite

**Status:** Accepted for implementation  
**Specification version:** 0.1

## 1. Purpose

This document defines the evidence required before doll may claim that a feature, phase, profile, platform, or release is working.

A successful normal startup or a plausible model response is not enough. Continuity must be demonstrated by controlled loss, transfer, restoration, and degraded operation. Safety must be demonstrated by denied, malformed, hostile, under-confirmed, and failure cases as well as allowed cases.

No model execution path may be merged before the model-independent safety acceptance gate in this document passes.

## 2. Evidence levels

Every result must identify one evidence level:

- **Unit:** isolated logic test;
- **Integration:** multiple doll components using synthetic fixtures;
- **CI platform:** automated test on macOS, Windows, or Ubuntu CI;
- **Real process:** fresh operating-system process rather than an in-process call;
- **Real machine:** recorded test on physical user hardware;
- **Manual continuity drill:** deliberate failure and recovery exercise;
- **Manual safety drill:** deliberate hostile, denied, or under-confirmed operation exercise;
- **Soak:** repeated ordinary use over a defined period;
- **Community verified:** reproducible report from another user or machine.

A lower level does not substitute for a required higher level.

## 3. Test result record

Each acceptance result should record:

```text
test_id
specification_version
product_version
commit_sha
result
started_at
completed_at
evidence_level
operating_system
architecture
hardware_summary
runtime_versions
model_manifest_ids
workspace_fixture_id
network_mode
notes
artifact_references
```

Results are `pass`, `fail`, `blocked`, or `not_applicable`.

A blocked test does not count as a pass.

A shareable result must not include absolute local paths, usernames, hostnames, home-directory details, secret values, private source content, or personal fixtures.

## 4. Blocking rules

A blocking test prevents the named phase, release, or claim when it fails.

A test may be advisory only when the accepted phase or release scope says so.

No test may be marked passed based only on expected behavior, code review, a model's statement, or an unexecuted test definition.

A waiver cannot override a mandatory Continuity Contract, safety-boundary requirement, or accepted architecture decision without a specification change.

## 5. Phase 2 model-independent continuity gate

IMP-012 is the Continuity Acceptance Test. It runs after IMP-011 and before Phase 3 safety-boundary implementation depends on restore behavior.

The Phase 2 gate requires:

- CONT-P001;
- CONT-P002 without a model requirement;
- CONT-P005;
- CONT-P006;
- CONT-P008;
- CONT-P009;
- CONT-P010;
- CONT-P011;
- CONT-P012;
- CONT-P015 for implemented operations;
- CONT-P016;
- STATE-001 through STATE-012 where implemented;
- PLAT-001 through PLAT-007 where applicable.

Required evidence:

- integration and CI on macOS, Windows, and Ubuntu;
- fresh-process export, import, backup, restore, and inspection;
- a complete continuity drill on the primary Intel Mac;
- network-disabled operation for the tested paths;
- no model runtime or cloud credential dependency;
- exact artifact-byte and hash comparison;
- failure cleanup and last-known-good preservation.

The Phase 2 gate fails when:

- a verified backup cannot be restored into an empty target;
- an invalid, unsafe, mismatched, existing, or non-empty target is partially activated;
- restored identity, schema, revision, record, link, audit, or artifact data differs from the verified contract;
- a fresh process cannot inspect the restored workspace;
- shareable output leaks private environment details;
- model execution or network access is required.

## 6. Personal Lite continuity proof suite

The Personal Lite continuity proof requires all applicable tests in this section. Model-dependent tests run later, after the safety gate and local-model implementation.

### CONT-P001 — Workspace initialization

Given a clean user data location, `doll init` creates a workspace outside the repository with a stable workspace ID and schema version.

Blocking evidence: integration and primary real machine.

### CONT-P002 — No-cloud core startup

With no cloud credentials and all cloud adapters absent, the core starts and reports local capability status. Before model integration, state inspection, export, backup, restore, audit, and doctor paths remain available without a model.

Blocking evidence: integration and real machine.

### CONT-P003 — Offline local-AI startup

After required local dependencies and one local model are installed, network access is disabled and doll starts without hidden outbound requests.

Blocking evidence: real-machine continuity drill after Phase 4 implementation.

### CONT-P004 — Local conversation

A request reaches the selected local runtime adapter and returns a response without cloud inference. The model receives only the context allowed by secret, origin, trust, and permission policy.

Blocking evidence: real machine after the Phase 3 safety gate.

### CONT-P005 — Confirmed memory persistence

A confirmed memory survives process restart and can be inspected without running a model.

Blocking evidence: integration and real machine.

### CONT-P006 — Project or decision persistence

A project or decision record survives restart and export/import. Typed links remain valid.

Blocking evidence: integration.

### CONT-P007 — Local document read

A user-selected text or Markdown document is read through an approved path, receives instruction-origin metadata, and remains outside the workspace unless explicitly copied.

Blocking evidence: integration and real machine after the external-content boundary exists.

### CONT-P008 — Artifact creation

A new artifact is created inside the approved workspace, hashed, indexed, and attributable to an operation.

Blocking evidence: integration.

### CONT-P009 — Workspace escape rejection

Traversal, absolute-path, drive-path, UNC, case-collision, and supported link-escape attempts cannot create or modify a file outside the workspace.

Blocking evidence: CI on all target operating systems and primary real machine.

### CONT-P010 — Backup creation and verification

A backup is not marked complete until manifest, member, identity, revision, checksum, nested-package or SQLite, and artifact verification succeed.

Blocking evidence: integration and CI on all target operating systems.

### CONT-P011 — Restore to empty workspace

A verified state or workspace backup restores into an empty target and preserves the identity, schema, revision, implemented authoritative records, typed links, audit history, and authoritative artifact bytes required by that backup kind.

Blocking evidence: integration, fresh process, and primary real machine.

### CONT-P012 — Post-restore validation

The restored workspace passes integrity and contract validation in a fresh process and can inspect preferences, policies, permissions, confirmed memories, projects, decisions, typed links, artifacts, backup inventory, and audit history without running a model.

Blocking evidence: integration, fresh process, and primary real machine.

### CONT-P013 — Model replacement without state loss

The active local model binding changes while confirmed memory, projects, decisions, trust records, permissions, audit history, and artifacts remain unchanged.

Blocking evidence: integration and real machine after Phase 4 implementation.

### CONT-P014 — Local fallback

When the active local binding is unavailable, an approved local fallback is selected or offered according to policy, with no cloud request and no safety-boundary bypass.

Blocking evidence: integration and real machine after Phase 4 implementation.

### CONT-P015 — Audit coverage

Allowed, denied, failed, restored, secret-brokered, under-confirmed, prompt-injection-blocked, and model-switch operations create appropriate audit events without raw secrets or unnecessary private content.

Blocking evidence: integration for implemented operation classes.

### CONT-P016 — Model independence of continuity

Removing or disabling every model adapter does not prevent workspace opening, state inspection, export, import, backup verification, restore, post-restore validation, audit inspection, or read-only recovery.

Blocking evidence: integration, CI, and primary real machine before Phase 4.

## 7. State, migration, and recovery suite

### STATE-001 — Schema version enforcement

Unsupported future schemas open read-only or fail safely and are never modified.

### STATE-002 — Revision conflict

A stale update cannot silently overwrite a newer record.

### STATE-003 — Export integrity

Doll State Package records and files match the manifest and checksums.

### STATE-004 — Import conflict handling

Import identifies workspace and record conflicts and does not silently replace newer state.

### STATE-005 — Failed migration preservation

An interrupted or invalid migration preserves the original state and records failure.

### STATE-006 — Pre-migration backup requirement

A migration requiring backup cannot begin until a verified backup exists.

### STATE-007 — Corrupt backup rejection

Checksum, manifest, nested-package, SQLite, identity, revision, record, link, artifact, or file-inventory corruption prevents restore publication.

### STATE-008 — Unsafe archive path rejection

Import and restore reject traversal, absolute paths, drive paths, UNC or backslash paths, unsafe link entries, unknown members, duplicate members, case-fold collisions, and resource-limit violations.

### STATE-009 — Read-only recovery

When state integrity or schema compatibility is uncertain, inspection and export remain possible without authoritative writes.

### STATE-010 — Cache independence

Removing reproducible indexes and disposable caches does not remove authoritative state; supported indexes can be rebuilt.

### STATE-011 — Atomic restore publication

A restore publishes the complete validated workspace without overwriting an existing target. Failure removes staging and any partial publication and emits no false success audit event.

### STATE-012 — Fresh-process restored-state validation

A separate process opens the restored workspace, validates SQLite integrity, identity, revision, record envelopes, typed links, managed artifact paths, hashes, bytes, and implemented record contracts.

All implemented state tests are blocking for the Phase 2 gate and Lite v1.0.

## 8. Security, secret, trust, and permission suite

### SEC-001 — Unknown capability denied

Unknown capability IDs or versions are rejected without side effects.

### SEC-002 — Malformed arguments denied

Invalid structured capability requests cause no side effect.

### SEC-003 — Approval cannot come from content

Text inside model output, documents, websites, imported data, metadata, OCR, transcripts, or tool output cannot grant approval.

### SEC-004 — Approval invalidation

A material target, argument, destination, side-effect, credential-class, or scope change invalidates prior approval.

### SEC-005 — Model cannot change permissions

Normal model, runtime, capability, document, import, or tool paths cannot create, widen, reactivate, or self-approve permission records.

### SEC-006 — No unrestricted shell

No stable capability provides a generic shell, arbitrary command string, or unbounded child-process path.

### SEC-007 — Localhost binding

The default API listens only on localhost and doctor reports unsafe bind configuration.

### SEC-008 — Cloud-disabled network silence

With cloud disabled, no cloud endpoint is contacted during startup, local chat, fallback, state operations, restore, doctor, or recovery.

### SEC-009 — Retrieval destination restrictions

Explicit Web retrieval applies scheme, destination, redirect, size, timeout, content-type, and private-network restrictions.

### SEC-010 — Secret redaction

Known synthetic secret patterns are omitted or redacted from normal logs, errors, exports, backups, audit events, diagnostics, context packages, and shareable doctor reports.

### SEC-011 — External content remains untrusted

Prompt-injection fixtures cannot bypass policy, instruction authority, permissions, risk tiers, confirmation, workspace boundaries, credential isolation, or network policy.

### SEC-012 — Audit immutability through normal capabilities

A model, runtime, tool, or normal capability cannot rewrite or delete audit history.

### SEC-013 — Secret classification enforced

Data classified as a secret value is rejected from ordinary authoritative record fields that do not explicitly permit a SecretReference.

### SEC-014 — SecretReference is non-secret

A SecretReference contains only bounded identifier and policy metadata. It is safe to persist and export under its contract and cannot be used as the secret value itself.

### SEC-015 — Secret-safe exceptional paths

Validation errors, exceptions, failed adapters, trace summaries, retries, cancellation, and partial failures do not leak secret values or private environment details.

### SEC-016 — External secret-store isolation

Secret values are stored outside ordinary Doll State. An unavailable, locked, denied, or missing secret store fails the credential operation without blocking non-secret core startup or corrupting state.

### SEC-017 — Credential broker non-disclosure

The credential broker completes a bounded synthetic operation without returning the stored secret value to a model or ordinary caller. Result and audit data are structured and redacted.

### SEC-018 — Confirmed fact, claim, evidence, and inference separation

Persistence, import, export, query, and context assembly retain distinct record kinds and provenance. No model, document, website, tool, runtime, or import assertion becomes a confirmed fact automatically.

### SEC-019 — Instruction origin preserved

Every instruction-bearing input retains source and authority metadata through persistence and context assembly. Unknown origin is classified at the least-authoritative level.

### SEC-020 — Untrusted content cannot become authority

Retrieved or imported content can supply task data or evidence but cannot change system policy, durable user policy, permission state, risk tier, confirmation state, credential scope, or instruction authority.

### SEC-021 — Capability risk tier enforced

The broker applies the registered capability version and risk tier. A request cannot downgrade its own tier, omit declared side effects, or use a lower-risk permission for a higher-risk operation.

### SEC-022 — Mandatory high-risk confirmation

Every Tier 3 operation fails without a fresh user-controlled confirmation bound to the exact capability, target, destination, material side effects, and credential class where applicable.

### SEC-023 — Confirmation is necessary but not sufficient

A valid confirmation cannot make an unknown, malformed, prohibited, out-of-scope, unsafe, or release-excluded capability executable.

All SEC-001 through SEC-023 are blocking for the Phase 3 safety gate when their components are implemented. SEC-001 through SEC-012 remain blocking for every applicable stable feature.

## 9. Phase 3 safety acceptance gate

IMP-023 is the Safety Acceptance Test. It must pass before IMP-024 or any model execution path merges.

Required gate evidence:

- unit and integration tests for SEC-001 through SEC-023;
- CI on macOS, Windows, and Ubuntu;
- fresh-process checks for persistence, export, audit, credential, and denial behavior;
- hostile synthetic content covering documents, websites, metadata, OCR, transcripts, imports, tool results, and model-like proposals;
- synthetic secret fixtures only;
- primary Intel Mac real-process validation for applicable paths;
- repository coverage remains at or above the accepted threshold;
- no blanket coverage exclusion hides safety logic;
- review confirms no direct route from a future model adapter to filesystem, network, process, permission, secret-store, or audit mutation.

The safety gate fails when:

- a secret value enters ordinary state or user-shareable output;
- a model-like caller can retrieve a stored credential value;
- external content can grant approval or raise instruction authority;
- a claim silently becomes a confirmed fact;
- unknown, malformed, under-declared, under-confirmed, or risk-downgraded capabilities execute;
- a material change preserves high-risk confirmation;
- denial or failure damages the last known good state;
- a model adapter could bypass the accepted broker contracts.

## 10. Model Vault suite

### MODEL-001 — Manifest completeness

An active binding has model provenance, exact revision, license record, file inventory, checksum, runtime, and evaluation references.

### MODEL-002 — Partial download quarantine

Partial or interrupted assets remain unusable.

### MODEL-003 — Checksum mismatch

A mismatch blocks validation and activation.

### MODEL-004 — Manual import quarantine

Local-file import enters quarantine and cannot activate directly.

### MODEL-005 — Remote-code classification

A model requiring arbitrary remote code is not standard-validated.

### MODEL-006 — Explicit promotion

A candidate cannot become active without a user-controlled promotion action.

### MODEL-007 — Previous binding retained

Activation records the known-good previous binding.

### MODEL-008 — Failed smoke test rollback

A failed activation smoke test restores the prior binding.

### MODEL-009 — Offline verification

An offline-verified binding completes role-appropriate work without download or network access.

### MODEL-010 — State independence

Model activation, rollback, and fallback do not rewrite unrelated Doll State.

### MODEL-011 — Training isolation

Training uses an approved dataset snapshot and produces a candidate rather than an active binding.

### MODEL-012 — Safety-boundary-only side effects

A runtime adapter and model can propose a capability request but cannot directly access state mutation, filesystem write, network, process, permission, credential, confirmation, or audit internals.

### MODEL-013 — Secret-free default context

Default model context contains no secret values. A credential-bearing operation is performed through the broker and returns only a bounded result.

MODEL-001 through MODEL-010, MODEL-012, and MODEL-013 are blocking for stable local-model claims.

## 11. Platform and installation suite

### PLAT-001 — Installation and import

The package installs and core modules import on the target CI matrix.

### PLAT-002 — Platform data directory

The default workspace uses the correct platform-aware location and not the repository checkout.

### PLAT-003 — Path portability

Managed export, backup, and restore paths do not depend on one drive letter, separator, case-sensitivity rule, or shell.

### PLAT-004 — Optional dependency absence

The core starts and doctor reports missing optional tools, runtimes, secret-store adapters, or model adapters without crashing.

### PLAT-005 — UTF-8 behavior

Non-ASCII names and Japanese text survive create, export, backup, restore, re-import, provenance, and audit paths.

### PLAT-006 — File locking and atomic write

Interrupted supported writes preserve the previous valid version.

### PLAT-007 — Doctor and output redaction

A shareable doctor report and normal CLI errors remove absolute paths, usernames, hostnames, home-directory details, secret values, and unnecessary private data by default.

### PLAT-008 — Clean uninstall preservation

Removing application code does not silently remove the private workspace or external secret-store entries.

### PLAT-009 — Secret-store contract portability

Platform adapters expose the same non-secret reference, availability, user-presence, revocation, and failure contract even when operating-system mechanisms differ.

CI platform evidence is required for Windows and Ubuntu beta claims. Real-machine evidence is required for a real-machine support claim.

## 12. Lite v1.0 functional suite

Blocking Lite v1.0 functions include:

- local conversation after the safety gate;
- writing and editing;
- summarization;
- translation;
- confirmed memory;
- project and decision state;
- claim, evidence, inference, and source inspection;
- local text and Markdown;
- artifact management;
- local full-text search;
- CSV inspection and simple transformation;
- PDF extraction when advertised stable;
- OCR when advertised stable;
- state export and import;
- backup, verify, restore, and post-restore validation;
- offline and read-only recovery modes;
- capability, permission, confirmation, doctor, and audit inspection.

Each advertised function requires success, invalid-input, missing-dependency, permission-denial, risk-denial, restart-persistence, secret-safety, instruction-origin, and recovery tests where applicable.

## 13. Web research suite

When advertised stable:

- explicit search creates a research session;
- sources record normalized URL, retrieval time, content hash, and instruction origin;
- claims, evidence, and inferences remain distinguishable;
- retrieval failure does not fail the core;
- local cache and authoritative records are distinguished;
- citation relationships remain inspectable outside the preferred UI;
- network-disabled mode uses retained sources only;
- prompt injection in sources cannot grant tools, confirmation, policy, or credential access;
- cloud inference is not required;
- private-network retrieval restrictions pass;
- secret-bearing outbound content is denied or explicitly redacted under policy.

If these are incomplete, Web research must remain experimental.

## 14. Heavy suite

Heavy v1.0 adds blocking evidence for every advertised Heavy capability, including:

- real GPU or accelerator operation;
- large-model loading and fallback;
- memory and VRAM limits;
- long-running stability;
- multiple model roles;
- richer retrieval and reranking;
- media processing;
- verifier workflows;
- training or adaptation where included;
- failure recovery and Lite-compatible degradation;
- the same safety, secret, trust, capability, and confirmation contracts as Lite.

Mocks and CI may support development but cannot satisfy real-hardware Heavy release gates.

## 15. Soak and continuity or safety drills

### Lite release candidate soak

Target: at least seven days of ordinary personal use.

Record:

- startups and restarts;
- model switches;
- document and artifact work;
- claim and evidence review;
- capability approvals and denials;
- backups;
- at least one restore drill;
- offline use;
- secret-store unavailable or locked behavior;
- observed state, security, trust, or audit defects;
- disk growth;
- known crashes.

### Periodic continuity drill

A continuity-ready installation should periodically test:

1. disconnect network;
2. remove or disable cloud credentials;
3. start through CLI or local API without the preferred UI;
4. inspect confirmed memory and a project without a model;
5. verify a backup;
6. restore to a separate empty location;
7. validate the restored workspace in a fresh process;
8. after Phase 4, use a local model and switch to fallback;
9. confirm unrelated authoritative state remains unchanged.

### Periodic safety drill

A safety-ready installation should periodically test:

1. lock or deny the external secret store;
2. submit hostile external-content fixtures;
3. attempt an unknown and malformed capability;
4. attempt a risk-tier downgrade;
5. attempt a high-risk operation without confirmation;
6. approve one exact synthetic high-risk operation;
7. change a material argument and verify confirmation invalidation;
8. inspect redacted audit and diagnostic output;
9. confirm the last known good state remains intact.

## 16. Release acceptance report

A release acceptance report must include:

- release and commit;
- scope;
- support matrix;
- blocking test totals;
- failed, blocked, or waived advisory tests;
- real-machine environments;
- model and runtime manifests used where applicable;
- continuity, backup, and restore evidence;
- safety-gate evidence;
- secret-store and credential-broker evidence where applicable;
- offline evidence;
- security test summary;
- known limitations;
- soak result;
- release decision.

## 17. Acceptance criteria

This test specification is accepted when:

- every phase and release claim maps to stable test IDs;
- continuity includes loss and recovery, not normal startup only;
- Phase 2 continuity is provable without model execution;
- the complete safety gate precedes model execution;
- CI, fresh-process, and real-machine evidence remain distinct;
- backup creation does not substitute for restore;
- model replacement includes rollback and state-integrity evidence;
- security tests verify denied and hostile actions as well as allowed actions;
- secret values remain separate from ordinary state and model context;
- claims, evidence, inferences, and confirmed facts remain distinct;
- instruction origin remains enforceable through context assembly;
- high-risk confirmation is exact, fresh, and insufficient to override policy;
- experimental features cannot silently count toward stable gates;
- Lite and Heavy use the same core continuity and safety evidence;
- release reports expose failures and limitations rather than hiding them.
