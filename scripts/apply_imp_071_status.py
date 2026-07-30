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
        "docs/implementation/imp-071-structured-local-failure-guidance.md",
        "**Status:** In progress  ",
        "**Status:** Implemented with deterministic synthetic CI evidence  ",
    )


def update_roadmap() -> None:
    path = "docs/spec/09-development-roadmap.md"
    replace_once(path, "- IMP-030 through IMP-070;", "- IMP-030 through IMP-071;")
    replace_once(
        path,
        "bounded local work-item proposals through IMP-069, and explicit local portability review through IMP-070.",
        "bounded local work-item proposals through IMP-069, explicit local portability review through IMP-070, and structured local runtime failure guidance through IMP-071.",
    )
    replace_once(
        path,
        "- Phase 6 local AI portability and daily-use integration is in progress through IMP-070;",
        "- Phase 6 local AI portability and daily-use integration is in progress through IMP-071;",
    )
    replace_once(
        path,
        "- the IMP-070 portability review extension passes at the `ci` evidence level and does not broaden the accepted IMP-057, IMP-062, or IMP-064 real-machine results;\n- the next bounded implementation receives IMP-071 only when a new implementation issue is opened;",
        "- the IMP-070 portability review extension passes at the `ci` evidence level and does not broaden the accepted IMP-057, IMP-062, or IMP-064 real-machine results;\n- IMP-071 adds one deterministic provider-neutral local failure-guidance payload for every accepted runtime failure code and persists the same bounded local-only options in canonical error events;\n- IMP-071 is assigned to Issue #225;\n- the IMP-071 failure-guidance extension passes at the `ci` evidence level and does not broaden accepted real-machine evidence;\n- the next bounded implementation receives IMP-072 only when a new implementation issue is opened;",
    )
    replace_once(
        path,
        "IMP-070 does not establish automatic batch discovery, ranking, semantic retrieval, model-selected records, original-source inspection, source-payload inspection, canonical replay, quarantine-detail review, automatic remediation, retry or rollback execution, publication approval, target-specific export, provider round-trip verification, attachments, PDF/OCR, tools, cloud review, external issue trackers, complete Phase 6, Lite v1.0 completion, or stable general anti-lock-in.\n\nSubsequent daily-use work may expand accessibility, error clarity, Lite performance, and soak testing.",
        "IMP-070 does not establish automatic batch discovery, ranking, semantic retrieval, model-selected records, original-source inspection, source-payload inspection, canonical replay, quarantine-detail review, automatic remediation, retry or rollback execution, publication approval, target-specific export, provider round-trip verification, attachments, PDF/OCR, tools, cloud review, external issue trackers, complete Phase 6, Lite v1.0 completion, or stable general anti-lock-in.\n\n### IMP-071 — Structured local runtime failure guidance\n\nStatus: implemented with deterministic synthetic CI evidence.\n\nImplemented one immutable provider-neutral LocalFailureGuidance payload for each of the nine accepted RuntimeFailureCode values. Every payload contains one versioned guidance identifier, the exact failure code, one bounded plain-language summary, an ordered bounded list of local-only available options, and explicit state-preserved, no-automatic-action, and no-cloud-fallback flags.\n\nFailed, cancelled, and timed-out canonical local turns expose the matching guidance through the content-free LocalConversationResult and persist the same guidance identifier, summary, options, and flags in the canonical error-event extensions. Completed turns contain no failure guidance. Audit metadata stores only the guidance identifier and available-option count.\n\nGuidance may describe local retry, smaller requests or context, local runtime-health or model-inventory inspection, manual repair of the configured local runtime, manual activation of an already approved installed local model or fallback binding, bounded local timeout adjustment, or continued state inspection, export, backup, restore, and recovery without model execution. It never performs or recommends automatic cloud fallback, provider login, API-key entry, remote upload, automatic model download or installation, automatic binding changes, process or shell execution, tools, capabilities, or destructive state mutation.\n\nDedicated acceptance covers all nine failure codes, deterministic identity, immutability, bounded provider-neutral text, completed-turn absence, failed/cancelled/timeout integration, canonical error-event parity, fixed safety flags, and prohibited-action wording. Existing local conversation, imported-context, writing, translation, work-item proposal, and portability-review regressions remain active. Standard CI covers Ubuntu, macOS, and Windows.\n\nIMP-071 does not establish preflight exception redesign, UI rendering, localization, accessibility presentation, telemetry, provider-specific troubleshooting, automatic repair, automatic fallback, automatic model acquisition, Lite performance measurements, the release soak gate, complete Phase 6, Lite v1.0 completion, or stable general anti-lock-in.\n\nSubsequent daily-use work may expand accessibility, Lite performance measurements, and soak testing.",
    )


def update_daily_use_matrix() -> None:
    target = ROOT / "docs/testing/phase-6-daily-use-matrix.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    if "failure_guidance_extension" in data:
        raise RuntimeError("failure_guidance_extension already exists")
    data["failure_guidance_extension"] = {
        "implementation": "IMP-071",
        "status": "ci-pass",
        "description": (
            "Every accepted local runtime failure code has one deterministic provider-neutral "
            "guidance payload with bounded local-only options and explicit no-automatic-action "
            "and no-cloud-fallback flags."
        ),
        "pytest_files": [
            "tests/test_imp_071_local_failure_guidance.py",
            "tests/test_local_conversation.py",
        ],
        "passed_evidence_levels": ["ci"],
        "required_evidence_levels": ["ci"],
        "failure_code_count": 9,
        "guidance_version": 1,
        "canonical_error_event_persistence": True,
        "completed_turn_guidance": False,
        "state_preserved": True,
        "automatic_action_taken": False,
        "cloud_fallback_used": False,
        "automatic_model_download": False,
        "automatic_model_installation": False,
        "automatic_binding_change": False,
        "process_launch": False,
        "shell_execution": False,
        "tool_execution": False,
        "capability_execution": False,
        "destructive_state_mutation": False,
        "phase6_gate_complete": False,
        "lite_v1_complete": False,
        "stable_anti_lock_in_claim": False,
        "implementation_doc": (
            "docs/implementation/imp-071-structured-local-failure-guidance.md"
        ),
    }
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def update_public_status() -> None:
    target = ROOT / "website/project-status.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    data["phase"]["next_implementation"] = 72
    data["model_runtime"]["message"] = (
        "Phase 6 is in progress through IMP-071. Offline Ollama session import, "
        "explicit text-only loopback capture, the accepted bounded local-portability "
        "migration drill, the deterministic shutdown escape bundle, bounded ChatGPT "
        "selected-history import, imported-context replay with accepted primary Intel "
        "Mac evidence, bounded local draft/revise/summarize/translate workflows, explicit "
        "data-only context, bounded local work-item proposals, explicit local portability "
        "review, and structured local runtime failure guidance are implemented. The "
        "IMP-063/IMP-064 writing workflow passes at both CI and real-machine evidence "
        "levels. IMP-069 keeps work-item acceptance and execution user-controlled; "
        "IMP-070 reviews one explicitly selected import batch without original-source "
        "reads or record mutation; IMP-071 gives every accepted local runtime failure "
        "code deterministic provider-neutral local-only options while recording no "
        "automatic action and no cloud fallback. Accessibility presentation, Lite "
        "performance measurements, the release soak gate, automatic or semantic "
        "retrieval, attachments, tools, the complete Phase 6 gate, Lite v1.0, "
        "target-specific application replacement, and stable general anti-lock-in "
        "remain incomplete."
    )
    data["last_reviewed"] = "2026-07-31"
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def update_public_checker() -> None:
    path = "scripts/check-public-site-status.mjs"
    replace_once(
        path,
        'status.phase?.next_implementation === 71,\n  "project-status.json must mark Phase 6 in progress through IMP-070 with IMP-071 next",',
        'status.phase?.next_implementation === 72,\n  "project-status.json must mark Phase 6 in progress through IMP-071 with IMP-072 next",',
    )
    replace_once(
        path,
        'status.model_runtime.message.includes("through IMP-070") &&\n    status.model_runtime.message.includes("IMP-069 keeps work-item acceptance and execution user-controlled") &&\n    status.model_runtime.message.includes("IMP-070 reviews one explicitly selected import batch") &&\n    status.model_runtime.message.includes("without original-source reads or record mutation") &&\n    status.model_runtime.message.includes("passes at both CI and real-machine evidence levels"),\n  "project-status.json must describe IMP-070 without broadening accepted real-machine evidence",',
        'status.model_runtime.message.includes("through IMP-071") &&\n    status.model_runtime.message.includes("IMP-069 keeps work-item acceptance and execution user-controlled") &&\n    status.model_runtime.message.includes("IMP-070 reviews one explicitly selected import batch") &&\n    status.model_runtime.message.includes("IMP-071 gives every accepted local runtime failure code") &&\n    status.model_runtime.message.includes("no automatic action and no cloud fallback") &&\n    status.model_runtime.message.includes("passes at both CI and real-machine evidence levels"),\n  "project-status.json must describe IMP-071 without broadening accepted real-machine evidence",',
    )
    marker = '''  "IMP-070 portability review must remain explicit, linked-only, data-only, and CI-only",\n);\n\nexpect(\n  localWritingPrimary.test_id ==='''
    insertion = '''  "IMP-070 portability review must remain explicit, linked-only, data-only, and CI-only",\n);\n\nexpect(\n  dailyUse.failure_guidance_extension?.implementation === "IMP-071" &&\n    dailyUse.failure_guidance_extension?.status === "ci-pass" &&\n    JSON.stringify(dailyUse.failure_guidance_extension?.passed_evidence_levels) ===\n      JSON.stringify(["ci"]) &&\n    JSON.stringify(dailyUse.failure_guidance_extension?.required_evidence_levels) ===\n      JSON.stringify(["ci"]) &&\n    dailyUse.failure_guidance_extension?.failure_code_count === 9 &&\n    dailyUse.failure_guidance_extension?.guidance_version === 1 &&\n    dailyUse.failure_guidance_extension?.canonical_error_event_persistence === true &&\n    dailyUse.failure_guidance_extension?.completed_turn_guidance === false &&\n    dailyUse.failure_guidance_extension?.state_preserved === true &&\n    dailyUse.failure_guidance_extension?.automatic_action_taken === false &&\n    dailyUse.failure_guidance_extension?.cloud_fallback_used === false &&\n    dailyUse.failure_guidance_extension?.automatic_model_download === false &&\n    dailyUse.failure_guidance_extension?.automatic_model_installation === false &&\n    dailyUse.failure_guidance_extension?.automatic_binding_change === false &&\n    dailyUse.failure_guidance_extension?.process_launch === false &&\n    dailyUse.failure_guidance_extension?.shell_execution === false &&\n    dailyUse.failure_guidance_extension?.tool_execution === false &&\n    dailyUse.failure_guidance_extension?.capability_execution === false &&\n    dailyUse.failure_guidance_extension?.destructive_state_mutation === false &&\n    dailyUse.failure_guidance_extension?.phase6_gate_complete === false &&\n    dailyUse.failure_guidance_extension?.lite_v1_complete === false &&\n    dailyUse.failure_guidance_extension?.stable_anti_lock_in_claim === false &&\n    dailyUse.failure_guidance_extension?.implementation_doc ===\n      "docs/implementation/imp-071-structured-local-failure-guidance.md",\n  "IMP-071 failure guidance must remain deterministic, local-only, and CI-only",\n);\n\nexpect(\n  localWritingPrimary.test_id ==='''
    replace_once(path, marker, insertion)
    replace_once(
        path,
        'roadmap.includes("### IMP-070 — Explicit local portability review workflow"),\n  "roadmap must record the IMP-070 portability review boundary",\n);',
        'roadmap.includes("### IMP-070 — Explicit local portability review workflow"),\n  "roadmap must record the IMP-070 portability review boundary",\n);\nexpect(\n  roadmap.includes("### IMP-071 — Structured local runtime failure guidance"),\n  "roadmap must record the IMP-071 failure-guidance boundary",\n);',
    )
    replace_once(
        path,
        'roadmap.includes("the next bounded implementation receives IMP-071 only when a new implementation issue is opened"),\n  "roadmap must identify IMP-071 as the next unallocated implementation identifier",',
        'roadmap.includes("the next bounded implementation receives IMP-072 only when a new implementation issue is opened"),\n  "roadmap must identify IMP-072 as the next unallocated implementation identifier",',
    )


def main() -> None:
    update_implementation_doc()
    update_roadmap()
    update_daily_use_matrix()
    update_public_status()
    update_public_checker()
    print("IMP-071 status and roadmap updates applied")


if __name__ == "__main__":
    main()
