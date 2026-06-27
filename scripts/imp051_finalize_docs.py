from __future__ import annotations

import json
import subprocess
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one match in {path}, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "README.md",
    "The safety-boundary implementation sequence runs through IMP-023. Phase 4A is now in progress: IMP-030 established canonical conversation and event contracts, IMP-031 added their persistence, and IMP-032 is the next planned adapter-contract and source-environment foundation. The current position is published through the [live implementation activity endpoint](https://doll.badjoke-lab.com/api/project-status). Phase 4B then establishes Doll State Package v2, ProjectRecord v2, WorkItemRecord, ProcedureRecord, ProjectCheckpointRecord, deterministic status, Resume Bundle, and PROJ acceptance. Local runtime and model work follows both Phase 4 gates and receives the next monotonic implementation identifiers when scheduled. Unused legacy identifiers IMP-024 through IMP-029 are retired and are not reused.",
    "Phases 4A and 4B are complete. Phase 5 is in progress through IMP-051: the runtime-independent adapter contract, loopback-only Ollama adapter, authoritative runtime/model manifests with explicit bindings, and the first canonical non-streaming local conversation turn are implemented. The turn path resolves one explicit active binding, packages context through the accepted instruction-origin, prompt-injection, and secret boundaries, persists managed conversation artifacts and canonical events, and keeps runtime output non-authoritative. CI uses synthetic adapters only; no real runtime or model is connected, and no local-inference release claim is made. The current position is published through the [live implementation activity endpoint](https://doll.badjoke-lab.com/api/project-status). Explicit model switching, local fallback execution, streaming integration, and the network-disabled real-runtime drill remain future bounded work. Unused legacy identifiers IMP-024 through IMP-029 are retired and are not reused.",
)

roadmap = Path("docs/spec/09-development-roadmap.md")
text = roadmap.read_text(encoding="utf-8")
replacements = [
    ("- IMP-030 through IMP-050;", "- IMP-030 through IMP-051;"),
    (
        "- local workspace, SQLite state, migrations, managed artifacts, preferences, policies, permissions, confirmed memory, projects, decisions, state-package v2 export with v1 read compatibility, a versioned authoritative record registry, ProjectRecord v2 with v1 read compatibility, WorkItemRecord v1 lifecycle and dependency integrity, and ProcedureRecord v1 lifecycle and non-authority guarantees, ProjectCheckpointRecord v1 confirmation and freshness, deterministic derived project status, deterministic project-scoped Resume Bundle export, project-continuity transfer and recovery coverage, completed Phase 4B acceptance evidence, a runtime-independent local adapter contract, a loopback-only Ollama adapter, and authoritative runtime/model manifests with explicit bindings, verified backup, restore, continuity acceptance, the model-independent safety boundary, canonical conversation and event state, portability adapter and result records, generic import staging, generic export, reviewed publication, source preservation, idempotency, loss visibility, and Phase 4A acceptance evidence.",
        "- local workspace, SQLite state, migrations, managed artifacts, preferences, policies, permissions, confirmed memory, projects, decisions, state-package v2 export with v1 read compatibility, a versioned authoritative record registry, ProjectRecord v2 with v1 read compatibility, WorkItemRecord v1 lifecycle and dependency integrity, and ProcedureRecord v1 lifecycle and non-authority guarantees, ProjectCheckpointRecord v1 confirmation and freshness, deterministic derived project status, deterministic project-scoped Resume Bundle export, project-continuity transfer and recovery coverage, completed Phase 4B acceptance evidence, a runtime-independent local adapter contract, a loopback-only Ollama adapter, authoritative runtime/model manifests with explicit bindings, and one canonical non-streaming local conversation turn with managed artifacts, deterministic context packaging, closed failure events, and non-authoritative runtime output, verified backup, restore, continuity acceptance, the model-independent safety boundary, canonical conversation and event state, portability adapter and result records, generic import staging, generic export, reviewed publication, source preservation, idempotency, loss visibility, and Phase 4A acceptance evidence.",
    ),
    (
        "- no runtime or model is connected and canonical local conversation receives IMP-051 when opened;\n- model execution must continue through the Phase 3 safety boundary and the Phase 4A/4B canonical state contracts.",
        "- IMP-051 adds the first canonical non-streaming local conversation path through one explicit active binding, exact manifest and adapter revalidation, deterministic prompt packaging, managed user/context/assistant artifacts, canonical user/context/assistant-or-error events, duplicate-operation rejection, and rollback on persistence failure;\n- IMP-051 uses synthetic adapters in CI, grants no model authority, invokes no capability or tool path, and adds no schema migration or State Package format change;\n- no real runtime or model is connected, and no real-machine local-inference evidence is claimed;\n- model execution must continue through the Phase 3 safety boundary and the Phase 4A/4B canonical state contracts.",
    ),
    ("Status: in progress through IMP-050.", "Status: in progress through IMP-051."),
    (
        "### Canonical local conversation path\n\nImplement local API and CLI conversation using only the Phase 4A canonical conversation and event records and Phase 4B project-continuity views where requested.\n\nRequired properties:\n\n- scoped state retrieval;\n- response provenance;\n- separate provider, application, interface, runtime, model, and operation attribution;\n- no provider-native object as authoritative state;\n- no automatic durable memory creation;\n- no direct model capability execution;\n- no automatic work completion, procedure approval, blocker clearing, or checkpoint confirmation;\n- model proposals pass through the safety boundary.",
        "### IMP-051 — Canonical local conversation execution\n\nStatus: complete in code; real-runtime evidence is deferred to the integrated drill.\n\nImplemented one model-independent, non-streaming local turn through `LocalRuntimeBoundary.generate`. The service resolves exactly one explicit active binding, revalidates exact runtime and model manifest revisions and the registered adapter declaration, creates the current user instruction outside the model, packages selected context through prompt-injection and secret controls, and renders one bounded deterministic runtime input.\n\nThe turn persists managed user, context-snapshot, and assistant artifacts plus canonical `user_message`, `system_context_snapshot`, and `assistant_message` or bounded `error` events. Runtime output is also stored as an immutable data-only instruction-origin record and cannot become policy, permission, memory, confirmation, project progress, or a capability request. Duplicate operation IDs fail closed, invalid runtime results do not become assistant messages, and persistence failures roll back newly created records and managed files.\n\nThe existing schema version 3 and State Package v2 remain sufficient. Tests use injected synthetic adapters only and perform no network request, process launch, model download, runtime installation, cloud access, credential retrieval, tool execution, or authoritative project mutation.",
    ),
    (
        "The required order after IMP-050 is:\n\n1. schedule canonical local conversation through the IMP-048 contract and Phase 3 safety boundary as IMP-051;\n2. implement scoped state retrieval, response provenance, canonical conversation/event persistence, and non-authoritative model proposals;\n3. implement explicit model switching and local fallback execution, then prove rollback without unrelated state rewrite;\n4. run the network-disabled real-runtime drill before making a local-inference release claim;\n5. prove a real local AI migration path before provider-specific cloud portability becomes a primary claim.",
        "The required order after IMP-051 is:\n\n1. implement explicit user-controlled model switching and local fallback execution, then prove smoke-test rollback without unrelated state rewrite or cloud access;\n2. add streaming integration only after the canonical non-streaming event and artifact path remains the authoritative committed result;\n3. run the network-disabled real-runtime drill before making a local-inference release claim;\n4. prove model replacement without canonical conversation, project, memory, portability, backup, or recovery loss;\n5. prove a real local AI migration path before provider-specific cloud portability becomes a primary claim.",
    ),
]
for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"roadmap replacement expected one match, found {count}: {old[:80]!r}")
    text = text.replace(old, new, 1)
roadmap.write_text(text, encoding="utf-8")

status_path = Path("website/project-status.json")
status = json.loads(status_path.read_text(encoding="utf-8"))
status["phase"]["next_implementation"] = 52
status["model_runtime"] = {
    "connected": False,
    "message": (
        "IMP-051 adds the first canonical non-streaming local conversation path through "
        "explicit active bindings and synthetic runtime evidence. No real runtime or model is "
        "connected; explicit switching, fallback execution, streaming integration, and the "
        "network-disabled drill remain."
    ),
}
status["last_reviewed"] = "2026-06-27"
status_path.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

Path("docs/implementation/imp-051-canonical-local-conversation.md").write_text(
    """# IMP-051 — Canonical local conversation execution

## Status

Complete in code. Full CI passes on Linux, macOS, and Windows with synthetic runtime adapters. No real runtime or model is connected, and no real-machine inference claim is made.

## Turn flow and trust boundary

`LocalConversationService` performs one bounded non-streaming turn. It accepts an existing canonical conversation, one explicit binding scope, a user message, an operation ID, optional parent and context record IDs, and bounded output, timeout, cancellation, and sensitivity settings.

The user instruction is created and authorized outside the model. The model receives only a deterministic transient request. It receives no repository, artifact service, permission store, project service, capability broker, secret store, credential, or private absolute path. The only runtime operation invoked is `LocalRuntimeBoundary.generate`.

## Binding and adapter validation

Before any runtime call, the service resolves exactly one active `ModelBindingRecord` for the requested scope and revalidates the bound runtime and model manifest identities and exact revisions. Both manifests must remain active and verified, and the runtime must remain local-only.

The registered adapter declaration must match the authoritative runtime manifest identity, version, runtime class, connection kind, operation set, offline declaration, cloud-fallback declaration, automatic-download declaration, and declaration fingerprint. Missing, stale, incompatible, quarantined, unavailable, or mismatched state fails closed. There is no automatic model selection, switching, or fallback in this slice.

## Prompt context and secret handling

Each turn creates an immutable `current_user_instruction` record for the user message. Explicitly selected additional records are packaged through `PromptDefenseService`, preserving system policy, current user instruction, durable user policy, user management action, untrusted content, model proposal, and unknown-origin channels.

Untrusted content retains data-only treatment. Prompt-injection findings remain findings rather than authority. Secret-bearing context follows the accepted redaction or denial policy. The rendered request is deterministic, bounded, and free of provider-native authority.

## Canonical persistence

A committed turn contains:

- a managed user-message artifact and `user_message` event;
- a bounded managed context-snapshot artifact and `system_context_snapshot` event;
- either a managed assistant artifact and `assistant_message` event, or a bounded terminal `error` event;
- exact binding, runtime manifest, model manifest, adapter, operation, parent, and content-reference attribution.

Completed runtime text is also stored as an immutable `runtime_output` instruction-origin record. It is data-only and cannot automatically become an instruction, durable policy, confirmation, permission, memory, decision, completed work item, approved procedure, confirmed checkpoint, or capability request.

## Failure, cancellation, rollback, and idempotency

Missing or invalid binding state, adapter mismatch, invalid parent linkage, duplicate context, prompt-size overflow, read-only state, and invalid constructor input fail before an authoritative model result is committed.

Closed runtime failure, cancellation, timeout, resource limit, malformed output, empty output, oversized output, or secret-bearing output does not create an assistant message. It produces a bounded normalized failure and, after the user and context records are accepted, a canonical error event without provider detail or partial model text.

Operation IDs are unique across turn origins, artifacts, and events. Reusing a committed or started operation ID is rejected. If artifact publication, state persistence, or audit completion fails, newly created turn records and managed files are rolled back. Cleanup failure is surfaced as a separate bounded rollback error.

## State, package, backup, and privacy effects

No new authoritative record type is introduced. Schema version 3 and State Package v2 remain unchanged. Existing conversation events, artifacts, instruction-origin records, backup, restore, and fresh-process inspection cover the new turn data.

Public result objects, audit metadata, errors, and context snapshots expose stable identifiers, revisions, hashes, counts, outcomes, and normalized failure codes only. They do not expose prompt text, user text, model output, provider bodies, exception text, credentials, host data, or private paths.

## Validation evidence

CI uses injected fake adapters and deterministic fixtures. It performs no real network request, runtime process launch, model download, runtime installation, cloud request, or credential retrieval. Coverage includes successful persistence, deterministic prompt rendering, exact binding and adapter matching, non-authoritative context, secret handling, prompt-injection findings, completed and closed runtime outcomes, graph relationships, managed artifacts, duplicate operation rejection, parent validation, rollback, read-only state, and static dependency guards.

## Deliberate limitations and next boundary

This slice does not add streaming user-visible output, automatic selection, explicit switching, fallback execution, tools, capabilities, permission or confirmation flows, durable memory publication, project mutation, cloud providers, runtime installation, model download, or real Ollama evidence.

The next bounded Phase 5 work is explicit user-controlled model switching and local fallback execution with smoke-test rollback and no unrelated state rewrite. Streaming integration follows only after the non-streaming canonical event and artifact path remains the committed source of truth. The network-disabled real-runtime drill remains required before any local-inference release claim.

## Issue

Closes #158.
""",
    encoding="utf-8",
)

subprocess.run(["python", "scripts/build_final_spec.py"], check=True)
