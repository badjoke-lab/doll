from __future__ import annotations

import json
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement target, found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def update_matrix() -> None:
    path = Path("docs/testing/phase-6-daily-use-matrix.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    extension = payload["explicit_context_extension"]
    extension["implementation"] = "IMP-066"
    extension["description"] = (
        "Explicit ordered confirmed-memory, ProjectRecord, and DecisionRecord "
        "snapshots can be selected for local writing while remaining data-only "
        "untrusted context."
    )
    extension["selected_record_types"] = [
        "confirmed_memory",
        "project",
        "decision",
    ]
    extension["implementation_doc"] = (
        "docs/implementation/imp-066-explicit-decision-context.md"
    )
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def update_status() -> None:
    path = Path("website/project-status.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["phase"]["next_implementation"] = 67
    payload["model_runtime"]["message"] = (
        "Phase 6 is in progress through IMP-066. Offline Ollama session import, "
        "explicit text-only loopback capture, the accepted bounded local-portability "
        "migration drill, the deterministic shutdown escape bundle, bounded ChatGPT "
        "selected-history import, imported-context replay with accepted primary Intel "
        "Mac evidence, and the bounded local draft/revise/summarize workflow are "
        "implemented. The IMP-063/IMP-064 writing workflow passes at both CI and "
        "real-machine evidence levels. IMP-065 adds explicit confirmed-memory and "
        "ProjectRecord context selection, and IMP-066 adds explicit DecisionRecord "
        "context selection through the same data-only untrusted boundary with CI "
        "evidence. Translation, automatic or semantic retrieval, Resume Bundle "
        "context, attachments, tools, the complete Phase 6 gate, target-specific "
        "application replacement, and stable general anti-lock-in remain incomplete."
    )
    payload["last_reviewed"] = "2026-07-18"
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def update_checker() -> None:
    path = Path("scripts/check-public-site-status.mjs")
    replace_once(
        path,
        "    status.phase?.started_by_implementation === 55 &&\n"
        "    status.phase?.next_implementation === 66,\n"
        '  "project-status.json must mark Phase 6 in progress through IMP-065 with IMP-066 next",',
        "    status.phase?.started_by_implementation === 55 &&\n"
        "    status.phase?.next_implementation === 67,\n"
        '  "project-status.json must mark Phase 6 in progress through IMP-066 with IMP-067 next",',
    )
    replace_once(
        path,
        '  status.model_runtime.message.includes("through IMP-065") &&\n'
        '    status.model_runtime.message.includes("IMP-065 adds explicit") &&\n'
        '    status.model_runtime.message.includes("passes at both CI and real-machine evidence levels"),\n'
        '  "project-status.json must describe IMP-065 without broadening IMP-064 evidence",',
        '  status.model_runtime.message.includes("through IMP-066") &&\n'
        '    status.model_runtime.message.includes("IMP-065 adds explicit") &&\n'
        '    status.model_runtime.message.includes("IMP-066 adds explicit DecisionRecord") &&\n'
        '    status.model_runtime.message.includes("passes at both CI and real-machine evidence levels"),\n'
        '  "project-status.json must describe IMP-066 without broadening IMP-064 evidence",',
    )
    replace_once(
        path,
        '  dailyUse.explicit_context_extension?.implementation === "IMP-065" &&',
        '  dailyUse.explicit_context_extension?.implementation === "IMP-066" &&',
    )
    replace_once(
        path,
        "    dailyUse.explicit_context_extension?.secret_records_allowed === false &&\n"
        "    dailyUse.explicit_context_extension?.context_origin_class ===",
        "    dailyUse.explicit_context_extension?.secret_records_allowed === false &&\n"
        "    JSON.stringify(dailyUse.explicit_context_extension?.selected_record_types) ===\n"
        '      JSON.stringify(["confirmed_memory", "project", "decision"]) &&\n'
        "    dailyUse.explicit_context_extension?.context_origin_class ===",
    )
    replace_once(
        path,
        "    dailyUse.explicit_context_extension?.implementation_doc ===\n"
        '      "docs/implementation/imp-065-explicit-writing-context.md",\n'
        '  "IMP-065 explicit writing context must remain bounded and CI-only",',
        "    dailyUse.explicit_context_extension?.implementation_doc ===\n"
        '      "docs/implementation/imp-066-explicit-decision-context.md",\n'
        '  "IMP-066 explicit decision context must remain bounded and CI-only",',
    )


def update_roadmap() -> None:
    path = Path("docs/spec/09-development-roadmap.md")
    replace_once(path, "IMP-030 through IMP-065", "IMP-030 through IMP-066")
    replace_once(
        path,
        "and explicit data-only confirmed-memory and ProjectRecord context selection through IMP-065.",
        "explicit data-only confirmed-memory and ProjectRecord context selection through IMP-065, "
        "and explicit data-only DecisionRecord context selection through IMP-066.",
    )
    replace_once(
        path,
        "Phase 6 local AI portability and daily-use integration is in progress through IMP-065;",
        "Phase 6 local AI portability and daily-use integration is in progress through IMP-066;",
    )
    replace_once(
        path,
        "- the IMP-065 explicit-context extension passes at the `ci` evidence level and does not broaden the accepted IMP-064 real-machine result;\n"
        "- the next bounded implementation receives IMP-066 only when a new implementation issue is opened;",
        "- the IMP-065 explicit-context extension passes at the `ci` evidence level and does not broaden the accepted IMP-064 real-machine result;\n"
        "- IMP-066 extends the explicit context boundary to active non-secret DecisionRecords with deterministic revision-pinned snapshots and no linked-record expansion;\n"
        "- IMP-066 is assigned to Issue #213;\n"
        "- the IMP-066 decision-context extension passes at the `ci` evidence level and does not broaden the accepted IMP-064 real-machine result;\n"
        "- the next bounded implementation receives IMP-067 only when a new implementation issue is opened;",
    )
    replace_once(
        path,
        "IMP-065 does not establish automatic or semantic retrieval, embeddings, vector search, ranking, model-selected context, decision or Resume Bundle context, translation, attachments, multimodal input, streaming workflow output, tools, capability execution, cloud portability or fallback, target-specific export, complete Phase 6, or stable general anti-lock-in.\n\n"
        "Subsequent daily-use work may expand translation, planning, explicit decision and Resume Bundle context selection, work-item proposals, portability review, accessibility, error clarity, Lite performance, and soak testing.",
        "IMP-065 does not establish automatic or semantic retrieval, embeddings, vector search, ranking, model-selected context, decision or Resume Bundle context, translation, attachments, multimodal input, streaming workflow output, tools, capability execution, cloud portability or fallback, target-specific export, complete Phase 6, or stable general anti-lock-in.\n\n"
        "### IMP-066 — Explicit decision context selection\n\n"
        "Status: implemented with deterministic synthetic CI evidence.\n\n"
        "Implemented explicit ordered selection of active DecisionRecords for the accepted local `draft`, `revise`, and `summarize` workflow. Selected decisions use the same bounded revision-pinned snapshot, sensitivity, external-content, retriever/retrieval, untrusted-data, and data-only boundary established by IMP-065.\n\n"
        "Decision snapshots contain only the selected record ID and revision, decision text, reason, decision status, decision time, alternatives, constraints, review date, supersedes ID, and project ID. Linked memories, artifacts, superseded decisions, and projects are not expanded automatically.\n\n"
        "Missing, wrong-type, archived, duplicate, secret-classified, oversized, or over-limit decision selections fail before any context origin or runtime request. Runtime failure preserves DecisionRecord revisions. The current user request remains the only task authority, and selected decisions cannot accept, reverse, supersede, or mutate decisions or related project state.\n\n"
        "The content-free result adds only selected DecisionRecord IDs and revisions. Dedicated synthetic acceptance covers data-only placement, authority denial, hostile embedded instructions, invalid-selection rejection before runtime, revision preservation on runtime failure, compatibility with existing memory/project selection, and result privacy. Standard CI covers Ubuntu, macOS, and Windows.\n\n"
        "IMP-066 does not establish Resume Bundle context, automatic or semantic retrieval, embeddings, vector search, ranking, model-selected context, translation, attachments, multimodal input, streaming workflow output, tools, capability execution, cloud portability or fallback, target-specific export, complete Phase 6, or stable general anti-lock-in.\n\n"
        "Subsequent daily-use work may expand translation, planning, explicit Resume Bundle context selection, work-item proposals, portability review, accessibility, error clarity, Lite performance, and soak testing.",
    )
    replace_once(
        path,
        "After IMP-065 explicit memory and project context selection, the immediate order is:",
        "After IMP-066 explicit decision context selection, the immediate order is:",
    )
    replace_once(
        path,
        "3. retain the IMP-063 task-versus-material separation and the IMP-065 explicit-selection boundary for all later decision, Resume Bundle, document, and retrieval context;\n"
        "4. retain the accepted IMP-063/IMP-064 local-writing result only within its documented real-machine draft/revise/summarize boundary, and treat IMP-065 as a separate CI-only context-selection extension;\n"
        "5. allocate IMP-066 only when a new bounded implementation issue is opened; translation, automatic retrieval, decision and Resume Bundle context, attachments, target-specific export, cloud credentials, tools, and automatic cloud fallback remain separate work;",
        "3. retain the IMP-063 task-versus-material separation and the IMP-065/IMP-066 explicit-selection boundary for all later Resume Bundle, document, and retrieval context;\n"
        "4. retain the accepted IMP-063/IMP-064 local-writing result only within its documented real-machine draft/revise/summarize boundary, and treat IMP-065/IMP-066 as separate CI-only context-selection extensions;\n"
        "5. allocate IMP-067 only when a new bounded implementation issue is opened; translation, automatic retrieval, Resume Bundle context, attachments, target-specific export, cloud credentials, tools, and automatic cloud fallback remain separate work;",
    )


def main() -> None:
    update_matrix()
    update_status()
    update_checker()
    update_roadmap()
    print("IMP-066 status and roadmap updates applied")


if __name__ == "__main__":
    main()
