# ADR-007: Project continuity and resumption

**Status:** Accepted

## Context

Doll already preserves user-controlled state independently of a preferred model, runtime, interface, or cloud provider. ProjectRecord and DecisionRecord prove that durable project information can survive restart, export, import, backup, restore, and fresh-process inspection.

That is not yet sufficient to resume real work. A replacement model, interface, process, machine, or future doll version also needs an explicit, inspectable account of:

- what the project is trying to achieve;
- what is in and out of scope;
- what work is active, next, blocked, completed, or cancelled;
- which decisions caused or constrain that work;
- which procedures are approved and repeatable;
- which validation remains required;
- which checkpoint is current and whether it has become stale.

Conversation history, ad hoc handoff notes, generated summaries, issue trackers, and repository Markdown files may help, but none of them may become the only authoritative location for this state. They may disappear, diverge, become provider-specific, or contain untrusted instructions.

## Decision

Project continuity is a required part of the existing Continuity Contract. It is not a third architectural pillar beside continuity and the safety boundary.

The top-level architecture remains:

```text
1. Continuity
2. Safety boundary
```

Continuity now includes:

```text
Continuity
├── state continuity
├── recovery continuity
├── AI environment portability
└── project continuity
```

Doll will introduce three model-independent authoritative record kinds:

- WorkItemRecord;
- ProcedureRecord;
- ProjectCheckpointRecord.

ProjectRecord will gain a backward-compatible v2 contract for project objectives, scope, exclusions, success criteria, and governing policies. DecisionRecord remains v1 during the first project-continuity implementation.

Project status, handoff material, roadmap views, and resume documents are derived views. They are not parallel authoritative records.

## Authority rules

A trusted user-controlled management path may create or confirm authoritative project-continuity state.

A model, runtime, tool, import, retrieved document, conversation transcript, or external service may propose:

- a work item;
- a procedure draft;
- a blocker candidate;
- a completion candidate;
- a checkpoint candidate;
- a summary or Resume Bundle view.

Those sources cannot by themselves:

- mark a WorkItemRecord completed;
- clear an authoritative blocker;
- approve a ProcedureRecord;
- confirm a ProjectCheckpointRecord;
- change the authoritative project objective or scope;
- turn imported text into durable policy, permission, confirmation, or instruction authority.

A deterministic verifier may record bounded evidence such as test success, checksum equality, schema validity, or CI success. Verification evidence does not automatically complete the whole work item.

## Checkpoint freshness

Checkpoint freshness must not depend only on the workspace-wide state revision. Unrelated state changes would otherwise invalidate every project checkpoint.

A ProjectCheckpointRecord therefore stores the relevant record IDs and revisions used to create it, plus a deterministic basis fingerprint. A checkpoint becomes stale when one or more relevant basis records no longer match. The old checkpoint remains inspectable and is not silently rewritten.

## Resume Bundle

Doll will provide a deterministic, project-scoped Resume Bundle derived from authoritative records.

The bundle will contain machine-readable JSON or JSONL, an inspectable Markdown handoff view, a manifest, and checksums. It must be usable without a running model, preferred UI, cloud account, or running doll service.

`HANDOFF.md` inside a Resume Bundle is generated output. It is not authoritative state.

## Package and recovery consequences

The current Doll State Package has a fixed list of supported authoritative record types. Adding project-continuity records without package support would break export, backup, restore, and fresh-process validation.

The first project-continuity implementation must therefore introduce Doll State Package format v2 before or together with the first new authoritative record type. New project-continuity records must participate in:

- export;
- inspection;
- verification;
- import;
- backup;
- restore;
- cross-record link validation;
- fresh-process validation.

A new doll version must continue to read supported v1 packages. A v2 package must not be silently interpreted as v1 by an older implementation.

## Implementation order

After the Phase 3 safety gate:

1. canonical AI-environment portability foundation;
2. project-continuity package foundation;
3. ProjectRecord v2 and WorkItemRecord;
4. ProcedureRecord;
5. ProjectCheckpointRecord and freshness detection;
6. deterministic project status and Resume Bundle;
7. project-continuity acceptance gate;
8. local runtime and model integration.

The existing Phase 3 implementation sequence remains unchanged.

## Consequences

### Positive

- Work can be resumed after model, UI, process, machine, or provider replacement.
- Project state is no longer trapped in one conversation or handoff document.
- AI-generated suggestions remain useful without gaining authority.
- Recovery claims cover the work itself, not only files and memories.
- Project status becomes derivable and testable.

### Costs

- The portable package format must advance to v2.
- More typed-link and authority validation is required.
- Backup, restore, and acceptance fixtures must expand.
- Project-continuity records increase the amount of state that must remain internally consistent.

### Rejected alternatives

#### Treat conversation history as the project state

Rejected because conversation history is provider- and interface-dependent, may contain branches or regenerated text, and does not provide authoritative lifecycle or validation state.

#### Store only a generated HANDOFF.md

Rejected because one mutable document duplicates and obscures the underlying source records, becomes stale, and is difficult to validate deterministically.

#### Add project continuity after model integration

Rejected because the first model integration should consume an accepted continuity foundation rather than create a second, model-shaped state system.

#### Let deterministic checks complete work items automatically

Rejected for the first implementation because a passing check may prove only one acceptance condition, not the full work item or user intent.

## Acceptance

This decision is implemented only when the normative project-continuity specification and acceptance suite are merged, the roadmap reflects the required order, and later implementation passes the named project-continuity tests.
