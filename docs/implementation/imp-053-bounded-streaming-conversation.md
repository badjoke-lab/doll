# IMP-053 — Bounded local streaming conversation path

## Status

Complete in code with synthetic runtime adapters. No real runtime, real model, user-side offline test, runtime installation, model download, browser or desktop live-rendering transport, cloud request, credential retrieval, tool execution, or capability execution is part of this implementation.

## Purpose

IMP-053 connects the accepted bounded `LocalRuntimeBoundary.stream` transcript to canonical local conversation persistence without allowing partial model output to become Doll State.

The stream is a transient presentation result. The authoritative conversation remains the same model-independent user message, system context snapshot, and completed assistant message or bounded error event introduced by IMP-051.

## Execution boundary

`LocalStreamingConversationService.execute_streaming_turn` follows the same pre-execution controls as the non-streaming path:

1. require a writable repository and an unused operation ID;
2. validate the conversation and optional parent event;
3. resolve exactly one active binding in the requested scope;
4. revalidate the exact runtime and model manifest revisions;
5. verify that the registered local adapter declaration matches the authoritative runtime manifest;
6. create the current user instruction outside the model;
7. package selected context through the accepted authority, prompt-injection, and secret controls;
8. render the same deterministic local-conversation input;
9. call only `LocalRuntimeBoundary.stream` with explicit output and timeout bounds.

The service does not inspect runtime inventory, select another model, activate a fallback, install a runtime, launch a process, download a model, request a cloud provider, retrieve a credential, execute a tool, or mutate project state.

## Transient stream result

The returned `LocalStreamingConversationResult` contains the canonical `LocalConversationResult` plus a bounded tuple of validated `RuntimeStreamEvent` values. The event tuple is excluded from object representation so streamed text is not exposed accidentally through logs or diagnostics.

The transcript is returned for presentation only. It is not saved as a record, artifact, conversation event, instruction-origin record, memory item, project record, audit value, capability request, or provider-native object.

IMP-053 does not add a browser, terminal, desktop, socket, or callback delivery transport. A future interface may present these bounded events, but the interface must not redefine the canonical conversation result.

## Canonical completion

A completed stream is accepted only when:

- operation, adapter, and model identities match the request;
- the bounded transcript has a valid terminal completion event;
- the combined delta text is non-blank;
- the combined text passes the existing bounded secret and private-path scan.

Only after those checks does the service create one immutable data-only runtime-output instruction origin and call the existing IMP-051 canonical persistence path. The resulting state contains exactly one user artifact and event, one context-snapshot artifact and event, and one assistant artifact and event.

The model output remains untrusted data. It cannot become policy, permission, confirmation, memory, fact, decision, completed work, checkpoint, project mutation, capability request, or tool result automatically.

## Failure, cancellation, timeout, and rejection

Failed, cancelled, timed-out, malformed, identity-mismatched, blank, resource-limited, or secret-bearing stream results create no assistant artifact, assistant event, or runtime-output instruction-origin record.

The canonical path records the user message, context snapshot, and one bounded error event with normalized outcome and failure code. Partial deltas may remain in the transient presentation result when they contain no detected secret or private path, but they are never persisted.

When combined streamed text contains a detected secret, personal identifier, or private path, the service converts the result to `invalid_response` and replaces the returned presentation transcript with a synthetic start and bounded error event. The rejected text is not returned or stored by this service.

## Rollback and duplicate operations

The streaming service reuses the IMP-051 operation reservation, artifact creation, event ordering, and rollback implementation. Duplicate operation IDs fail before runtime execution.

If canonical persistence fails, every record and managed file created by the attempted turn is removed. If cleanup itself cannot complete, the service raises `LocalConversationRollbackError` instead of reporting a successful or partially successful turn.

## State, package, and continuity effects

IMP-053 introduces no authoritative record type and no schema migration. Schema version 3 and State Package v2 remain unchanged.

Because only the existing canonical conversation, artifact, instruction-origin, and audit records are used, backup, restore, package transfer, and fresh-process behavior remain unchanged. Runtime-private stream objects and partial deltas are not required to inspect or recover the canonical conversation later.

## Validation boundary

Tests use deterministic injected adapters only. They cover completed multi-delta output, exact canonical event and artifact persistence, data-only runtime origin, transient partial output on failure, cancellation, timeout, resource limit, pre-cancellation, blank completion, malformed event ordering, secret-bearing output sanitization, adapter declaration mismatch, duplicate operation rejection, read-only state, boundary contract errors, persistence rollback, rollback failure, prompt bounds, identity mismatch, result representation privacy, and static absence of network, process, cloud, credential, tool, and capability dependencies.

CI performs no real network request, runtime process launch, runtime installation, model download, cloud request, or credential retrieval. No user-side local or offline action is required for IMP-053.

## Deliberate limitations and next boundary

IMP-053 does not prove live incremental UI delivery and does not prove real Ollama or real-model streaming. It integrates the bounded stream transcript into the canonical conversation boundary while keeping partial output non-authoritative and non-persistent.

The remaining Phase 5 work is the network-disabled real-runtime continuity drill: real local startup, local conversation, streamed and non-streamed execution where supported, explicit model replacement and rollback, state preservation, outbound-request guarding, and primary-machine evidence.

## Issue

Closes #166.
