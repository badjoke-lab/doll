# IMP-060 — Bounded ChatGPT numbered conversation-file aggregation

## Status

Implementation slice for fresh ChatGPT exports that contain numbered conversation JSON members instead of one exact `conversations.json` file.

This implementation does not parse ZIP archives. It accepts only an explicit caller-provided member list outside the repository. Small synthetic inputs may still use the in-memory deterministic aggregator, while the real private-manual path processes numbered members sequentially, validates and cryptographically binds the complete member set, and materializes only the bounded selected-conversation projection passed to the accepted IMP-059 mapping and private manual workflow.

## Motivation

The fresh project-owner July 2026 export used 12 numbered `conversations-*.json` members and no exact `conversations.json` member. IMP-059 correctly stopped before staging because numbered-file aggregation was explicitly outside its accepted boundary.

The same export also established a content-free aggregate member size of 724.55 MiB. Materializing that complete aggregate together with all raw member bytes, parsed objects, duplicate-comparison bytes, and final aggregate bytes would create an unnecessary multi-copy memory peak. The private-manual path therefore uses sequential member processing and a bounded selected projection.

IMP-060 adds only this numbered-member aggregation and projection boundary.

## Boundary

The private-manual path is:

```text
explicit caller-owned member list outside repository
        ↓
validate member labels, paths, numeric indices, sequence, and bounded total size
        ↓
read one numbered member at a time
        ↓
strict JSON validation, nesting/count checks, per-member hash and manifest
        ↓
numeric aggregate ordering
        ↓
full-set logical aggregate hash + exact canonical duplicate checks
        ↓
full-set member stability re-hash
        ↓
bounded deterministic selected-conversation projection
        ↓
unchanged IMP-059 selected-history mapping
        ↓
unchanged review / publish / generic export / shutdown escape flow
```

The private-manual projector does not keep every numbered member byte string, every parsed member root, and the complete aggregate JSON byte stream in memory simultaneously.

The aggregation path performs no:

- ZIP extraction;
- directory discovery;
- archive traversal;
- network request;
- account access;
- browser or desktop automation;
- email handling;
- credential, token, cookie, or OAuth access;
- model execution;
- runtime installation;
- model download.

## Member validation

Accepted member labels match `conversations-<numeric-index>.json`.

Members are:

- supplied explicitly;
- sorted by numeric index, not lexical filename order;
- required to form a contiguous sequence starting at index 0 or 1;
- rejected on duplicate paths, labels, or numeric indices;
- rejected when aggregate bytes, member count, conversation count, or nesting exceed the bounded limits.

The default aggregate input byte ceiling is 1 GiB. This remains a hard bounded limit rather than an unbounded input path and is calibrated above the content-free observed fresh project-owner export size while preserving fail-closed behavior for larger aggregate inputs.

Each member must decode as strict UTF-8 JSON with:

- no duplicate object keys;
- no non-finite constants;
- a list root;
- valid conversation identity semantics compatible with IMP-059.

After the sequential pass, each member is re-hashed from disk and compared with the byte count and SHA-256 captured during processing. A member that changes during the run fails closed.

## Duplicate semantics

Cross-member duplicate conversation identities are handled explicitly:

- exact canonical duplicates are compared against a temporary local canonical byte store, collapsed deterministically, and counted in the content-free manifest;
- conflicting duplicates fail closed.

The canonical byte store is temporary local state used only to preserve exact duplicate semantics without retaining the complete canonical aggregate in RAM. No duplicate is silently overwritten.

## Selected projection semantics

The complete numbered member set is validated and cryptographically bound, but only explicitly selected conversation objects are materialized into the projection handed to IMP-059.

The projection:

- preserves numeric member order and first-unique conversation order;
- preserves provider conversation objects through deterministic canonical JSON serialization;
- contains only explicitly selected conversation identities;
- is bounded by the unchanged IMP-059 adapter byte ceiling;
- keeps the existing IMP-059 provider mapping, publication, authority, generic export, and shutdown escape semantics unchanged.

The evidence model distinguishes:

- `aggregate_source_hash`: SHA-256 of the logical deterministic complete aggregate stream;
- `member_set_root_hash`: hash binding ordered canonical member labels and exact member manifests;
- `selected_projection_sha256`: SHA-256 of the bounded selected projection actually handed to IMP-059.

Exact-source preservation in the complete private drill therefore applies to the selected projection. The complete numbered source set is instead bound by the member manifests, per-member hashes, member-set root hash, and logical aggregate hash.

## Integrity evidence

The private-manual aggregation result contains:

- processing mode identifying sequential member selected projection;
- SHA-256 of the logical deterministic complete aggregate stream;
- a member-set root hash binding ordered canonical member labels and exact member hashes;
- content-free member manifests with label, numeric index, byte count, conversation count, and SHA-256;
- aggregate input and output conversation counts;
- exact duplicate conversation count;
- aggregate node, message, attachment-reference, malformed-object, and unknown-field counts;
- selected projection byte count and SHA-256.

The manifest never includes caller paths, conversation IDs, titles, prompts, responses, model names, usernames, hostnames, credentials, or secret values.

## Private manual workflow

`scripts/run_imp_060_private_manual.py` accepts:

- one member-list text file outside the repository, containing one explicit member path per line;
- one selected-conversation file outside the repository;
- the existing source-environment, import-batch, observation, and runner-commit values.

The runner:

1. verifies its exact commit binding;
2. reads only the explicitly listed numbered member paths;
3. validates and projects the complete set sequentially;
4. writes only the bounded selected projection to a temporary local `conversations.json` file;
5. invokes the accepted IMP-059 private manual runner against that projection;
6. distinguishes selected-projection source preservation from complete numbered-set integrity evidence;
7. emits only content-free numbered aggregation and selected-projection evidence.

## Acceptance

Synthetic acceptance must establish:

1. numeric ordering including indices above 9;
2. caller argument-order independence;
3. support for zero-based and one-based contiguous sequences;
4. rejection of unsupported labels, duplicate indices, missing members, invalid starts, malformed JSON, duplicate keys, non-finite constants, non-list roots, and resource-limit violations;
5. exact duplicate collapse and conflicting duplicate fail-closed behavior;
6. equality of the sequential logical aggregate hash and member-set root hash with the accepted in-memory aggregator for equivalent small inputs;
7. selected projection contains only the explicit selected set;
8. selected projection byte limit remains enforced;
9. content-free manifest and projection evidence;
10. selected-only IMP-059 review semantics after projection;
11. complete reviewed publication, generic export, and shutdown escape through the existing IMP-059 path;
12. no private path or fixture content in bounded output;
13. Linux, macOS, and Windows acceptance.

## Non-claims

IMP-060 does not establish:

- ZIP ingestion;
- automatic directory discovery;
- archive-member byte preservation as separate managed snapshots;
- publication of every conversation from the complete numbered set;
- attachment-byte recovery;
- account restoration;
- memory migration;
- GPT migration;
- settings migration;
- file restoration;
- provider round-trip fidelity;
- the complete Phase 6 gate;
- stable general anti-lock-in.

PORT-014 remains incomplete until privacy-reviewed project-owner private manual evidence is accepted.
