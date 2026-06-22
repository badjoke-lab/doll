from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/run_imp_023_safety_acceptance.py")


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


def test_imp_023_ci_safety_acceptance_passes_without_claiming_real_machine_gate() -> None:
    result = _run("--commit-sha", _head(), "--evidence-level", "ci")

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["test_id"] == "IMP-023-SAFETY-ACCEPTANCE"
    assert payload["result"] == "pass"
    assert payload["evidence_level"] == "ci"
    assert payload["security_test_count"] == 23
    assert payload["executable_security_test_count"] == 22
    assert payload["not_applicable_security_test_ids"] == ["SEC-007"]
    assert payload["primary_intel_mac_gate"] == "pending"
    assert payload["phase3_gate_complete"] is False
    assert payload["model_runtime_used"] is False
    assert payload["cloud_credentials_used"] is False
    assert payload["live_side_effect_used"] is False
    assert all(payload["checks"].values())
    assert all(value is False for value in payload["privacy"].values())


def test_imp_023_failure_report_is_bounded_and_secret_safe() -> None:
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
    assert "path" not in result.stdout.lower()
    assert "secret" not in result.stdout.lower()
