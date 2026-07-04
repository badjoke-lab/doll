from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs" / "testing" / "phase-6-chatgpt-history-matrix.json"
RUNNER = ROOT / "scripts" / "run_imp_059_chatgpt_export.py"


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _run(commit_sha: str | None = None) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(ROOT / "src"), str(ROOT)))
    return subprocess.run(
        [sys.executable, str(RUNNER), "--commit-sha", commit_sha or _head()],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_imp_059_matrix_keeps_port_014_private_gate_pending() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    assert matrix["schema_version"] == 1
    assert matrix["phase"] == "6"
    assert matrix["implementation"] == "IMP-059"
    assert matrix["port014_foundation_complete"] is True
    assert matrix["chatgpt_history_gate_complete"] is False
    assert matrix["accepted_private_manual_result"] is None
    assert matrix["portability_tests"] == [
        {
            "id": "PORT-014",
            "status": "ci-pass",
            "description": (
                "A selected synthetic ChatGPT conversations.json history is parsed offline, "
                "staged, reviewed, published as external data, exported generically, and retained "
                "through the shutdown escape surface without provider credentials "
                "or model execution."
            ),
            "pytest_files": [
                "tests/test_chatgpt_export_import.py",
                "tests/test_chatgpt_export_acceptance.py",
            ],
            "passed_evidence_levels": ["ci"],
            "required_evidence_levels": ["ci", "private-manual"],
        }
    ]
    assert matrix["private_manual_gate"] == {
        "required": True,
        "status": "pending",
        "source_format": "chatgpt-conversations-json",
        "source_format_version": "observed-v1",
        "commit_sha": None,
        "completed_at": None,
    }


def test_imp_059_ci_runner_is_bounded_and_keeps_claims_pending() -> None:
    result = _run()
    payload = cast(dict[str, Any], json.loads(result.stdout))

    assert result.returncode == 0, result.stdout
    assert payload["test_id"] == "IMP-059-CHATGPT-CONVERSATIONS-JSON"
    assert payload["result"] == "pass"
    assert payload["commit_sha"] == _head()
    assert payload["evidence_level"] == "ci"
    assert payload["network_mode"] == "synthetic-no-network"
    assert payload["portability_test_ids"] == ["PORT-014"]
    assert payload["portability_test_count"] == 1
    assert payload["port014_foundation_complete"] is True
    assert payload["chatgpt_history_gate_complete"] is False
    assert payload["phase6_gate_complete"] is False
    assert payload["stable_anti_lock_in_claim"] is False
    assert payload["real_machine_used"] is False
    assert payload["real_runtime_used"] is False
    assert payload["private_source_used"] is False
    assert payload["model_execution_used"] is False
    assert payload["cloud_credentials_used"] is False
    assert payload["external_network_request_used"] is False
    assert payload["checks"] and all(payload["checks"].values())
    assert payload["privacy"] and not any(payload["privacy"].values())

    evidence = payload["evidence"]
    assert evidence["source_environment_class"] == "cloud-ai-history-export"
    assert evidence["source_format"] == "chatgpt-conversations-json"
    assert evidence["source_format_version"] == "observed-v1"
    assert evidence["source_adapter_id"] == "chatgpt-conversations"
    assert evidence["source_adapter_version"] == "1.0.0"
    assert evidence["conversation_count"] == 2
    assert evidence["selected_conversation_count"] == 1
    assert evidence["selected_message_count"] == 3
    assert evidence["published_object_count"] == 4
    assert evidence["runtime_mode"] == "synthetic"


def test_imp_059_runner_rejects_commit_mismatch() -> None:
    result = _run("0" * 40)
    payload = json.loads(result.stdout)

    assert result.returncode == 1
    assert payload["result"] == "fail"
    assert payload["error_stage"] == "environment"
    assert payload["error_class"] == "RuntimeError"
    assert payload["chatgpt_history_gate_complete"] is False
    assert payload["phase6_gate_complete"] is False
    assert payload["stable_anti_lock_in_claim"] is False
