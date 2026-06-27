from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"missing replacement target: {label}")
    return text.replace(old, new, 1)


def update_roadmap() -> None:
    path = ROOT / "docs/spec/09-development-roadmap.md"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "- IMP-030 through IMP-050;",
        "- IMP-030 through IMP-051;",
        "completed implementation range",
    )
    text = replace_once(
        text,
        "a loopback-only Ollama adapter, and authoritative runtime/model manifests with explicit bindings, verified backup",
        "a loopback-only Ollama adapter, authoritative runtime/model manifests with explicit bindings, and a canonical non-streaming local conversation path through explicit active bindings, verified backup",
        "completed capability summary",
    )
    text = replace_once(
        text,
        """- IMP-050 performs no runtime installation, model download, inference, automatic activation, automatic fallback execution, or capability grant;
- no runtime or model is connected and canonical local conversation receives IMP-051 when opened;
- model execution must continue through the Phase 3 safety boundary and the Phase 4A/4B canonical state contracts.""",
        """- IMP-050 performs no runtime installation, model download, inference, automatic activation, automatic fallback execution, or capability grant;
- IMP-051 implements the first canonical non-streaming local conversation turn through one explicit active binding and `LocalRuntimeBoundary.generate`;
- IMP-051 revalidates exact binding, runtime manifest, model manifest, and adapter declaration state before every call, packages context through the instruction-origin, prompt-injection, and secret boundaries, and persists managed user, context-snapshot, assistant, or bounded error artifacts and events;
- IMP-051 keeps runtime output data-only and non-authoritative, rejects duplicate operation IDs, and rolls back newly created records and managed artifacts after persistence failure;
- IMP-051 adds no schema migration or State Package category and has fake-adapter CI evidence only; no real runtime or model evidence is accepted yet;
- explicit model switching and local fallback execution receive IMP-052 when opened;
- model execution must continue through the Phase 3 safety boundary and the Phase 4A/4B canonical state contracts.""",
        "current IMP-051 implementation point",
    )
    text = replace_once(
        text,
        "Status: in progress through IMP-050.",
        "Status: in progress through IMP-051.",
        "Phase 5 status",
    )
    text = replace_once(
        text,
        """### Canonical local conversation path

Implement local API and CLI conversation using only the Phase 4A canonical conversation and event records and Phase 4B project-continuity views where requested.

Required properties:

- scoped state retrieval;
- response provenance;
- separate provider, application, interface, runtime, model, and operation attribution;
- no provider-native object as authoritative state;
- no automatic durable memory creation;
- no direct model capability execution;
- no automatic work completion, procedure approval, blocker clearing, or checkpoint confirmation;
- model proposals pass through the safety boundary.""",
        """### IMP-051 — Canonical local conversation execution

Status: complete in code; real-runtime evidence is deferred to the integrated drill.

Implemented one bounded non-streaming local turn through an explicit active binding, exact manifest and adapter declaration revalidation, immutable current-user instruction origin, deterministic prompt-defense packaging, one `LocalRuntimeBoundary.generate` call, managed message and context-snapshot artifacts, canonical user/context/assistant/error events, bounded result identifiers, duplicate-operation rejection, and cleanup after persistence failure.

Runtime output is stored as `runtime_output`, remains data-only and non-authoritative, and cannot create durable memory, execute capabilities, grant permission, complete work, approve procedures, clear blockers, confirm checkpoints, or mutate project state. Tests use injected fake adapters and perform no real network request or runtime process launch.""",
        "IMP-051 roadmap section",
    )
    text = replace_once(
        text,
        """The required order after IMP-050 is:

1. schedule canonical local conversation through the IMP-048 contract and Phase 3 safety boundary as IMP-051;
2. implement scoped state retrieval, response provenance, canonical conversation/event persistence, and non-authoritative model proposals;
3. implement explicit model switching and local fallback execution, then prove rollback without unrelated state rewrite;
4. run the network-disabled real-runtime drill before making a local-inference release claim;
5. prove a real local AI migration path before provider-specific cloud portability becomes a primary claim.""",
        """The required order after IMP-051 is:

1. schedule explicit model switching and local fallback execution as IMP-052;
2. implement user-directed active-binding changes, fallback selection or offer, smoke-test failure handling, previous-binding retention, and scope-local rollback without automatic cloud access;
3. add bounded user-visible streaming only after canonical non-streaming persistence and fallback semantics remain intact;
4. run the network-disabled real-runtime drill before making a local-inference release claim;
5. prove a real local AI migration path before provider-specific cloud portability becomes a primary claim.""",
        "immediate work",
    )
    path.write_text(text, encoding="utf-8")


def update_status() -> None:
    path = ROOT / "website/project-status.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["phase"]["next_implementation"] = 52
    payload["model_runtime"] = {
        "connected": False,
        "message": (
            "IMP-051 implements the first canonical non-streaming local conversation path "
            "through explicit active bindings. No real runtime or model evidence is accepted; "
            "explicit switching and local fallback remain next."
        ),
    }
    payload["last_reviewed"] = "2026-06-27"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def update_checker() -> None:
    path = ROOT / "scripts/check-public-site-status.mjs"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "status.phase?.next_implementation === 51",
        "status.phase?.next_implementation === 52",
        "public next implementation",
    )
    text = replace_once(
        text,
        '"project-status.json must mark Phase 5 in progress from IMP-048 with IMP-051 next"',
        '"project-status.json must mark Phase 5 in progress from IMP-048 with IMP-052 next"',
        "public status message",
    )
    text = replace_once(
        text,
        '''expect(
  roadmap.includes("canonical local conversation receives IMP-051 when opened"),
  "roadmap must identify IMP-051 as the next implementation identifier",
);''',
        '''expect(
  roadmap.includes("IMP-051 implements the first canonical non-streaming local conversation turn"),
  "roadmap must record the IMP-051 canonical local conversation path",
);
expect(
  roadmap.includes("explicit model switching and local fallback execution receive IMP-052 when opened"),
  "roadmap must identify IMP-052 as the next implementation identifier",
);''',
        "IMP-051 and IMP-052 roadmap checks",
    )
    path.write_text(text, encoding="utf-8")


def update_implementation_record() -> None:
    path = ROOT / "docs/implementation/imp-051-canonical-local-conversation.md"
    path.write_text(
        """# IMP-051 — Canonical local conversation execution

## Status

Implemented and validated against the IMP-048 runtime contract, the IMP-050 explicit binding foundation, and the completed Phase 3 safety boundary.

IMP-051 adds the first canonical non-streaming local conversation turn. It does not claim that a real runtime or model is installed, connected, or usable on the project owner's machine.

## Turn flow

`LocalConversationService.execute_turn` performs one bounded turn:

1. reject read-only state, invalid input, duplicate operation IDs, missing conversations, and invalid parent events;
2. resolve exactly one active binding by scope;
3. revalidate the exact binding, RuntimeManifestRecord, ModelManifestRecord, and adapter declaration state;
4. create an immutable `current_user_instruction` InstructionOriginRecord and require task authority outside the model;
5. package explicitly selected context through `PromptDefenseService`;
6. render a deterministic bounded JSON prompt with authority channels kept separate;
7. call only `LocalRuntimeBoundary.generate`;
8. validate the normalized completed or closed-failure result;
9. persist managed user and context-snapshot artifacts plus an assistant artifact only after valid completed output;
10. persist canonical user, context-snapshot, assistant, or error events and append a bounded audit entry.

## Binding and adapter validation

Execution requires one explicit active binding. The service rechecks:

- binding scope and active state;
- bound runtime and model manifest identities and exact revisions;
- active, verified, compatible, and non-quarantined manifest state through the IMP-050 resolver;
- adapter identity, version, runtime class, connection kind, operation set, offline declaration, cloud-fallback declaration, automatic-download declaration, and declaration fingerprint;
- a bounded adapter-facing runtime-private model locator.

Missing, stale, archived, quarantined, deprecated, unavailable, incompatible, ambiguous, or declaration-mismatched state fails before a model call. Runtime inventory cannot select a model automatically. IMP-051 performs no automatic switching or fallback.

## Prompt context and trust boundary

The current user message is recorded as `current_user_instruction` with task authority limited to the current turn. Additional context retains its accepted origin and effective authority classification.

The renderer preserves separate channels for:

- system policy;
- current user instruction;
- durable user policy;
- user management action;
- untrusted content;
- model proposals;
- unknown origin.

Prompt-injection findings, authority failures, transformations, and secret-redaction counts remain explicit. The rendered prompt is transient and bounded. No repository, state service, secret store, permission service, project service, artifact service, or capability broker is given to the runtime adapter.

## Canonical persistence

A committed turn contains:

- an immutable user-message managed artifact;
- a `user_message` event referencing the user artifact and instruction-origin record;
- an immutable context-snapshot JSON artifact containing record IDs, channel and authority metadata, hashes, finding kinds, redaction counts, binding identity, and exact manifest revisions without message text;
- a `system_context_snapshot` event;
- for valid completed output, an immutable assistant-message artifact and `assistant_message` event;
- for runtime failure, cancellation, timeout, malformed response, resource limit, or secret-bearing output, a bounded `error` event without provider body, exception text, partial output, or assistant artifact.

Managed paths are deterministic workspace-relative paths derived from the canonical conversation ID and a hash of the operation ID.

## Model-output non-authority

Valid model output is also stored as an immutable InstructionOriginRecord with `origin_class=runtime_output`, `actor_type=runtime`, and data-only treatment.

Runtime output cannot automatically:

- create durable memory;
- become policy or a current user instruction;
- grant or change permission;
- invoke a capability or tool;
- confirm a dangerous action;
- complete a work item;
- approve a procedure;
- clear a blocker;
- confirm a project checkpoint;
- mutate project or decision state.

Text resembling any of those actions remains inert model output.

## Failure, idempotency, and rollback

Operation IDs are bounded and must be unused across conversation events, managed artifacts, and instruction-origin records. Reuse is rejected rather than replayed.

A failed, cancelled, timed-out, malformed, oversized, or secret-bearing runtime response never becomes an assistant message. Runtime failures produce closed failure codes only.

If persistence or audit completion fails after records or files are created, the service removes the newly created records transactionally, advances the canonical state revision, deletes the associated managed files, and removes empty turn directories. Incomplete cleanup becomes a dedicated bounded rollback error rather than being hidden.

## State, package, backup, and migration effects

IMP-051 introduces no new authoritative record type and no SQLite migration. Schema version 3 remains current.

The implementation reuses existing:

- InstructionOriginRecord;
- ConversationRecord and ConversationEventRecord;
- managed Artifact records;
- AuditRecord;
- RuntimeManifestRecord, ModelManifestRecord, and ModelBindingRecord.

State Package format v2 and package-v1 read compatibility are unchanged. Existing backup, restore, generic state-package, fresh-process inspection, portability, and project-continuity behavior remains available without a runtime or model.

## Secret and privacy effects

- User and assistant text is stored only in explicit bounded instruction-origin and managed-artifact records with caller-selected sensitivity.
- Context snapshots contain IDs, revisions, authority channels, hashes, finding kinds, and counts rather than prompt or message text.
- Secret-bearing model output is rejected as `invalid_response` and is not persisted as assistant content.
- Result objects, audit metadata, errors, and object representations contain identifiers, counts, and closed codes only.
- Provider response bodies, transport exception text, credentials, private absolute paths, usernames, and hostnames are not emitted.

## Tests

Deterministic injected adapters cover successful persistence, exact active-binding selection, manifest and adapter declaration checks, prompt rendering, origin and authority channels, prompt-injection findings, secret redaction and output rejection, parent validation, duplicate-operation rejection, closed runtime failure, cancellation, timeout, malformed output, resource limits, artifact and state rollback, read-only state, bounded representations, and absence of authority-bearing dependencies.

CI performs no real network request, process launch, runtime installation, model download, or cloud access.

## Deliberate limitations

- No real Ollama request is made.
- No local model is installed or downloaded.
- No user-visible streaming path exists.
- No automatic model selection or fallback occurs.
- No explicit switching UI or CLI exists yet.
- No tool, capability, permission, confirmation, durable-memory, or project-mutation path is connected.
- No primary Intel Mac or network-disabled inference evidence is claimed.

## Next slice

The next bounded Phase 5 slice is explicit model switching and local fallback execution, receiving IMP-052 when opened.

## Issue

Closes #158.
""",
        encoding="utf-8",
    )


def main() -> None:
    update_roadmap()
    update_status()
    update_checker()
    update_implementation_record()


if __name__ == "__main__":
    main()
