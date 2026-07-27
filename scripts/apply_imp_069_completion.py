from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one match in {path}, found {count}: {old}")
    target.write_text(text.replace(old, new), encoding="utf-8")


def harden_source() -> None:
    replace_once(
        "src/doll/local_work_proposal.py",
        "from doll.audit import AuditService\n",
        "",
    )
    replace_once(
        "src/doll/local_work_proposal.py",
        '''        selected_result = selected_service.materialize(
            conversation_id=conversation_id,
            operation_id=safe_operation_id,
            plan=selected_plan,
        )
''',
        '''        try:
            selected_result = selected_service.materialize(
                conversation_id=conversation_id,
                operation_id=safe_operation_id,
                plan=selected_plan,
            )
        except SelectedWritingContextValidationError as exc:
            raise LocalWorkProposalValidationError(
                "local work proposal context could not be prepared"
            ) from exc
''',
    )
    replace_once(
        "src/doll/local_work_proposal.py",
        '''            AuditService(self.repository).append(
                action="local_work_proposal.reject",
                result="failed",
                actor_type="system",
                operation_id=_proposal_audit_operation_id(safe_operation_id),
                target_type="project",
                target_id=selected_result.project_ids[0],
                metadata={"rejection_code": "invalid_model_proposal"},
            )
''',
        "",
    )
    replace_once(
        "src/doll/local_work_proposal.py",
        '''        AuditService(self.repository).append(
            action="local_work_proposal.create",
            result="success",
            actor_type="system",
            operation_id=_proposal_audit_operation_id(safe_operation_id),
            target_type="work_item",
            target_id=work_item.work_item_id,
            metadata={
                "project_id": work_item.project_id,
                "work_status": work_item.work_status,
                "verification_state": work_item.verification_state,
                "criterion_count": len(work_item.acceptance_criteria),
            },
        )
''',
        "",
    )
    replace_once(
        "src/doll/local_work_proposal.py",
        '''

def _proposal_audit_operation_id(operation_id: str) -> str:
    digest = hashlib.sha256(f"audit\\0{operation_id}".encode()).hexdigest()[:32]
    return f"imp069.audit.{digest}"
''',
        "",
    )


def update_implementation_doc() -> None:
    replace_once(
        "docs/implementation/imp-069-local-work-item-proposal.md",
        "**Status:** In progress\n**Phase:**",
        "**Status:** Implemented with deterministic synthetic CI evidence\n"
        "**Issue:** #221\n**Phase:**",
    )


def update_roadmap() -> None:
    path = "docs/spec/09-development-roadmap.md"
    replace_once(path, "- IMP-030 through IMP-068;", "- IMP-030 through IMP-069;")
    replace_once(
        path,
        "explicit verified Resume Bundle writing context through IMP-067, and explicit local translation through IMP-068.",
        "explicit verified Resume Bundle writing context through IMP-067, explicit local translation through IMP-068, and bounded local work-item proposals through IMP-069.",
    )
    replace_once(
        path,
        "- Phase 6 local AI portability and daily-use integration is in progress through IMP-068;",
        "- Phase 6 local AI portability and daily-use integration is in progress through IMP-069;",
    )
    replace_once(
        path,
        "- the IMP-068 translation extension passes at the `ci` evidence level and does not broaden the accepted IMP-064 real-machine result;\n- the next bounded implementation receives IMP-069 only when a new implementation issue is opened;",
        "- the IMP-068 translation extension passes at the `ci` evidence level and does not broaden the accepted IMP-064 real-machine result;\n"
        "- IMP-069 adds one bounded local-model planning turn that may create exactly one model-proposed WorkItemRecord while acceptance, start, blocking, verification, completion, cancellation, and capability authority remain outside the model path;\n"
        "- IMP-069 is assigned to Issue #221;\n"
        "- the IMP-069 work-item proposal extension passes at the `ci` evidence level and does not broaden the accepted IMP-064 real-machine result;\n"
        "- the next bounded implementation receives IMP-070 only when a new implementation issue is opened;",
    )
    replace_once(
        path,
        "IMP-068 does not establish automatic source-language detection, translation memory, glossary management, locale-specific formatting, document or attachment translation, PDF or OCR translation, multimodal input, streaming workflow output, semantic retrieval, model-selected context, tools, cloud translation, provider routing, target-specific export, personal translation-quality claims, complete Phase 6, Lite v1.0 completion, or stable general anti-lock-in.\n\nSubsequent daily-use work may expand planning, work-item proposals, portability review, accessibility, error clarity, Lite performance, and soak testing.",
        "IMP-068 does not establish automatic source-language detection, translation memory, glossary management, locale-specific formatting, document or attachment translation, PDF or OCR translation, multimodal input, streaming workflow output, semantic retrieval, model-selected context, tools, cloud translation, provider routing, target-specific export, personal translation-quality claims, complete Phase 6, Lite v1.0 completion, or stable general anti-lock-in.\n\n"
        "### IMP-069 — Local work-item proposal workflow\n\n"
        "Status: implemented with deterministic synthetic CI evidence.\n\n"
        "Implemented one bounded local-model planning turn above the accepted canonical local conversation path. The caller selects one active ProjectRecord, provides one bounded planning request, and may explicitly select confirmed-memory and DecisionRecord context. All selected records remain revision-pinned data-only external content and cannot become task authority.\n\n"
        "The runtime must return exactly one strict JSON proposal containing only schema version, work kind, title, description, priority, and bounded acceptance criteria. The service validates exact keys, duplicate keys, constants, text, kinds, priority, criteria, artifact identity, runtime-output provenance, and selected context before persisting through `WorkItemService.propose(..., actor_type=\"model\")`.\n\n"
        "Every successful model proposal is forced to `proposed`, `not_verified`, without blockers, start time, completion time, or verification evidence. The existing WorkItemRecord service supplies the authoritative proposal audit. The model cannot accept, start, block, verify, complete, cancel, execute, or mutate project, decision, procedure, checkpoint, policy, permission, credential, capability, memory, or binding state. Invalid or secret-bearing output and runtime failure create no WorkItemRecord.\n\n"
        "Dedicated acceptance covers strict parsing, hostile selected context, invalid project selection, secret-bearing output, duplicate operations, runtime failure, content-free results, and authoritative revision preservation. Standard CI covers Ubuntu, macOS, and Windows.\n\n"
        "IMP-069 does not establish multiple proposals per turn, dependency graphs, automatic acceptance, automatic execution, blocker mutation, procedure or checkpoint generation, semantic retrieval, attachments, tools, cloud planning, external issue trackers, complete Phase 6, Lite v1.0 completion, or stable general anti-lock-in.\n\n"
        "Subsequent daily-use work may expand portability review, accessibility, error clarity, Lite performance, and soak testing.",
    )


def update_daily_use_matrix() -> None:
    target = ROOT / "docs/testing/phase-6-daily-use-matrix.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    if "work_item_proposal_extension" in data:
        raise RuntimeError("work_item_proposal_extension already exists")
    data["work_item_proposal_extension"] = {
        "implementation": "IMP-069",
        "status": "ci-pass",
        "description": (
            "One bounded local-model planning turn can create exactly one model-proposed "
            "WorkItemRecord while all accepted-work and execution authority remains on the user path."
        ),
        "pytest_files": ["tests/test_imp_069_local_work_proposal.py"],
        "passed_evidence_levels": ["ci"],
        "required_evidence_levels": ["ci"],
        "project_selection_mode": "explicit-only",
        "maximum_proposals_per_turn": 1,
        "model_provenance": "model-proposed",
        "forced_work_status": "proposed",
        "forced_verification_state": "not_verified",
        "automatic_acceptance": False,
        "automatic_start": False,
        "automatic_completion": False,
        "capability_execution": False,
        "tool_execution": False,
        "semantic_retrieval": False,
        "selected_context_types": ["project", "confirmed_memory", "decision"],
        "context_origin_class": "external_content",
        "context_authority_class": "untrusted_data",
        "phase6_gate_complete": False,
        "lite_v1_complete": False,
        "stable_anti_lock_in_claim": False,
        "implementation_doc": "docs/implementation/imp-069-local-work-item-proposal.md",
    }
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def update_public_status() -> None:
    target = ROOT / "website/project-status.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    data["phase"]["next_implementation"] = 70
    data["model_runtime"]["message"] = (
        "Phase 6 is in progress through IMP-069. Offline Ollama session import, explicit "
        "text-only loopback capture, the accepted bounded local-portability migration drill, "
        "the deterministic shutdown escape bundle, bounded ChatGPT selected-history import, "
        "imported-context replay with accepted primary Intel Mac evidence, bounded local "
        "draft/revise/summarize/translate workflows, explicit data-only context, and bounded "
        "local work-item proposals are implemented. The IMP-063/IMP-064 writing workflow "
        "passes at both CI and real-machine evidence levels. IMP-065 through IMP-068 add "
        "explicit memory, project, decision, Resume Bundle, and translation boundaries; "
        "IMP-069 adds exactly one model-proposed WorkItemRecord while acceptance and execution "
        "remain user-controlled. Automatic acceptance, automatic execution, automatic or "
        "semantic retrieval, attachments, tools, the complete Phase 6 gate, Lite v1.0, "
        "target-specific application replacement, and stable general anti-lock-in remain incomplete."
    )
    data["last_reviewed"] = "2026-07-27"
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def update_public_checker() -> None:
    path = "scripts/check-public-site-status.mjs"
    replace_once(
        path,
        'status.phase?.next_implementation === 69,\n  "project-status.json must mark Phase 6 in progress through IMP-068 with IMP-069 next",',
        'status.phase?.next_implementation === 70,\n  "project-status.json must mark Phase 6 in progress through IMP-069 with IMP-070 next",',
    )
    replace_once(
        path,
        '''status.model_runtime.message.includes("through IMP-068") &&
    status.model_runtime.message.includes("IMP-065 adds explicit") &&
    status.model_runtime.message.includes("IMP-066 adds explicit DecisionRecord") &&
    status.model_runtime.message.includes("IMP-067 adds one explicit verified Resume Bundle") &&
    status.model_runtime.message.includes("IMP-068 adds explicit local translation") &&
    status.model_runtime.message.includes("passes at both CI and real-machine evidence levels"),
  "project-status.json must describe IMP-068 without broadening IMP-064 evidence",''',
        '''status.model_runtime.message.includes("through IMP-069") &&
    status.model_runtime.message.includes("IMP-069 adds exactly one model-proposed WorkItemRecord") &&
    status.model_runtime.message.includes("acceptance and execution remain user-controlled") &&
    status.model_runtime.message.includes("passes at both CI and real-machine evidence levels"),
  "project-status.json must describe IMP-069 without broadening IMP-064 evidence",''',
    )
    marker = '''  "IMP-068 translation must remain explicit, data-only, bounded, and CI-only",
);

expect(
  localWritingPrimary.test_id ==='''
    insertion = '''  "IMP-068 translation must remain explicit, data-only, bounded, and CI-only",
);

expect(
  dailyUse.work_item_proposal_extension?.implementation === "IMP-069" &&
    dailyUse.work_item_proposal_extension?.status === "ci-pass" &&
    JSON.stringify(dailyUse.work_item_proposal_extension?.passed_evidence_levels) ===
      JSON.stringify(["ci"]) &&
    JSON.stringify(dailyUse.work_item_proposal_extension?.required_evidence_levels) ===
      JSON.stringify(["ci"]) &&
    dailyUse.work_item_proposal_extension?.project_selection_mode === "explicit-only" &&
    dailyUse.work_item_proposal_extension?.maximum_proposals_per_turn === 1 &&
    dailyUse.work_item_proposal_extension?.model_provenance === "model-proposed" &&
    dailyUse.work_item_proposal_extension?.forced_work_status === "proposed" &&
    dailyUse.work_item_proposal_extension?.forced_verification_state === "not_verified" &&
    dailyUse.work_item_proposal_extension?.automatic_acceptance === false &&
    dailyUse.work_item_proposal_extension?.automatic_start === false &&
    dailyUse.work_item_proposal_extension?.automatic_completion === false &&
    dailyUse.work_item_proposal_extension?.capability_execution === false &&
    dailyUse.work_item_proposal_extension?.tool_execution === false &&
    dailyUse.work_item_proposal_extension?.semantic_retrieval === false &&
    JSON.stringify(dailyUse.work_item_proposal_extension?.selected_context_types) ===
      JSON.stringify(["project", "confirmed_memory", "decision"]) &&
    dailyUse.work_item_proposal_extension?.context_origin_class === "external_content" &&
    dailyUse.work_item_proposal_extension?.context_authority_class === "untrusted_data" &&
    dailyUse.work_item_proposal_extension?.phase6_gate_complete === false &&
    dailyUse.work_item_proposal_extension?.lite_v1_complete === false &&
    dailyUse.work_item_proposal_extension?.stable_anti_lock_in_claim === false &&
    dailyUse.work_item_proposal_extension?.implementation_doc ===
      "docs/implementation/imp-069-local-work-item-proposal.md",
  "IMP-069 work-item proposals must remain explicit, proposed-only, and CI-only",
);

expect(
  localWritingPrimary.test_id ==='''
    replace_once(path, marker, insertion)
    replace_once(
        path,
        '''expect(
  roadmap.includes("### IMP-067 — Explicit Resume Bundle writing context"),
  "roadmap must record the IMP-067 Resume Bundle writing context boundary",
);
expect(
  roadmap.includes("the next bounded implementation receives IMP-069 only when a new implementation issue is opened"),
  "roadmap must identify IMP-069 as the next unallocated implementation identifier",
);''',
        '''expect(
  roadmap.includes("### IMP-067 — Explicit Resume Bundle writing context"),
  "roadmap must record the IMP-067 Resume Bundle writing context boundary",
);
expect(
  roadmap.includes("### IMP-069 — Local work-item proposal workflow"),
  "roadmap must record the IMP-069 work-item proposal boundary",
);
expect(
  roadmap.includes("the next bounded implementation receives IMP-070 only when a new implementation issue is opened"),
  "roadmap must identify IMP-070 as the next unallocated implementation identifier",
);''',
    )


def main() -> None:
    harden_source()
    update_implementation_doc()
    update_roadmap()
    update_daily_use_matrix()
    update_public_status()
    update_public_checker()
    print("IMP-069 completion updates applied")


if __name__ == "__main__":
    main()
