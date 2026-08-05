# IMP-073 — Explicit local full-text state search

## Status

Implemented with deterministic synthetic CI evidence.

## Objective

Provide the Lite v1.0-blocking local full-text search function without adding automatic retrieval, semantic ranking, a model dependency, a network dependency, or a persistent search index.

## Implemented boundary

IMP-073 adds one top-level `doll search` command and one explicit local-search service.

The stable search boundary:

- accepts one caller-supplied query;
- searches only active authoritative records;
- excludes every `secret`-sensitivity record;
- searches titles and recursively selected textual metadata values;
- normalizes Unicode with NFKC and uses case-folded substring matching;
- applies multi-term AND semantics within one record;
- supports one optional exact record-type filter;
- returns deterministic bounded hits, field paths, and snippets;
- ranks title matches before metadata-only matches and otherwise preserves deterministic authoritative ordering;
- opens SQLite through immutable read-only access;
- fails closed when a non-empty SQLite WAL or rollback journal is present;
- emits stable human-readable output or deterministic JSON;
- leaves the query outside authoritative state, audit, model context, and artifacts.

## Safety and continuity effects

The search path performs no:

- state, workspace, artifact, audit, index, cache, or backup write;
- schema migration or persistent FTS-table creation;
- model or runtime invocation;
- automatic or semantic retrieval;
- model-selected context or context injection;
- process or shell execution;
- tool or capability execution;
- network or cloud request;
- credential, permission, confirmation, or binding access or change.

Query validation rejects blank input, control characters, oversized input, excessive terms, malformed record-type filters, and invalid limits. The initial stable scan is bounded to 10,000 active non-secret records and reports when that bound truncates the scan.

## Acceptance coverage

Dedicated acceptance covers:

- title, nested metadata, Japanese, Unicode normalization, and case folding;
- multi-term matching across fields in one record;
- inactive and secret-record exclusion;
- exact record-type filtering;
- deterministic ordering, result limits, field paths, snippets, and JSON;
- exact workspace-file preservation;
- writable-repository rejection;
- invalid queries and limits;
- pending SQLite journal rejection without deletion;
- human and JSON CLI output;
- invalid-workspace handling without creation or native-path disclosure.

Standard CI provides Ubuntu, macOS, and Windows coverage. IMP-073 evidence is CI-only and does not broaden previously accepted real-machine evidence.

## Out of scope

IMP-073 does not establish semantic search, embeddings, vector databases, automatic retrieval, model-selected context, persistent search indexes, inactive-record search, secret-record search, artifact-byte extraction, attachments, PDF, OCR, CSV processing, Web search, performance acceptance, the seven-day release-candidate soak, complete Phase 6, Lite v1.0 completion, or stable general anti-lock-in.
