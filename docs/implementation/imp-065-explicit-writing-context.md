# IMP-065 — Explicit memory and project context selection

## Status

Implemented with deterministic synthetic acceptance; merge and cross-platform CI remain required.

## Objective

Extend the accepted local `draft`, `revise`, and `summarize` workflow with explicit user-selected confirmed-memory and ProjectRecord context without turning durable state into task authority.

## Accepted basis

IMP-065 composes the existing contracts established by:

- confirmed-memory records and user-only authoritative mutation;
- ProjectRecord v1 and v2 continuity;
- immutable instruction origins and authority classification;
- prompt-defense channel separation;
- canonical local conversation persistence;
- IMP-063 bounded local writing;
- IMP-064 accepted primary Intel Mac local-writing evidence.

It does not add a schema migration, State Package version, authoritative record type, runtime adapter, model binding type, capability, credential, provider, cloud path, or network behavior.

## Explicit selection boundary

The caller may supply ordered confirmed-memory IDs and ProjectRecord IDs for one writing turn.

Selection is explicit. IMP-065 performs no search, ranking, embedding, semantic retrieval, background lookup, model-selected lookup, or automatic context expansion.

Before any context instruction origin is created, the implementation validates:

- the configured memory, project, total-item, and aggregate-character limits;
- duplicate-free ordered selections;
- record existence and record type;
- active lifecycle state;
- supported ProjectRecord schema;
- non-secret sensitivity.

Missing, wrong-type, archived, duplicate, secret, oversized, or over-limit selections fail before runtime execution and before selected-context materialization.

## Snapshot representation

Each accepted record is serialized into one deterministic snapshot.

A confirmed-memory snapshot contains only its record ID, revision, subject, content, validity window, and confidence.

A project snapshot contains only its record ID, revision, schema version, name, description, project status, dates, and, for ProjectRecord v2, its explicit objective, in-scope items, out-of-scope items, and success criteria.

Linked memories, decisions, artifacts, policies, work items, procedures, checkpoints, and Resume Bundles are not expanded automatically.

## Authority and prompt boundary

Each selected snapshot becomes an immutable instruction-origin record with:

- `origin_class = external_content`;
- `actor_type = retriever`;
- `acquisition_method = retrieval`;
- `authority_class = untrusted_data`;
- `data_only = true`.

The current user request remains the only `task_instruction` authority.

Selected memory and project snapshots reach the runtime only through `untrusted_content`. Embedded instructions remain reference data, cannot authorize the task, and remain visible to advisory prompt-injection detection.

Selected records cannot mutate policy, permission, capability, credential, confirmed memory, project state, work completion, procedure approval, checkpoint confirmation, or model binding state.

## Sensitivity

Secret-classified confirmed-memory and project records are rejected rather than inserted into a prompt.

For accepted non-secret records, the canonical writing turn uses at least the highest sensitivity among the caller-requested turn sensitivity and the selected records. Context therefore cannot be persisted at a lower sensitivity than its authoritative source.

## Result privacy

The bounded result may contain selected instruction-origin IDs, selected authoritative record IDs, revisions, counts, aggregate character count, canonical event IDs, manifest IDs, outcome, failure code, and prompt-defense counts.

It excludes selected subjects, memory content, project names, descriptions, objectives, generated text, native model names, paths, usernames, hostnames, credentials, and secret values.

## Failure behavior

Invalid selection fails before runtime execution and before selected-context materialization.

Runtime failure preserves the existing canonical user/context/error graph. Confirmed-memory and ProjectRecord revisions remain unchanged. Created data-only snapshot origins remain auditable preparation records and do not alter authoritative state.

Existing IMP-063 callers that select no context continue through the same source-text and canonical local-conversation path.

## Verification

Synthetic acceptance covers:

- explicit confirmed-memory and ProjectRecord v2 selection;
- deterministic snapshot rendering;
- data-only `untrusted_content` placement;
- denial of task authority;
- hostile embedded instruction visibility;
- missing, wrong-type, archived, duplicate, secret, and over-limit rejection before runtime;
- runtime failure with authoritative revision preservation;
- content-free results;
- unchanged no-selection behavior through existing IMP-063 and IMP-064 tests.

Standard CI must pass on Ubuntu, macOS, and Windows.

## Non-claims

IMP-065 does not establish automatic or semantic retrieval, embeddings, vector search, ranking, model-selected context, decision context, Resume Bundle context, translation, attachments, multimodal input, streaming workflow output, tools, capability execution, cloud portability or fallback, target-specific export, complete Phase 6, or stable general anti-lock-in.
