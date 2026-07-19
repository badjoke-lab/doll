# IMP-067 — Explicit Resume Bundle writing context

## Status

Implementation in progress with deterministic synthetic acceptance required before merge.

## Objective

Extend the accepted local `draft`, `revise`, and `summarize` workflow with one explicitly selected external Resume Bundle without importing it into canonical state or turning portable project material into task authority.

## Accepted basis

IMP-067 composes the existing contracts established by:

- deterministic Resume Bundle v1 export and verification;
- immutable instruction origins and authority classification;
- prompt-defense channel separation;
- canonical local conversation persistence;
- IMP-063 bounded local writing;
- IMP-064 accepted primary Intel Mac local-writing evidence;
- IMP-065 explicit confirmed-memory and ProjectRecord context selection;
- IMP-066 explicit DecisionRecord context selection.

It does not add a schema migration, State Package version, Resume Bundle format, authoritative record type, runtime adapter, model binding type, capability, credential, provider, cloud path, or network behavior.

## Explicit external selection boundary

The caller may supply at most one Resume Bundle path for one writing turn.

Selection is explicit. IMP-067 performs no file search, directory scan, workspace discovery, semantic retrieval, ranking, embedding, background lookup, or model-selected lookup.

Before any instruction-origin record is created, the implementation validates:

- the selected path refers to one regular non-symlink file;
- the bundle passes the existing Resume Bundle v1 inventory, member-path, checksum, format, identity, count, and size verification;
- the extracted snapshot passes secret detection without truncation or finding-limit exhaustion;
- the shared selected-context item and character limits remain satisfied.

Invalid, tampered, unsupported, unsafe, unreadable, oversized, or secret-bearing bundles fail before runtime execution and before context materialization.

## Snapshot representation

One accepted Resume Bundle becomes one deterministic snapshot containing only:

- bundle format version;
- project ID;
- generated-from workspace ID and state revision;
- checkpoint ID and freshness;
- included and omitted record counts;
- project data;
- checkpoint data;
- active, next, and blocked work items;
- decisions;
- procedures;
- governing policies;
- pending validation requirements.

`HANDOFF.md`, checksum rows, artifact-reference rows, source-reference rows, artifact bytes, external source content, and linked-record expansion are excluded.

The snapshot is revision-pinned by the bundle SHA-256 and source state revision. Native file paths are not persisted in workflow results or source identifiers.

## Authority and prompt boundary

The selected snapshot becomes one immutable instruction-origin record with:

- `origin_class = external_content`;
- `actor_type = extractor`;
- `acquisition_method = extraction`;
- `authority_class = untrusted_data`;
- `data_only = true`.

The current user request remains the only `task_instruction` authority.

The snapshot reaches the runtime only through `untrusted_content`. Embedded instructions remain reference data and cannot authorize work, confirm checkpoints, accept decisions, mutate project state, create work items, approve procedures, modify policy, select model bindings, retrieve credentials, or execute capabilities.

## Sensitivity and failure preservation

The canonical writing turn sensitivity is never lower than `sensitive` when a Resume Bundle is selected. Secret-bearing extracted content is rejected rather than inserted into prompts.

Runtime failure preserves the external bundle bytes and canonical state. IMP-067 does not import, publish, rewrite, move, delete, or rename the selected bundle.

Existing no-bundle, memory-only, project-only, decision-only, combined selected-record, and source-text callers remain compatible.

## Content-free result

The workflow result adds only:

- selected Resume Bundle project ID;
- generated-from state revision;
- bundle SHA-256;
- included member-group count;
- snapshot character count.

It does not expose bundle content, native paths, generated text, model names, usernames, hostnames, credentials, or secret values.

## Acceptance

Dedicated synthetic acceptance must cover:

- explicit verified Resume Bundle selection in all three writing modes;
- deterministic core-member snapshot construction;
- data-only placement and task-authority denial;
- hostile embedded instruction visibility;
- exclusion of HANDOFF, checksum, artifact-reference, and source-reference content;
- invalid, tampered, symlink, oversized, unsupported, and secret-bearing rejection before runtime and origin creation;
- aggregate item and character-limit rejection;
- external bundle and canonical state preservation on runtime failure;
- content-free, path-free workflow results;
- compatibility with existing memory, project, and decision selection;
- standard Ubuntu, macOS, and Windows CI.

## Non-claims

IMP-067 does not establish Resume Bundle import into canonical state, shutdown escape import, automatic or semantic retrieval, embeddings, vector search, ranking, translation, attachments, multimodal input, streaming workflow output, tools, capability execution, cloud portability or fallback, target-specific export, complete Phase 6, or stable general anti-lock-in.
