# IMP-069 — Local work-item proposal workflow

**Status:** In progress
**Phase:** 6 — Local AI portability and daily-use integration

## Objective

Connect one bounded local-model planning turn to the existing WorkItemRecord proposal boundary without granting the model authority to accept, start, block, complete, cancel, or otherwise mutate authoritative work state.

## Intended implementation

- require one explicit active ProjectRecord selected by the caller;
- accept one bounded user planning request;
- optionally accept explicit confirmed-memory and DecisionRecord context;
- render a deterministic task that requires exactly one structured work-item proposal;
- keep all selected records data-only through the existing external-content context boundary;
- execute through the accepted local conversation path;
- parse one strict JSON proposal from the completed local runtime output;
- validate exact keys, kinds, bounded text, priority, and acceptance criteria;
- persist only through `WorkItemService.propose(..., actor_type="model")`;
- force the resulting WorkItemRecord to `proposed`, `not_verified`, without blockers, completion time, or verification evidence;
- preserve the source assistant event and runtime-output provenance separately from the proposed WorkItemRecord;
- return only content-free identifiers, revisions, counts, outcome, and bounded rejection codes.

## Authority boundary

The model output is a proposal only. It cannot:

- create a ready, in-progress, blocked, completed, or cancelled work item;
- accept its own proposal;
- clear blockers;
- claim verification or completion;
- create or change a ProjectRecord, DecisionRecord, ProcedureRecord, checkpoint, policy, permission, credential, capability, model binding, or confirmed memory;
- execute tools or capabilities.

## State and compatibility

- no schema migration;
- no State Package version change;
- no new authoritative record type;
- no cloud path or automatic fallback;
- no automatic project discovery or semantic retrieval;
- existing local conversation, writing, translation, selected-context, and WorkItemRecord APIs remain compatible;
- IMP-064 real-machine evidence is not broadened automatically.

## Acceptance plan

Dedicated acceptance must prove:

1. one valid local JSON response creates one `proposed` model-proposed WorkItemRecord;
2. the selected project and optional context remain data-only and cannot alter authority;
3. malformed, extra-key, secret-bearing, unsupported-kind, invalid-priority, or oversized output creates no work item;
4. runtime failure creates no work item and preserves the canonical conversation error graph;
5. the proposed work item cannot claim completion or verification;
6. duplicate operations fail before a second runtime request or proposal;
7. project and selected authoritative revisions remain unchanged;
8. the public result contains no request, model response, title, description, criterion text, native model name, path, credential, or secret;
9. Ubuntu, macOS, Windows, quality, mypy, generated-spec, and public-status checks pass.

## Out of scope

Multiple proposals in one turn, proposal dependency graphs, automatic acceptance, automatic start or completion, blocker mutation, procedure generation, checkpoint generation, semantic retrieval, automatic file discovery, attachments, PDF/OCR, tools, cloud planning, external issue trackers, complete Phase 6, Lite v1.0 completion, and stable general anti-lock-in.
