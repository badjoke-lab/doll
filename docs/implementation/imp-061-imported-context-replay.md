# IMP-061 — Bounded imported conversation context replay

## Status

Implementation slice for replaying an explicit bounded subset of already-published imported canonical conversation events through the existing approved local conversation and runtime boundary.

Synthetic acceptance is required on Linux, macOS, and Windows. This implementation does not by itself add new primary real-machine evidence or expand the complete Phase 6 claim.

## Motivation

IMP-055 through IMP-057 proved that a caller-controlled local session can be captured, imported canonically, transferred, restored, and inspected without the original capture component in the execution path. The remaining practical continuity step is to make selected imported text usable as context for a new local turn through an approved target runtime while preserving the Phase 3 and IMP-019 authority boundaries.

IMP-061 adds only this replay boundary.

## Boundary

The path is:

```text
explicit imported canonical conversation ID
        ↓
explicit ordered canonical event-ID selection
        ↓
validate imported provenance, conversation ownership, event kind, and active status
        ↓
resolve imported-source mapping
        ↓
validate mapping-to-canonical identity and external-data authority
        ↓
extract bounded preserved source text
        ↓
create data-only imported-data instruction origins
        ↓
PromptDefenseService packages them as untrusted_content
        ↓
LocalConversationService resolves one explicit active local binding
        ↓
LocalRuntimeBoundary executes the target runtime request
        ↓
existing canonical local turn persistence and failure semantics
```

The implementation performs no automatic context selection, semantic search, embedding generation, ranking, summarization, source-application discovery, attachment-byte recovery, tool execution, model installation, runtime installation, process launch, cloud request, or automatic fallback.

## Selection contract

The caller supplies:

- one imported canonical source conversation ID;
- one distinct target canonical conversation ID;
- a non-empty ordered event-ID sequence;
- one explicit target binding scope type and key;
- one current user instruction and operation ID.

The first implementation accepts at most 32 selected events. Each selected item is limited to 16,000 characters and the complete selected context is limited to 65,536 characters.

Selections fail closed when:

- the source and target conversation IDs are the same;
- the source conversation is not an active imported canonical conversation;
- an event is missing, inactive, duplicated, non-imported, or belongs to another conversation;
- an event does not use `origin_class = imported_data`;
- an event kind is outside the supported text replay set;
- an imported-source mapping is missing or does not point back to the selected canonical event;
- mapping authority is not `external_data`;
- source-environment linkage conflicts;
- the preserved source payload has no supported non-blank text field;
- item-count or character bounds are exceeded.

Supported replay event kinds are:

- `user_message`;
- `assistant_message`;
- `system_context_snapshot`.

## Authority contract

Re-materialized replay context uses the existing IMP-019 imported-data origin contract:

- `origin_class = imported_data`;
- `actor_type = importer`;
- `acquisition_method = import`;
- `data_only = true`;
- effective authority class `untrusted_data`.

Imported context therefore cannot authorize a task instruction or create policy, permission, capability, credential, confirmed memory, trusted fact, project state, work completion, procedure approval, checkpoint confirmation, or model binding.

Prompt-injection findings remain advisory. Secret detection and redaction use the existing PromptDefenseService path. Neither finding detection nor successful target-runtime output promotes imported context authority.

## Target runtime separation

The synthetic integration scenario uses a source environment whose preserved runtime metadata identifies the accepted local Ollama source path and a distinct synthetic target local runtime adapter.

The target runtime and model are resolved only through the existing active binding contract. Source-native model or runtime identifiers remain imported metadata and cannot select the target execution path.

The local turn path remains unchanged:

- current user instruction is authoritative only for the current task;
- replayed imported context enters only `untrusted_content`;
- runtime output remains data-only;
- successful output persists through the canonical user/context/assistant event graph;
- runtime failure uses the existing user/context/error event graph and creates no assistant event.

## State effects

IMP-061 adds no schema migration, State Package version change, or new authoritative conversation or project record type.

Source mappings remain the provenance source of truth for replayed imported content. Replay materialization creates immutable data-only instruction-origin records using the existing instruction-origin contract and audit behavior. Canonical target turns continue to use the existing LocalConversationService persistence and rollback semantics.

## Acceptance

Synthetic acceptance covers:

1. explicit imported text selection and deterministic mapping resolution;
2. replay through a distinct approved synthetic local target runtime;
3. imported context appearing only in the `untrusted_content` channel;
4. imported-data authority decisions remaining denied for task authority;
5. prompt-injection findings without authority promotion;
6. cross-conversation selection rejection;
7. non-imported event rejection;
8. duplicate selection rejection;
9. unsupported event-kind rejection;
10. missing and mismatched source-mapping rejection;
11. event-count, per-item, and total-character limits;
12. inactive and missing state rejection;
13. source/target conversation validation;
14. malformed source-payload rejection;
15. runtime failure preserving the existing error-event contract with no assistant event;
16. Linux, macOS, and Windows dedicated acceptance.

## Non-claims

IMP-061 does not establish:

- automatic or semantic retrieval;
- embeddings or vector search;
- automatic context ranking;
- attachment-byte or multimodal replay;
- tool-call or capability execution;
- native application history discovery;
- target-specific export;
- provider round-trip fidelity;
- cloud portability;
- automatic cloud fallback;
- model or runtime installation;
- full application replacement;
- the complete Phase 6 gate;
- stable general anti-lock-in.

Any broader PORT-013 real-machine claim must be bound separately to an exact implementation commit and accepted primary-machine evidence. IMP-061 itself provides only the bounded implementation and synthetic acceptance layer for cross-runtime imported-context replay.
