# IMP-086 — Optional rebuildable memory lexical index

**Issue:** #263  
**Phase:** 6 — Local AI portability and daily-use integration  
**Status:** Implementation candidate  
**Specification authority:** `03c-memory-interoperability-recall-and-project-experience.md`, `08c-memory-interoperability-recall-and-project-experience-acceptance.md`, `09a-post-imp-083-memory-continuity-roadmap.md`, ADR-008

## Purpose

IMP-086 adds the first persistent retrieval structure in the post-IMP-083 memory track without turning retrieval state into Doll State.

IMP-084 established derived `RecallState`. IMP-085 added deterministic weighted lexical ranking while retaining the IMP-073 authoritative scan as the candidate boundary. IMP-086 takes the next roadmap step: an **optional, disposable lexical sidecar** that can survive process restarts but can be deleted, corrupted, or rebuilt without changing confirmed memory.

The important architectural distinction is:

> persistent on disk does not mean authoritative continuity state.

The index exists only to accelerate or support later derived retrieval work. The accepted IMP-085 scan-based RecallState remains available whether the sidecar exists or not.

## Sidecar location

The fixed v1 location is:

```text
temporary/recall-index/memory-lexical-v1.sqlite3
```

It lives under the existing private workspace `temporary/` directory rather than `state/` because it is reproducible and excluded from continuity authority.

This choice intentionally means:

- no Doll State schema migration;
- no new authoritative record type;
- no workspace schema change;
- no State Package registry entry;
- no requirement to back up the index bytes;
- no recovery dependency on the sidecar.

The existing backup contract already treats `temporary_files`, `caches`, and `reproducible_indexes` as excluded categories. Full workspace layout verification allows ordinary non-symlink content under `temporary/` without treating it as durable backup payload.

On POSIX systems the `recall-index` directory is restricted to mode `0700` and the SQLite file to `0600`. Windows relies on the existing private workspace boundary rather than POSIX mode bits.

## Index contract

The v1 sidecar uses only Python's standard-library SQLite support. It does not require SQLite FTS extensions or a third-party search package.

Contract identity:

```text
schema_version: 1
algorithm_id: memory-exact-token-inverted
algorithm_version: 1
query_mode: unicode-nfkc-casefold-exact-token-and
```

The sidecar contains three tables:

```text
index_metadata
indexed_memories
 token_postings
```

`index_metadata` records:

- schema version;
- algorithm ID and version;
- source workspace ID;
- source Doll State revision;
- indexed-memory count;
- posting count;
- whether the bounded source scan was truncated.

`indexed_memories` stores only memory ID, authoritative memory revision, and deterministic source rank.

`token_postings` stores only normalized token, memory ID, and field class (`subject`, `content`, or `metadata`). It does not store a parallel copy of the full MemoryRecord, whole prompt, generated response, native path, or model output.

## Source boundary and bounds

The builder reads only authoritative records satisfying all of these conditions:

```text
record_type = memory
status = active
sensitivity != secret
```

The source order matches the existing local-search scan boundary:

```text
updated_at DESC, id ASC
```

Fixed v1 bounds are:

```text
maximum indexed memories: 10,000
maximum postings: 1,000,000
maximum tokens per memory: 4,096
maximum token length: 240 characters
maximum query length: 240 characters
maximum query terms: 12
maximum query results: 100
```

If more than 10,000 eligible memories exist, the index records `scan_truncated=true`. Posting/token bounds fail closed rather than silently publishing a partial per-memory index.

Secret and archived memories contribute no postings.

## Normalization and query semantics

Index normalization is deterministic:

1. Unicode NFKC normalization;
2. collapse all whitespace runs to single spaces;
3. Unicode `casefold()`;
4. split on normalized spaces;
5. keep unique bounded tokens per field class.

The initial query API uses exact normalized-token AND semantics. Every unique query token must have a posting for a memory before that memory is returned.

This is deliberately **not** claimed to be identical to IMP-073 substring search. The sidecar is an optional derived index API whose semantics are explicit and versioned. IMP-086 does not replace the default IMP-085 scan-based candidate path.

That separation prevents an index-format decision from silently changing already accepted recall behavior.

## Rebuild and publication

A build requires a read-only authoritative repository. The builder verifies that the loaded workspace identity and Doll State revision agree before indexing.

The new SQLite database is built at a temporary sibling path, checked with SQLite `integrity_check`, flushed, and only then published with atomic `os.replace` where the platform permits it.

If publication fails, the temporary file is removed and an already-valid prior index remains in place.

The final published index is immediately reopened through the same validation path used by normal inspection.

## Freshness and fail-closed behavior

Every usable index is bound to both:

- the workspace ID;
- the exact source Doll State revision.

Inspection or query fails closed when the sidecar is:

- absent;
- unreadable;
- corrupt;
- from another workspace;
- built for another state revision;
- using an unsupported schema version;
- using an unsupported algorithm ID or version.

A stale or corrupt sidecar is never treated as current retrieval authority.

Returned hits are additionally checked against the currently authoritative MemoryRecord revision, lifecycle, and sensitivity before they are reported.

## Continuity behavior

MCON-001 remains the governing claim: loss of derived retrieval state must preserve authoritative memory.

IMP-086 tests therefore prove that deleting or corrupting the sidecar does not:

- edit MemoryRecord content;
- bump MemoryRecord revision;
- change confirmation, validity, provenance, sensitivity, or lifecycle;
- change Doll State merely because the index was removed;
- prevent confirmed-memory inspection;
- prevent IMP-085 scan-based RecallState derivation;
- prevent State Package export/verification;
- prevent state-backup creation/verification.

Rebuilding after loss produces usable derived index state again from authoritative inputs.

MCON-002 also remains satisfied: retrieval/index implementation can change without rewriting confirmed memory, and the pre-index IMP-085 path remains a rollback/fallback path.

## Why the index is not backed up

Backing up reproducible index bytes would increase package size and compatibility burden while providing no continuity information that is not already recoverable from authoritative memory.

More importantly, including the sidecar in authoritative backup inventory could encourage later code to treat its tokenization, ranking, or implementation version as canonical truth.

The accepted design does the opposite: backup preserves the inputs required to rebuild retrieval state, not the retrieval cache itself.

## Security and privacy

The sidecar is local-only and does not invoke:

- a model;
- an embedding service;
- cloud APIs;
- network access;
- subprocesses or shell execution;
- tools or capability execution;
- automatic prompt-context injection.

Secret memories are excluded at the authoritative source query. The sidecar stores bounded normalized tokens rather than complete MemoryRecord payloads, but it is still private workspace data and must not be exposed publicly.

Symlinked index directories/files fail closed.

## Non-claims

IMP-086 does **not** establish:

- a new default RecallState candidate path;
- performance or latency improvement claims;
- `MemoryUsageSignalRecord` or MCON-003;
- recency, usefulness feedback, activation, or decay;
- semantic/vector embeddings;
- lexical-semantic fusion or RRF;
- context-budget selection;
- automatic/model-selected context;
- consolidation;
- PAM, PLUR, or PROJECTMEM adapters;
- `ProjectExperienceRecord`;
- `ContinuityPreflight`;
- MCP;
- cloud recall;
- Phase 6 completion;
- Lite v1.0 completion.

## Acceptance evidence

The IMP-086 synthetic suite covers:

- deterministic build/query/rebuild behavior across fresh repository opens;
- active/non-secret inclusion and secret/archived exclusion;
- sidecar schema and absence of a canonical `recall_index` record;
- deletion with unchanged authoritative state and working IMP-085 fallback;
- stale detection after authoritative state advances;
- corrupt-index fail-closed behavior while State Package and backup continue to work;
- unsupported index-version rejection;
- atomic publication failure preserving a prior valid sidecar;
- bounded invalid-request rejection;
- POSIX private-mode checks where applicable.

The public project status must remain at merged IMP-085 until this implementation itself passes normal quality and Ubuntu/macOS/Windows CI and merges.
