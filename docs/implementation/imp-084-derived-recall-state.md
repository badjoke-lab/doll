# IMP-084 — Derived RecallState boundary

## Objective

Establish the first accepted post-IMP-083 adaptive-memory boundary by separating authoritative confirmed memory from ephemeral retrieval state.

IMP-084 does not make recall metadata authoritative. It proves that deterministic local recall can expose algorithm identity, authoritative memory revision bindings, source-state revision, lexical evidence, and result rank without writing to MemoryRecord or creating a persistent retrieval index.

## Implemented boundary

IMP-084 adds a read-only `derive_memory_recall_state` service over the existing IMP-073 local-search surface.

Each derived `RecallState` exposes:

- authoritative `memory_id`;
- authoritative `memory_revision`;
- source Doll State revision;
- recall algorithm identifier and version;
- one bounded lexical score;
- deterministic result rank.

The report also exposes the underlying accepted local-search mode, bounded scan metadata, and result count. It contains no timestamp, embedding, model output, prompt content, or persistent cache identifier, so identical authoritative input and algorithm selection can be regenerated deterministically.

## Recall algorithms

The first boundary supports two small deterministic local policies solely to prove algorithm replacement without rewriting memory:

- `local-search-order` version 1 preserves the accepted IMP-073 local-search ordering;
- `bounded-field-count-rerank` version 1 reranks only the already bounded IMP-073 result set by the number of returned matched fields, with deterministic source-rank and memory-ID tie breaking.

The second policy is not a semantic-retrieval claim and is not a general search-quality upgrade. It exists to make algorithm identity and replacement observable for MCON-002 while preserving the existing lexical search surface.

## Authority and storage

RecallState is derived and rebuildable.

IMP-084 creates no:

- new authoritative record type;
- SQLite schema or migration;
- persistent index, FTS table, vector database, embedding, cache, or usage counter;
- `MemoryRecord.last_recalled_at` or `MemoryRecord.recall_count` write;
- MemoryRecord content, confirmation, lifecycle, provenance, sensitivity, or revision mutation;
- automatic prompt or context injection;
- linked-record expansion;
- model, runtime, network, cloud, tool, capability, permission, or confirmation operation.

The service requires a caller-supplied read-only StateRepository and delegates candidate selection to the accepted active, non-secret IMP-073 search boundary with an exact `memory` record-type filter.

## Acceptance coverage

Synthetic acceptance covers the implemented portions of:

- **MCON-001** — derived recall can be discarded completely, a fresh read-only repository can regenerate equivalent output, authoritative memory remains inspectable, secret memory stays excluded, no recall-state record exists, and state/record revisions remain unchanged;
- **MCON-002** — two supported deterministic recall policies can produce different ranking while authoritative MemoryRecord content and revision and the workspace state revision remain unchanged.

A writable repository is rejected before derivation, and unsupported algorithm identifiers fail closed.

Standard CI provides Ubuntu, macOS, and Windows coverage.

## Non-claims

IMP-084 does not establish:

- persistent `MemoryUsageSignalRecord`;
- recall feedback or reinforcement;
- semantic search;
- embeddings or vector retrieval;
- a persistent lexical index;
- automatic or model-selected context;
- context-budget selection;
- memory consolidation;
- PAM, PLUR, or PROJECTMEM interoperability;
- ProjectExperienceRecord;
- ContinuityPreflight;
- MCP;
- cloud recall;
- broader Phase 6 completion or Lite v1.0 completion.

Those remain separate claim-specific slices under the accepted post-IMP-083 roadmap.