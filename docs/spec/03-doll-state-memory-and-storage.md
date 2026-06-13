# Doll State, memory, and storage

**Status:** Accepted for implementation  
**Specification version:** 0.1  
**Depends on:** `00-decisions-baseline.md`, `01-product-and-continuity-contract.md`, `02-architecture-and-data-flow.md`

## 1. Purpose

This document defines the authoritative state model for doll.

The objective is to ensure that user-controlled state remains:

- local by default;
- independent of any one model, runtime, or UI;
- inspectable and exportable;
- versioned and migratable;
- recoverable after failure;
- compatible across Lite and Heavy profiles;
- safe to back up without including secrets by accident.

## 2. State categories

All stored data must be classified into one of the following categories.

### 2.1 Authoritative state

Authoritative state is the durable source of truth.

Examples:

- workspace identity;
- confirmed memories;
- preferences and policies;
- permissions;
- project records;
- decisions;
- source records;
- research-session metadata;
- artifact metadata;
- model manifests;
- runtime manifests;
- migration history;
- backup manifests.

Authoritative state must be included in normal backups.

### 2.2 Authoritative files

Authoritative files are user or doll-created files whose contents cannot be reconstructed from indexes alone.

Examples:

- user-managed copies of imported documents;
- confirmed notes;
- generated reports;
- exported tables;
- transcripts;
- media artifacts;
- user-authored identity or personality files.

Authoritative files must be hashed and indexed.

### 2.3 Reproducible indexes

Reproducible indexes can be rebuilt from authoritative records or files.

Examples:

- SQLite FTS indexes;
- embedding vectors;
- chunk maps;
- thumbnail indexes;
- derived metadata;
- search caches.

A backup may omit reproducible indexes when the manifest records how to rebuild them.

### 2.4 Disposable caches

Disposable caches improve performance but have no continuity value.

Examples:

- temporary downloads;
- transient extraction files;
- model response caches;
- browser caches;
- temporary OCR images;
- partial media frames.

They must not be required for restoration.

### 2.5 Restricted assets

Restricted assets may be necessary for operation but have separate licensing, privacy, or size constraints.

Examples:

- model weights;
- tokenizers;
- runtime installers;
- private datasets;
- training checkpoints;
- encrypted secret stores.

Restricted assets are not included in the public repository. A user-controlled backup or Offline Recovery Kit may include or reference them when legally and technically permitted.

## 3. Workspace identity

Each workspace must have a stable identity record.

Minimum fields:

```text
workspace_id
created_at
updated_at
schema_version
product_version_created
product_version_last_opened
profile_preference
state_revision
instance_label
```

### Rules

- `workspace_id` is immutable.
- `schema_version` identifies the authoritative state schema.
- `state_revision` increases after committed authoritative changes.
- moving or restoring a workspace must not silently create a new workspace identity;
- cloning a workspace intentionally must create a new clone record and provenance relationship.

## 4. Common record envelope

All authoritative records must use a common logical envelope, even if the physical storage representation differs.

Required fields:

```text
id
record_type
schema_version
created_at
updated_at
revision
status
provenance
sensitivity
```

Recommended optional fields:

```text
title
tags
project_id
source_ids
artifact_ids
supersedes_id
deleted_at
metadata
```

### 4.1 IDs

- IDs must be globally unique within a workspace.
- IDs must not encode personal information.
- UUIDv7 or another sortable, collision-resistant identifier is preferred.
- User-facing slugs may exist but are not authoritative identifiers.

### 4.2 Time

- Stored timestamps use UTC and an unambiguous standard representation.
- User interfaces may display local time.
- Creation time is immutable.
- Update time changes only on committed modification.

### 4.3 Revision

- Each mutable record has an integer or equivalent revision.
- Updates must detect stale revisions where simultaneous writes are possible.
- Imports must not silently overwrite a newer local revision.

### 4.4 Status

The shared status field must distinguish at least:

- active;
- archived;
- superseded;
- deleted or tombstoned;
- invalid or quarantined, where applicable.

Status semantics may be narrowed by record type.

### 4.5 Provenance

Provenance identifies how a record was created.

Minimum concepts:

- user-created;
- user-confirmed;
- imported;
- model-proposed;
- system-generated;
- migrated;
- restored.

Where a model contributed, provenance should reference:

- model manifest ID;
- runtime adapter ID;
- session ID;
- operation ID.

### 4.6 Sensitivity

Initial sensitivity classes:

- public;
- internal;
- personal;
- sensitive;
- secret.

`secret` records must not be passed to models or exported through normal state packages unless a future explicit secret-handling specification permits it.

## 5. Core record types

## 5.1 WorkspaceRecord

Defines workspace identity and schema state.

## 5.2 PreferenceRecord

Stores user-controlled preferences that affect presentation or operation.

Examples:

- language;
- output format preference;
- verbosity preference;
- profile preference;
- local-only policy;
- retention preferences.

Preferences must not be hidden only inside prompts.

## 5.3 PolicyRecord

Stores explicit behavioral rules, prohibitions, and operating constraints.

Examples:

- never upload original files;
- do not perform external POST requests;
- prefer official sources;
- ask before overwriting;
- do not retain health information.

Policy records are authoritative and must be distinguishable from ordinary memories.

## 5.4 PermissionRecord

Defines user-approved capability settings.

Minimum concepts:

- capability ID;
- scope;
- mode;
- expiration;
- approval source;
- last changed at;
- last used at, where safe.

Initial permission modes:

- denied;
- allow once;
- ask every time;
- allow within defined scope.

The initial product must not include a universal `allow all` mode.

## 5.5 MemoryRecord

Stores a unit of remembered information.

Required fields in addition to the common envelope:

```text
memory_class
content
subject
source_type
confirmation_state
valid_from
valid_until
confidence
```

Optional fields:

```text
related_memory_ids
contradicts_memory_ids
project_id
last_recalled_at
recall_count
```

Memory classes:

- session;
- suggested;
- confirmed.

Only confirmed memory is authoritative long-term memory.

### Memory granularity

A memory should represent one coherent fact, preference, decision, or durable context item where practical.

The system should avoid storing whole conversations as one confirmed memory.

### Memory provenance

A confirmed memory must identify whether it was:

- explicitly entered by the user;
- accepted from a suggestion;
- imported from an approved source;
- migrated from a previous version.

### Memory contradiction

The system must not silently overwrite an existing memory when a new statement conflicts with it.

It should:

1. create a suggested update or contradiction record;
2. show the conflicting records;
3. require user confirmation;
4. supersede or preserve both according to the decision.

### Memory recall

Memory retrieval must be scoped by:

- current task;
- sensitivity;
- project;
- recency or validity;
- explicit user instruction;
- model context budget.

The system must not send the entire memory store to a model by default.

## 5.6 ProjectRecord

Represents a durable body of work.

Minimum fields:

```text
name
description
status
started_at
ended_at
```

Projects may link to:

- decisions;
- memories;
- documents;
- research sessions;
- artifacts;
- policies;
- tasks, if later specified.

## 5.7 DecisionRecord

Stores an explicit decision and its context.

Minimum fields:

```text
decision
reason
status
decided_at
```

Optional fields:

```text
alternatives
constraints
review_after
supersedes_id
```

A decision must not be inferred into authoritative state without user confirmation.

## 5.8 ConversationRecord

Conversation records preserve interaction history but are not automatically long-term memory.

Minimum fields:

```text
conversation_id
started_at
ended_at
interface_id
profile
```

Message records may include:

```text
role
content_reference
created_at
model_manifest_id
runtime_adapter_id
operation_id
```

Conversation storage policy must support:

- export;
- deletion by the user;
- separation from confirmed memory;
- configurable retention;
- secret redaction in logs.

Raw conversation content may be stored as files or structured records, but the format must be documented.

## 5.9 DocumentRecord

Represents a document known to doll.

Minimum fields:

```text
display_name
media_type
storage_mode
content_hash
size_bytes
```

Storage modes:

- managed copy inside workspace;
- external reference;
- imported snapshot;
- generated artifact.

Optional fields:

```text
original_path_hint
managed_path
external_reference
source_id
extraction_status
```

Absolute external paths must not be required for portable exports.

## 5.10 SourceRecord

Represents the origin of information.

Minimum fields:

```text
source_type
title
locator
retrieved_at
content_hash
```

Source types may include:

- web URL;
- local document;
- imported archive;
- user statement;
- generated source record;
- later connector source.

Web source records should support:

```text
published_at
last_modified_at
retrieval_method
http_status
canonical_url
cache_path
```

## 5.11 ResearchSessionRecord

Groups a research activity.

Minimum fields:

```text
question
started_at
completed_at
status
```

Links may include:

- queries;
- source records;
- citation records;
- notes;
- produced artifacts;
- model and runtime provenance.

## 5.12 CitationRecord

Links a claim or artifact section to a source location.

Minimum fields:

```text
source_id
locator_type
locator_value
quoted_hash
```

Possible locator types:

- text offset;
- line range;
- page number;
- section anchor;
- timestamp range;
- image region, later.

The citation record must remain useful even if a display UI changes.

## 5.13 ArtifactRecord

Represents an output created or imported as a user work product.

Minimum fields:

```text
artifact_type
title
managed_path
content_hash
size_bytes
created_by
```

Optional fields:

```text
project_id
source_ids
parent_artifact_id
format
model_manifest_id
runtime_adapter_id
```

Artifacts are authoritative files unless explicitly marked temporary.

## 5.14 ModelManifestRecord

Identifies a model independently of one runtime tag.

Minimum fields:

```text
model_id
display_name
developer
source
revision
license_id
format
quantization
checksum
```

Optional fields:

```text
parameter_count
context_window
roles
runtime_compatibility
minimum_ram
recommended_ram
minimum_vram
validation_status
offline_verified_at
```

Runtime aliases such as an Ollama tag are adapter bindings, not the authoritative model identity.

## 5.15 RuntimeManifestRecord

Identifies a model runtime installation or supported runtime definition.

Minimum fields:

```text
runtime_id
runtime_type
version
platform
```

Optional fields:

```text
executable_path
installation_source
checksum
capabilities
last_health_check
```

## 5.16 ModelBindingRecord

Binds a model role to a validated model and runtime.

Minimum fields:

```text
role
model_manifest_id
runtime_manifest_id
status
```

Statuses:

- active;
- previous;
- fallback;
- candidate;
- disabled.

Only one active binding per role and profile is allowed unless a later routing specification permits ensembles.

## 5.17 CapabilityDefinitionRecord

Defines a versioned capability contract.

Minimum fields:

```text
capability_id
version
permission_class
input_schema_ref
output_schema_ref
```

Optional fields:

```text
network_behavior
path_scope
approval_requirement
timeout_seconds
```

## 5.18 AuditEventRecord

Stores an append-oriented audit event.

Minimum fields:

```text
event_id
event_type
occurred_at
actor_type
result
```

Optional fields:

```text
session_id
operation_id
capability_id
model_manifest_id
runtime_manifest_id
target_type
target_id
network_destination
approval_id
error_class
```

Audit records must avoid raw secrets and unnecessary full content.

## 5.19 BackupManifestRecord

Describes a backup.

Minimum fields:

```text
backup_id
created_at
workspace_id
schema_version
state_revision
backup_type
manifest_hash
verification_status
```

Optional fields:

```text
base_backup_id
included_categories
excluded_categories
encryption_method
storage_location_hint
verified_at
restored_at
```

## 5.20 MigrationRecord

Records a migration attempt.

Minimum fields:

```text
migration_id
from_schema_version
to_schema_version
started_at
status
```

Optional fields:

```text
completed_at
pre_migration_backup_id
error_class
rollback_status
```

## 6. Doll State Package

The Doll State Package is the portable representation of authoritative state.

## 6.1 Package goals

The package must be:

- versioned;
- self-describing;
- integrity-checkable;
- independent of a specific UI or runtime;
- importable into an empty compatible workspace;
- explicit about omitted files and external references;
- safe to inspect without executing code.

## 6.2 Package structure direction

```text
doll-state-package/
  manifest.json
  records/
    workspace.json
    preferences.jsonl
    policies.jsonl
    permissions.jsonl
    memories.jsonl
    projects.jsonl
    decisions.jsonl
    conversations.jsonl
    documents.jsonl
    sources.jsonl
    research-sessions.jsonl
    citations.jsonl
    artifacts.jsonl
    model-manifests.jsonl
    runtime-manifests.jsonl
    model-bindings.jsonl
    backup-history.jsonl
    migration-history.jsonl
  files/
    authoritative/
  checksums.json
  README.txt
```

This structure is directional. Exact filenames and grouping may change before schema implementation.

## 6.3 Manifest requirements

The package manifest must state:

- package format version;
- workspace ID;
- export time;
- source product version;
- source schema version;
- state revision;
- included categories;
- excluded categories;
- file count;
- total size;
- checksum algorithm;
- encryption state;
- external references;
- compatibility notes.

## 6.4 Import rules

Import must:

1. parse without executing package content;
2. verify checksums;
3. validate schemas;
4. detect workspace identity conflicts;
5. detect unsupported future versions;
6. stage records and files;
7. show planned changes;
8. require confirmation where destructive conflict resolution is possible;
9. commit atomically where practical;
10. produce an import and audit record.

Import must not silently replace a newer record with an older one.

## 7. Physical storage direction

## 7.1 SQLite

SQLite is the initial authoritative metadata store.

Suitable data:

- record envelopes;
- preferences;
- policies;
- permissions;
- memory metadata and text;
- projects and decisions;
- source and research metadata;
- artifact metadata;
- model and runtime manifests;
- audit events;
- migration and backup metadata.

SQLite must not be the only portable representation. Export formats and schemas remain required.

## 7.2 Filesystem

The filesystem stores:

- authoritative user and generated files;
- imported managed copies;
- source snapshots;
- extracts;
- backups;
- caches;
- model assets;
- optional private datasets and checkpoints.

Files must be referenced by stable record IDs and content hashes, not only by display names.

## 7.3 Text formats

Preferred text formats:

- JSON for manifests;
- JSONL for record exports;
- Markdown for human-readable notes and reports;
- CSV for tabular user outputs;
- plain UTF-8 text where appropriate.

The project may use binary formats internally for performance, but continuity exports must remain documented.

## 8. Workspace layout direction

```text
doll-data/
  workspace.json
  state/
    doll.sqlite3
  memory/
  documents/
    managed/
    extracts/
  research/
    sources/
    sessions/
  artifacts/
  media/
  models/
    manifests/
    weights/
    tokenizers/
    licenses/
    checksums/
    benchmarks/
  backups/
  recovery-kits/
  caches/
  temporary/
  audit/
  config/
```

The exact layout is subject to platform and security review.

### Layout rules

- private data must not be placed under the repository checkout by default;
- temporary and cache directories must be distinguishable from authoritative files;
- model assets must be distinguishable from model manifests;
- secrets must not be stored in normal configuration files;
- managed file paths must use record IDs or collision-resistant names;
- user-facing titles must not be trusted as safe filenames.

## 9. Retention and deletion

## 9.1 Model autonomy

Models cannot autonomously delete authoritative state or files.

## 9.2 User deletion

The user must have an explicit management path to delete their own records and files.

Default deletion direction:

```text
active
  -> user-confirmed trash or tombstone
  -> retention period
  -> explicit purge
```

A default trash retention of 30 days is the current product direction, subject to later platform specification.

## 9.3 Automatic cleanup

Automatic cleanup may apply only to clearly classified caches and temporary files.

It must never automatically delete:

- confirmed memories;
- authoritative documents;
- artifacts;
- model manifests;
- backups;
- model weights;
- fixed source records.

without an explicit policy accepted by the user.

## 9.4 Capacity protection

When disk space is low, the system should:

1. stop nonessential acquisition;
2. report space usage by category;
3. propose cache cleanup;
4. avoid deleting authoritative data;
5. preserve the current valid state.

## 10. Memory behavior

## 10.1 Session memory

Session memory exists for active interaction context.

It may be summarized or discarded after the session according to configuration.

It is not automatically durable.

## 10.2 Suggested memory

Suggested memory is a review queue.

Each suggestion must show:

- proposed content;
- reason for saving;
- source;
- sensitivity classification;
- related or conflicting memories;
- proposed project scope;
- proposed expiration, if any.

The user may accept, edit, reject, or defer it.

## 10.3 Confirmed memory

Confirmed memory is durable and model-independent.

The user must be able to:

- list it;
- search it;
- inspect provenance;
- edit it;
- archive it;
- delete it;
- export it.

## 10.4 Sensitive information

The system must not propose durable storage by default for:

- passwords;
- API keys;
- private keys;
- authentication tokens;
- full payment-card data;
- banking credentials;
- government identification numbers;
- health information unless explicitly requested;
- third-party personal data inferred from documents.

Detection is best-effort and cannot replace user review.

## 10.5 Memory retrieval transparency

Where practical, the interface should show which confirmed memories influenced a response.

The user must be able to request a response without long-term memory.

## 11. Conversation and artifact separation

A conversation is not the same as an artifact.

Important output should be savable as a separate artifact with:

- stable title;
- format;
- file hash;
- project link;
- source links;
- creation provenance;
- version relationship.

This prevents important work from remaining trapped inside chat history.

## 12. Backup classes

Initial backup classes:

### 12.1 State backup

Includes authoritative structured records and necessary manifests.

### 12.2 Full workspace backup

Includes authoritative records and authoritative files, excluding restricted assets unless selected.

### 12.3 Recovery backup

Includes state, files, environment manifests, validation instructions, and selected restricted assets or references suitable for an Offline Recovery Kit.

### 12.4 Backup requirements

Every completed backup must include:

- manifest;
- checksums;
- source workspace ID;
- schema version;
- state revision;
- included and excluded categories;
- verification result.

## 13. Migration

## 13.1 Version rules

- Every authoritative schema has an explicit version.
- Product version and schema version are separate.
- A product version must declare supported schema versions.
- Unsupported future schemas must not be opened for writing.

## 13.2 Migration process

```text
inspect
  -> compatibility check
  -> pre-migration backup
  -> stage migration
  -> validate staged result
  -> commit
  -> post-migration doctor check
  -> record success
```

On failure:

```text
stop
  -> preserve original
  -> record failure
  -> offer rollback or restore
```

## 13.3 Irreversible migrations

An irreversible migration requires:

- explicit specification;
- release notes;
- verified backup;
- explicit user confirmation;
- export path to a documented prior format where practical.

## 14. Cross-platform portability

Portable state must not depend on:

- drive letters;
- POSIX-only absolute paths;
- case-sensitive filenames;
- symlink-only behavior;
- one operating system's credential store;
- one shell;
- one line-ending convention.

Exports should use normalized relative paths for managed files.

Invalid or reserved filenames must be mapped through safe managed names rather than altering user-facing titles.

## 15. Integrity and hashing

The project must define one default cryptographic hash algorithm for package and file integrity.

Initial direction:

- SHA-256 for file and manifest integrity;
- content hashes stored independently of filenames;
- checksum verification before import, restore, model activation, or source reuse where applicable.

Hash mismatch must fail closed.

## 16. Encryption direction

The core must not invent custom cryptography.

Initial direction:

- rely on operating-system disk encryption for normal workspace-at-rest protection;
- support an optional standard encrypted archive format for exported backups later;
- store cloud credentials, when cloud is implemented, in operating-system credential storage;
- never write secrets to ordinary logs or state exports.

Encryption implementation details belong in the security and platform specification.

## 17. Export and inspection

A user must be able to inspect state without running a model.

At minimum, the project must eventually provide:

- human-readable package manifest;
- machine-readable records;
- schema documentation;
- file checksum list;
- compatibility summary;
- warnings about omitted restricted assets;
- a way to list memory, projects, artifacts, models, backups, and migrations through CLI or API.

## 18. First implementation subset

The first continuity proof needs only a minimal subset of this model:

- WorkspaceRecord;
- PreferenceRecord;
- PolicyRecord;
- confirmed MemoryRecord;
- ProjectRecord or DecisionRecord;
- ArtifactRecord;
- ModelManifestRecord;
- RuntimeManifestRecord;
- ModelBindingRecord;
- AuditEventRecord;
- BackupManifestRecord;
- MigrationRecord.

The schemas must still be versioned and extensible.

Conversation, research, citation, media, and suggested-memory details may follow in later PRs.

## 19. Acceptance criteria

This specification is acceptable when the later implementation can prove that:

- durable records have version, provenance, sensitivity, and revision metadata;
- confirmed memory is distinct from conversation history;
- important outputs can exist outside chat history;
- model and runtime identities are separate from user state;
- exports are documented and integrity-checkable;
- restore can target an empty workspace;
- indexes and caches are distinguishable from authoritative data;
- imports cannot silently overwrite newer state;
- automatic cleanup cannot delete authoritative data;
- paths are portable across supported platforms;
- a model cannot directly mutate state outside approved services.
