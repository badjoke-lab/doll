# ruff: noqa: E501
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
        "docs/implementation/imp-070-explicit-local-portability-review.md",
        "**Status:** In progress",
        "**Status:** Implemented with deterministic synthetic CI evidence",
    )


def update_roadmap() -> None:
    path = "docs/spec/09-development-roadmap.md"
    replace_once(path, "- IMP-030 through IMP-069;", "- IMP-030 through IMP-070;")
    replace_once(
        path,
        "explicit local translation through IMP-068, and bounded local work-item proposals through IMP-069.",
        "explicit local translation through IMP-068, bounded local work-item proposals through IMP-069, and explicit local portability review through IMP-070.",
    )
    replace_once(
        path,
        "- Phase 6 local AI portability and daily-use integration is in progress through IMP-069;",
        "- Phase 6 local AI portability and daily-use integration is in progress through IMP-070;",
    )
    replace_once(
        path,
        "- the IMP-069 work-item proposal extension passes at the `ci` evidence level and does not broaden the accepted IMP-064 real-machine result;\n- the next bounded implementation receives IMP-070 only when a new implementation issue is opened;",
        "- the IMP-069 work-item proposal extension passes at the `ci` evidence level and does not broaden the accepted IMP-064 real-machine result;\n- IMP-070 adds one explicit local portability review turn over one caller-selected import batch, its exact linked mapping report, and only the linked portability-loss records, with no original-source read or record mutation;\n- IMP-070 is assigned to Issue #223;\n- the IMP-070 portability review extension passes at the `ci` evidence level and does not broaden the accepted IMP-057, IMP-062, or IMP-064 real-machine results;\n- the next bounded implementation receives IMP-071 only when a new implementation issue is opened;",
    )
    replace_once(
        path,
        "IMP-069 does not establish multiple proposals per turn, dependency graphs, automatic acceptance, automatic execution, blocker mutation, procedure or checkpoint generation, semantic retrieval, attachments, tools, cloud planning, external issue trackers, complete Phase 6, Lite v1.0 completion, or stable general anti-lock-in.\n\nSubsequent daily-use work may expand portability review, accessibility, error clarity, Lite performance, and soak testing.",
        "IMP-069 does not establish multiple proposals per turn, dependency graphs, automatic acceptance, automatic execution, blocker mutation, procedure or checkpoint generation, semantic retrieval, attachments, tools, cloud planning, external issue trackers, complete Phase 6, Lite v1.0 completion, or stable general anti-lock-in.\n\n### IMP-070 — Explicit local portability review workflow\n\nStatus: implemented with deterministic synthetic CI evidence.\n\nImplemented one bounded local-model review turn over one caller-selected active ImportBatchRecord, its exact linked import-direction MappingReportRecord, and only the PortabilityLossRecords explicitly named by that report. Missing, wrong-type, archived, secret, mismatched, excessive, oversized, secret-like, duplicate, unavailable, or changed-during-read selections fail before runtime execution and before context-origin creation.\n\nThe deterministic review snapshot contains only revision-pinned batch counts, mapping counts, fidelity status, and bounded loss category, severity, description, preservation, recoverability, materiality, and required-user-action fields. Original source bytes, source payloads, canonical conversation content, source root hashes, source-object IDs, quarantine details, managed paths, native model names, credentials, and secret values remain excluded. The snapshot enters only as data-only `external_content` through `retriever` / `retrieval`; the current user request remains the only task authority.\n\nThe workflow cannot approve publication, retry or roll back imports, mutate portability or project records, claim remediation completion, select another binding, execute tools or capabilities, or access network or cloud paths. Runtime failure preserves selected revisions and uses the unchanged canonical user/context/error graph. The public result remains content-free. Dedicated acceptance covers linked-only selection, task/material separation, hostile selected text, invalid records and requests, secret rejection, runtime failure, duplicate denial, immutability, and result privacy. Standard CI covers Ubuntu, macOS, and Windows.\n\nIMP-070 does not establish automatic batch discovery, ranking, semantic retrieval, model-selected records, original-source inspection, source-payload inspection, canonical replay, quarantine-detail review, automatic remediation, retry or rollback execution, publication approval, target-specific export, provider round-trip verification, attachments, PDF/OCR, tools, cloud review, external issue trackers, complete Phase 6, Lite v1.0 completion, or stable general anti-lock-in.\n\nSubsequent daily-use work may expand accessibility, error clarity, Lite performance, and soak testing.",
    )


def update_daily_use_matrix() -> None:
    target = ROOT / "docs/testing/phase-6-daily-use-matrix.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    if "portability_review_extension" in data:
        raise RuntimeError("portability_review_extension already exists")
    data["portability_review_extension"] = {
        "implementation": "IMP-070",
        "status": "ci-pass",
        "description": (
            "One caller-selected import batch, its exact linked mapping report, and only "
            "linked portability losses can be explained locally as bounded data-only "
            "untrusted context without original-source reads or record mutation."
        ),
        "pytest_files": ["tests/test_imp_070_local_portability_review.py"],
        "passed_evidence_levels": ["ci"],
        "required_evidence_levels": ["ci"],
        "selection_mode": "explicit-only",
        "selected_record_types": [
            "portability_import_batch",
            "portability_mapping_report",
            "portability_loss",
        ],
        "exact_link_resolution": True,
        "original_source_read": False,
        "source_payload_read": False,
        "automatic_retrieval": False,
        "semantic_retrieval": False,
        "model_selected_context": False,
        "context_origin_class": "external_content",
        "context_actor_type": "retriever",
        "context_acquisition_method": "retrieval",
        "context_authority_class": "untrusted_data",
        "record_mutation": False,
        "tool_execution": False,
        "capability_execution": False,
        "phase6_gate_complete": False,
        "lite_v1_complete": False,
        "stable_anti_lock_in_claim": False,
        "implementation_doc": ("docs/implementation/imp-070-explicit-local-portability-review.md"),
    }
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def update_public_status() -> None:
    target = ROOT / "website/project-status.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    data["phase"]["next_implementation"] = 71
    data["model_runtime"]["message"] = (
        "Phase 6 is in progress through IMP-070. Offline Ollama session import, "
        "explicit text-only loopback capture, the accepted bounded local-portability "
        "migration drill, the deterministic shutdown escape bundle, bounded ChatGPT "
        "selected-history import, imported-context replay with accepted primary Intel "
        "Mac evidence, bounded local draft/revise/summarize/translate workflows, explicit "
        "data-only context, bounded local work-item proposals, and explicit local "
        "portability review are implemented. The IMP-063/IMP-064 writing workflow "
        "passes at both CI and real-machine evidence levels. IMP-065 through IMP-068 "
        "add explicit memory, project, decision, Resume Bundle, and translation "
        "boundaries; IMP-069 keeps work-item acceptance and execution user-controlled; "
        "IMP-070 reviews one explicitly selected import batch and exact linked mapping "
        "and loss records without original-source reads or record mutation. Automatic "
        "remediation, automatic acceptance or execution, automatic or semantic retrieval, "
        "attachments, tools, the complete Phase 6 gate, Lite v1.0, target-specific "
        "application replacement, and stable general anti-lock-in remain incomplete."
    )
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def update_public_checker() -> None:
    path = "scripts/check-public-site-status.mjs"
    replace_once(
        path,
        'status.phase?.next_implementation === 70,\n  "project-status.json must mark Phase 6 in progress through IMP-069 with IMP-070 next",',
        'status.phase?.next_implementation === 71,\n  "project-status.json must mark Phase 6 in progress through IMP-070 with IMP-071 next",',
    )
    replace_once(
        path,
        'status.model_runtime.message.includes("through IMP-069") &&\n    status.model_runtime.message.includes("IMP-069 adds exactly one model-proposed WorkItemRecord") &&\n    status.model_runtime.message.includes("acceptance and execution remain user-controlled") &&\n    status.model_runtime.message.includes("passes at both CI and real-machine evidence levels"),\n  "project-status.json must describe IMP-069 without broadening IMP-064 evidence",',
        'status.model_runtime.message.includes("through IMP-070") &&\n    status.model_runtime.message.includes("IMP-069 keeps work-item acceptance and execution user-controlled") &&\n    status.model_runtime.message.includes("IMP-070 reviews one explicitly selected import batch") &&\n    status.model_runtime.message.includes("without original-source reads or record mutation") &&\n    status.model_runtime.message.includes("passes at both CI and real-machine evidence levels"),\n  "project-status.json must describe IMP-070 without broadening accepted real-machine evidence",',
    )
    marker = """  \"IMP-069 work-item proposals must remain explicit, proposed-only, and CI-only\",\n);\n\nexpect(\n  localWritingPrimary.test_id ==="""
    insertion = """  \"IMP-069 work-item proposals must remain explicit, proposed-only, and CI-only\",\n);\n\nexpect(\n  dailyUse.portability_review_extension?.implementation === \"IMP-070\" &&\n    dailyUse.portability_review_extension?.status === \"ci-pass\" &&\n    JSON.stringify(dailyUse.portability_review_extension?.passed_evidence_levels) ===\n      JSON.stringify([\"ci\"]) &&\n    JSON.stringify(dailyUse.portability_review_extension?.required_evidence_levels) ===\n      JSON.stringify([\"ci\"]) &&\n    dailyUse.portability_review_extension?.selection_mode === \"explicit-only\" &&\n    JSON.stringify(dailyUse.portability_review_extension?.selected_record_types) ===\n      JSON.stringify([\n        \"portability_import_batch\",\n        \"portability_mapping_report\",\n        \"portability_loss\",\n      ]) &&\n    dailyUse.portability_review_extension?.exact_link_resolution === true &&\n    dailyUse.portability_review_extension?.original_source_read === false &&\n    dailyUse.portability_review_extension?.source_payload_read === false &&\n    dailyUse.portability_review_extension?.automatic_retrieval === false &&\n    dailyUse.portability_review_extension?.semantic_retrieval === false &&\n    dailyUse.portability_review_extension?.model_selected_context === false &&\n    dailyUse.portability_review_extension?.context_origin_class ===\n      \"external_content\" &&\n    dailyUse.portability_review_extension?.context_actor_type === \"retriever\" &&\n    dailyUse.portability_review_extension?.context_acquisition_method ===\n      \"retrieval\" &&\n    dailyUse.portability_review_extension?.context_authority_class ===\n      \"untrusted_data\" &&\n    dailyUse.portability_review_extension?.record_mutation === false &&\n    dailyUse.portability_review_extension?.tool_execution === false &&\n    dailyUse.portability_review_extension?.capability_execution === false &&\n    dailyUse.portability_review_extension?.phase6_gate_complete === false &&\n    dailyUse.portability_review_extension?.lite_v1_complete === false &&\n    dailyUse.portability_review_extension?.stable_anti_lock_in_claim === false &&\n    dailyUse.portability_review_extension?.implementation_doc ===\n      \"docs/implementation/imp-070-explicit-local-portability-review.md\",\n  \"IMP-070 portability review must remain explicit, linked-only, data-only, and CI-only\",\n);\n\nexpect(\n  localWritingPrimary.test_id ==="""
    replace_once(path, marker, insertion)
    replace_once(
        path,
        'roadmap.includes("### IMP-069 — Local work-item proposal workflow"),\n  "roadmap must record the IMP-069 work-item proposal boundary",\n);',
        'roadmap.includes("### IMP-069 — Local work-item proposal workflow"),\n  "roadmap must record the IMP-069 work-item proposal boundary",\n);\nexpect(\n  roadmap.includes("### IMP-070 — Explicit local portability review workflow"),\n  "roadmap must record the IMP-070 portability review boundary",\n);',
    )
    replace_once(
        path,
        'roadmap.includes("the next bounded implementation receives IMP-070 only when a new implementation issue is opened"),\n  "roadmap must identify IMP-070 as the next unallocated implementation identifier",',
        'roadmap.includes("the next bounded implementation receives IMP-071 only when a new implementation issue is opened"),\n  "roadmap must identify IMP-071 as the next unallocated implementation identifier",',
    )


def main() -> None:
    update_implementation_doc()
    update_roadmap()
    update_daily_use_matrix()
    update_public_status()
    update_public_checker()
    print("IMP-070 status and roadmap updates applied")


if __name__ == "__main__":
    main()
