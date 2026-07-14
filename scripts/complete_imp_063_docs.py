"""Apply deterministic IMP-063 roadmap and public-status updates."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"ERROR: {label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)


def update_roadmap() -> None:
    path = ROOT / "docs" / "spec" / "09-development-roadmap.md"
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "- IMP-030 through IMP-062;",
        "- IMP-030 through IMP-063;",
        "completed implementation range",
    )
    text = replace_once(
        text,
        "bounded imported conversation context replay through IMP-061, and the exact-commit imported-context replay real-machine acceptance harness through IMP-062.",
        "bounded imported conversation context replay through IMP-061, the exact-commit imported-context replay real-machine acceptance harness through IMP-062, and the bounded local writing workflow through IMP-063.",
        "completed implementation summary",
    )
    text = replace_once(
        text,
        "- Phase 6 local AI portability and daily-use integration is in progress through IMP-062;",
        "- Phase 6 local AI portability and daily-use integration is in progress through IMP-063;",
        "current Phase 6 implementation point",
    )

    old_allocation = """- IMP-062 adds an exact-commit primary Intel Mac acceptance runner, deterministic synthetic ChatGPT-format source, injected no-socket CI mode, fixed-loopback real Ollama mode, strict privacy-safe evidence schema, and a private-machine runbook for the IMP-061 replay extension;
- IMP-062 is assigned to Issue #200;
- the IMP-061/IMP-062 cross-runtime replay extension passes at both `ci` and `real-machine` evidence levels; accepted privacy-safe evidence is stored at `docs/testing/results/IMP-062-primary-intel-mac-2026-07-12.json` and is bound to exact implementation commit `65f3b5e9ac8c9961c7ec2a152dfdfbb637386e93`;
- the next bounded implementation receives IMP-063 only when a new implementation issue is opened;
"""
    new_allocation = """- IMP-062 adds an exact-commit primary Intel Mac acceptance runner, deterministic synthetic ChatGPT-format source, injected no-socket CI mode, fixed-loopback real Ollama mode, strict privacy-safe evidence schema, and a private-machine runbook for the IMP-061 replay extension;
- IMP-062 is assigned to Issue #200;
- the IMP-061/IMP-062 cross-runtime replay extension passes at both `ci` and `real-machine` evidence levels; accepted privacy-safe evidence is stored at `docs/testing/results/IMP-062-primary-intel-mac-2026-07-12.json` and is bound to exact implementation commit `65f3b5e9ac8c9961c7ec2a152dfdfbb637386e93`;
- IMP-063 adds the first bounded daily-use workflow with explicit `draft`, `revise`, and `summarize` modes, deterministic task rendering, source text isolated as data-only `external_content`, and unchanged canonical local conversation persistence;
- IMP-063 is assigned to Issue #204;
- the next bounded implementation receives IMP-064 only when a new implementation issue is opened;
"""
    text = replace_once(
        text,
        old_allocation,
        new_allocation,
        "current IMP-063 allocation",
    )

    marker = "Daily-use work may then expand writing, editing, summarization, translation, planning, memory review, project and decision workflows, work-item proposals, portability review, accessibility, error clarity, Lite performance, and soak testing."
    section = """### IMP-063 — Bounded local writing workflow

Status: implemented with deterministic synthetic CI evidence; separate exact-commit primary Intel Mac daily-use evidence is not yet claimed.

Implemented the first bounded Phase 6 daily-use workflow above the accepted non-streaming local conversation path. The workflow supports exactly three explicit modes: `draft`, `revise`, and `summarize`.

The current user request is deterministically rendered as the only task-authority instruction. `draft` receives no source text. `revise` and `summarize` require one explicitly supplied non-blank source text, store it as an immutable `external_content` instruction origin, and pass it only through `untrusted_content`. The source text is never concatenated into the current user instruction, cannot authorize the task, and cannot create policy, permission, capability, credential, confirmed memory, confirmed fact, project state, work completion, procedure approval, checkpoint confirmation, or model binding.

The workflow validates exact mode and source-presence rules, request and source character limits, target conversation and parent integrity, event capacity, exact active binding and adapter declaration, duplicate turn operations, and deterministic duplicate source preparation before runtime execution. It delegates execution and persistence to the unchanged `LocalConversationService`, preserving the accepted user/context/assistant graph on completion and user/context/error graph on runtime failure, cancellation, or timeout.

The content-free result contains only mode, source counts, character counts, canonical event IDs, binding/runtime/model manifest IDs, runtime ID, outcome, failure code, prompt-injection finding count, and secret-redaction count. It excludes the request, source, generated response, native model name, private path, username, hostname, credential, and secret value.

Synthetic integration covers all three modes, deterministic task rendering, source-channel separation, hostile source instructions, prompt-injection visibility, invalid combinations, duplicate denial, resource limits, canonical runtime failure, and result privacy. Standard CI provides Ubuntu, macOS, and Windows evidence.

IMP-063 does not establish translation, automatic or semantic retrieval, embeddings, vector search, confirmed-memory retrieval, project or Resume Bundle context selection, attachments, multimodal input, streaming workflow output, arbitrary file publication, tools, cloud fallback, target-specific export, native application history discovery, automatic background operation, the complete Phase 6 gate, or stable general anti-lock-in.

Subsequent daily-use work may expand translation, planning, explicit memory review, explicit project and decision context selection, work-item proposals, portability review, accessibility, error clarity, Lite performance, and soak testing."""
    text = replace_once(text, marker, section, "IMP-063 roadmap section")

    old_immediate = """After accepted IMP-062 imported-context replay real-machine evidence, the immediate order is:

1. retain PORT-014 as `pass` only within the accepted bounded IMP-059/IMP-060 selected-history migration boundary and keep its material-loss limitations visible;
2. retain PORT-013 as `pass` within both the accepted IMP-057 migration boundary and the accepted IMP-061/IMP-062 imported-context replay extension, without broadening either result beyond its documented limits;
3. allocate IMP-063 only when a new bounded implementation issue is opened; ZIP ingestion, attachment bytes, target-specific export, cloud credentials, tools, automatic cloud fallback, and unrelated daily-use features remain separate work;
4. continue Phase 6 daily-use integration and independently required portability work without weakening the Phase 3 safety boundary or Phase 4A/4B canonical state contracts;
5. keep the complete Phase 6 gate and stable general anti-lock-in incomplete until their independent remaining requirements pass.
"""
    new_immediate = """After IMP-063 bounded local writing workflow, the immediate order is:

1. retain PORT-014 as `pass` only within the accepted bounded IMP-059/IMP-060 selected-history migration boundary and keep its material-loss limitations visible;
2. retain PORT-013 as `pass` within both the accepted IMP-057 migration boundary and the accepted IMP-061/IMP-062 imported-context replay extension, without broadening either result beyond its documented limits;
3. use the IMP-063 task-versus-material separation as the required boundary for later explicit memory, project, decision, and Resume Bundle context selection;
4. allocate IMP-064 only when a new bounded implementation issue is opened; translation, automatic retrieval, attachments, target-specific export, cloud credentials, tools, and automatic cloud fallback remain separate work;
5. continue Phase 6 daily-use integration and independently required portability work without weakening the Phase 3 safety boundary or Phase 4A/4B canonical state contracts;
6. keep the complete Phase 6 gate and stable general anti-lock-in incomplete until their independent remaining requirements pass.
"""
    text = replace_once(text, old_immediate, new_immediate, "immediate work")
    path.write_text(text, encoding="utf-8")


def update_status() -> None:
    path = ROOT / "website" / "project-status.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    phase = data.get("phase")
    if not isinstance(phase, dict) or phase.get("next_implementation") != 63:
        raise SystemExit("ERROR: expected IMP-063 as current next implementation")
    phase["next_implementation"] = 64
    data["model_runtime"]["message"] = (
        "Phase 6 is in progress through IMP-063. Offline Ollama session import, "
        "explicit text-only loopback capture, the accepted bounded local-portability "
        "migration drill, the deterministic shutdown escape bundle, bounded ChatGPT "
        "selected-history import, imported-context replay with accepted primary Intel "
        "Mac evidence, and the first bounded local draft/revise/summarize workflow are "
        "implemented. Writing source text remains separate data-only untrusted content, "
        "while the user request remains the only task instruction. Translation, automatic "
        "retrieval, explicit memory/project context selection, attachments, tools, the "
        "complete Phase 6 gate, target-specific application replacement, and stable "
        "general anti-lock-in remain incomplete."
    )
    data["last_reviewed"] = "2026-07-14"
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def update_checker() -> None:
    path = ROOT / "scripts" / "check-public-site-status.mjs"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        """    status.phase?.started_by_implementation === 55 &&
    status.phase?.next_implementation === 63,
  "project-status.json must mark Phase 6 in progress through IMP-062 with IMP-063 next",
);
""",
        """    status.phase?.started_by_implementation === 55 &&
    status.phase?.next_implementation === 64,
  "project-status.json must mark Phase 6 in progress through IMP-063 with IMP-064 next",
);
""",
        "project status implementation point",
    )
    text = replace_once(
        text,
        """expect(
  roadmap.includes("### IMP-062 — Primary Intel Mac imported-context replay acceptance"),
  "roadmap must record the IMP-062 real-machine acceptance boundary",
);
expect(
  roadmap.includes("the next bounded implementation receives IMP-063 only when a new implementation issue is opened"),
  "roadmap must identify IMP-063 as the next unallocated implementation identifier",
);
""",
        """expect(
  roadmap.includes("### IMP-062 — Primary Intel Mac imported-context replay acceptance"),
  "roadmap must record the IMP-062 real-machine acceptance boundary",
);
expect(
  roadmap.includes("### IMP-063 — Bounded local writing workflow"),
  "roadmap must record the IMP-063 local writing workflow boundary",
);
expect(
  roadmap.includes("the next bounded implementation receives IMP-064 only when a new implementation issue is opened"),
  "roadmap must identify IMP-064 as the next unallocated implementation identifier",
);
""",
        "roadmap IMP-063 checker",
    )
    text = replace_once(
        text,
        """  roadmap.includes(
    "After accepted IMP-062 imported-context replay real-machine evidence, the immediate order is:",
  ),
  "roadmap must record accepted IMP-062 evidence and remaining Phase 6 work",
);
""",
        """  roadmap.includes(
    "After IMP-063 bounded local writing workflow, the immediate order is:",
  ),
  "roadmap must record IMP-063 and remaining Phase 6 work",
);
""",
        "immediate work checker",
    )
    path.write_text(text, encoding="utf-8")


def main() -> None:
    update_roadmap()
    update_status()
    update_checker()
    print("IMP-063 documentation and public status updates applied")


if __name__ == "__main__":
    main()
