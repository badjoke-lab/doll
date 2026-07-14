# IMP-063 — Bounded local writing workflow

## Status

Implementation in progress with deterministic synthetic CI evidence required.

Issue: #204

## Objective

Provide the first bounded Phase 6 daily-use workflow above the accepted local runtime and canonical conversation path.

The workflow supports three explicit operations:

- `draft` creates original text from one current user request;
- `revise` revises one explicitly supplied source text;
- `summarize` summarizes one explicitly supplied source text.

## Authority boundary

The user request is rendered deterministically and passed to `LocalConversationService` as the current user instruction. It is the only instruction in the workflow that may authorize the task.

For `revise` and `summarize`, source text is persisted separately as an immutable `external_content` instruction origin. It therefore has `untrusted_data` authority, is data-only, and reaches the runtime only through `untrusted_content`.

The source text is never concatenated into the current user instruction. Any apparent instruction inside the source remains untrusted writing material and passes through the existing prompt-injection and secret controls.

## Canonical execution

The workflow delegates model execution and persistence to the unchanged non-streaming `LocalConversationService` contract.

A completed turn retains the accepted graph:

1. `user_message`;
2. `system_context_snapshot`;
3. `assistant_message`.

A failed, cancelled, or timed-out runtime turn retains the accepted user/context/error graph and creates no assistant content.

The workflow result contains only mode, counts, identifiers, outcome, failure code, prompt-injection finding count, and secret-redaction count. It does not include the request, source, generated response, model name, private path, username, hostname, credential, or secret value.

## Validation and limits

The workflow validates before runtime execution:

- mode is exactly `draft`, `revise`, or `summarize`;
- `draft` receives no source text;
- `revise` and `summarize` receive one non-blank source text;
- the request is at most 12,000 characters;
- the source is at most 16,000 characters;
- the target conversation exists and has event capacity;
- any selected parent belongs to the target conversation;
- an exact active local binding and matching adapter declaration exist;
- the turn operation ID is unused;
- the deterministic source-preparation operation ID is unused.

## State effects

IMP-063 adds no new authoritative record type, schema version, State Package version, runtime adapter, model manifest type, model binding type, permission path, credential path, capability path, or project-continuity record.

It creates only:

- one ordinary `external_content` instruction origin for `revise` or `summarize`;
- the existing current-user and runtime-output instruction origins;
- the existing canonical conversation events and managed artifacts;
- the existing local-conversation audit entry.

Imported, external, runtime, and model content cannot become policy, permission, capability, credential, confirmed memory, confirmed fact, project progress, work completion, procedure approval, checkpoint confirmation, or model binding through this workflow.

## Evidence

Synthetic integration tests cover:

- all three supported modes;
- deterministic task rendering;
- exact source-presence rules;
- source-channel separation;
- hostile source instructions remaining data-only;
- prompt-injection finding visibility;
- duplicate turn and source-preparation denial;
- request and source limits;
- canonical runtime failure persistence;
- content-free result shape;
- no increase in authority-bearing record categories.

The standard repository CI provides Ubuntu, macOS, and Windows evidence.

A separate exact-commit primary Intel Mac local-runtime drill may be scheduled after implementation merge. Until then, IMP-063 is not real-machine daily-use evidence.

## Non-claims

IMP-063 does not establish:

- translation;
- automatic or semantic retrieval;
- embeddings or vector search;
- confirmed-memory selection;
- project, decision, work-item, procedure, checkpoint, or Resume Bundle context selection;
- attachments or multimodal input;
- streaming workflow output;
- direct publication to arbitrary files;
- tool or capability execution;
- cloud providers or cloud fallback;
- target-specific export;
- native application history discovery;
- automatic background operation;
- completion of the Phase 6 gate;
- stable general anti-lock-in.
