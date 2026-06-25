from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/run_imp_037_portability_acceptance.py")


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path.cwd() / "src")
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        cwd=Path.cwd(),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_imp_037_ci_evidence_preserves_completed_machine_gate() -> None:
    result = _run("--commit-sha", _head(), "--evidence-level", "ci")

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["test_id"] == "IMP-037-PORTABILITY-ACCEPTANCE"
    assert payload["result"] == "pass"
    assert payload["evidence_level"] == "ci"
    assert payload["network_mode"] == "no-network-path-in-probe"
    assert payload["portability_test_count"] == 9
    assert payload["primary_intel_mac_gate"] == "pass"
    assert payload["phase4a_gate_complete"] is True
    assert payload["stable_anti_lock_in_claim"] is False
    assert payload["model_runtime_used"] is False
    assert payload["cloud_credentials_used"] is False
    assert payload["network_request_used"] is False
    assert payload["running_service_used"] is False
    assert payload["preferred_ui_used"] is False
    assert all(payload["checks"].values())
    assert all(value is False for value in payload["privacy"].values())

    evidence = payload["evidence"]
    assert evidence["source_environment_class"] == "generic-file-export"
    assert evidence["source_format"] == "json"
    assert evidence["source_adapter_id"] == "generic-import"
    assert evidence["target_format"] == "doll-generic-export"
    assert evidence["duplicate_counts"] == {"unchanged_reimport_canonical_duplicates": 0}
    assert evidence["quarantine_counts"] == {"loss_fixture": 1}
    assert evidence["loss_counts_by_severity"]["material"] >= 1


def test_imp_037_wrong_commit_returns_bounded_failure() -> None:
    result = _run(
        "--commit-sha",
        "0123456789abcdef0123456789abcdef01234567",
        "--evidence-level",
        "ci",
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert set(payload) == {
        "commit_sha",
        "completed_at",
        "error_class",
        "error_stage",
        "result",
        "test_id",
    }
    assert payload["result"] == "fail"
    assert payload["error_class"] == "RuntimeError"
    assert payload["error_stage"] == "environment"


def test_imp_037_real_machine_mode_requires_offline_confirmation() -> None:
    result = _run("--commit-sha", _head(), "--evidence-level", "real-machine")

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["result"] == "fail"
    assert payload["error_stage"] == "environment"
    assert payload["error_class"] == "RuntimeError"
