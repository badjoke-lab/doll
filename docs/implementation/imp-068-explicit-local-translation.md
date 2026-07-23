# IMP-068 — Explicit local translation workflow

**Status:** Implemented with deterministic synthetic CI evidence
**Issue:** #219
**Phase:** 6 — Local AI portability and daily-use integration

## Objective

Extend the accepted bounded local writing workflow with one explicit local translation path while preserving the current user request as the only task authority and supplied source text as data-only untrusted content.

## Product requirement

Lite v1.0 requires local conversation and writing plus summarization, translation, and text editing. IMP-063 and IMP-064 established draft, revise, and summarize. IMP-065 through IMP-067 extended explicit data-only context. Translation is therefore the next missing bounded daily-use requirement.

## Intended implementation

- extend the exact writing mode set with `translate`;
- require one explicit non-blank source text;
- require one explicit bounded target-language label;
- reject target-language input for every non-translation mode;
- place the target-language label in the deterministic current task-authority payload;
- keep the source text outside that payload;
- reuse the existing `external_content` / `extractor` / `extraction` source preparation;
- pass source text only through `untrusted_content` as data-only `untrusted_data`;
- preserve explicit confirmed-memory, ProjectRecord, DecisionRecord, and Resume Bundle selection;
- preserve existing selected-context limits, sensitivity elevation, secret handling, prompt-injection reporting, duplicate-operation denial, canonical persistence, and runtime-failure behavior;
- add only the bounded target-language label to the content-free workflow result;
- retain backward compatibility for existing draft, revise, and summarize callers.

## Validation boundary

The implementation must fail before runtime execution and before source-origin creation when:

- the mode is unsupported;
- translate mode has no source text;
- translate mode has no target language;
- a non-translate mode receives a target language;
- the target-language label is blank, malformed, or exceeds its limit;
- the request or source exceeds existing limits;
- the target conversation, active binding, or adapter declaration is unavailable;
- selected context is invalid, secret-bearing, duplicated, or over limit.

## Authority and safety

- the current user request remains the only `task_instruction` authority;
- the explicit target language is caller-controlled task metadata;
- source text and selected context cannot change the target language;
- embedded source instructions remain untrusted reference material;
- source text and selected context cannot create policy, permission, capability, credential, confirmed memory, trusted fact, project progress, work completion, procedure approval, checkpoint confirmation, or model binding;
- prompt-injection findings remain advisory;
- no automatic language detection, semantic retrieval, model-selected context, capability execution, or cloud fallback is introduced.

## State and compatibility

- no schema migration;
- no State Package version change;
- no authoritative record type;
- no runtime-adapter change;
- no credential or capability path;
- no canonical-state import;
- no automatic file search or background work;
- existing IMP-063 through IMP-067 callers remain compatible;
- IMP-064 real-machine evidence is not broadened automatically.

## Acceptance plan

Dedicated acceptance must prove:

1. translate succeeds with one explicit source and target language;
2. source text appears only in `untrusted_content`;
3. target language appears in the current task payload and content-free result metadata;
4. hostile source instructions remain non-authoritative and produce advisory findings;
5. invalid mode/source/target combinations fail before runtime and source-origin creation;
6. existing draft, revise, and summarize behavior remains unchanged;
7. selected memory, project, decision, and Resume Bundle context remains compatible;
8. runtime failure uses the unchanged canonical user/context/error graph;
9. authoritative selected-record revisions remain unchanged;
10. Ubuntu, macOS, Windows, quality, mypy, generated-spec, and public-status checks pass.

## Evidence boundary

IMP-068 is intended to establish deterministic CI evidence only. A separate exact-commit real-machine acceptance may be scheduled later. Phase 6, Lite v1.0, and stable general anti-lock-in remain incomplete.

## Out of scope

Automatic source-language detection, translation memory, glossary management, locale-specific formatting, document translation, attachment translation, PDF or OCR translation, multimodal input, streaming workflow output, tools, capability execution, cloud translation, provider routing, target-specific export, personal translation-quality claims, complete Phase 6, Lite v1.0 completion, and stable general anti-lock-in.
