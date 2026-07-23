from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one match in {path}, found {count}")
    target.write_text(text.replace(old, new), encoding="utf-8")


def update_implementation_doc() -> None:
    replace_once(
        "docs/implementation/imp-068-explicit-local-translation.md",
        "**Status:** In progress  ",
        "**Status:** Implemented with deterministic synthetic CI evidence  ",
    )


def update_roadmap() -> None:
    path = "docs/spec/09-development-roadmap.md"
    replace_once(path, "- IMP-030 through IMP-067;", "- IMP-030 through IMP-068;")
    replace_once(
        path,
        "and explicit verified Resume Bundle writing context through IMP-067.",
        "explicit verified Resume Bundle writing context through IMP-067, and explicit local translation through IMP-068.",
    )
    replace_once(
        path,
        "- Phase 6 local AI portability and daily-use integration is in progress through IMP-067;",
        "- Phase 6 local AI portability and daily-use integration is in progress through IMP-068;",
    )
    replace_once(
        path,
        "- the IMP-067 Resume Bundle context extension passes at the `ci` evidence level and does not broaden the accepted IMP-064 real-machine result;\n- the next bounded implementation receives IMP-068 only when a new implementation issue is opened;",
        "- the IMP-067 Resume Bundle context extension passes at the `ci` evidence level and does not broaden the accepted IMP-064 real-machine result;\n- IMP-068 adds one explicit `translate` mode with caller-controlled target-language metadata while source text remains data-only `external_content` through the accepted extractor/extraction path;\n- IMP-068 is assigned to Issue #219;\n- the IMP-068 translation extension passes at the `ci` evidence level and does not broaden the accepted IMP-064 real-machine result;\n- the next bounded implementation receives IMP-069 only when a new implementation issue is opened;",
    )
    replace_once(
        path,
        "IMP-067 does not establish Resume Bundle import into canonical state, shutdown escape import, automatic or semantic retrieval, embeddings, ranking, translation, attachments, multimodal input, streaming workflow output, tools, cloud fallback, target-specific export, complete Phase 6, or stable general anti-lock-in.\n\nSubsequent daily-use work may expand translation, planning, work-item proposals, portability review, accessibility, error clarity, Lite performance, and soak testing.",
        "IMP-067 does not establish Resume Bundle import into canonical state, shutdown escape import, automatic or semantic retrieval, embeddings, ranking, translation, attachments, multimodal input, streaming workflow output, tools, cloud fallback, target-specific export, complete Phase 6, or stable general anti-lock-in.\n\n### IMP-068 — Explicit local translation workflow\n\nStatus: implemented with deterministic synthetic CI evidence.\n\nImplemented one explicit `translate` mode for the accepted bounded local writing workflow. The caller supplies one non-blank source text and one bounded target-language label. Draft, revise, and summarize callers remain compatible and reject target-language metadata.\n\nThe target language is normalized and validated before runtime or source-origin creation, then placed only in the deterministic current task-authority payload and content-free result metadata. Source text remains separate immutable `external_content` through `extractor` / `extraction`, reaches the runtime only through `untrusted_content`, and cannot override the caller-selected language or authorize another task.\n\nDedicated acceptance covers successful translation, source/task channel separation, target-language validation, hostile source authority denial, failure before runtime and origin creation, canonical runtime-error persistence, and content-free results. Existing IMP-063 through IMP-067 regression coverage remains active. Standard CI covers Ubuntu, macOS, and Windows.\n\nIMP-068 does not establish automatic source-language detection, translation memory, glossary management, locale-specific formatting, document or attachment translation, PDF or OCR translation, multimodal input, streaming workflow output, semantic retrieval, model-selected context, tools, cloud translation, provider routing, target-specific export, personal translation-quality claims, complete Phase 6, Lite v1.0 completion, or stable general anti-lock-in.\n\nSubsequent daily-use work may expand planning, work-item proposals, portability review, accessibility, error clarity, Lite performance, and soak testing.",
    )


def update_daily_use_matrix() -> None:
    target = ROOT / "docs/testing/phase-6-daily-use-matrix.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    if "translation_extension" in data:
        raise RuntimeError("translation_extension already exists")
    data["translation_extension"] = {
        "implementation": "IMP-068",
        "status": "ci-pass",
        "description": (
            "One explicit local translation mode accepts caller-controlled target-language "
            "metadata while source material remains data-only untrusted external content."
        ),
        "pytest_files": ["tests/test_imp_068_local_translation.py"],
        "passed_evidence_levels": ["ci"],
        "required_evidence_levels": ["ci"],
        "mode": "translate",
        "source_required": True,
        "target_language_required": True,
        "automatic_language_detection": False,
        "source_origin_class": "external_content",
        "source_actor_type": "extractor",
        "source_acquisition_method": "extraction",
        "source_authority_class": "untrusted_data",
        "selected_context_compatible": True,
        "phase6_gate_complete": False,
        "lite_v1_complete": False,
        "stable_anti_lock_in_claim": False,
        "implementation_doc": (
            "docs/implementation/imp-068-explicit-local-translation.md"
        ),
    }
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def update_public_status() -> None:
    target = ROOT / "website/project-status.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    data["phase"]["next_implementation"] = 69
    data["model_runtime"]["message"] = (
        "Phase 6 is in progress through IMP-068. Offline Ollama session import, "
        "explicit text-only loopback capture, the accepted bounded local-portability "
        "migration drill, the deterministic shutdown escape bundle, bounded ChatGPT "
        "selected-history import, imported-context replay with accepted primary Intel "
        "Mac evidence, and the bounded local draft/revise/summarize/translate workflow "
        "are implemented. The IMP-063/IMP-064 writing workflow passes at both CI and "
        "real-machine evidence levels. IMP-065 adds explicit confirmed-memory and "
        "ProjectRecord context selection, IMP-066 adds explicit DecisionRecord context "
        "selection, IMP-067 adds one explicit verified Resume Bundle, and IMP-068 adds "
        "explicit local translation through bounded data-only untrusted boundaries with "
        "CI evidence. Automatic language detection, automatic or semantic retrieval, "
        "attachments, tools, the complete Phase 6 gate, Lite v1.0, target-specific "
        "application replacement, and stable general anti-lock-in remain incomplete."
    )
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def update_public_checker() -> None:
    path = "scripts/check-public-site-status.mjs"
    replace_once(
        path,
        "status.phase?.next_implementation === 68,\n  \"project-status.json must mark Phase 6 in progress through IMP-067 with IMP-068 next\",",
        "status.phase?.next_implementation === 69,\n  \"project-status.json must mark Phase 6 in progress through IMP-068 with IMP-069 next\",",
    )
    replace_once(
        path,
        "status.model_runtime.message.includes(\"through IMP-067\") &&\n    status.model_runtime.message.includes(\"IMP-065 adds explicit\") &&\n    status.model_runtime.message.includes(\"IMP-066 adds explicit DecisionRecord\") &&\n    status.model_runtime.message.includes(\"IMP-067 adds one explicit verified Resume Bundle\") &&\n    status.model_runtime.message.includes(\"passes at both CI and real-machine evidence levels\"),\n  \"project-status.json must describe IMP-067 without broadening IMP-064 evidence\",",
        "status.model_runtime.message.includes(\"through IMP-068\") &&\n    status.model_runtime.message.includes(\"IMP-065 adds explicit\") &&\n    status.model_runtime.message.includes(\"IMP-066 adds explicit DecisionRecord\") &&\n    status.model_runtime.message.includes(\"IMP-067 adds one explicit verified Resume Bundle\") &&\n    status.model_runtime.message.includes(\"IMP-068 adds explicit local translation\") &&\n    status.model_runtime.message.includes(\"passes at both CI and real-machine evidence levels\"),\n  \"project-status.json must describe IMP-068 without broadening IMP-064 evidence\",",
    )
    marker = """  \"IMP-067 Resume Bundle context must remain explicit, bounded, and CI-only\",\n);\n\nexpect(\n  localWritingPrimary.test_id ==="""
    insertion = """  \"IMP-067 Resume Bundle context must remain explicit, bounded, and CI-only\",\n);\n\nexpect(\n  dailyUse.translation_extension?.implementation === \"IMP-068\" &&\n    dailyUse.translation_extension?.status === \"ci-pass\" &&\n    JSON.stringify(dailyUse.translation_extension?.passed_evidence_levels) ===\n      JSON.stringify([\"ci\"]) &&\n    JSON.stringify(dailyUse.translation_extension?.required_evidence_levels) ===\n      JSON.stringify([\"ci\"]) &&\n    dailyUse.translation_extension?.mode === \"translate\" &&\n    dailyUse.translation_extension?.source_required === true &&\n    dailyUse.translation_extension?.target_language_required === true &&\n    dailyUse.translation_extension?.automatic_language_detection === false &&\n    dailyUse.translation_extension?.source_origin_class === \"external_content\" &&\n    dailyUse.translation_extension?.source_actor_type === \"extractor\" &&\n    dailyUse.translation_extension?.source_acquisition_method === \"extraction\" &&\n    dailyUse.translation_extension?.source_authority_class === \"untrusted_data\" &&\n    dailyUse.translation_extension?.selected_context_compatible === true &&\n    dailyUse.translation_extension?.phase6_gate_complete === false &&\n    dailyUse.translation_extension?.lite_v1_complete === false &&\n    dailyUse.translation_extension?.stable_anti_lock_in_claim === false &&\n    dailyUse.translation_extension?.implementation_doc ===\n      \"docs/implementation/imp-068-explicit-local-translation.md\",\n  \"IMP-068 translation must remain explicit, data-only, bounded, and CI-only\",\n);\n\nexpect(\n  localWritingPrimary.test_id ==="""
    replace_once(path, marker, insertion)


def main() -> None:
    update_implementation_doc()
    update_roadmap()
    update_daily_use_matrix()
    update_public_status()
    update_public_checker()
    print("IMP-068 status and roadmap updates applied")


if __name__ == "__main__":
    main()
