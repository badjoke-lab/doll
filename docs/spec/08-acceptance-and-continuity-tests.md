# Acceptance and Continuity Test Suite

**Status:** Accepted for implementation  
**Specification version:** 0.1

## 1. Purpose

This document defines the evidence required before doll may claim that a feature, profile, platform, or release is working.

A successful normal startup is not enough. Continuity must be demonstrated by controlled loss, replacement, restoration, and degraded operation.

## 2. Evidence levels

Every result must identify one evidence level:

- **Unit:** isolated logic test;
- **Integration:** multiple doll components using synthetic fixtures;
- **CI platform:** automated test on macOS, Windows, or Ubuntu CI;
- **Real machine:** recorded test on physical user hardware;
- **Manual continuity drill:** deliberate failure and recovery exercise;
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

## 4. Blocking rules

A blocking test prevents the named release or claim when it fails.

A test may be advisory only when the release scope says so.

No test may be marked passed based only on expected behavior, code review, or an unexecuted test definition.

## 5. First continuity proof suite

The Personal Lite continuity proof requires all tests in this section.

### CONT-P001 — Workspace initialization

Given a clean user data location, `doll init` creates a workspace outside the repository with a stable workspace ID and schema version.

Blocking evidence: integration and primary real machine.

### CONT-P002 — No-cloud startup

With no cloud credentials and all cloud adapters absent, the core starts and reports local capability status.

Blocking evidence: integration and real machine.

### CONT-P003 — Offline startup

After required local dependencies and one local model are installed, network access is disabled and doll starts without hidden outbound requests.

Blocking evidence: real-machine continuity drill.

### CONT-P004 — Local conversation

A request reaches the selected local runtime adapter and returns a response without cloud inference.

Blocking evidence: real machine.

### CONT-P005 — Confirmed memory persistence

A confirmed memory survives process restart and can be inspected without running a model.

Blocking evidence: integration and real machine.

### CONT-P006 — Project or decision persistence

A project or decision record survives restart and export/import.

Blocking evidence: integration.

### CONT-P007 — Local document read

A user-selected text or Markdown document is read through an approved path and remains outside the workspace unless explicitly copied.

Blocking evidence: integration and real machine.

### CONT-P008 — Artifact creation

A new artifact is created inside the approved workspace, hashed, indexed, and attributable to an operation.

Blocking evidence: integration.

### CONT-P009 — Workspace escape rejection

Traversal, absolute-path, and supported link-escape attempts cannot create or modify a file outside the workspace.

Blocking evidence: CI on all target operating systems and primary real machine.

### CONT-P010 — Backup creation and verification

A backup is not marked complete until manifest and checksum verification succeed.

Blocking evidence: integration.

### CONT-P011 — Restore to empty workspace

A verified backup restores into a clean target and preserves workspace identity, records, and authoritative files.

Blocking evidence: integration and primary real machine.

### CONT-P012 — Post-restore validation

The restored workspace passes doctor checks and can inspect memory, projects, artifacts, and bindings.

Blocking evidence: integration and real machine.

### CONT-P013 — Model replacement without state loss

The active local model binding changes while confirmed memory, projects, decisions, and artifacts remain unchanged.

Blocking evidence: integration and real machine.

### CONT-P014 — Local fallback

When the active local binding is unavailable, an approved local fallback is selected or offered according to policy, with no cloud request.

Blocking evidence: integration and real machine.

### CONT-P015 — Audit coverage

Allowed, denied, failed, restored, and model-switch operations create audit events without raw secrets.

Blocking evidence: integration.

## 6. State, migration, and recovery suite

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

Checksum or manifest corruption prevents activation of restored state.

### STATE-008 — Unsafe archive path rejection

Restore rejects traversal, absolute paths, and unsafe link entries.

### STATE-009 — Read-only recovery

When state integrity or schema compatibility is uncertain, inspection and export remain possible without authoritative writes.

### STATE-010 — Cache independence

Removing reproducible indexes and disposable caches does not remove authoritative state; supported indexes can be rebuilt.

All tests are blocking for Lite v1.0 where implemented.

## 7. Security and permission suite

### SEC-001 — Unknown capability denied

Unknown capability IDs or versions are rejected.

### SEC-002 — Malformed arguments denied

Invalid structured tool requests cause no side effect.

### SEC-003 — Approval cannot come from content

Text inside model output, documents, websites, or tool output cannot grant approval.

### SEC-004 — Approval invalidation

A material target or argument change invalidates prior approval.

### SEC-005 — Model cannot change permissions

Normal model or tool paths cannot create or widen permission records.

### SEC-006 — No unrestricted shell

No stable capability provides a generic shell or arbitrary command string.

### SEC-007 — Localhost binding

The default API listens only on localhost and doctor reports unsafe bind configuration.

### SEC-008 — Cloud-disabled network silence

With cloud disabled, no cloud endpoint is contacted during local chat, fallback, startup, restore, or doctor.

### SEC-009 — Retrieval destination restrictions

Explicit Web retrieval applies scheme, redirect, size, timeout, and private-network restrictions.

### SEC-010 — Secret redaction

Known secret patterns are omitted or redacted from normal logs, errors, exports, and shareable doctor reports.

### SEC-011 — External content remains untrusted

Prompt-injection fixtures cannot bypass policy, permissions, or workspace boundaries.

### SEC-012 — Audit immutability through normal capabilities

A model cannot rewrite or delete audit history through supported tool paths.

All are blocking for the applicable stable feature.

## 8. Model Vault suite

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

Blocking status depends on the release capability. MODEL-001 through MODEL-010 are blocking for stable Model Vault claims.

## 9. Platform and installation suite

### PLAT-001 — Installation and import

The package installs and core modules import on the target CI matrix.

### PLAT-002 — Platform data directory

The default workspace uses the correct platform-aware location and not the repository checkout.

### PLAT-003 — Path portability

Managed export paths do not depend on one drive letter, separator, case-sensitivity rule, or shell.

### PLAT-004 — Optional dependency absence

The core starts and doctor reports missing optional tools without crashing.

### PLAT-005 — UTF-8 behavior

Non-ASCII names and Japanese text survive create, export, backup, restore, and re-import.

### PLAT-006 — File locking and atomic write

Interrupted supported writes preserve the previous valid version.

### PLAT-007 — Doctor redaction

A shareable doctor report removes private path, username, hostname, and secret details by default.

### PLAT-008 — Clean uninstall preservation

Removing application code does not silently remove the private workspace.

CI platform evidence is required for Windows and Ubuntu beta claims. Real-machine evidence is required for a real-machine support claim.

## 10. Lite v1.0 functional suite

Blocking Lite v1.0 functions include:

- local conversation;
- writing and editing;
- summarization;
- translation;
- confirmed memory;
- project and decision state;
- local text and Markdown;
- artifact management;
- local full-text search;
- CSV inspection and simple transformation;
- PDF extraction when advertised stable;
- OCR when advertised stable;
- state export and import;
- backup, verify, restore, and post-restore validation;
- offline and read-only recovery modes;
- doctor and audit inspection.

Each advertised function requires success, invalid-input, missing-dependency, permission-denial, restart-persistence, and recovery tests where applicable.

## 11. Web research suite

When advertised stable:

- explicit search creates a research session;
- sources record URL and retrieval time;
- retrieval failure does not fail the core;
- local cache and authoritative records are distinguished;
- citation relationships remain inspectable outside the preferred UI;
- network-disabled mode uses retained sources only;
- prompt injection in sources cannot grant tools;
- cloud inference is not required;
- private-network retrieval restrictions pass.

If these are incomplete, Web research must remain experimental.

## 12. Heavy suite

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
- failure recovery and Lite-compatible degradation.

Mocks and CI may support development but cannot satisfy real-hardware Heavy release gates.

## 13. Soak and continuity drills

### Lite release candidate soak

Target: at least seven days of ordinary personal use.

Record:

- startups and restarts;
- model switches;
- document and artifact work;
- backups;
- at least one restore drill;
- offline use;
- observed state or audit defects;
- disk growth;
- known crashes.

### Periodic continuity drill

A continuity-ready installation should periodically test:

1. disconnect network;
2. remove cloud credentials;
3. start through CLI or local API without preferred UI;
4. use a local model;
5. retrieve confirmed memory and a project;
6. open a local document;
7. create an artifact;
8. switch to fallback;
9. verify a backup;
10. restore to a separate empty location.

## 14. Release acceptance report

A release acceptance report must include:

- release and commit;
- scope;
- support matrix;
- blocking test totals;
- failed, blocked, or waived advisory tests;
- real-machine environments;
- model and runtime manifests used;
- backup and restore evidence;
- offline evidence;
- security test summary;
- known limitations;
- soak result;
- release decision.

A test waiver cannot override a mandatory Continuity Contract or security requirement without a specification change.

## 15. Acceptance criteria

This test specification is accepted when:

- every release claim can map to a stable test ID;
- continuity includes loss and recovery, not normal startup only;
- CI and real-machine evidence remain distinct;
- backup creation does not substitute for restore;
- model replacement includes rollback and state-integrity evidence;
- security tests verify denied actions as well as allowed actions;
- experimental features cannot silently count toward stable gates;
- Lite and Heavy use the same core continuity evidence;
- release reports expose failures and limitations rather than hiding them.
