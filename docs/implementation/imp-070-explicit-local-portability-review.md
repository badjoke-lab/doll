# IMP-070 — Explicit local portability review workflow

**Status:** In progress
**Issue:** #223
**Phase:** 6 — Local AI portability and daily-use integration

## Objective

Add one bounded local-model review turn for an explicitly selected existing import batch, its exact mapping report, and only the linked portability-loss records. The workflow must explain recorded migration quality and limitations without reading original source content or granting mutation or execution authority.

## Intended implementation

- require one explicit `ImportBatchRecord` selected by the caller;
- require one exact linked `MappingReportRecord` for the same import batch;
- resolve only loss IDs declared by that mapping report;
- require all selected records to be active, schema-compatible, non-secret, and unchanged during preparation;
- build one deterministic bounded snapshot containing record IDs and revisions, batch counts, mapping counts, fidelity status, loss categories, severity, descriptions, preservation state, recoverability, materiality, and required-user-action text;
- exclude source root hashes, source-object IDs, payload JSON, canonical conversation content, original source bytes, quarantine details, managed paths, native model names, credentials, and secrets;
- secret-scan the complete snapshot before any context-origin creation;
- materialize the snapshot once as immutable data-only `external_content` through `retriever` / `retrieval`;
- keep the current user request as the only task authority;
- execute through the accepted non-streaming local conversation path;
- return only content-free selected-record identities, revisions, counts, fidelity facts, event and manifest IDs, outcome, failure code, defense counts, and runtime ID.

## Validation boundary

The workflow must fail before runtime execution and before context-origin creation when:

- the import batch is missing, malformed, archived, secret, or wrong-type;
- the batch has no mapping report;
- the mapping report is missing, malformed, archived, secret, wrong-type, export-directed, or linked to another batch;
- a linked loss is missing, malformed, archived, secret, wrong-type, or linked to another batch;
- the mapping report declares more than the accepted loss-record limit;
- the deterministic snapshot exceeds its character limit;
- the snapshot contains secret-like or private-environment content;
- a selected record changes after planning;
- the context preparation or local turn operation already exists;
- the target conversation, parent, active binding, or adapter declaration is unavailable.

## Authority and safety

Selected portability records remain reference data only. The local model cannot:

- approve, publish, retry, roll back, or delete an import;
- mutate mapping or loss records;
- alter fidelity, preservation, or recoverability declarations;
- claim remediation or recovery completion;
- inspect original source bytes or source-object payloads;
- mutate canonical imported conversation content;
- create or change project, work-item, decision, procedure, checkpoint, policy, permission, credential, capability, memory, runtime, model, or binding state;
- execute tools or capabilities.

Descriptions and required-user-action text are untrusted material. Embedded instructions remain non-authoritative and may only produce advisory prompt-injection findings.

## State and compatibility

- no schema migration;
- no State Package version change;
- no new authoritative record type;
- no portability-record mutation;
- no automatic discovery, search, ranking, semantic retrieval, original-source read, network request, process launch, tool execution, capability execution, cloud path, or automatic fallback;
- existing generic import/publication, local conversation, writing, translation, selected-context, and work-item proposal APIs remain compatible;
- accepted IMP-057, IMP-062, and IMP-064 real-machine evidence is not broadened automatically.

## Acceptance plan

Dedicated acceptance must prove:

1. one valid selected batch produces one completed local review turn;
2. only linked losses enter the review snapshot;
3. the snapshot reaches the runtime only through `untrusted_content` as data-only `external_content`;
4. the current task instruction excludes loss descriptions, required actions, source hashes, source-object IDs, payloads, and original content;
5. hostile selected text remains non-authoritative and produces advisory findings;
6. invalid or mismatched records fail before runtime and origin creation;
7. duplicate operations fail before a second request or context creation;
8. runtime failure preserves every selected revision and uses the canonical user/context/error graph;
9. the result remains content-free;
10. Ubuntu, macOS, Windows, quality, mypy, generated-spec, public-status, and implementation-numbering checks pass.

## Evidence boundary

IMP-070 establishes deterministic CI evidence only. A separate exact-commit real-machine acceptance may be scheduled later. Complete Phase 6, Lite v1.0, and stable general anti-lock-in remain incomplete.

## Out of scope

Automatic batch discovery or ranking, semantic retrieval, model-selected records, original-source or source-payload inspection, canonical replay, quarantine-detail review, automatic remediation, retry or rollback execution, publication approval, loss-record mutation, target-specific export, provider round-trip verification, attachments, PDF/OCR, tools, cloud review, external issue trackers, complete Phase 6, Lite v1.0 completion, and stable general anti-lock-in.
