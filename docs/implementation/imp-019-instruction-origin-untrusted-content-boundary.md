# IMP-019 — Instruction Origin and Untrusted-Content Boundary

## Status

Phase 3 implementation following IMP-018.

## Purpose

IMP-019 establishes a model-independent boundary between instruction authority and instruction-shaped data.

Retrieved pages, imported records, extracted text, OCR, transcripts, tool results, runtime output, model proposals, and unknown-origin text remain data even when they contain imperative wording, role labels, policy claims, approval language, or requests to use capabilities.

The implementation does not attempt to decide authority by interpreting the text. Authority is derived only from validated immutable origin metadata.

## Record type

IMP-019 adds the ordinary Doll State record type `instruction_origin` using the existing generic record envelope and records table.

Each record stores:

- title and bounded instruction-bearing content;
- origin class;
- authority class derived from origin;
- data-only marker;
- actor type;
- acquisition method;
- optional source identifier;
- optional parent operation and session identifiers;
- optional SHA-256 content hash and observation time;
- bounded transformation history;
- optional parent instruction record;
- optional authority reference and revision;
- optional model manifest and runtime adapter identifiers;
- common revision, status, provenance, sensitivity, and timestamps.

The title, content, and source metadata are immutable after creation. A trusted user-controlled path may archive the record, but cannot rewrite its origin history.

No new database table or migration is required.

## Origin classes

The closed initial origin set is:

- `system_policy`;
- `current_user_instruction`;
- `durable_user_policy`;
- `user_management_action`;
- `external_content`;
- `imported_data`;
- `tool_result`;
- `runtime_output`;
- `model_proposal`;
- `unknown`.

Origin, actor, and acquisition method must agree. Required identifiers are validated for each origin. Unsupported or contradictory combinations fail closed.

Unknown origin accepts only the least-informative provenance. It cannot assert a source, operation, session, model, runtime, or authority reference.

## Authority classes

Authority is derived from origin through a closed mapping:

- system policy → `system_policy`;
- current user instruction → `current_user_instruction`;
- durable user policy → `durable_user_policy`;
- user management action → `user_management_action`;
- external content, imported data, tool results, and runtime output → `untrusted_data`;
- model proposal → `model_proposal`;
- unknown origin → `unknown_data`.

Callers cannot supply, raise, or rewrite the authority class.

The following do not grant authority:

- imperative or policy-like wording;
- claims to be a system or administrator message;
- apparent approval or confirmation text;
- local execution;
- structured JSON;
- source popularity or visual appearance;
- trust assessments or confidence values;
- repeated statements;
- successful retrieval, extraction, tool, runtime, or model execution.

## Data-only boundary

The following origins are always data-only:

- external content;
- imported data;
- tool result;
- runtime output;
- model proposal;
- unknown origin.

They cannot authorize task instructions, policy changes, permission changes, confirmations, capability definitions, risk-tier changes, workspace widening, network-policy changes, secret-policy changes, or security-instruction changes.

Tool and runtime output may later inform a response or be recorded as evidence, but the output itself does not grant a chained side effect.

A model proposal remains a proposal and cannot grant authority to itself or another record.

## Authority purposes

`authority_decision` uses a closed purpose set and deterministic origin policy.

- current user instructions may authorize only the current task instruction purpose;
- durable user policies may authorize task and durable-policy purposes while their referenced policy remains current;
- user management actions may represent task, management, permission-state, or confirmation-state authority;
- system policy may constrain all defined purposes;
- data-only, model-proposal, and unknown-origin records authorize none.

This is classification, not execution authorization. IMP-019 does not create permissions, confirmations, capabilities, risk tiers, or side effects. Future brokers must still perform their own exact validation. In particular, a management-action record does not replace the fresh exact confirmation required by IMP-022.

## Durable policy binding

A durable user policy record must reference an existing active and enabled `policy` record.

Creation requires:

- matching policy record ID;
- exact policy revision;
- instruction content equal to the referenced policy rule.

At context assembly, the reference is checked again. If the policy was archived, disabled, revised, removed, malformed, or changed, the instruction record is not rewritten. Its declared provenance remains visible, but its effective authority is downgraded to untrusted data with a machine-readable failure reason.

## Derivation boundary

A derived instruction record may reference one parent instruction record.

Validation requires:

- the parent exists and is an `instruction_origin` record;
- the derivation graph is acyclic;
- the child cannot have a higher authority rank than the parent;
- source and transformation history remain explicit.

Summarization, translation, extraction, OCR, transcription, normalization, or format conversion cannot increase authority.

## Context assembly

`assemble_context` returns a structured `InstructionContextBundle` with separate channels for:

- system policy;
- current user instruction;
- durable user policy;
- user management action;
- untrusted content;
- model proposals;
- unknown origin.

The service does not concatenate these records into a prompt or an unlabeled narrative. Every item retains declared and effective authority, active state, failure reason, origin class, source identifier, and transformations.

Archived records have no active authority. Stale durable-policy records are downgraded rather than silently omitted or treated as current.

Context packaging for an actual model remains part of IMP-020. IMP-019 provides the typed source material and authority decision boundary only.

## Persistence and state package

State packages add the optional member:

- `records/instruction-origins.jsonl`.

It is optional while reading, so packages created before IMP-019 remain valid.

Package verification checks:

- the typed record contract;
- immutable origin and authority consistency;
- derivation target types;
- derivation cycles;
- authority escalation through derivation;
- durable policy target type and historical revision validity.

Origin metadata survives export, import, backup, restore, and transfer through the existing record envelope and checksum machinery.

## Transactions and audit

Create and archive operations use one SQLite transaction containing:

1. the instruction-origin record mutation;
2. a secret-safe audit event;
3. the authoritative state-revision increment.

Any failure rolls back all three.

Audit metadata contains only bounded non-secret summaries such as origin class, authority class, actor type, acquisition method, transformation count, data-only status, and presence flags. Content, source identifiers, authority identifiers, model identifiers, runtime identifiers, hashes, and free-form text are not copied into audit metadata.

## Validation and secret boundary

The implementation rejects:

- unsupported enums;
- contradictory origin/actor/acquisition combinations;
- missing required references;
- forged authority classes;
- invalid UUIDs, hashes, timestamps, revisions, and transformations;
- unsafe control characters;
- local absolute paths in identifiers;
- credential-like values in ordinary state;
- stale write revisions;
- mutation through a read-only repository;
- non-user lifecycle mutation;
- malformed persisted records;
- missing or wrong-type cross-record links;
- derivation cycles and authority elevation.

Missing optional provenance remains visible as `null`; the implementation does not invent it.

## Model-independent boundary

IMP-019 adds no:

- model runtime or model call;
- prompt construction or prompt execution;
- retrieval, browser, OCR, transcript, or import adapter;
- prompt-injection classifier;
- tool execution or chained capability;
- permission grant or confirmation creation;
- capability registry or risk-tier implementation;
- network access;
- new dependency;
- custom cryptography.

Synthetic hostile content and source records test the boundary without executing or trusting that content.

Prompt-injection indicators and policy enforcement during model context packaging remain IMP-020. Capability taxonomy and exact high-risk confirmation remain IMP-021 and IMP-022.

## Platform and dependency effects

- macOS, Windows, Linux: SQLite and pure-Python contract behavior only.
- Dependencies: no new dependency.
- Network: none.
- Model execution: none.
- Database schema: unchanged.
- Migration: none.
- State-package format version: unchanged; the new member is optional for backward compatibility.
- Custom cryptography: none; optional SHA-256 values are validated provenance identifiers, not authority proofs.

## Acceptance evidence

Permanent synthetic tests prove:

- every required origin class maps to a fixed authority class;
- external, imported, tool, runtime, model, and unknown content remains data-only;
- hostile wording cannot raise authority;
- unknown origin defaults to the least authority;
- current user instructions and durable policies have bounded purposes;
- durable policy authority is lost when its referenced policy changes;
- user management records do not create an operational side effect;
- derived content cannot raise authority;
- derivation cycles and wrong-type links fail closed;
- context output keeps authority classes structurally separate;
- metadata is immutable and lifecycle mutation is user-controlled;
- stale revisions, read-only state, malformed records, and database failures fail closed;
- failed audit writes roll back record and state revision;
- state-package export and import preserve origin records and graph links;
- older packages may omit IMP-019 records;
- no model, network, adapter, new schema, migration, dependency, or custom cryptography is required.
