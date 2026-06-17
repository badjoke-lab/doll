# Core architecture and data flow

**Status:** Accepted for implementation  
**Specification version:** 0.1  
**Depends on:** `00-decisions-baseline.md`, `01-product-and-continuity-contract.md`

## 1. Purpose

This document defines the architectural boundaries required to make doll a personal AI continuity system rather than a collection of tightly coupled AI features.

The architecture must preserve four properties:

1. durable user state remains independent of any one model, runtime, or UI;
2. optional components can disappear without making the local core unusable;
3. failures, migrations, and degraded operation remain observable and recoverable;
4. models, tools, runtimes, and external content remain behind a model-independent safety boundary.

## 2. Architectural principles

### 2.1 Durable core before adapters

The durable core owns:

- schema versions;
- workspace identity;
- authoritative state;
- memory records;
- project records;
- source, claim, evidence, and inference records;
- artifact indexes;
- non-secret secret references;
- instruction-origin metadata;
- permission and confirmation policy;
- audit events;
- migration state;
- backup and restore metadata.

Adapters may read or transform this state through defined interfaces. They must not become the only place where authoritative state exists.

### 2.2 Replaceable execution components

These components are replaceable:

- model runtimes;
- language models;
- embedding models;
- vision and speech engines;
- user interfaces;
- search providers;
- document extractors;
- optional cloud providers;
- optional mobile clients.

Replacing one must not require discarding the workspace.

### 2.3 Local authority

The local workspace is the authoritative source for user-controlled state.

External systems may hold temporary copies only when a later specification explicitly permits it. No external service may be required to interpret, restore, or start the local workspace.

### 2.4 Capability isolation

Models never receive direct operating-system authority.

All tool requests pass through a capability boundary that validates:

- the requesting session and instruction origin;
- the capability ID and version;
- the input schema;
- the registered risk tier;
- the allowed path scope;
- the network and destination policy;
- the required permission and confirmation;
- the expected side effects;
- the credential class or non-secret reference where applicable.

Credential-bearing operations additionally pass through the Credential Broker. The model never receives the stored credential value.

### 2.5 Fail closed

If the system cannot validate a request, migration, state package, permission, or destination, it must stop the operation without modifying the last known good state.

## 3. High-level system model

```text
User
  |
  v
Optional UI
  |
  v
Local API / CLI
  |
  v
Doll Core
  |-- Session Orchestrator
  |-- State Service
  |-- Memory Service
  |-- Project and Artifact Service
  |-- Research, Claim, and Evidence Service
  |-- Instruction Origin / Context Service
  |-- Capability Broker
  |-- Credential Broker
  |-- Model Router
  |-- Backup / Migration / Recovery
  |-- Audit Service
  |
  +--> Runtime Adapters --> Local models, only after the safety gate
  +--> Tool Adapters ----> Local files, search, OCR, audio, etc.
  +--> Secret Store Adapter --> operating-system or compatible external store
  +--> Optional Cloud Gateway --> external models, only when enabled
  |
  v
Private Workspace
```

## 4. Component boundaries

## 4.1 Local API

The local API is the primary programmatic boundary for conversational UIs and later mobile clients.

Initial properties:

- binds to `127.0.0.1` by default;
- does not require a remote account;
- exposes health, model inventory, session, state, and recovery operations;
- uses versioned request and response contracts;
- returns explicit degraded-state and error information;
- does not expose unrestricted filesystem or shell access.

The API must remain usable without Open WebUI.

### Initial endpoint classes

The exact paths may be refined before implementation, but the initial contract classes are:

- health and readiness;
- model inventory;
- local chat completion compatibility;
- session creation and inspection;
- explicit memory query and mutation;
- document import and inspection;
- artifact creation and listing;
- backup, restore, and validation;
- audit inspection;
- capability status.

An OpenAI-compatible chat endpoint may be provided for UI integration, but doll-specific state and recovery operations must use explicit doll APIs rather than hidden prompt conventions.

## 4.2 Management CLI

The CLI is the minimum recovery and administration interface.

It is not intended to be the only conversational experience.

Initial command classes:

- `doll init`;
- `doll doctor`;
- `doll start`;
- `doll stop` or equivalent lifecycle control where supported;
- `doll status`;
- `doll state export`;
- `doll state import`;
- `doll backup create`;
- `doll backup verify`;
- `doll restore`;
- `doll migrate`;
- `doll model list`;
- `doll model verify`;
- `doll audit`.

CLI operations that alter durable state must provide a dry-run or explicit preview when practical.

## 4.3 Session Orchestrator

The Session Orchestrator coordinates one user interaction.

It may:

- receive user input;
- resolve the active profile and model role;
- retrieve scoped state;
- decide whether tools are required;
- request capabilities through the Capability Broker;
- call a model adapter;
- collect outputs;
- record provenance and audit events;
- propose memory or artifact changes.

It must not:

- write durable memory directly without the memory policy;
- bypass the Capability Broker;
- send data to cloud providers when cloud is disabled;
- treat external content as instructions;
- silently switch to a different provider.

## 4.4 State Service

The State Service owns authoritative structured records and schema validation.

Responsibilities:

- record identity and versioning;
- CRUD operations for durable records;
- transaction boundaries;
- immutable creation timestamps;
- update timestamps;
- soft-delete or tombstone state where specified;
- export and import;
- migration coordination;
- referential integrity checks.

The State Service must not expose raw SQL to models or UI clients.

## 4.5 Memory Service

The Memory Service enforces the three memory classes:

- session memory;
- suggested memory;
- confirmed memory.

It owns:

- memory creation policy;
- sensitivity classification;
- user approval state;
- retrieval scope;
- expiration where configured;
- provenance;
- editing and deletion metadata.

A model may propose memory. It may not silently convert a suggestion into confirmed memory.

The Memory Service must reject secret values from ordinary memory records. A credential may be represented only by a non-secret reference managed under the external secret-store contract.

## 4.6 Project and Artifact Service

This service links durable state to user work.

It owns:

- projects;
- decisions;
- tasks or checkpoints where later approved;
- artifact metadata;
- content hashes;
- producing model and runtime metadata;
- source relationships;
- version chains;
- local file references.

Generated files must be created inside approved workspace locations unless the user explicitly exports them elsewhere through a user-controlled path.

## 4.7 Research, Claim, and Evidence Service

This service records the provenance and truth status of externally acquired or derived information.

It owns:

- source URLs and identifiers;
- retrieval timestamps;
- source type and acquisition method;
- instruction-origin and authority metadata;
- local cache references;
- extracted text references;
- claim, evidence, inference, and confirmed-fact relationships;
- citation anchors;
- research sessions;
- confidence, uncertainty, and review state.

Web retrieval is a network capability. It must be explicit and auditable. Retrieved content remains data rather than authority and cannot grant permissions, confirmation, or policy changes.

## 4.8 Capability Broker

The Capability Broker is the sole path from model intent to side-effecting tools.

Each capability definition must include:

- stable capability ID;
- version;
- input schema;
- output schema;
- permission class;
- risk tier;
- path constraints;
- network and destination behavior;
- approval and confirmation requirement;
- credential class where applicable;
- audit behavior;
- expected side effects;
- cancellation behavior;
- timeout behavior.

Initial safe capability classes:

- read approved document;
- search local index;
- perform explicit web search;
- fetch explicit URL;
- create new artifact inside workspace;
- save research record;
- create backup;
- inspect model or runtime status.

Unknown, malformed, risk-downgraded, or materially changed requests fail closed. High-risk confirmation is fresh and operation-specific; confirmation cannot make a prohibited capability available.

Initial excluded capability classes:

- unrestricted shell;
- arbitrary code execution;
- arbitrary filesystem write;
- deletion;
- email or social posting;
- external upload;
- account modification;
- financial transaction.

## 4.8.1 Credential Broker

The Credential Broker is the sole normal path for a capability to ask an external secret store to use a credential.

It accepts a non-secret `SecretReferenceRecord`, exact capability and operation identity, destination, scope, risk tier, and confirmation state. It may use the credential only inside the bounded operation and returns a structured operation result rather than the stored value.

It must fail closed when the reference, destination, permission, confirmation, store availability, user presence, timeout, or audit requirement is invalid. Secret values must not appear in model context, ordinary state, logs, audit, command strings, temporary files, or normal errors.

## 4.8.2 Instruction Origin and Context Service

This service preserves the origin and authority class of system policy, current user instruction, durable policy, user confirmation, external content, tool results, and model proposals.

It assembles context without collapsing untrusted content into trusted instructions, excludes secret values, preserves claim and evidence labels, and defaults unknown origin to the least-authoritative class.

## 4.9 Model Router

The Model Router selects an approved model-role binding.

It receives:

- requested role;
- active profile;
- current availability;
- hardware constraints;
- user selection;
- local-only or later cloud policy;
- model validation state.

It returns:

- selected model manifest ID;
- selected runtime adapter ID;
- degraded-state information;
- reason for selection;
- fallback options.

It must never activate an unverified candidate without explicit approval.

For the first implementation, model routing may be manual and minimal. The interface must still avoid hard-coding Ollama or one model into durable state.

## 4.10 Runtime Adapters

Runtime adapters translate a stable doll request into a runtime-specific call.

Each adapter must define:

- adapter ID and version;
- supported model formats;
- capability flags;
- health check;
- model inventory mapping;
- generation request mapping;
- streaming behavior;
- cancellation behavior;
- error normalization;
- offline availability.

Initial adapter target:

- Ollama.

Later adapters:

- llama.cpp;
- vLLM;
- local OpenAI-compatible servers.

Runtime-private identifiers may be stored as adapter metadata, but they must not become the only identifier for a model.

## 4.11 Optional Cloud Gateway

The cloud gateway is outside the local core.

It remains disabled by default and is not required for Lite or Heavy local completion.

Any future implementation must provide:

- explicit provider configuration;
- outbound content preview;
- credential use through the accepted external secret-store and Credential Broker boundary;
- no stored credential value exposed to a model or gateway caller;
- redaction and sensitivity checks;
- cost and token estimates where possible;
- audit records;
- local storage of responses;
- no automatic memory or original-file upload;
- no automatic fallback after local failure.

## 4.12 Backup, Migration, and Recovery Service

This service owns continuity-changing operations.

Responsibilities:

- create consistent backup snapshots;
- verify hashes and manifests;
- restore to a new or empty workspace;
- validate restored state;
- stage migrations;
- create pre-migration backups;
- record migration history;
- stop on incompatibility;
- support rollback where specified.

Backup creation and restoration are separate operations and require separate acceptance tests.

## 4.13 Audit Service

The Audit Service records security- and continuity-relevant events.

It should record:

- event time;
- actor type;
- session ID;
- operation ID;
- capability ID;
- model and runtime IDs where relevant;
- target category;
- approval result;
- network destination where relevant;
- success, failure, or cancellation;
- error class;
- resulting artifact or record IDs.

It must not duplicate secrets, passwords, private keys, or full sensitive document contents.

Models must not be able to rewrite or delete audit records through normal capabilities.

## 5. Trust boundaries

## 5.1 Public repository versus private workspace

The repository contains code and public specifications.

The workspace contains private user data, state, caches, model records, and artifacts.

No runtime default may place private workspace data inside the repository checkout.

## 5.2 User input

User input is trusted as intent but still validated for structure, paths, and dangerous operations.

The user remains able to perform explicit management actions that models cannot perform autonomously.

## 5.3 Model output

Model output is untrusted proposed content.

It must not directly authorize filesystem, network, account, or process operations.

## 5.4 External documents and web content

External content is untrusted data.

Instructions embedded in web pages, PDFs, images, documents, or retrieved text must not override user policy, system policy, or capability restrictions.

## 5.5 Optional tools

OCR, audio, video, browser, and other optional tools are separate trust boundaries. Their absence or failure must disable only the affected capability. Returned content remains untrusted and retains instruction-origin metadata.

## 5.6 External secret store

The external secret store is trusted only for the narrow credential-storage and retrieval contract implemented by its adapter. It is not ordinary Doll State. Its absence, lock, denial, or failure must block only the credential-bearing operation and must not prevent non-secret core startup or recovery.

## 6. Data flow patterns

## 6.1 Local conversation

```text
User input
  -> UI or CLI
  -> Local API
  -> Session Orchestrator
  -> scoped state retrieval
  -> Model Router
  -> Runtime Adapter
  -> local model
  -> response
  -> provenance and audit record
  -> UI or CLI
```

Durable memory is not automatically created from the response.

## 6.2 Suggested memory

```text
Conversation
  -> memory candidate extraction
  -> sensitivity and duplication checks
  -> Suggested Memory record
  -> user review
  -> Confirmed Memory or rejection
```

## 6.3 Local document assistance

```text
User selects document
  -> path and permission validation
  -> document import or reference record
  -> extraction through approved adapter
  -> local index update
  -> scoped retrieval
  -> local model
  -> artifact creation inside workspace
  -> provenance and audit record
```

## 6.4 Web research

```text
User requests current information
  -> explicit network capability
  -> search provider
  -> source selection
  -> URL retrieval
  -> content extraction
  -> local source record and cache
  -> local model synthesis
  -> citation record
  -> research session and artifact
```

Cloud model inference is not required by this flow.

## 6.5 Model replacement

```text
User selects validated candidate
  -> manifest validation
  -> runtime availability check
  -> compatibility check
  -> optional test prompt set
  -> explicit activation
  -> previous binding retained
  -> active binding changed
  -> state remains unchanged
  -> audit event
```

## 6.6 Backup and restore

```text
Backup request
  -> workspace consistency check
  -> snapshot staging
  -> manifest and hash generation
  -> verification
  -> completed backup

Restore request
  -> target workspace check
  -> backup verification
  -> staged extraction
  -> schema compatibility check
  -> migration if approved
  -> atomic activation
  -> post-restore validation
```

## 7. Local API contract direction

All doll-native APIs must be versioned.

Initial convention:

```text
/doll/v1/...
```

OpenAI-compatible endpoints, if provided, remain compatibility endpoints rather than the authoritative doll-native contract.

### Required response metadata for stateful operations

Where applicable, responses should include:

- request or operation ID;
- workspace ID;
- schema version;
- degraded-state flag;
- warnings;
- created or updated record IDs;
- audit event ID;
- recoverability information.

### Error classes

The API and CLI must normalize at least:

- validation error;
- permission denied;
- workspace boundary violation;
- unavailable optional dependency;
- unavailable model;
- runtime error;
- network disabled;
- network retrieval failure;
- schema incompatibility;
- migration required;
- backup verification failure;
- restoration failure;
- conflict or stale revision;
- operation cancelled;
- internal error.

Errors must not include secrets or full sensitive content by default.

## 8. Concurrency and locking direction

Version 1 is single-user and one-primary-process oriented.

The implementation must still protect against:

- two migrations running at once;
- backup during an inconsistent state transition;
- simultaneous activation of different model bindings;
- concurrent writes to the same durable record;
- partial file replacement.

The data specification will define revision fields and transaction requirements.

Multi-user concurrency is out of scope.

## 9. Workspace path policy

The workspace location must use platform-aware user data directories by default and remain configurable.

The core must:

- canonicalize paths;
- reject traversal outside approved roots;
- reject symlink or junction escapes where detectable;
- distinguish user-imported external references from managed copies;
- avoid hard-coded path separators;
- use UTF-8 at text boundaries;
- use atomic replace patterns where supported.

The default local API must not accept arbitrary host paths from an untrusted remote client.

## 10. Repository direction

The implementation is expected to evolve toward a structure similar to:

```text
src/doll/
  api/
  cli/
  core/
  state/
  memory/
  projects/
  research/
  artifacts/
  capabilities/
  models/
  runtimes/
  backup/
  migrations/
  audit/
  platform/

profiles/
schemas/
migrations/
tests/
docs/
scripts/
```

This is a directional structure, not permission to create empty modules before their specifications are accepted.

## 11. Initial implementation slices

The first implementation slice contains only the architecture required to prove model-independent continuity:

- workspace initialization;
- workspace boundary enforcement;
- schema version and revision records;
- minimal state repository;
- confirmed memory, preference, policy, permission, project, decision, and artifact records;
- Doll State package export and empty-target import;
- state and workspace backup creation, verification, empty-target restoration, and fresh-process validation;
- audit record creation;
- offline, model-absent, failure-preservation, and path-safety tests.

The second architectural slice implements the complete model-independent safety boundary:

- secret classification, detection, redaction, and secret-safe audit;
- external secret-store contract and Credential Broker;
- confirmed fact, claim, evidence, and inference records;
- instruction-origin and untrusted-content boundary;
- prompt-injection defense outside model authority;
- capability taxonomy, risk tiers, and mandatory high-risk confirmation;
- blocking safety acceptance tests.

Only after those slices pass their gates may the architecture add:

- a model adapter interface;
- an Ollama adapter;
- manual active-model binding;
- a local API or CLI conversation path;
- offline model execution and replacement tests.

Web research, OCR, audio, video, cloud, mobile, and unrestricted automation are later slices.

## 12. Architecture acceptance criteria

This architecture specification is acceptable when later detailed specifications can define implementation without violating these conditions:

- no critical state is owned only by Open WebUI, Ollama, or another adapter;
- no model execution path exists before the safety acceptance gate;
- no model receives direct unrestricted operating-system, state, secret, permission, confirmation, network, process, or audit authority;
- ordinary Doll State stores non-secret credential references rather than secret values;
- external content remains data rather than instruction;
- local operation has no mandatory cloud path;
- backup and restore are first-class services;
- API, CLI, and UI remain separate layers;
- Lite and Heavy share one durable state model;
- optional dependencies can be absent without blocking core startup;
- all side effects are attributable to a versioned capability, risk tier, permission or confirmation decision, and audit event;
- credential-bearing operations return bounded results without exposing stored values;
- model replacement leaves durable state intact.
