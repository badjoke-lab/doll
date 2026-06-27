# IMP-051 — Canonical local conversation execution

## Status

Complete in code. Full CI passes on Linux, macOS, and Windows with synthetic runtime adapters. No real runtime or model is connected, and no real-machine inference claim is made.

## Turn flow and trust boundary

`LocalConversationService` performs one bounded non-streaming turn. It accepts an existing canonical conversation, one explicit binding scope, a user message, an operation ID, optional parent and context record IDs, and bounded output, timeout, cancellation, and sensitivity settings.

The user instruction is created and authorized outside the model. The model receives only a deterministic transient request. It receives no repository, artifact service, permission store, project service, capability broker, secret store, credential, or private absolute path. The only runtime operation invoked is `LocalRuntimeBoundary.generate`.

## Binding and adapter validation

Before any runtime call, the service resolves exactly one active `ModelBindingRecord` for the requested scope and revalidates the bound runtime and model manifest identities and exact revisions. Both manifests must remain active and verified, and the runtime must remain local-only.

The registered adapter declaration must match the authoritative runtime manifest identity, version, runtime class, connection kind, operation set, offline declaration, cloud-fallback declaration, automatic-download declaration, and declaration fingerprint. Missing, stale, incompatible, quarantined, unavailable, or mismatched state fails closed. There is no automatic model selection, switching, or fallback in this slice.

## Prompt context and secret handling

Each turn creates an immutable `current_user_instruction` record for the user message. Explicitly selected additional records are packaged through `PromptDefenseService`, preserving system policy, current user instruction, durable user policy, user management action, untrusted content, model proposal, and unknown-origin channels.

Untrusted content retains data-only treatment. Prompt-injection findings remain findings rather than authority. Secret-bearing context follows the accepted redaction or denial policy. The rendered request is deterministic, bounded, and free of provider-native authority.

## Canonical persistence

A committed turn contains:

- a managed user-message artifact and `user_message` event;
- a bounded managed context-snapshot artifact and `system_context_snapshot` event;
- either a managed assistant artifact and `assistant_message` event, or a bounded terminal `error` event;
- exact binding, runtime manifest, model manifest, adapter, operation, parent, and content-reference attribution.

Completed runtime text is also stored as an immutable `runtime_output` instruction-origin record. It is data-only and cannot automatically become an instruction, durable policy, confirmation, permission, memory, decision, completed work item, approved procedure, confirmed checkpoint, or capability request.

## Failure, cancellation, rollback, and idempotency

Missing or invalid binding state, adapter mismatch, invalid parent linkage, duplicate context, prompt-size overflow, read-only state, and invalid constructor input fail before an authoritative model result is committed.

Closed runtime failure, cancellation, timeout, resource limit, malformed output, empty output, oversized output, or secret-bearing output does not create an assistant message. It produces a bounded normalized failure and, after the user and context records are accepted, a canonical error event without provider detail or partial model text.

Operation IDs are unique across turn origins, artifacts, and events. Reusing a committed or started operation ID is rejected. If artifact publication, state persistence, or audit completion fails, newly created turn records and managed files are rolled back. Cleanup failure is surfaced as a separate bounded rollback error.

## State, package, backup, and privacy effects

No new authoritative record type is introduced. Schema version 3 and State Package v2 remain unchanged. Existing conversation events, artifacts, instruction-origin records, backup, restore, and fresh-process inspection cover the new turn data.

Public result objects, audit metadata, errors, and context snapshots expose stable identifiers, revisions, hashes, counts, outcomes, and normalized failure codes only. They do not expose prompt text, user text, model output, provider bodies, exception text, credentials, host data, or private paths.

## Validation evidence

CI uses injected fake adapters and deterministic fixtures. It performs no real network request, runtime process launch, model download, runtime installation, cloud request, or credential retrieval. Coverage includes successful persistence, deterministic prompt rendering, exact binding and adapter matching, non-authoritative context, secret handling, prompt-injection findings, completed and closed runtime outcomes, graph relationships, managed artifacts, duplicate operation rejection, parent validation, rollback, read-only state, and static dependency guards.

## Deliberate limitations and next boundary

This slice does not add streaming user-visible output, automatic selection, explicit switching, fallback execution, tools, capabilities, permission or confirmation flows, durable memory publication, project mutation, cloud providers, runtime installation, model download, or real Ollama evidence.

The next bounded Phase 5 work is explicit user-controlled model switching and local fallback execution with smoke-test rollback and no unrelated state rewrite. Streaming integration follows only after the non-streaming canonical event and artifact path remains the committed source of truth. The network-disabled real-runtime drill remains required before any local-inference release claim.

## Issue

Closes #158.
