# IMP-018 — Claim, Evidence, and Trust Model

## Status

Phase 3 implementation following IMP-017.

## Purpose

IMP-018 establishes a model-independent truth-status boundary for Doll State.

The implementation keeps these concepts separate:

- confirmed fact;
- claim;
- evidence;
- inference;
- trust assessment.

A high-confidence model proposal, imported statement, tool result, runtime output, repeated assertion, local process result, or structured JSON object does not become a confirmed fact merely because it appears plausible or well formed.

## Confirmed facts

The existing `ConfirmedMemoryService` remains the authoritative confirmed-fact path.

Confirmed memories:

- are created or accepted only through the existing trusted user-controlled mutation path;
- retain their existing audit, provenance, history, revision, archive, export, backup, and restore behavior;
- are not created by the IMP-018 claim, evidence, inference, or trust APIs;
- are not created automatically from imported content, tool output, runtime output, model proposals, evidence, inferences, confidence values, or trust assessments.

IMP-018 deliberately does not add a `promote_to_fact` operation. A later trusted management interface may explicitly copy reviewed information into a confirmed memory, but it must use the confirmed-memory contract and preserve the source history. No untrusted record can promote itself.

## New record types

IMP-018 adds four ordinary Doll State record types using the existing generic record envelope and records table:

- `claim`;
- `evidence`;
- `inference`;
- `trust_assessment`.

All use schema version 1 and the existing active or archived lifecycle.

No database migration or new table is required.

### Claim

A claim is an assertion that may be true or false.

A claim retains:

- title;
- statement;
- optional confidence;
- optional uncertainty;
- review state and review provenance;
- source and creator provenance;
- common record revision, status, provenance, sensitivity, and timestamps.

A claim remains a claim after review. Review does not make it a confirmed fact.

### Evidence

Evidence is a source, observation, record, or artifact that bears on one or more claims.

Evidence relations are explicit and disjoint:

- supports a claim;
- contradicts a claim;
- contextualizes a claim.

Every evidence record must link to at least one existing claim. One claim ID cannot occupy more than one relation class in the same evidence record.

Evidence also retains source provenance, optional confidence, optional uncertainty, and review state. Evidence confidence describes the recorded assessment of the evidence item; it is not a trust decision and it does not confirm the linked claim.

### Inference

An inference is a derived conclusion.

Every inference retains:

- conclusion;
- derivation method;
- at least one linked claim or evidence record;
- source and actor provenance;
- optional confidence;
- optional uncertainty;
- review state.

An inference with confidence `1.0` remains an inference. It cannot become a confirmed fact or trusted source automatically.

### Trust assessment

A trust assessment is an explicit decision about one subject.

Supported subjects are:

- claim;
- evidence;
- inference;
- confirmed fact;
- source identifier.

Supported trust levels are:

- `unknown`;
- `distrusted`;
- `limited`;
- `trusted`.

A trust assessment retains:

- subject type and ID;
- trust level;
- reason;
- assessor type;
- optional policy reference;
- linked evidence IDs;
- common record history.

Trust is separate from confidence, truth status, review state, and instruction authority.

A trusted claim is still a claim. A distrusted confirmed fact remains a confirmed-fact record until the user revises or supersedes it through the confirmed-memory path. IMP-018 does not silently rewrite either record.

## Provenance model

`TruthSource` provides explicit provenance for claims, evidence, and inferences.

It retains where applicable:

- origin type;
- creator actor type;
- source identifier;
- observation time;
- SHA-256 content hash;
- transformation or extraction method;
- model manifest ID;
- runtime adapter ID;
- session ID;
- origin operation ID.

Missing optional provenance remains `null`. The implementation does not invent source IDs, times, hashes, models, runtimes, sessions, or methods.

### Origin classes

The initial closed origin set is:

- `user_statement`;
- `imported_content`;
- `external_source`;
- `tool_result`;
- `runtime_output`;
- `model_proposal`;
- `system_observation`;
- `migrated`;
- `restored`;
- `unknown`.

### Creator actors

The initial closed creator set is:

- `user`;
- `model`;
- `runtime`;
- `tool`;
- `system`;
- `importer`;
- `migration`.

Origin and actor combinations are validated. Examples:

- `user_statement` requires a user creator;
- `imported_content` requires an importer, source identifier, and origin operation;
- `tool_result` requires a tool, source identifier, and origin operation;
- `runtime_output` requires a runtime adapter and origin operation;
- `model_proposal` requires model, runtime, session, and operation provenance;
- `system_observation` requires a system creator;
- `migrated` requires a migration creator;
- `restored` requires a system creator.

Unknown origin remains accepted only as the least-informative data classification. It does not grant authority or trust.

## Common record provenance

The common record envelope remains consistent with the explicit source:

- user source → `user-created`;
- imported source → `imported`;
- model proposal → `model-proposed`;
- runtime, tool, or system source → `system-generated`;
- migration → `migrated`;
- restore → `restored`.

Stored records whose common provenance conflicts with their source provenance are treated as malformed.

## Review state

Claims, evidence, and inferences use a closed review-state set:

- `unreviewed`;
- `reviewed`;
- `disputed`;
- `rejected`.

Non-user actors may create only `unreviewed` records and cannot attach review notes.

Only the trusted user-controlled path may change review state. A reviewed state records:

- review time;
- reviewer actor `user`;
- optional review note.

Review mutation uses optimistic revision checking and cannot modify archived records.

Review is not confirmation. It does not change the record type or create a confirmed memory.

## Trust authority

Trust assessment is restricted to:

- the trusted user path;
- a system path bound to an explicit policy reference.

Models, runtimes, tools, imported content, and migrations cannot assess trust through this service.

A system assessment without a policy reference fails closed.

IMP-018 does not infer trust from:

- local execution;
- open-source status;
- popularity;
- repetition;
- model confidence;
- review state;
- signed-in status;
- official appearance;
- structured output;
- successful tool execution.

## Validation and links

All record IDs use canonical UUID form except source trust subjects, which use bounded non-secret identifiers.

Typed links are checked before writes:

- evidence relations target claims;
- inference claim links target claims;
- inference evidence links target evidence;
- trust evidence links target evidence;
- trust subjects target the declared record type;
- confirmed-fact trust subjects target valid confirmed-memory records.

Duplicate IDs, missing records, wrong record types, overlapping evidence relations, malformed source metadata, invalid confidence, non-finite values, invalid timestamps, unsafe text, local absolute paths, credential-like values, and unsupported enums fail closed.

## Transactions and audit

Each create, review, or archive operation uses one SQLite transaction containing:

1. the record mutation;
2. the secret-safe audit event;
3. the authoritative state-revision increment.

If any part fails, the record mutation, audit event, and state-revision change roll back together.

Audit events are limited to non-secret summaries such as:

- truth record kind;
- origin type;
- review state;
- whether confidence, uncertainty, source ID, or source hash is present;
- relation counts;
- trust subject type, level, assessor, evidence count, and policy-reference presence.

Claim text, evidence summaries, inference conclusions, trust reasons, review notes, source identifiers, hashes, and other free text are not copied into audit metadata.

## State-package, backup, restore, and transfer

The state package adds optional JSONL members:

- `records/claims.jsonl`;
- `records/evidence.jsonl`;
- `records/inferences.jsonl`;
- `records/trust-assessments.jsonl`.

They are optional during package reading so packages created before IMP-018 remain valid.

New exports include the members and preserve typed cross-record links. Import verification checks link targets and rejects missing or wrong-type references before publishing the imported workspace.

Because the records use the existing generic records table, existing state-package, backup, restore, revision, and checksum machinery carries them without a database migration.

The existing ordinary-state secret policy applies. IMP-018 does not create a secret-value storage path.

## Model and untrusted-content boundary

This implementation is model-independent.

It includes no:

- model runtime;
- prompt construction;
- model call;
- retrieval adapter;
- web request;
- OCR engine;
- import adapter;
- provider integration;
- real tool execution;
- automatic extraction;
- automatic truth scoring;
- automatic source reputation;
- model-based verification;
- automatic fact promotion.

Synthetic actor and source records exercise the boundary without giving those actors runtime authority.

Instruction authority remains outside this implementation and is handled by IMP-019. Prompt-injection handling remains IMP-020. Capability and confirmation enforcement remain IMP-021 and IMP-022.

## Platform and dependency effects

- macOS, Windows, Linux: SQLite and pure-Python contract behavior only.
- Dependencies: no new dependency.
- Network: none.
- Model execution: none.
- Filesystem: only existing state-package behavior.
- Database schema: unchanged.
- Migration: none.
- State-package format version: unchanged; new typed members are optional for backward compatibility.
- Custom cryptography: none; optional source hashes are validated SHA-256 identifiers, not generated trust proofs.

## Acceptance evidence

Permanent synthetic tests prove:

- model and imported claims remain unreviewed and non-authoritative;
- confidence `1.0` does not create trust or confirmed facts;
- only the confirmed-memory path creates confirmed facts;
- evidence relations are typed, existing, and disjoint;
- inferences require linked claims or evidence;
- non-user self-review is denied;
- user review preserves record type and source provenance;
- trust assessment is explicit and actor restricted;
- system trust requires an explicit policy reference;
- missing provenance remains visible;
- malformed and hostile records fail closed;
- stale revisions and archived mutation are denied;
- failed audit writes roll back records and state revision;
- package export and import preserve the truth graph;
- prior packages may omit IMP-018 members;
- no model, network, provider, new schema, migration, secret-value path, or custom cryptography is required.
