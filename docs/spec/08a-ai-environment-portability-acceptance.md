# AI environment portability acceptance suite

**Status:** Accepted for implementation when merged  
**Specification version:** 0.1  
**Depends on:** `03a-ai-environment-portability.md`, `08-acceptance-and-continuity-tests.md`, `ADR-006-ai-environment-portability.md`

## 1. Purpose

This document defines blocking evidence for claims that doll can preserve and move supported user-owned AI state across models, runtimes, interfaces, applications, providers, machines, and doll itself.

A successful parser run is not sufficient. Portability must demonstrate source attribution, deterministic mapping, duplicate prevention, explicit loss reporting, authority separation, inspectable export, and controlled replacement of execution components.

## 2. Evidence rules

The evidence levels and result-record requirements from `08-acceptance-and-continuity-tests.md` apply.

Portability results should additionally record:

```text
source_environment_class
source_format
source_format_version
source_adapter_id
source_adapter_version
target_format
target_adapter_id
target_adapter_version
source_object_counts
published_object_counts
duplicate_counts
quarantine_counts
loss_counts_by_severity
mapping_report_reference
original_source_hash
```

Fixtures must be synthetic unless a private manual migration drill is explicitly required. Private source data and original source archives must not be committed or exposed in shareable reports.

## 3. PORT test suite

### PORT-001 — Model replacement preserves state

Changing the active model binding does not rewrite or remove unrelated confirmed memory, projects, decisions, policies, permissions, conversations, sources, artifacts, audit history, or portability records.

Blocking evidence: integration and real machine after local model integration.

### PORT-002 — Runtime replacement preserves state

A supported model or equivalent role moves between two runtime adapters, or one runtime is replaced by another, while canonical Doll State remains valid and runtime-specific identifiers remain adapter metadata rather than authoritative state.

Blocking evidence: integration and real machine when two runtime paths are implemented.

### PORT-003 — Interface replacement preserves authority

The preferred interface can be removed or replaced while state inspection, conversation history, export, and recovery remain available through another supported interface, local API, or CLI. Interface-local data is not the only authoritative copy.

Blocking evidence: integration and real process.

### PORT-004 — Generic conversation import

A documented generic fixture containing conversations, events, branches, attachments, timestamps, and source attribution is parsed without execution, staged, previewed, and published into canonical records.

Blocking evidence: integration and CI on macOS, Windows, and Ubuntu.

### PORT-005 — Generic inspectable export

Implemented portable records export to documented generic files with a manifest and checksums. A fresh process without a model or running doll service can inspect the manifest, conversations, provenance, and loss report.

Blocking evidence: integration, fresh process, and primary real machine.

### PORT-006 — Source identity and provenance preservation

Provider, application, interface, runtime, model, adapter, source-object, import-batch, and content-hash fields remain distinct through import, restart, export, and re-import where the source provides them.

Unknown source identity remains unknown and is not invented.

Blocking evidence: integration.

### PORT-007 — Idempotent repeated import

Importing the same unchanged source package twice through the same compatible adapter does not silently duplicate conversations, events, attachments, artifacts, projects, memories, or other canonical records.

Changed source objects produce documented update candidates, revisions, conflicts, or distinct records according to their contract.

Blocking evidence: integration and CI.

### PORT-008 — Mapping and loss reporting

Every non-native import and target-specific export reports mapped, transformed, partially mapped, unsupported-preserved, unsupported-omitted, missing, malformed, quarantined, and unknown counts where applicable.

A material loss prevents a full-fidelity claim.

Blocking evidence: integration.

### PORT-009 — Original source preservation

When source preservation is enabled and allowed, the retained source snapshot or reference is integrity-checkable, linked to its import batch, separate from canonical records, and excluded from instruction authority.

When preservation is impossible or disabled, the report states that fact.

Blocking evidence: integration.

### PORT-010 — Imported content cannot grant authority

Imported prompts, permissions, tool definitions, approvals, confirmations, policies, and configuration cannot change system policy, durable policy, PermissionRecords, capability definitions, risk tiers, confirmation state, credential scope, or instruction authority.

Blocking evidence: hostile synthetic integration fixtures.

### PORT-011 — Imported content cannot become confirmed memory or fact automatically

Imported service memory, summaries, assistant assertions, and profile data remain imported content, claims, or suggestions until the trusted user-controlled confirmation path promotes them.

Blocking evidence: integration.

### PORT-012 — Parser and archive safety

Malformed structures, unsafe paths, unsupported archive members, excessive nesting, duplicate members, case-fold collisions, over-limit attachments, and executable source content fail closed or enter quarantine without modifying the last known good state.

Blocking evidence: CI on macOS, Windows, and Ubuntu.

### PORT-013 — Local AI environment migration drill

A real supported local AI environment exports or exposes a test workspace containing conversation history and at least one supported attachment or metadata relationship. Doll imports it, reports inventory and loss, uses a different approved model or runtime to retrieve the imported context, and exports the resulting canonical state generically.

The drill verifies that removal of the original local application does not remove the imported Doll State.

Blocking evidence: primary real machine before a stable local-environment portability claim.

### PORT-014 — Project-owner history migration drill

The project owner's ChatGPT export is handled through a provider-specific source adapter after the generic and local paths pass. Doll preserves original export provenance, imports selected conversation history, prevents automatic memory promotion, reports unsupported events and missing attachments, and exports selected canonical state generically.

This is private manual evidence. No personal archive, conversation text, identifier, or private fixture is committed.

Blocking evidence: private manual continuity drill before claiming ChatGPT migration support.

### PORT-015 — Doll shutdown escape test

From a valid workspace, a generic export is created and then inspected without model execution, the preferred UI, network access, cloud credentials, or a running doll service. The user can recover implemented conversations, confirmed memory, projects, decisions, artifacts, sources, and portability reports in documented forms.

Blocking evidence: fresh process and primary real machine before a stable anti-lock-in claim.

### PORT-016 — Target-specific export failure preserves Doll State

A failed, denied, cancelled, incompatible, or partially completed target-specific export does not rewrite or delete authoritative Doll State and does not report false success.

Blocking evidence: integration.

## 4. Portability phase gate

The portability foundation gate requires, when implemented:

- PORT-004 through PORT-012;
- canonical conversation and event schemas;
- source and target adapter contracts;
- generic inspectable export;
- staged generic import;
- provenance, idempotency, quarantine, mapping, and loss records;
- secret and instruction-origin enforcement on imported content;
- CI on macOS, Windows, and Ubuntu;
- no provider-specific cloud adapter required.

The local portability claim additionally requires PORT-001, PORT-003, PORT-013, and applicable PORT-002 evidence.

The ChatGPT migration claim additionally requires PORT-014.

A stable anti-lock-in claim requires PORT-015.

## 5. Failure conditions

The applicable gate or claim fails when:

- provider-native objects become the only authoritative representation;
- an import executes source content;
- repeated import silently duplicates unchanged records;
- source identity is invented or collapsed into the wrong category;
- material branches, attachments, or unsupported events disappear without a report;
- imported content gains policy, permission, confirmation, capability, memory, or fact authority automatically;
- a model or runtime switch rewrites unrelated state;
- a failed export damages authoritative state;
- generic export cannot be inspected without the preferred environment;
- a full-fidelity claim is made despite material reported loss.

## 6. Release reporting

A release claiming portability must publish or retain, as appropriate:

- supported source and target formats and versions;
- adapter IDs and versions;
- implemented event and attachment coverage;
- known unsupported data;
- mapping and loss summaries;
- idempotency evidence;
- security and authority-boundary evidence;
- real local migration evidence where claimed;
- private manual evidence status for personal cloud-history migration without exposing private data;
- whether round-trip compatibility was tested or only one-way import/export.

## 7. Acceptance criteria

This test specification is accepted when:

- each portability claim maps to stable PORT identifiers;
- local model, runtime, interface, application, cloud source, and doll-exit cases are distinguished;
- loss visibility is required rather than optional;
- imported content remains non-authoritative;
- generic export provides a doll-independent recovery path;
- local AI migration is required before provider-specific cloud portability becomes the primary claim;
- private real-data drills remain private while their result and limitations can be recorded safely.
