from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULT_RELATIVE = "docs/testing/results/IMP-062-primary-intel-mac-2026-07-12.json"
IMPLEMENTATION_COMMIT = "65f3b5e9ac8c9961c7ec2a152dfdfbb637386e93"
COMPLETED_AT = "2026-07-12T14:48:39.025820Z"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"ERROR: {label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


result_path = ROOT / RESULT_RELATIVE
result = json.loads(result_path.read_text(encoding="utf-8"))
checks = result.get("checks")
privacy = result.get("privacy")
if (
    result.get("test_id") != "IMP-062-IMPORTED-CONTEXT-REPLAY-PRIMARY"
    or result.get("result") != "pass"
    or result.get("evidence_level") != "real-machine"
    or result.get("commit_sha") != IMPLEMENTATION_COMMIT
    or result.get("completed_at") != COMPLETED_AT
    or result.get("operating_system") != "Darwin"
    or result.get("architecture") != "x86_64"
    or result.get("network_mode") != "offline-confirmed"
    or result.get("context_replay_real_machine_gate") != "pass"
    or result.get("context_replay_extension_complete") is not True
    or result.get("phase6_gate_complete") is not False
    or result.get("stable_anti_lock_in_claim") is not False
    or not isinstance(checks, dict)
    or not checks
    or not all(value is True for value in checks.values())
    or not isinstance(privacy, dict)
    or any(privacy.values())
):
    raise SystemExit("ERROR: IMP-062 evidence does not match the accepted result")

matrix_path = ROOT / "docs/testing/phase-6-local-portability-matrix.json"
matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
extension = matrix.get("context_replay_extension")
if not isinstance(extension, dict):
    raise SystemExit("ERROR: context replay extension is missing")
gate = extension.get("real_machine_gate")
if not isinstance(gate, dict):
    raise SystemExit("ERROR: context replay real-machine gate is missing")
if extension.get("status") != "ci-pass" or gate.get("status") != "pending":
    raise SystemExit("ERROR: context replay extension is not pending evidence acceptance")
extension["status"] = "pass"
extension["passed_evidence_levels"] = ["ci", "real-machine"]
extension["accepted_real_machine_result"] = RESULT_RELATIVE
gate["status"] = "pass"
gate["commit_sha"] = IMPLEMENTATION_COMMIT
gate["completed_at"] = COMPLETED_AT
extension["real_machine_gate_status"] = "pass"
write_json(matrix_path, matrix)

status_path = ROOT / "website/project-status.json"
status = json.loads(status_path.read_text(encoding="utf-8"))
phase = status.get("phase")
if not isinstance(phase, dict) or phase.get("next_implementation") != 63:
    raise SystemExit("ERROR: project status does not retain IMP-063 next")
status["model_runtime"]["message"] = (
    "Phase 6 is in progress through IMP-062. Offline Ollama session import, "
    "explicit text-only loopback capture, the accepted bounded local-portability "
    "migration drill, the deterministic shutdown escape bundle, the bounded "
    "selected-history ChatGPT source path, numbered ChatGPT conversation-member "
    "aggregation, bounded imported conversation context replay, and its "
    "exact-commit primary Intel Mac acceptance are implemented. PORT-001, "
    "PORT-003, the bounded IMP-057 portion of PORT-013, PORT-014, and PORT-015 "
    "retain their accepted evidence. The IMP-061/IMP-062 cross-runtime replay "
    "extension now passes at both CI and real-machine evidence levels using the "
    "privacy-reviewed primary Intel Mac result. The complete Phase 6 gate, "
    "target-specific application replacement, and stable general anti-lock-in "
    "remain incomplete."
)
status["last_reviewed"] = "2026-07-12"
write_json(status_path, status)

implementation_path = (
    ROOT
    / "docs/implementation/imp-062-imported-context-replay-real-machine-acceptance.md"
)
implementation = implementation_path.read_text(encoding="utf-8")
implementation = replace_once(
    implementation,
    "Implemented with deterministic synthetic CI evidence.\n\nPrimary Intel Mac real-machine evidence remains pending until the merged implementation commit is executed with networking operator-confirmed disabled and a privacy-reviewed result is accepted through a separate completion pull request.\n\nIssue: #200",
    "Implemented with deterministic synthetic CI evidence and accepted primary Intel Mac real-machine evidence.\n\nThe accepted privacy-safe result is bound to exact implementation commit `65f3b5e9ac8c9961c7ec2a152dfdfbb637386e93` and stored at `docs/testing/results/IMP-062-primary-intel-mac-2026-07-12.json`. The run passed on Darwin `x86_64` with networking operator-confirmed disabled and fixed IPv4 loopback Ollama only.\n\nImplementation issue: #200  \nEvidence acceptance issue: #202",
    "implementation status",
)
implementation = replace_once(
    implementation,
    "The raw real-machine result must first be written outside the repository and reviewed manually. A later separate completion pull request may store only a privacy-safe result accepted against the exact merged implementation commit.",
    "The raw real-machine result was written outside the repository and reviewed manually. The accepted repository result contains only the bounded privacy-safe schema and is tied to the exact merged implementation commit.",
    "implementation evidence boundary",
)
implementation_path.write_text(implementation, encoding="utf-8")

roadmap_path = ROOT / "docs/spec/09-development-roadmap.md"
roadmap = roadmap_path.read_text(encoding="utf-8")
roadmap = replace_once(
    roadmap,
    "- the IMP-061/IMP-062 cross-runtime replay extension remains `ci-pass`; separate exact-commit privacy-reviewed primary Intel Mac evidence remains required before a real-machine cross-runtime replay claim;",
    "- the IMP-061/IMP-062 cross-runtime replay extension passes at both `ci` and `real-machine` evidence levels; accepted privacy-safe evidence is stored at `docs/testing/results/IMP-062-primary-intel-mac-2026-07-12.json` and is bound to exact implementation commit `65f3b5e9ac8c9961c7ec2a152dfdfbb637386e93`;",
    "roadmap current evidence",
)
roadmap = replace_once(
    roadmap,
    "Status: implemented with deterministic synthetic CI evidence; IMP-062 provides the exact-commit primary Intel Mac acceptance path, and accepted real-machine evidence remains pending.",
    "Status: implemented with deterministic synthetic CI and accepted exact-commit primary Intel Mac real-machine evidence through IMP-062.",
    "IMP-061 status",
)
roadmap = replace_once(
    roadmap,
    "Status: acceptance infrastructure implemented with deterministic synthetic CI evidence; separate exact-commit primary Intel Mac execution and privacy-safe evidence acceptance remain pending.",
    "Status: acceptance infrastructure and privacy-reviewed exact-commit primary Intel Mac real-machine evidence accepted.",
    "IMP-062 status",
)
roadmap = replace_once(
    roadmap,
    "Dedicated synthetic acceptance passes on Ubuntu, macOS, and Windows. The context replay extension remains `ci-pass` until exact-commit primary Intel Mac evidence is executed and accepted separately.",
    "Dedicated synthetic acceptance passes on Ubuntu, macOS, and Windows. The accepted primary Intel Mac run used exact implementation commit `65f3b5e9ac8c9961c7ec2a152dfdfbb637386e93`, Darwin `x86_64`, Python 3.12.13, networking operator-confirmed disabled, fixed IPv4 loopback Ollama, and one explicitly selected already-installed local model. All 36 checks passed, five loopback socket attempts were allowed, no non-loopback attempt occurred, no authority record was created, and all privacy flags remained false. The privacy-safe result is stored at `docs/testing/results/IMP-062-primary-intel-mac-2026-07-12.json`. The context replay extension therefore passes at both `ci` and `real-machine` evidence levels.",
    "IMP-062 accepted evidence paragraph",
)
roadmap = replace_once(
    roadmap,
    "After IMP-062 imported-context replay real-machine acceptance infrastructure, the immediate order is:\n\n1. retain PORT-014 as `pass` only within the accepted bounded IMP-059/IMP-060 selected-history migration boundary and keep its material-loss limitations visible;\n2. retain the accepted IMP-057 bounded PORT-013 evidence while recording the IMP-061/IMP-062 cross-runtime replay extension as `ci-pass` until separate exact-commit privacy-reviewed primary Intel Mac evidence is accepted;\n3. merge the IMP-062 implementation, execute its network-disabled primary Intel Mac run against the exact merged commit, and accept only a content-free privacy-reviewed result through a separate completion pull request;\n4. allocate IMP-063 only when a new bounded implementation issue is opened; ZIP ingestion, attachment bytes, target-specific export, cloud credentials, tools, automatic cloud fallback, and unrelated daily-use features remain separate work;\n5. keep the complete Phase 6 gate and stable general anti-lock-in incomplete until their independent remaining requirements pass.",
    "After accepted IMP-062 imported-context replay real-machine evidence, the immediate order is:\n\n1. retain PORT-014 as `pass` only within the accepted bounded IMP-059/IMP-060 selected-history migration boundary and keep its material-loss limitations visible;\n2. retain PORT-013 as `pass` within both the accepted IMP-057 migration boundary and the accepted IMP-061/IMP-062 imported-context replay extension, without broadening either result beyond its documented limits;\n3. allocate IMP-063 only when a new bounded implementation issue is opened; ZIP ingestion, attachment bytes, target-specific export, cloud credentials, tools, automatic cloud fallback, and unrelated daily-use features remain separate work;\n4. continue Phase 6 daily-use integration and independently required portability work without weakening the Phase 3 safety boundary or Phase 4A/4B canonical state contracts;\n5. keep the complete Phase 6 gate and stable general anti-lock-in incomplete until their independent remaining requirements pass.",
    "roadmap immediate work",
)
roadmap_path.write_text(roadmap, encoding="utf-8")

checker_path = ROOT / "scripts/check-public-site-status.mjs"
checker = checker_path.read_text(encoding="utf-8")
checker = replace_once(
    checker,
    'const chatgptPrivate = JSON.parse(\n  read("docs/testing/results/IMP-060-project-owner-chatgpt-2026-07-10.json"),\n);\n',
    'const chatgptPrivate = JSON.parse(\n  read("docs/testing/results/IMP-060-project-owner-chatgpt-2026-07-10.json"),\n);\nconst importedReplayPrimary = JSON.parse(\n  read("docs/testing/results/IMP-062-primary-intel-mac-2026-07-12.json"),\n);\n',
    "checker result load",
)
old_checker = '''expect(
  localPortability.context_replay_extension?.implementation === "IMP-061" &&
    localPortability.context_replay_extension?.acceptance_implementation ===
      "IMP-062" &&
    localPortability.context_replay_extension?.portability_test_id ===
      "PORT-013" &&
    localPortability.context_replay_extension?.status === "ci-pass" &&
    localPortability.context_replay_extension?.passed_evidence_levels?.length ===
      1 &&
    localPortability.context_replay_extension?.passed_evidence_levels?.[0] ===
      "ci" &&
    localPortability.context_replay_extension?.required_evidence_levels?.includes(
      "real-machine",
    ) &&
    localPortability.context_replay_extension?.accepted_real_machine_result ===
      null &&
    localPortability.context_replay_extension?.real_machine_gate?.required ===
      true &&
    localPortability.context_replay_extension?.real_machine_gate?.status ===
      "pending" &&
    localPortability.context_replay_extension?.real_machine_gate?.commit_sha ===
      null &&
    localPortability.context_replay_extension?.real_machine_gate?.completed_at ===
      null &&
    localPortability.context_replay_extension?.real_machine_gate_status ===
      "pending" &&
    localPortability.context_replay_extension?.implementation_doc ===
      "docs/implementation/imp-062-imported-context-replay-real-machine-acceptance.md" &&
    localPortability.context_replay_extension?.runbook ===
      "docs/testing/imp-062-primary-intel-mac-runbook.md" &&
    localPortability.context_replay_extension?.phase6_gate_complete === false &&
    localPortability.context_replay_extension?.stable_anti_lock_in_claim === false,
  "IMP-061/IMP-062 context replay extension must remain CI-only until accepted real-machine evidence",
);
'''
new_checker = '''expect(
  localPortability.context_replay_extension?.implementation === "IMP-061" &&
    localPortability.context_replay_extension?.acceptance_implementation ===
      "IMP-062" &&
    localPortability.context_replay_extension?.portability_test_id ===
      "PORT-013" &&
    localPortability.context_replay_extension?.status === "pass" &&
    localPortability.context_replay_extension?.passed_evidence_levels?.length ===
      2 &&
    localPortability.context_replay_extension?.passed_evidence_levels?.includes(
      "ci",
    ) &&
    localPortability.context_replay_extension?.passed_evidence_levels?.includes(
      "real-machine",
    ) &&
    localPortability.context_replay_extension?.required_evidence_levels?.includes(
      "real-machine",
    ) &&
    localPortability.context_replay_extension?.accepted_real_machine_result ===
      "docs/testing/results/IMP-062-primary-intel-mac-2026-07-12.json" &&
    localPortability.context_replay_extension?.real_machine_gate?.required ===
      true &&
    localPortability.context_replay_extension?.real_machine_gate?.status ===
      "pass" &&
    localPortability.context_replay_extension?.real_machine_gate?.commit_sha ===
      "65f3b5e9ac8c9961c7ec2a152dfdfbb637386e93" &&
    localPortability.context_replay_extension?.real_machine_gate?.completed_at ===
      "2026-07-12T14:48:39.025820Z" &&
    localPortability.context_replay_extension?.real_machine_gate_status ===
      "pass" &&
    localPortability.context_replay_extension?.implementation_doc ===
      "docs/implementation/imp-062-imported-context-replay-real-machine-acceptance.md" &&
    localPortability.context_replay_extension?.runbook ===
      "docs/testing/imp-062-primary-intel-mac-runbook.md" &&
    localPortability.context_replay_extension?.phase6_gate_complete === false &&
    localPortability.context_replay_extension?.stable_anti_lock_in_claim === false,
  "IMP-061/IMP-062 context replay extension must bind accepted real-machine evidence",
);

expect(
  importedReplayPrimary.test_id ===
    "IMP-062-IMPORTED-CONTEXT-REPLAY-PRIMARY" &&
    importedReplayPrimary.result === "pass" &&
    importedReplayPrimary.evidence_level === "real-machine" &&
    importedReplayPrimary.commit_sha ===
      "65f3b5e9ac8c9961c7ec2a152dfdfbb637386e93" &&
    importedReplayPrimary.operating_system === "Darwin" &&
    importedReplayPrimary.architecture === "x86_64" &&
    importedReplayPrimary.network_mode === "offline-confirmed" &&
    importedReplayPrimary.real_runtime_used === true &&
    importedReplayPrimary.external_network_request_used === false &&
    importedReplayPrimary.cloud_credentials_used === false &&
    importedReplayPrimary.model_download_used === false &&
    importedReplayPrimary.runtime_installation_used === false &&
    importedReplayPrimary.process_launch_used === false &&
    importedReplayPrimary.tool_execution_used === false &&
    importedReplayPrimary.capability_execution_used === false &&
    importedReplayPrimary.context_replay_extension_complete === true &&
    importedReplayPrimary.phase6_gate_complete === false &&
    importedReplayPrimary.stable_anti_lock_in_claim === false &&
    Object.values(importedReplayPrimary.checks || {}).every(
      (value) => value === true,
    ) &&
    Object.values(importedReplayPrimary.privacy || {}).every(
      (value) => value === false,
    ),
  "accepted IMP-062 primary evidence must remain bounded, offline, and privacy-safe",
);
'''
checker = replace_once(checker, old_checker, new_checker, "checker evidence block")
checker = replace_once(
    checker,
    '    "After IMP-062 imported-context replay real-machine acceptance infrastructure, the immediate order is:",\n  ),\n  "roadmap must record IMP-062 acceptance infrastructure and remaining Phase 6 work",\n);',
    '    "After accepted IMP-062 imported-context replay real-machine evidence, the immediate order is:",\n  ),\n  "roadmap must record accepted IMP-062 evidence and remaining Phase 6 work",\n);',
    "checker immediate work",
)
checker_path.write_text(checker, encoding="utf-8")

test_path = ROOT / "tests/test_imp_062_imported_context_replay_acceptance.py"
test_text = test_path.read_text(encoding="utf-8")
test_text = replace_once(
    test_text,
    'RUNBOOK = ROOT / "docs" / "testing" / "imp-062-primary-intel-mac-runbook.md"\n',
    'RUNBOOK = ROOT / "docs" / "testing" / "imp-062-primary-intel-mac-runbook.md"\nEVIDENCE = (\n    ROOT\n    / "docs"\n    / "testing"\n    / "results"\n    / "IMP-062-primary-intel-mac-2026-07-12.json"\n)\n',
    "test evidence constant",
)
test_text = replace_once(
    test_text,
    '    assert payload["context_replay_real_machine_gate"] == "pending"\n    assert payload["context_replay_extension_complete"] is False\n',
    '    assert payload["context_replay_real_machine_gate"] == "pass"\n    assert payload["context_replay_extension_complete"] is True\n',
    "CI accepted gate expectation",
)
old_test = '''def test_imp_062_matrix_keeps_real_machine_evidence_pending() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    extension = matrix["context_replay_extension"]

    assert extension["implementation"] == "IMP-061"
    assert extension["acceptance_implementation"] == "IMP-062"
    assert extension["portability_test_id"] == "PORT-013"
    assert extension["status"] == "ci-pass"
    assert extension["passed_evidence_levels"] == ["ci"]
    assert extension["required_evidence_levels"] == ["ci", "real-machine"]
    assert extension["accepted_real_machine_result"] is None
    assert extension["implementation_doc"] == (
        "docs/implementation/imp-062-imported-context-replay-real-machine-acceptance.md"
    )
    assert extension["runbook"] == ("docs/testing/imp-062-primary-intel-mac-runbook.md")
    assert IMPLEMENTATION_DOC.is_file()
    assert RUNBOOK.is_file()
    assert extension["real_machine_gate"] == {
        "required": True,
        "status": "pending",
        "platform": "Darwin",
        "architectures": ["x86_64", "amd64"],
        "minimum_local_models": 1,
        "network_mode": "offline-confirmed",
        "commit_sha": None,
        "completed_at": None,
    }
    assert extension["phase6_gate_complete"] is False
    assert extension["stable_anti_lock_in_claim"] is False
'''
new_test = '''def test_imp_062_matrix_accepts_real_machine_evidence() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    extension = matrix["context_replay_extension"]
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))

    assert extension["implementation"] == "IMP-061"
    assert extension["acceptance_implementation"] == "IMP-062"
    assert extension["portability_test_id"] == "PORT-013"
    assert extension["status"] == "pass"
    assert extension["passed_evidence_levels"] == ["ci", "real-machine"]
    assert extension["required_evidence_levels"] == ["ci", "real-machine"]
    assert extension["accepted_real_machine_result"] == (
        "docs/testing/results/IMP-062-primary-intel-mac-2026-07-12.json"
    )
    assert extension["implementation_doc"] == (
        "docs/implementation/imp-062-imported-context-replay-real-machine-acceptance.md"
    )
    assert extension["runbook"] == ("docs/testing/imp-062-primary-intel-mac-runbook.md")
    assert IMPLEMENTATION_DOC.is_file()
    assert RUNBOOK.is_file()
    assert EVIDENCE.is_file()
    assert extension["real_machine_gate"] == {
        "required": True,
        "status": "pass",
        "platform": "Darwin",
        "architectures": ["x86_64", "amd64"],
        "minimum_local_models": 1,
        "network_mode": "offline-confirmed",
        "commit_sha": "65f3b5e9ac8c9961c7ec2a152dfdfbb637386e93",
        "completed_at": "2026-07-12T14:48:39.025820Z",
    }
    assert extension["real_machine_gate_status"] == "pass"
    assert extension["phase6_gate_complete"] is False
    assert extension["stable_anti_lock_in_claim"] is False

    assert evidence["result"] == "pass"
    assert evidence["evidence_level"] == "real-machine"
    assert evidence["commit_sha"] == "65f3b5e9ac8c9961c7ec2a152dfdfbb637386e93"
    assert evidence["operating_system"] == "Darwin"
    assert evidence["architecture"] == "x86_64"
    assert evidence["network_mode"] == "offline-confirmed"
    assert evidence["real_runtime_used"] is True
    assert all(evidence["checks"].values())
    assert not any(evidence["privacy"].values())
    assert evidence["evidence"]["allowed_loopback_socket_attempts"] == 5
    assert evidence["evidence"]["rejected_socket_attempts"] == 0
    assert evidence["evidence"]["authority_record_count"] == 0
    assert evidence["phase6_gate_complete"] is False
    assert evidence["stable_anti_lock_in_claim"] is False
'''
test_text = replace_once(test_text, old_test, new_test, "matrix evidence test")
test_path.write_text(test_text, encoding="utf-8")

print("IMP-062 primary evidence acceptance updates applied")
