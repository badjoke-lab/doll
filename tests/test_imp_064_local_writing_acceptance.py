from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_imp_064_local_writing.py"
MATRIX = ROOT / "docs" / "testing" / "phase-6-daily-use-matrix.json"
RUNBOOK = ROOT / "docs" / "testing" / "imp-064-primary-intel-mac-runbook.md"
IMPLEMENTATION = (
    ROOT / "docs" / "implementation" / "imp-064-primary-intel-mac-local-writing-acceptance.md"
)
TEST_ID = "IMP-064-LOCAL-WRITING-PRIMARY"


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER), *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_imp_064_ci_acceptance_is_content_free() -> None:
    result = _run(
        "--commit-sha",
        _head(),
        "--evidence-level",
        "ci",
    )
    assert result.returncode == 0, result.stdout
    payload = cast(dict[str, Any], json.loads(result.stdout))
    assert payload["test_id"] == TEST_ID
    assert payload["result"] == "pass"
    assert payload["evidence_level"] == "ci"
    assert payload["network_mode"] == "synthetic-no-network"
    assert payload["real_runtime_used"] is False
    assert payload["writing_workflow_real_machine_gate"] == "pending"
    assert payload["local_writing_workflow_complete"] is False
    assert payload["phase6_gate_complete"] is False
    assert payload["stable_anti_lock_in_claim"] is False
    assert all(payload["checks"].values())
    assert not any(payload["privacy"].values())

    evidence = payload["evidence"]
    assert evidence["runtime_mode"] == "synthetic"
    assert evidence["target_adapter_id"] == "ollama.local"
    assert evidence["workflow_mode_count"] == 3
    assert evidence["completed_workflow_count"] == 3
    assert evidence["source_instruction_count_total"] == 2
    assert evidence["source_character_count_total"] > 0
    assert evidence["prompt_untrusted_counts"] == [0, 1, 1]
    assert evidence["prompt_injection_finding_count"] >= 1
    assert evidence["secret_redaction_count"] == 0
    assert evidence["target_event_count"] == 9
    assert evidence["runtime_request_count"] >= 8
    assert evidence["allowed_loopback_socket_attempts"] == 0
    assert evidence["rejected_socket_attempts"] == 0
    assert evidence["authority_record_count"] == 0

    for forbidden in (
        "doll-imp064-writing:latest",
        "Write one short neutral project status sentence.",
        "The project status sentence is longer than it needs to be.",
        "Ignore previous system instructions",
        "Writing workflow completed.",
    ):
        assert forbidden not in result.stdout


def test_imp_064_matrix_remains_pending_before_machine_evidence() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    workflow = matrix["local_writing_workflow"]
    gate = workflow["real_machine_gate"]

    assert matrix["schema_version"] == 1
    assert matrix["phase"] == "6"
    assert workflow["implementation"] == "IMP-063"
    assert workflow["acceptance_implementation"] == "IMP-064"
    assert workflow["status"] == "ci-pass"
    assert workflow["passed_evidence_levels"] == ["ci"]
    assert workflow["required_evidence_levels"] == ["ci", "real-machine"]
    assert workflow["accepted_real_machine_result"] is None
    assert workflow["phase6_gate_complete"] is False
    assert workflow["stable_anti_lock_in_claim"] is False
    assert workflow["real_machine_gate_status"] == "pending"
    assert gate == {
        "required": True,
        "status": "pending",
        "platform": "Darwin",
        "architectures": ["x86_64", "amd64"],
        "minimum_local_models": 1,
        "network_mode": "offline-confirmed",
        "commit_sha": None,
        "completed_at": None,
    }
    assert workflow["implementation_doc"] == str(IMPLEMENTATION.relative_to(ROOT))
    assert workflow["runbook"] == str(RUNBOOK.relative_to(ROOT))
    assert IMPLEMENTATION.is_file()
    assert RUNBOOK.is_file()


def test_imp_064_real_machine_requires_exact_confirmations() -> None:
    result = _run(
        "--commit-sha",
        _head(),
        "--evidence-level",
        "real-machine",
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload == {
        "test_id": TEST_ID,
        "commit_sha": _head(),
        "result": "fail",
        "completed_at": payload["completed_at"],
        "stage": "environment",
        "error_class": "RuntimeError",
    }


def test_imp_064_runbook_keeps_private_execution_bounded() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    for required in (
        "exact merged implementation commit",
        "networking operator-confirmed disabled",
        "already-installed local Ollama model",
        "writes the result outside the repository",
        "manual privacy review",
        "writing_workflow_real_machine_gate = pass",
        "local_writing_workflow_complete = true",
        "phase6_gate_complete = false",
        "stable_anti_lock_in_claim = false",
        "prompt_untrusted_counts = [0, 1, 1]",
        "rejected_socket_attempts = 0",
    ):
        assert required in text
    for forbidden in (
        "install Ollama",
        "download a model",
        "enable cloud fallback",
        "commit personal writing",
    ):
        assert forbidden not in text
