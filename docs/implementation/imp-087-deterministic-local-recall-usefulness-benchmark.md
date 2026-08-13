# IMP-087 — Deterministic local recall usefulness benchmark

Status: implementation branch

## Purpose

IMP-087 adds a small synthetic benchmark for the local memory-recall stack before doll accepts any semantic-embedding dependency.

The accepted post-IMP-083 roadmap permits local semantic embeddings only when measured usefulness justifies their dependency and rebuild cost. IMP-084 separated authoritative memory from derived recall state, IMP-085 added deterministic weighted lexical ranking, and IMP-086 added an optional rebuildable exact-token sidecar. IMP-087 measures those existing paths without changing them.

This is an evidence slice, not a semantic-retrieval implementation.

## Corpus

The version-1 corpus is:

`docs/testing/imp-087-memory-recall-benchmark-corpus.json`

It contains only fabricated records. It must never contain real user memories, imported chats, private documents, credentials, or production workspace material.

The corpus covers:

- direct lexical retrieval;
- subject-versus-content weighting;
- exact phrase ranking;
- metadata-only fallback evidence;
- Unicode NFKC and casefold normalization;
- a substring case intentionally supported by IMP-085 scan recall but not by the IMP-086 exact-token index;
- two low-overlap paraphrase cases classified as `semantic_opportunity`;
- unrelated distractor material;
- secret and archived exclusion cases.

Synthetic MemoryRecord UUIDs are generated normally and therefore differ between fresh workspaces. Stable benchmark identity uses corpus labels. The full report retains generated IDs as evidence, while `logical_dict()` excludes those IDs so independently created synthetic workspaces can be compared deterministically.

## Runner boundary

`src/doll/recall_benchmark.py` provides:

- strict corpus loading;
- explicit population of an empty disposable synthetic workspace;
- a read-only benchmark runner;
- case-level evidence and aggregate deterministic metrics.

The runner calls the production APIs directly:

- `derive_memory_recall_state()` for the IMP-085 scan path;
- `inspect_memory_lexical_index()` and `query_memory_lexical_index()` for the optional IMP-086 sidecar.

There is no hidden benchmark-only retrieval algorithm.

Benchmark execution performs no model call, embedding generation, network access, cloud access, subprocess launch, shell execution, tool execution, automatic context injection, or authoritative memory mutation. The only writes are the explicit creation of fabricated MemoryRecords in the disposable benchmark workspace and, when requested by the test harness, the already accepted rebuildable IMP-086 sidecar.

## Version-1 metrics

The report records rational values as exact strings rather than wall-clock or floating-point thresholds:

- lexical recall@1;
- lexical recall@3;
- lexical mean reciprocal rank;
- semantic-opportunity miss count and rate;
- secret/archive exclusion pass count;
- optional exact-token index coverage for lexical cases declared index-compatible.

Each case records:

- stable case ID;
- classification;
- query;
- expected stable memory label when applicable;
- returned labels and generated MemoryRecord IDs;
- expected rank;
- index-compatible flag;
- optional index-returned labels and IDs.

## Accepted baseline

The version-1 synthetic baseline is intentionally small and inspectable:

- lexical cases: 6;
- expected lexical recall@1: `1`;
- expected lexical recall@3: `1`;
- expected lexical MRR: `1`;
- semantic-opportunity cases: 2;
- expected current lexical misses: 2;
- exclusion cases: 2, both required to remain empty;
- exact-token-compatible lexical cases: 5;
- expected IMP-086 index coverage when a valid current index exists: `1`;
- the substring fallback case must remain retrievable through IMP-085 even though the exact-token index does not return it.

The two semantic-opportunity misses are not counted as lexical regressions. They record a measurable gap for a later experiment.

## Index failure behavior

The benchmark scan path does not depend on the IMP-086 sidecar.

If the sidecar is missing, corrupt, stale, unsupported, or otherwise unavailable, the report records the index as unavailable and continues to measure the IMP-085 scan path. It does not rebuild silently and does not treat stale or corrupt results as current.

This preserves the accepted deterministic lexical fallback and prevents a derived index from becoming an undeclared availability dependency.

## What a later semantic experiment must prove

IMP-087 does **not** establish that embeddings are justified.

A later optional semantic experiment must use this same versioned corpus, or an explicitly versioned successor, and at minimum demonstrate all of the following before semantic retrieval can be considered for product integration:

1. reduce the semantic-opportunity miss count below the current baseline of 2;
2. preserve lexical recall@3 at `1` on the version-1 lexical regression set;
3. preserve both exclusion cases as empty;
4. preserve the IMP-085 deterministic lexical fallback when the semantic component is absent;
5. keep semantic state derived/rebuildable rather than authoritative;
6. add separate evidence for dependency size, rebuild behavior, local resource cost, and offline availability before any dependency is made part of a supported profile.

Passing this tiny synthetic corpus alone is not a general quality claim. It is a deterministic regression and comparison surface.

## Non-claims

IMP-087 does not establish:

- an embedding model;
- vector or semantic retrieval;
- hybrid fusion or RRF;
- automatic or model-selected context;
- MemoryUsageSignalRecord or MCON-003;
- consolidation;
- PAM, PLUR, or PROJECTMEM adapters;
- ProjectExperienceRecord;
- ContinuityPreflight;
- MCP;
- cloud recall;
- latency or performance thresholds;
- Phase 6 completion;
- Lite v1.0 completion.

## Acceptance evidence

The IMP-087 tests must prove that:

- the declared lexical baseline is reproduced through production recall APIs;
- independently populated fresh synthetic workspaces produce the same logical report despite different generated UUIDs;
- semantic-opportunity misses are explicit and separately classified;
- secret and archived memories never appear as eligible scan results;
- missing or corrupt index state cannot block the scan baseline;
- benchmark execution does not change authoritative MemoryRecord revisions, Doll State revision, or record count;
- quality and Ubuntu/macOS/Windows CI remain green.
