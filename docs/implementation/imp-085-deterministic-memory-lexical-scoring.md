# IMP-085 — Deterministic memory lexical scoring

## Objective

Add the first bounded local-retrieval upgrade on top of the IMP-084 derived RecallState boundary.

IMP-085 improves recall ordering with a small deterministic integer score over authoritative confirmed-memory subject and content while preserving the IMP-073 candidate boundary and all IMP-084 non-authority guarantees.

## Candidate boundary

Candidates still come exclusively from IMP-073 local search with an exact `memory` record-type filter.

That means the candidate set remains:

- explicit-query only;
- active records only;
- secret records excluded;
- all normalized query terms required somewhere in the record;
- bounded by the existing query, scan, and result limits;
- local-only and read-only;
- without linked-record expansion, model selection, network access, or cloud fallback.

IMP-085 does not broaden what can be recalled. It only adds a new deterministic ordering policy inside the already accepted candidate set.

## Algorithm

The new RecallState algorithm is:

```text
algorithm_id = weighted-memory-fields
algorithm_version = 1
```

It becomes the default RecallState algorithm while the two IMP-084 algorithms remain available for explicit rollback and comparison.

Normalization matches the existing lexical boundary:

1. Unicode NFKC normalization;
2. whitespace collapse;
3. case folding;
4. unique query terms in caller order.

For every candidate memory, version 1 computes an integer score:

```text
for each unique query term:
  +8 if present in subject
  +4 if present in content
  +1 if present in neither subject nor content

+8 if the complete normalized query phrase is present in subject
+4 if the complete normalized query phrase is present in content
```

The `+1` case is fallback evidence for a term that was admitted by IMP-073 through another searchable memory metadata field. It does not promote that metadata to authority.

With the existing maximum of 12 unique query terms, the maximum score is 156. No floating point, timestamp, model output, usage history, recency, embedding, or external state participates.

Ranking is deterministic:

1. lexical score descending;
2. existing IMP-073 source rank;
3. memory ID.

## Authority and storage

The weighted score is derived RecallState only.

IMP-085 creates no:

- new authoritative record type;
- SQLite schema or migration;
- persistent lexical index, FTS table, vector database, embedding, or cache;
- MemoryUsageSignalRecord;
- recall counter or last-recalled write;
- memory content, confirmation, validity, provenance, sensitivity, lifecycle, or revision mutation;
- Doll State revision change;
- automatic prompt/context injection;
- model, process, network, cloud, tool, capability, permission, or confirmation path.

Existing `local-search-order` and `bounded-field-count-rerank` algorithm IDs remain supported. Switching to either and back does not require a state migration or authoritative-memory rollback.

## Acceptance coverage

Synthetic tests extend the IMP-084 MCON-001/MCON-002 evidence and prove:

- subject, content, and metadata-only weights produce the documented ordering and exact integer scores;
- exact phrase bonuses deterministically break otherwise equal same-field term coverage;
- a fresh immutable read-only process reproduces identical score/rank output;
- secret memory remains excluded by the candidate boundary;
- changing from the legacy local-search order to weighted scoring may change rank while authoritative memory and Doll State revisions remain unchanged;
- weighted scoring stays within the documented v1 bound.

Standard CI supplies Ubuntu, macOS, and Windows coverage.

## Non-claims

IMP-085 does not establish:

- persistent memory-use signals or MCON-003;
- recency, feedback, activation, or decay scoring;
- persistent lexical indexing or BM25/FTS;
- semantic embeddings or vector search;
- hybrid lexical/semantic fusion;
- context-budget selection;
- automatic or model-selected context;
- memory consolidation;
- PAM, PLUR, or PROJECTMEM interoperability;
- ProjectExperienceRecord;
- ContinuityPreflight;
- MCP;
- cloud recall;
- broader Phase 6 completion or Lite v1.0 completion.