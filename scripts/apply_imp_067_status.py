from __future__ import annotations

import json
from pathlib import Path


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement target, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def update_daily_use() -> None:
    path = Path("docs/testing/phase-6-daily-use-matrix.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    value["resume_bundle_context_extension"] = {
        "implementation": "IMP-067",
        "status": "ci-pass",
        "description": (
            "One explicitly selected verified Resume Bundle can provide bounded core "
            "continuity material to local writing as data-only untrusted context without "
            "canonical-state import or native-path disclosure."
        ),
        "pytest_files": [
            "tests/test_imp_066_decision_context_acceptance.py",
            "tests/test_resume_bundle_context_coverage.py",
        ],
        "passed_evidence_levels": ["ci"],
        "required_evidence_levels": ["ci"],
        "selection_mode": "explicit-only",
        "maximum_selected_bundles": 1,
        "automatic_file_search": False,
        "semantic_retrieval": False,
        "model_selected_context": False,
        "canonical_state_import": False,
        "secret_content_allowed": False,
        "context_origin_class": "external_content",
        "context_actor_type": "extractor",
        "context_acquisition_method": "extraction",
        "context_authority_class": "untrusted_data",
        "excluded_member_groups": [
            "HANDOFF.md",
            "checksums",
            "artifact_references",
            "source_references",
            "artifact_bytes",
            "external_source_content",
        ],
        "phase6_gate_complete": False,
        "stable_anti_lock_in_claim": False,
        "implementation_doc": (
            "docs/implementation/imp-067-resume-bundle-writing-context.md"
        ),
    }
    write_json(path, value)


def update_project_status() -> None:
    path = Path("website/project-status.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    value["phase"]["next_implementation"] = 68
    value["model_runtime"]["message"] = (
        "Phase 6 is in progress through IMP-067. Offline Ollama session import, explicit "
        "text-only loopback capture, the accepted bounded local-portability migration "
        "drill, the deterministic shutdown escape bundle, bounded ChatGPT selected-history "
        "import, imported-context replay with accepted primary Intel Mac evidence, and the "
        "bounded local draft/revise/summarize workflow are implemented. The IMP-063/IMP-064 "
        "writing workflow passes at both CI and real-machine evidence levels. IMP-065 adds "
        "explicit confirmed-memory and ProjectRecord context selection, IMP-066 adds explicit "
        "DecisionRecord context selection, and IMP-067 adds one explicit verified Resume "
        "Bundle through a bounded data-only untrusted boundary with CI evidence. Translation, "
        "automatic or semantic retrieval, attachments, tools, the complete Phase 6 gate, "
        "target-specific application replacement, and stable general anti-lock-in remain "
        "incomplete."
    )
    value["last_reviewed"] = "2026-07-23"
    write_json(path, value)


def update_implementation_doc() -> None:
    replace_once(
        Path("docs/implementation/imp-067-resume-bundle-writing-context.md"),
        (
            "Implementation in progress with deterministic synthetic acceptance required "
            "before merge."
        ),
        (
            "Implemented with deterministic synthetic acceptance and successful "
            "cross-platform CI; merge remains required."
        ),
    )


def update_roadmap() -> None:
    path = Path("docs/spec/09-development-roadmap.md")
    replacements = (
        ("- IMP-030 through IMP-066;", "- IMP-030 through IMP-067;"),
        (
            "explicit data-only confirmed-memory and ProjectRecord context selection through "
            "IMP-065, and explicit data-only DecisionRecord context selection through IMP-066.",
            "explicit data-only confirmed-memory and ProjectRecord context selection through "
            "IMP-065, explicit data-only DecisionRecord context selection through IMP-066, "
            "and explicit verified Resume Bundle writing context through IMP-067.",
        ),
        (
            "- Phase 6 local AI portability and daily-use integration is in progress through "
            "IMP-066;",
            "- Phase 6 local AI portability and daily-use integration is in progress through "
            "IMP-067;",
        ),
        (
            "- the IMP-066 decision-context extension passes at the `ci` evidence level and "
            "does not broaden the accepted IMP-064 real-machine result;\n"
            "- the next bounded implementation receives IMP-067 only when a new "
            "implementation issue is opened;",
            "- the IMP-066 decision-context extension passes at the `ci` evidence level and "
            "does not broaden the accepted IMP-064 real-machine result;\n"
            "- IMP-067 adds one explicitly selected verified external Resume Bundle as a "
            "bounded core-continuity snapshot for local writing, with no canonical-state "
            "import, native-path disclosure, automatic search, or excluded-member expansion;\n"
            "- IMP-067 is assigned to Issue #217;\n"
            "- the IMP-067 Resume Bundle context extension passes at the `ci` evidence level "
            "and does not broaden the accepted IMP-064 real-machine result;\n"
            "- the next bounded implementation receives IMP-068 only when a new "
            "implementation issue is opened;",
        ),
        (
            "Subsequent daily-use work may expand translation, planning, explicit Resume "
            "Bundle context selection, work-item proposals, portability review, accessibility, "
            "error clarity, Lite performance, and soak testing.\n\n"
            "## 13. Phase 7 — Optional cloud and multiple models",
            "### IMP-067 — Explicit Resume Bundle writing context\n\n"
            "Status: implemented with deterministic synthetic CI evidence.\n\n"
            "Implemented at most one caller-selected external Resume Bundle path for the "
            "accepted local `draft`, `revise`, and `summarize` workflow. The existing Resume "
            "Bundle v1 verifier runs before any origin or runtime request, and the selected "
            "file is bound to a content-free SHA-256 identity without exposing its native "
            "path.\n\n"
            "Only the bounded core continuity groups enter one deterministic snapshot: "
            "project, checkpoint, active/next/blocked work, decisions, procedures, policies, "
            "and pending validation. HANDOFF text, checksum rows, artifact/source reference "
            "rows, artifact bytes, external source content, and linked-record expansion remain "
            "excluded.\n\n"
            "The snapshot is secret-scanned, shares the existing ten-item and 24,000-character "
            "limits, persists at no lower than sensitive classification, and enters only as "
            "data-only external content through extractor/extraction. Missing, unreadable, "
            "tampered, symlinked, unsupported, oversized, secret-bearing, changed-during-read, "
            "or over-limit bundles fail before runtime and before context-origin creation.\n\n"
            "The content-free result exposes only project ID, source state revision, bundle "
            "SHA-256, member-group count, and character counts. Dedicated acceptance covers "
            "all three writing modes, authority denial, excluded-member proof, failure "
            "preservation, aggregate limits, path privacy, malformed input, and coverage of "
            "fail-closed branches. Standard CI covers Ubuntu, macOS, and Windows.\n\n"
            "IMP-067 does not establish Resume Bundle import into canonical state, shutdown "
            "escape import, automatic or semantic retrieval, embeddings, ranking, translation, "
            "attachments, multimodal input, streaming workflow output, tools, cloud fallback, "
            "target-specific export, complete Phase 6, or stable general anti-lock-in.\n\n"
            "Subsequent daily-use work may expand translation, planning, work-item proposals, "
            "portability review, accessibility, error clarity, Lite performance, and soak "
            "testing.\n\n"
            "## 13. Phase 7 — Optional cloud and multiple models",
        ),
        (
            "After IMP-066 explicit decision context selection, the immediate order is:",
            "After IMP-067 explicit Resume Bundle writing context, the immediate order is:",
        ),
        (
            "3. retain the IMP-063 task-versus-material separation and the IMP-065/IMP-066 "
            "explicit-selection boundary for all later Resume Bundle, document, and retrieval "
            "context;",
            "3. retain the IMP-063 task-versus-material separation and the "
            "IMP-065/IMP-066/IMP-067 explicit-selection and extraction boundaries for all "
            "later document and retrieval context;",
        ),
        (
            "4. retain the accepted IMP-063/IMP-064 local-writing result only within its "
            "documented real-machine draft/revise/summarize boundary, and treat IMP-065/IMP-066 "
            "as separate CI-only context-selection extensions;",
            "4. retain the accepted IMP-063/IMP-064 local-writing result only within its "
            "documented real-machine draft/revise/summarize boundary, and treat "
            "IMP-065/IMP-066/IMP-067 as separate CI-only context extensions;",
        ),
        (
            "5. allocate IMP-067 only when a new bounded implementation issue is opened; "
            "translation, automatic retrieval, Resume Bundle context, attachments, "
            "target-specific export, cloud credentials, tools, and automatic cloud fallback "
            "remain separate work;",
            "5. allocate IMP-068 only when a new bounded implementation issue is opened; "
            "translation, automatic retrieval, attachments, target-specific export, cloud "
            "credentials, tools, and automatic cloud fallback remain separate work;",
        ),
    )
    for old, new in replacements:
        replace_once(path, old, new)


def update_checker() -> None:
    path = Path("scripts/check-public-site-status.mjs")
    replacements = (
        (
            "status.phase?.next_implementation === 67,\n"
            "  \"project-status.json must mark Phase 6 in progress through IMP-066 with "
            "IMP-067 next\",",
            "status.phase?.next_implementation === 68,\n"
            "  \"project-status.json must mark Phase 6 in progress through IMP-067 with "
            "IMP-068 next\",",
        ),
        (
            "status.model_runtime.message.includes(\"through IMP-066\") &&\n"
            "    status.model_runtime.message.includes(\"IMP-065 adds explicit\") &&\n"
            "    status.model_runtime.message.includes(\"IMP-066 adds explicit "
            "DecisionRecord\") &&\n"
            "    status.model_runtime.message.includes(\"passes at both CI and real-machine "
            "evidence levels\"),\n"
            "  \"project-status.json must describe IMP-066 without broadening IMP-064 "
            "evidence\",",
            "status.model_runtime.message.includes(\"through IMP-067\") &&\n"
            "    status.model_runtime.message.includes(\"IMP-065 adds explicit\") &&\n"
            "    status.model_runtime.message.includes(\"IMP-066 adds explicit "
            "DecisionRecord\") &&\n"
            "    status.model_runtime.message.includes(\"IMP-067 adds one explicit verified "
            "Resume Bundle\") &&\n"
            "    status.model_runtime.message.includes(\"passes at both CI and real-machine "
            "evidence levels\"),\n"
            "  \"project-status.json must describe IMP-067 without broadening IMP-064 "
            "evidence\",",
        ),
        (
            "expect(\n"
            "  localWritingPrimary.test_id === \"IMP-064-LOCAL-WRITING-PRIMARY\" &&",
            "expect(\n"
            "  dailyUse.resume_bundle_context_extension?.implementation === \"IMP-067\" &&\n"
            "    dailyUse.resume_bundle_context_extension?.status === \"ci-pass\" &&\n"
            "    JSON.stringify(\n"
            "      dailyUse.resume_bundle_context_extension?.passed_evidence_levels,\n"
            "    ) === JSON.stringify([\"ci\"]) &&\n"
            "    dailyUse.resume_bundle_context_extension?.selection_mode ===\n"
            "      \"explicit-only\" &&\n"
            "    dailyUse.resume_bundle_context_extension?.maximum_selected_bundles === 1 &&\n"
            "    dailyUse.resume_bundle_context_extension?.automatic_file_search === false &&\n"
            "    dailyUse.resume_bundle_context_extension?.semantic_retrieval === false &&\n"
            "    dailyUse.resume_bundle_context_extension?.model_selected_context === false &&\n"
            "    dailyUse.resume_bundle_context_extension?.canonical_state_import === false &&\n"
            "    dailyUse.resume_bundle_context_extension?.secret_content_allowed === false &&\n"
            "    dailyUse.resume_bundle_context_extension?.context_actor_type ===\n"
            "      \"extractor\" &&\n"
            "    dailyUse.resume_bundle_context_extension?.context_acquisition_method ===\n"
            "      \"extraction\" &&\n"
            "    dailyUse.resume_bundle_context_extension?.context_authority_class ===\n"
            "      \"untrusted_data\" &&\n"
            "    dailyUse.resume_bundle_context_extension?.phase6_gate_complete === false &&\n"
            "    dailyUse.resume_bundle_context_extension?.stable_anti_lock_in_claim ===\n"
            "      false &&\n"
            "    dailyUse.resume_bundle_context_extension?.implementation_doc ===\n"
            "      \"docs/implementation/imp-067-resume-bundle-writing-context.md\",\n"
            "  \"IMP-067 Resume Bundle context must remain explicit, bounded, and CI-only\",\n"
            ");\n\n"
            "expect(\n"
            "  localWritingPrimary.test_id === \"IMP-064-LOCAL-WRITING-PRIMARY\" &&",
        ),
        (
            "roadmap.includes(\"### IMP-066 — Explicit decision context selection\"),\n"
            "  \"roadmap must record the IMP-066 explicit decision context boundary\",\n"
            ");\n"
            "expect(\n"
            "  roadmap.includes(\"the next bounded implementation receives IMP-067 only "
            "when a new implementation issue is opened\"),\n"
            "  \"roadmap must identify IMP-067 as the next unallocated implementation "
            "identifier\",\n"
            ");",
            "roadmap.includes(\"### IMP-066 — Explicit decision context selection\"),\n"
            "  \"roadmap must record the IMP-066 explicit decision context boundary\",\n"
            ");\n"
            "expect(\n"
            "  roadmap.includes(\"### IMP-067 — Explicit Resume Bundle writing context\"),\n"
            "  \"roadmap must record the IMP-067 Resume Bundle writing context boundary\",\n"
            ");\n"
            "expect(\n"
            "  roadmap.includes(\"the next bounded implementation receives IMP-068 only "
            "when a new implementation issue is opened\"),\n"
            "  \"roadmap must identify IMP-068 as the next unallocated implementation "
            "identifier\",\n"
            ");",
        ),
        (
            "roadmap.includes(\n"
            "    \"After IMP-066 explicit decision context selection, the immediate order "
            "is:\",\n"
            "  ),\n"
            "  \"roadmap must record IMP-066 and remaining Phase 6 work\",",
            "roadmap.includes(\n"
            "    \"After IMP-067 explicit Resume Bundle writing context, the immediate "
            "order is:\",\n"
            "  ),\n"
            "  \"roadmap must record IMP-067 and remaining Phase 6 work\",",
        ),
    )
    for old, new in replacements:
        replace_once(path, old, new)


def main() -> None:
    update_daily_use()
    update_project_status()
    update_implementation_doc()
    update_roadmap()
    update_checker()
    print("IMP-067 status and roadmap updates applied")


if __name__ == "__main__":
    main()
