# IMP-066 — Explicit decision context selection

## Status

Completed and merged at `e72a56b426ed629cc1c94f478e3a54025c3e3ad1` from implementation head `4d70018be0935adcde593de7d5d14cff00c46800` after deterministic synthetic acceptance and standard CI passed on Ubuntu, macOS, and Windows. This remains a CI-only extension and does not broaden the accepted IMP-064 primary Intel Mac real-machine evidence.

## Objective

Extend the accepted local `draft`, `revise`, and `summarize` workflow with explicit user-selected DecisionRecord context without turning durable decisions into task authority or mutable model state.

## Accepted basis

IMP-066 composes the existing contracts established by:

- user-authoritative DecisionRecord creation, update, and archive;
- immutable instruction origins and authority classification;
- prompt-defense channel separation;
- canonical local conversation persistence;
- IMP-063 bounded local writing;
- IMP-064 accepted primary Intel Mac local-writing evidence;
- IMP-065 explicit confirmed-memory and ProjectRecord context selection.

It does not add a schema migration, State Package version, authoritative record type, runtime adapter, model binding type, capability, credential, provider, cloud path, or network behavior.

## Explicit selection boundary

The caller may supply ordered DecisionRecord IDs for one writing turn.

Selection is explicit. IMP-066 performs no search, ranking, embedding, semantic retrieval, background lookup, model-selected lookup, or automatic context expansion.

Before any decision-context origin is created, the implementation validates:

- the configured decision and total-item limits;
- duplicate-free ordered selections;
- record existence and DecisionRecord type;
- active lifecycle state;
- non-secret sensitivity;
- aggregate selected-context character limits shared with IMP-065.

Missing, wrong-type, archived, duplicate, secret, oversized, or over-limit selections fail before runtime execution and before decision-context materialization.

## Snapshot representation

Each accepted DecisionRecord is serialized into one deterministic revision-pinned snapshot containing only:

- record ID and revision;
- decision text and reason;
- decision status and decided-at timestamp;
- alternatives and constraints;
- review-after timestamp;
- supersedes ID;
- project ID.

Linked memories, artifacts, superseded decisions, and projects are not expanded automatically.

Accepted, superseded, and reversed decision statuses may all be selected when the underlying record remains active. The snapshot preserves the status as reference data and cannot change it.

## Authority and prompt boundary

Each selected decision snapshot becomes an immutable instruction-origin record with:

- `origin_class = external_content`;
- `actor_type = retriever`;
- `acquisition_method = retrieval`;
- `authority_class = untrusted_data`;
- `data_only = true`.

The current user request remains the only `task_instruction` authority.

Selected decisions reach the runtime only through `untrusted_content`. Embedded instructions remain reference data, cannot authorize the task, and remain visible to advisory prompt-injection detection.

Selected decisions cannot accept, reverse, supersede, archive, or update decisions; mutate project state; complete work; approve procedures; confirm checkpoints; change permissions; select a model binding; retrieve credentials; or execute capabilities.

## Sensitivity and failure preservation

The canonical writing turn sensitivity is never lower than the highest selected record sensitivity. Secret DecisionRecords are rejected rather than inserted into prompts.

Runtime failure uses the unchanged canonical user/context/error graph and preserves every selected DecisionRecord revision.

Existing no-selection, memory-only, project-only, and combined memory/project callers remain compatible.

## Content-free result

The workflow result adds only:

- selected DecisionRecord IDs;
- selected DecisionRecord revisions.

It does not expose decision text, reason, alternatives, constraints, generated text, native model names, paths, usernames, hostnames, credentials, or secret values.

## Acceptance

Dedicated synthetic acceptance covers:

- explicit DecisionRecord selection in the local writing path;
- deterministic snapshot fields;
- data-only placement and task-authority denial;
- hostile embedded instruction visibility;
- archived, missing, wrong-type, duplicate, secret, and over-limit rejection before runtime and origin creation;
- DecisionRecord revision preservation on runtime failure;
- content-free workflow results;
- compatibility with existing confirmed-memory and ProjectRecord selection;
- standard Ubuntu, macOS, and Windows CI.

## Non-claims

IMP-066 does not establish Resume Bundle context, automatic or semantic retrieval, embeddings, vector search, ranking, model-selected context, translation, attachments, multimodal input, streaming workflow output, tools, capability execution, cloud portability or fallback, target-specific export, complete Phase 6, or stable general anti-lock-in.
