from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "d40ba32e87f6d211b05e9da1e1f51974ec6fc369"
COMPLETED = "2026-07-14T16:17:03.751999Z"
RESULT = "docs/testing/results/IMP-064-primary-intel-mac-2026-07-15.json"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one replacement anchor, found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


matrix_path = ROOT / "docs/testing/phase-6-daily-use-matrix.json"
matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
workflow = matrix["local_writing_workflow"]
workflow["status"] = "pass"
workflow["passed_evidence_levels"] = ["ci", "real-machine"]
workflow["accepted_real_machine_result"] = RESULT
workflow["real_machine_gate"].update(
    {
        "status": "pass",
        "commit_sha": COMMIT,
        "completed_at": COMPLETED,
    }
)
workflow["real_machine_gate_status"] = "pass"
workflow["phase6_gate_complete"] = False
workflow["stable_anti_lock_in_claim"] = False
matrix_path.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")

implementation = ROOT / "docs/implementation/imp-064-primary-intel-mac-local-writing-acceptance.md"
replace_once(
    implementation,
    "Acceptance infrastructure implemented with deterministic synthetic CI evidence.\n\n"
    "Primary Intel Mac real-machine evidence remains pending until the merged implementation commit is executed with networking operator-confirmed disabled and a privacy-reviewed content-free result is accepted through a separate completion pull request.",
    "Acceptance infrastructure and privacy-reviewed exact-commit primary Intel Mac real-machine evidence accepted.\n\n"
    "The accepted run is bound to implementation commit `d40ba32e87f6d211b05e9da1e1f51974ec6fc369` and stored at `docs/testing/results/IMP-064-primary-intel-mac-2026-07-15.json`. It used Darwin `x86_64`, Python 3.12.13, networking operator-confirmed disabled, fixed IPv4 loopback Ollama, and one explicitly selected already-installed local model. All 48 checks passed, all three workflow modes completed, 11 loopback socket attempts were allowed, no non-loopback attempt occurred, no authority record was created, and every privacy flag remained false.",
)

roadmap = ROOT / "docs/spec/09-development-roadmap.md"
replace_once(
    roadmap,
    "the exact-commit primary Intel Mac local-writing acceptance infrastructure through IMP-064.",
    "the accepted exact-commit primary Intel Mac local-writing evidence through IMP-064.",
)
replace_once(
    roadmap,
    "- the IMP-063/IMP-064 local-writing workflow remains `ci-pass`; separate exact-commit privacy-reviewed primary Intel Mac evidence remains required before a real-machine daily-use claim;",
    "- the IMP-063/IMP-064 local-writing workflow passes at both `ci` and `real-machine` evidence levels; accepted privacy-safe evidence is stored at `docs/testing/results/IMP-064-primary-intel-mac-2026-07-15.json` and bound to exact implementation commit `d40ba32e87f6d211b05e9da1e1f51974ec6fc369`;",
)
replace_once(
    roadmap,
    "Status: implemented with deterministic synthetic CI evidence; IMP-064 provides the exact-commit primary Intel Mac acceptance path, and accepted real-machine evidence remains pending.",
    "Status: implemented with deterministic synthetic CI and accepted exact-commit primary Intel Mac real-machine evidence through IMP-064.",
)
replace_once(
    roadmap,
    "Status: acceptance infrastructure implemented with deterministic synthetic CI evidence; separate exact-commit primary Intel Mac execution and privacy-safe evidence acceptance remain pending.",
    "Status: acceptance infrastructure and privacy-reviewed exact-commit primary Intel Mac real-machine evidence accepted.",
)
replace_once(
    roadmap,
    "The content-free result schema contains only bounded platform facts, booleans, counts, hashes, event counts, runtime request counts, socket-attempt counts, and explicit non-claim flags. It excludes model names, requests, source material, prompts, responses, paths, usernames, hostnames, credentials, and secret values. Dedicated synthetic acceptance covers Ubuntu, macOS, and Windows. The local-writing workflow remains `ci-pass` until exact-commit primary Intel Mac evidence is executed and accepted separately.",
    "The content-free result schema contains only bounded platform facts, booleans, counts, hashes, event counts, runtime request counts, socket-attempt counts, and explicit non-claim flags. It excludes model names, requests, source material, prompts, responses, paths, usernames, hostnames, credentials, and secret values. Dedicated synthetic acceptance covers Ubuntu, macOS, and Windows. The accepted primary Intel Mac run used exact implementation commit `d40ba32e87f6d211b05e9da1e1f51974ec6fc369`, Darwin `x86_64`, Python 3.12.13, networking operator-confirmed disabled, fixed IPv4 loopback Ollama, and one explicitly selected already-installed local model. All 48 checks passed, all three modes completed, 11 loopback attempts were allowed, no non-loopback attempt occurred, no authority record was created, and all privacy flags remained false. The privacy-safe result is stored at `docs/testing/results/IMP-064-primary-intel-mac-2026-07-15.json`. The bounded local-writing workflow therefore passes at both `ci` and `real-machine` evidence levels.",
)
replace_once(
    roadmap,
    "After IMP-064 local-writing real-machine acceptance infrastructure, the immediate order is:",
    "After accepted IMP-064 local-writing real-machine evidence, the immediate order is:",
)
replace_once(
    roadmap,
    "4. merge the IMP-064 acceptance infrastructure, execute its network-disabled primary Intel Mac run against the exact merged commit, and accept only a content-free privacy-reviewed result through a separate completion pull request;",
    "4. retain the accepted IMP-063/IMP-064 local-writing result only within its documented draft/revise/summarize boundary and keep personal writing quality, translation, retrieval, attachments, tools, and cloud claims excluded;",
)

status_path = ROOT / "website/project-status.json"
status = json.loads(status_path.read_text(encoding="utf-8"))
status["model_runtime"]["message"] = (
    "Phase 6 is in progress through IMP-064. Offline Ollama session import, explicit text-only loopback capture, the accepted bounded local-portability migration drill, the deterministic shutdown escape bundle, bounded ChatGPT selected-history import, imported-context replay with accepted primary Intel Mac evidence, and the bounded local draft/revise/summarize workflow are implemented. The IMP-063/IMP-064 writing workflow now passes at both CI and real-machine evidence levels with privacy-reviewed exact-commit primary Intel Mac evidence. Translation, automatic retrieval, explicit memory/project context selection, attachments, tools, the complete Phase 6 gate, target-specific application replacement, and stable general anti-lock-in remain incomplete."
)
status["last_reviewed"] = "2026-07-15"
status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")

checker = ROOT / "scripts/check-public-site-status.mjs"
replace_once(
    checker,
    'const importedReplayPrimary = JSON.parse(\n  read("docs/testing/results/IMP-062-primary-intel-mac-2026-07-12.json"),\n);',
    'const importedReplayPrimary = JSON.parse(\n  read("docs/testing/results/IMP-062-primary-intel-mac-2026-07-12.json"),\n);\nconst localWritingPrimary = JSON.parse(\n  read("docs/testing/results/IMP-064-primary-intel-mac-2026-07-15.json"),\n);',
)
replace_once(
    checker,
    '  status.model_runtime.message.includes("through IMP-064") &&\n    status.model_runtime.message.includes("real-machine evidence remains pending"),\n  "project-status.json must describe the bounded IMP-064 pending machine gate",',
    '  status.model_runtime.message.includes("through IMP-064") &&\n    status.model_runtime.message.includes("passes at both CI and real-machine evidence levels"),\n  "project-status.json must describe the accepted bounded IMP-064 machine evidence",',
)
old_daily = '''expect(
  dailyUse.schema_version === 1 &&
    dailyUse.phase === "6" &&
    dailyUse.local_writing_workflow?.implementation === "IMP-063" &&
    dailyUse.local_writing_workflow?.acceptance_implementation === "IMP-064" &&
    dailyUse.local_writing_workflow?.status === "ci-pass" &&
    JSON.stringify(dailyUse.local_writing_workflow?.passed_evidence_levels) ===
      JSON.stringify(["ci"]) &&
    JSON.stringify(dailyUse.local_writing_workflow?.required_evidence_levels) ===
      JSON.stringify(["ci", "real-machine"]) &&
    dailyUse.local_writing_workflow?.accepted_real_machine_result === null &&
    dailyUse.local_writing_workflow?.real_machine_gate?.required === true &&
    dailyUse.local_writing_workflow?.real_machine_gate?.status === "pending" &&
    dailyUse.local_writing_workflow?.real_machine_gate?.commit_sha === null &&
    dailyUse.local_writing_workflow?.real_machine_gate?.completed_at === null &&
    dailyUse.local_writing_workflow?.real_machine_gate_status === "pending" &&
    dailyUse.local_writing_workflow?.implementation_doc ===
      "docs/implementation/imp-064-primary-intel-mac-local-writing-acceptance.md" &&
    dailyUse.local_writing_workflow?.runbook ===
      "docs/testing/imp-064-primary-intel-mac-runbook.md" &&
    dailyUse.local_writing_workflow?.phase6_gate_complete === false &&
    dailyUse.local_writing_workflow?.stable_anti_lock_in_claim === false,
  "IMP-063/IMP-064 writing workflow must remain ci-pass pending machine evidence",
);'''
new_daily = '''expect(
  dailyUse.schema_version === 1 &&
    dailyUse.phase === "6" &&
    dailyUse.local_writing_workflow?.implementation === "IMP-063" &&
    dailyUse.local_writing_workflow?.acceptance_implementation === "IMP-064" &&
    dailyUse.local_writing_workflow?.status === "pass" &&
    JSON.stringify(dailyUse.local_writing_workflow?.passed_evidence_levels) ===
      JSON.stringify(["ci", "real-machine"]) &&
    JSON.stringify(dailyUse.local_writing_workflow?.required_evidence_levels) ===
      JSON.stringify(["ci", "real-machine"]) &&
    dailyUse.local_writing_workflow?.accepted_real_machine_result ===
      "docs/testing/results/IMP-064-primary-intel-mac-2026-07-15.json" &&
    dailyUse.local_writing_workflow?.real_machine_gate?.required === true &&
    dailyUse.local_writing_workflow?.real_machine_gate?.status === "pass" &&
    dailyUse.local_writing_workflow?.real_machine_gate?.commit_sha ===
      "d40ba32e87f6d211b05e9da1e1f51974ec6fc369" &&
    dailyUse.local_writing_workflow?.real_machine_gate?.completed_at ===
      "2026-07-14T16:17:03.751999Z" &&
    dailyUse.local_writing_workflow?.real_machine_gate_status === "pass" &&
    dailyUse.local_writing_workflow?.implementation_doc ===
      "docs/implementation/imp-064-primary-intel-mac-local-writing-acceptance.md" &&
    dailyUse.local_writing_workflow?.runbook ===
      "docs/testing/imp-064-primary-intel-mac-runbook.md" &&
    dailyUse.local_writing_workflow?.phase6_gate_complete === false &&
    dailyUse.local_writing_workflow?.stable_anti_lock_in_claim === false,
  "IMP-063/IMP-064 writing workflow must bind accepted real-machine evidence",
);

expect(
  localWritingPrimary.test_id === "IMP-064-LOCAL-WRITING-PRIMARY" &&
    localWritingPrimary.result === "pass" &&
    localWritingPrimary.evidence_level === "real-machine" &&
    localWritingPrimary.commit_sha ===
      "d40ba32e87f6d211b05e9da1e1f51974ec6fc369" &&
    localWritingPrimary.operating_system === "Darwin" &&
    localWritingPrimary.architecture === "x86_64" &&
    localWritingPrimary.network_mode === "offline-confirmed" &&
    localWritingPrimary.real_runtime_used === true &&
    localWritingPrimary.external_network_request_used === false &&
    localWritingPrimary.cloud_credentials_used === false &&
    localWritingPrimary.model_download_used === false &&
    localWritingPrimary.runtime_installation_used === false &&
    localWritingPrimary.process_launch_used === false &&
    localWritingPrimary.tool_execution_used === false &&
    localWritingPrimary.capability_execution_used === false &&
    localWritingPrimary.writing_workflow_real_machine_gate === "pass" &&
    localWritingPrimary.local_writing_workflow_complete === true &&
    localWritingPrimary.phase6_gate_complete === false &&
    localWritingPrimary.stable_anti_lock_in_claim === false &&
    localWritingPrimary.evidence?.workflow_mode_count === 3 &&
    localWritingPrimary.evidence?.completed_workflow_count === 3 &&
    localWritingPrimary.evidence?.target_event_count === 9 &&
    localWritingPrimary.evidence?.runtime_request_count === 11 &&
    localWritingPrimary.evidence?.allowed_loopback_socket_attempts === 11 &&
    localWritingPrimary.evidence?.rejected_socket_attempts === 0 &&
    localWritingPrimary.evidence?.authority_record_count === 0 &&
    Object.values(localWritingPrimary.checks || {}).every(
      (value) => value === true,
    ) &&
    Object.values(localWritingPrimary.privacy || {}).every(
      (value) => value === false,
    ),
  "accepted IMP-064 primary evidence must remain bounded, offline, and privacy-safe",
);'''
replace_once(checker, old_daily, new_daily)
replace_once(
    checker,
    '    "After IMP-064 local-writing real-machine acceptance infrastructure, the immediate order is:",\n  ),\n  "roadmap must record IMP-064 infrastructure and remaining Phase 6 work",',
    '    "After accepted IMP-064 local-writing real-machine evidence, the immediate order is:",\n  ),\n  "roadmap must record accepted IMP-064 evidence and remaining Phase 6 work",',
)

acceptance = ROOT / "tests/test_imp_064_local_writing_acceptance.py"
replace_once(
    acceptance,
    'RUNBOOK = ROOT / "docs" / "testing" / "imp-064-primary-intel-mac-runbook.md"\nIMPLEMENTATION = (',
    'RUNBOOK = ROOT / "docs" / "testing" / "imp-064-primary-intel-mac-runbook.md"\nRESULT = ROOT / "docs" / "testing" / "results" / "IMP-064-primary-intel-mac-2026-07-15.json"\nIMPLEMENTATION = (',
)
replace_once(
    acceptance,
    '    assert payload["writing_workflow_real_machine_gate"] == "pending"\n    assert payload["local_writing_workflow_complete"] is False',
    '    assert payload["writing_workflow_real_machine_gate"] == "pass"\n    assert payload["local_writing_workflow_complete"] is True',
)
replace_once(
    acceptance,
    "def test_imp_064_matrix_remains_pending_before_machine_evidence() -> None:",
    "def test_imp_064_matrix_binds_accepted_machine_evidence() -> None:",
)
replace_once(acceptance, '    assert workflow["status"] == "ci-pass"', '    assert workflow["status"] == "pass"')
replace_once(
    acceptance,
    '    assert workflow["passed_evidence_levels"] == ["ci"]',
    '    assert workflow["passed_evidence_levels"] == ["ci", "real-machine"]',
)
replace_once(
    acceptance,
    '    assert workflow["accepted_real_machine_result"] is None',
    '    assert workflow["accepted_real_machine_result"] == str(RESULT.relative_to(ROOT).as_posix())',
)
replace_once(
    acceptance,
    '    assert workflow["real_machine_gate_status"] == "pending"',
    '    assert workflow["real_machine_gate_status"] == "pass"',
)
old_gate = '''    assert gate == {
        "required": True,
        "status": "pending",
        "platform": "Darwin",
        "architectures": ["x86_64", "amd64"],
        "minimum_local_models": 1,
        "network_mode": "offline-confirmed",
        "commit_sha": None,
        "completed_at": None,
    }'''
new_gate = '''    assert gate == {
        "required": True,
        "status": "pass",
        "platform": "Darwin",
        "architectures": ["x86_64", "amd64"],
        "minimum_local_models": 1,
        "network_mode": "offline-confirmed",
        "commit_sha": COMMIT,
        "completed_at": "2026-07-14T16:17:03.751999Z",
    }'''
replace_once(acceptance, old_gate, new_gate)
replace_once(
    acceptance,
    'TEST_ID = "IMP-064-LOCAL-WRITING-PRIMARY"',
    'TEST_ID = "IMP-064-LOCAL-WRITING-PRIMARY"\nCOMMIT = "d40ba32e87f6d211b05e9da1e1f51974ec6fc369"',
)
replace_once(
    acceptance,
    '    assert IMPLEMENTATION.is_file()\n    assert RUNBOOK.is_file()',
    '    assert IMPLEMENTATION.is_file()\n    assert RUNBOOK.is_file()\n    result = json.loads(RESULT.read_text(encoding="utf-8"))\n    assert result["result"] == "pass"\n    assert result["commit_sha"] == COMMIT\n    assert all(result["checks"].values())\n    assert not any(result["privacy"].values())',
)

print("IMP-064 primary writing evidence acceptance updates applied")
