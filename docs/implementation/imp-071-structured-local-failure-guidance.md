# IMP-071 — Structured local runtime failure guidance

**Status:** Implemented with deterministic synthetic CI evidence
**Issue:** #225
**Phase:** 6 — Local AI portability and daily-use integration

## Objective

Add one deterministic provider-neutral guidance payload for every accepted local runtime failure code so failed local turns explain safe local-only options without exposing provider detail or enabling automatic action.

## Requirement basis

The accepted product baseline requires a local failure to fail locally and explain the available options. Before IMP-071, canonical local conversation results and error events recorded only an outcome and failure code.

## Intended implementation

- define one immutable `LocalFailureGuidance` payload for every accepted `RuntimeFailureCode`;
- include one versioned guidance identifier, the exact failure code, one bounded summary, and an ordered bounded option list;
- mark state preservation, automatic-action absence, and cloud-fallback absence explicitly;
- attach guidance to failed, cancelled, and timed-out local conversation results;
- persist the same guidance fields in canonical error-event extensions;
- keep completed turns free of failure guidance;
- keep audit records content-free by storing only guidance identity and option count;
- preserve existing local conversation, writing, translation, work-item proposal, and portability-review behavior.

## Allowed options

Guidance may only describe local and user-controlled actions:

- retry locally;
- reduce request, context, or output size;
- inspect local runtime health or local model inventory;
- start or repair the configured local runtime;
- manually activate an already approved installed model or fallback binding;
- increase the local timeout within its configured limit;
- continue state inspection, export, backup, restore, or recovery without model execution.

## Prohibited options

Guidance cannot recommend or perform automatic cloud fallback, remote upload, provider login, API-key entry, automatic download, automatic installation, automatic binding changes, process launch, shell execution, tools, capabilities, destructive state changes, or provider-specific diagnostics containing private detail.

## State and compatibility

- no schema migration;
- no State Package version change;
- no new authoritative record type;
- no runtime-adapter contract change;
- no accepted failure-code change;
- no automatic action or state mutation beyond existing canonical turn and error records;
- existing result consumers remain compatible through one optional defaulted guidance field;
- accepted real-machine evidence is not broadened automatically.

## Acceptance plan

Dedicated acceptance must prove:

1. all nine accepted runtime failure codes have exactly one deterministic guidance payload;
2. summaries and options are bounded, provider-neutral, and content-free;
3. completed turns contain no guidance;
4. failed, cancelled, and timed-out turns contain matching guidance;
5. canonical error events persist the same guidance fields;
6. guidance always records `state_preserved=true`, `automatic_action_taken=false`, and `cloud_fallback_used=false`;
7. no option authorizes cloud fallback, downloads, automatic binding changes, process launch, shell execution, tools, capabilities, or state mutation;
8. canonical user/context/error persistence remains unchanged;
9. existing Phase 6 workflows remain green;
10. Ubuntu, macOS, Windows, quality, mypy, coverage, generated-spec, public-status, and numbering checks pass.

## Evidence boundary

IMP-071 establishes deterministic CI evidence only. It does not complete Phase 6, Lite v1.0, accessibility presentation, Lite performance measurement, the release soak gate, or stable general anti-lock-in.
