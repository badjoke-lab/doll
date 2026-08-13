# IMP-089 — Inspectable lexical memory context-budget preview

Status: implementation branch

## Purpose

IMP-089 adds a bounded read-only preview over the accepted IMP-085 deterministic lexical RecallState. Given an explicit query and explicit limits, it recommends confirmed-memory IDs for possible later explicit context selection.

The preview is advisory only. It does not create context, run a model, or mutate Doll State.

## Versioned boundary

- policy ID: `lexical-recall-budget-preview`
- policy version: `1`
- scope: `global-confirmed-memory-only`
- maximum recalled candidates: 50
- maximum selected memories: existing explicit-context limit, 8
- maximum selected characters: existing explicit-context limit, 24,000

Version 1 uses only IMP-085 `weighted-memory-fields` RecallState. It adds no Ollama, embedding, vector, model, network, cloud, or semantic dependency.

## Existing context contract is reused

IMP-089 does not define another context serializer. For each eligible candidate it uses `SelectedWritingContextService.plan()` for the single candidate and for the combined selected-ID set.

The preview therefore measures the same data-only memory snapshots used by the existing explicit writing-context path. A higher-ranked memory that does not fit the requested character budget is excluded, and a later smaller candidate may still fit.

## Eligibility

The caller supplies an explicit UTC `as_of` time and may set a maximum sensitivity, item limit, character limit, and `memory_enabled` flag.

A candidate must remain revision-consistent, active, non-secret, at or below the requested sensitivity, valid at `as_of`, and within the explicit budgets. `valid_from` and `valid_until` are inclusive.

Bounded exclusion reasons are:

- `not_yet_valid`
- `expired`
- `sensitivity_limit`
- `item_limit`
- `character_budget`

Secret and archived records remain excluded by the existing upstream confirmed-memory/local-search boundary.

`memory_enabled=False` returns an empty preview while still binding the result to the Doll State revision.

## Inspectability and authority

The report exposes policy and RecallState version identity, Doll State revision, normalized `as_of`, configured limits, selected IDs/revisions, original lexical ranks/scores, estimated context characters, and bounded exclusions.

The serialized report explicitly states that automatic context injection is false and explicit context materialization is still required.

The preview requires a read-only repository. It never calls `SelectedWritingContextService.materialize()`, creates no `InstructionOrigin`, persists no recall/preview record, records no usage signal, and changes no authoritative memory, project, decision, permission, policy, procedure, work, model, runtime, or binding state. Doll State revision is checked across the preview and revision drift fails closed.

## Global-only scope

Confirmed MemoryRecord does not currently provide a canonical project-membership field. Version 1 therefore does not infer project membership from text, related records, source references, history, or model judgment. Project-aware selection requires a separate accepted relationship and implementation slice.

## Validation

Synthetic tests cover deterministic ordering, version/revision identity, item and character budgets, validity windows, sensitivity, archive/secret exclusion, disabled-memory output, invalid controls, read-only enforcement, no InstructionOrigin creation during preview, and explicit materialization remaining a separate write.

Quality, type checking, and Ubuntu/macOS/Windows CI are blocking before merge.

## Non-claims

IMP-089 does not establish automatic or model-selected context, project-aware automatic context, semantic retrieval as a supported/default dependency, lexical-semantic fusion, persistent embeddings, memory-use signals, consolidation, PAM/PLUR/PROJECTMEM adapters, ProjectExperienceRecord, ContinuityPreflight, MCP, cloud recall, Phase 6 completion, or Lite v1.0.
