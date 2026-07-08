# IMP-060 — Bounded ChatGPT numbered conversation-file aggregation

## Status

Implementation slice for fresh ChatGPT exports that contain numbered conversation JSON members instead of one exact `conversations.json` file.

This implementation does not parse ZIP archives. It accepts only an explicit caller-provided member list outside the repository and aggregates those numbered JSON members deterministically before handing the resulting canonical bytes to the accepted IMP-059 source adapter and private manual workflow.

## Motivation

The fresh project-owner July 2026 export used 12 numbered `conversations-*.json` members and no exact `conversations.json` member. IMP-059 correctly stopped before staging because numbered-file aggregation was explicitly outside its accepted boundary.

IMP-060 adds only the missing aggregation boundary.

## Boundary

The aggregation path is:

```text
explicit caller-owned member list outside repository
        ↓
read exact numbered member bytes
        ↓
validate labels, numeric indices, sequence, bytes, JSON roots, nesting, counts
        ↓
numeric member ordering
        ↓
cross-member duplicate conversation identity check
        ↓
deterministic canonical aggregated JSON bytes
        ↓
unchanged IMP-059 selected-history adapter
        ↓
unchanged review / publish / generic export / shutdown escape flow
```

The aggregator performs no:

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

## Duplicate semantics

Cross-member duplicate conversation identities are handled explicitly:

- exact canonical duplicates are collapsed deterministically and counted in the content-free manifest;
- conflicting duplicates fail closed.

No duplicate is silently overwritten.

## Integrity evidence

The aggregation result contains:

- deterministic aggregated JSON bytes;
- SHA-256 of the aggregated bytes;
- a member-set root hash binding ordered canonical member labels and exact member hashes;
- content-free member manifests with label, numeric index, byte count, conversation count, and SHA-256;
- aggregate input and output conversation counts;
- exact duplicate conversation count.

The manifest never includes caller paths, conversation IDs, titles, prompts, responses, model names, usernames, hostnames, credentials, or secret values.

## Private manual workflow

`scripts/run_imp_060_private_manual.py` accepts:

- one member-list text file outside the repository, containing one explicit member path per line;
- one selected-conversation file outside the repository;
- the existing source-environment, import-batch, observation, and runner-commit values.

The runner:

1. verifies its exact commit binding;
2. reads only the explicitly listed numbered members;
3. aggregates them deterministically;
4. writes the aggregate to a temporary local file;
5. invokes the accepted IMP-059 private manual runner;
6. emits the IMP-059 result plus content-free numbered aggregation evidence.

## Acceptance

Synthetic acceptance must establish:

1. numeric ordering including indices above 9;
2. caller argument-order independence;
3. support for zero-based and one-based contiguous sequences;
4. rejection of unsupported labels, duplicate indices, missing members, invalid starts, malformed JSON, duplicate keys, non-finite constants, non-list roots, and resource-limit violations;
5. exact duplicate collapse and conflicting duplicate fail-closed behavior;
6. content-free manifest output;
7. selected-only IMP-059 review semantics after aggregation;
8. complete reviewed publication, generic export, and shutdown escape through the existing IMP-059 path;
9. no private path or fixture content in bounded output;
10. Linux, macOS, and Windows acceptance.

## Non-claims

IMP-060 does not establish:

- ZIP ingestion;
- automatic directory discovery;
- archive-member byte preservation as separate managed snapshots;
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
