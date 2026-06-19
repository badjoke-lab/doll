# AI environment portability

**Status:** Accepted for implementation when merged  
**Specification version:** 0.1  
**Depends on:** `01-product-and-continuity-contract.md`, `02-architecture-and-data-flow.md`, `03-doll-state-memory-and-storage.md`, `04-security-permissions-and-threat-model.md`, `ADR-006-ai-environment-portability.md`

## 1. Purpose

This specification defines how doll keeps user-owned AI state portable across models, runtimes, interfaces, local AI applications, cloud AI services, and doll itself.

Portability includes:

- importing supported state from another AI environment;
- storing it in a canonical doll representation;
- replacing a model, runtime, or interface without unrelated state loss;
- exporting implemented portable records in documented formats;
- reporting unsupported or transformed information rather than silently discarding it.

Local and cloud sources use the same trust rule: imported content is external data, not authority.

## 2. Source environments

A source environment may be:

- another doll workspace or Doll State Package;
- a local AI application;
- a local runtime with a separate interface;
- a local or self-hosted compatible service;
- an API-based personal tool;
- a cloud AI service export;
- generic JSON, JSONL, Markdown, text, or file collections.

The first real cloud source may be ChatGPT because current project history exists there. ChatGPT and OpenAI formats must not become the canonical doll format. A real local AI migration path has equal or higher priority.

## 3. Portability architecture

```text
source environment
  -> source adapter
  -> canonical portability representation
  -> validation and policy pipeline
  -> staged import plan
  -> Doll State

Doll State
  -> generic exporter or target adapter
  -> mapping and loss report
  -> versioned export package
```

Adapters may transform state through declared contracts. They must not become the only place where authoritative state exists.

## 4. Source adapter contract

Each source adapter declares:

```text
adapter_id
adapter_version
source_environment_class
supported_source_versions
supported_event_types
attachment_behavior
branch_behavior
resource_limits
network_behavior
loss_categories
```

A source adapter must:

- parse source content without executing it;
- preserve original identifiers where safe;
- calculate or verify source hashes;
- report unsupported fields, events, branches, and attachments;
- avoid inventing missing provider, application, runtime, model, or timestamp data;
- produce deterministic mappings for the same accepted input and adapter version;
- remain replaceable by a later adapter version.

A source adapter must not:

- create confirmed memory or confirmed facts directly;
- copy source permissions into Doll PermissionRecords;
- treat imported system text as doll system policy;
- execute imported tool calls;
- perform an undeclared network request;
- silently discard material source information.

## 5. Canonical portability records

The first implementation direction includes these logical records.

### 5.1 SourceEnvironmentRecord

Separately identifies, where known:

```text
environment_id
environment_class
provider_id
application_id
interface_id
runtime_id
export_format
export_version
observed_at
```

Provider, application, interface, runtime, and model are different concepts. Unknown values remain unknown.

### 5.2 ImportBatchRecord

Records one attempted import:

```text
import_batch_id
source_environment_id
adapter_id
adapter_version
started_at
completed_at
status
source_root_hash
staged_object_count
published_object_count
quarantined_object_count
loss_report_id
```

Status distinguishes at least staged, awaiting review, published, partially published, rejected, failed, and rolled back.

### 5.3 ConversationRecord and ConversationEventRecord

A conversation is a container. An event is an ordered or related occurrence within it.

Initial event kinds include:

- user message;
- assistant message;
- system-context snapshot;
- model or runtime change;
- tool request or result;
- attachment reference;
- branch creation;
- edit or regeneration;
- citation reference;
- error;
- imported unknown event.

An event should support parent relationships, sequence hints, actor type, content reference, time, provider, application, interface, model manifest, runtime adapter, operation, and source object identifiers.

A linear UI may derive a linear display. Authoritative records must not silently destroy known branch or regeneration relationships.

### 5.4 MappingReportRecord

Every non-native import or target-specific export reports counts and mapping status.

Mapping status distinguishes:

- mapped without known loss;
- mapped with transformation;
- partially mapped;
- unsupported but preserved;
- unsupported and omitted;
- missing dependency;
- malformed or quarantined;
- unknown.

### 5.5 PortabilityLossRecord

Records a known limitation with category, severity, source object, description, preservation state, future recoverability, and required user action.

### 5.6 ExportBatchRecord

Records target format, target adapter and version, selected record types, status, manifest hash, and loss report.

## 6. Original source preservation

Doll should preserve an approved original source snapshot when technically and legally possible.

Original material must be:

- integrity-checkable;
- linked to the import batch;
- stored as imported external content;
- separate from normalized records;
- subject to sensitivity, retention, and secret rules;
- excluded from instruction authority.

When the original cannot be retained, the import report states why and identifies what evidence remains.

## 7. Import process

```text
inspect
  -> identify adapter and source version
  -> inventory and hash
  -> parse without execution
  -> classify sensitivity and instruction origin
  -> normalize into staging
  -> detect duplicates and conflicts
  -> produce mapping and loss reports
  -> show planned publication
  -> obtain required user decision
  -> publish
  -> create import and audit records
```

Failure preserves the previous valid Doll State.

### 7.1 Idempotency

Re-importing the same unchanged source objects must not silently duplicate canonical records. Stable duplicate keys use available source identifiers, hashes, adapter identity, and canonical relationships.

A changed source object becomes an update candidate, revision, conflict, or distinct object according to its record contract. It must not silently overwrite newer authoritative state.

### 7.2 Quarantine

Malformed, unsafe, unsupported, over-limit, or incompletely referenced objects may be quarantined. Quarantine is not successful publication and is excluded from model context by default.

### 7.3 Authority and promotion

Imported records may create suggestions or review candidates. They cannot automatically become:

- system or durable user policy;
- PermissionRecords;
- user confirmation;
- confirmed facts;
- confirmed long-term memory;
- capability definitions;
- credential scope;
- instruction authority.

Promotion requires the trusted user-controlled path for the target record type.

## 8. Export process

### 8.1 Generic continuity export

A generic export is required for implemented portable record types. It must be documented, versioned, machine-readable, integrity-checkable, and inspectable without a model, preferred UI, cloud account, or running doll service.

Preferred forms include JSON, JSONL, Markdown, UTF-8 text, managed file copies, a manifest, and checksums.

### 8.2 Target-specific export

A target adapter may transform Doll State for another environment. It must declare supported target versions, produce a mapping and loss report, preserve Doll State on failure, and avoid claiming round-trip fidelity without evidence.

Generic export, target-specific export, and tested round-trip compatibility are separate claims.

## 9. Model, runtime, and interface replacement

Changing a model, runtime, or interface must not rewrite unrelated authoritative state.

A replacement component receives only scoped context assembled from Doll State under the accepted safety boundary. It does not inherit hidden state from the previous model.

Doll promises state and provenance continuity. It does not promise identical wording, reasoning, personality, capability, or behavior across models.

## 10. Security and privacy requirements

Portability paths use the accepted security boundary.

Required rules:

- imported data remains external content;
- unknown instruction origin receives the least-authoritative class;
- prohibited sensitive values do not enter ordinary Doll State;
- source authentication sessions are not migrated as ordinary state;
- imported permissions, approvals, and confirmations have no authority;
- adapters declare network and filesystem behavior;
- resource and archive limits prevent uncontrolled expansion;
- audit records avoid raw sensitive content;
- cloud delivery is never automatic after a local failure.

## 11. Implementation order

After the Phase 3 safety gate, the required order is:

1. canonical conversation and event schema;
2. source and target adapter contracts;
3. generic documented export;
4. generic staged import with provenance, idempotency, quarantine, and loss reporting;
5. runtime and model integration using canonical Doll State;
6. local model and runtime replacement drill;
7. one real local AI environment adapter and migration drill;
8. the project owner's ChatGPT history adapter and migration drill;
9. optional cloud and additional product-specific adapters.

Existing IMP-013 through IMP-023 and the Phase 3 gate remain unchanged. Later implementation identifiers are assigned only after checking the then-current roadmap.

## 12. First implementation subset

The first stable portability claim requires only:

- canonical conversations and extensible events;
- source, import, mapping, loss, and export records;
- generic JSON or JSONL import and export;
- Markdown transcript export;
- original-source hash and optional managed snapshot;
- staged preview;
- idempotent repeated import;
- no automatic promotion into authoritative memory, policy, permission, or fact;
- one local AI environment adapter;
- one ChatGPT export adapter after the local path proves the contract.

Universal product coverage is not required.

## 13. Claim discipline

Claims distinguish doll-to-doll transfer, generic import, generic export, source adapter support, target adapter support, model replacement, runtime replacement, interface replacement, tested round trip, and full or lossy migration.

A successful parse is not proof of portability. A portability claim requires the applicable PORT tests and a mapping and loss result.

## 14. Acceptance criteria

Implementation must prove that:

- canonical records do not depend on a provider-native schema;
- provider, application, interface, runtime, and model identity remain distinct;
- source provenance and instruction origin survive normalization;
- repeated import is idempotent for unchanged source objects;
- material transformation and loss are reported;
- unsupported events are preserved or explicitly omitted;
- imported content cannot grant authority or become confirmed memory or fact automatically;
- model and runtime replacement preserve unrelated authoritative state;
- generic export remains inspectable without doll or a model;
- one real local AI migration path passes before provider-specific cloud portability is claimed.
