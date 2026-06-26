from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/run_imp_047_project_continuity_acceptance.py")


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
    environment["DOLL_DISABLE_MODEL_ADAPTERS"] = "1"
    environment["NO_PROXY"] = "*"
    environment["HTTP_PROXY"] = "http://127.0.0.1:9"
    environment["HTTPS_PROXY"] = "http://127.0.0.1:9"
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        cwd=Path.cwd(),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_imp_047_ci_evidence_preserves_completed_primary_machine_gate() -> None:
    result = _run("--commit-sha", _head(), "--evidence-level", "ci")

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["test_id"] == "IMP-047-PROJECT-CONTINUITY-ACCEPTANCE"
    assert payload["result"] == "pass"
    assert payload["evidence_level"] == "ci"
    assert payload["network_mode"] == "no-network-path-in-probe"
    assert payload["project_test_count"] == 12
    assert payload["project_test_ids"] == [f"PROJ-{number:03d}" for number in range(1, 13)]
    assert payload["primary_intel_mac_gate"] == "pass"
    assert payload["phase4b_gate_complete"] is True
    assert payload["model_runtime_used"] is False
    assert payload["cloud_credentials_used"] is False
    assert payload["network_request_used"] is False
    assert payload["running_service_used"] is False
    assert payload["preferred_ui_used"] is False
    assert all(payload["checks"].values())
    assert all(value is False for value in payload["privacy"].values())
    evidence = payload["evidence"]
    assert evidence["project_schema_version"] == 2
    assert evidence["project_status_schema"] == "doll.project-status.v1"
    assert evidence["state_package_format_version"] == 2
    assert evidence["resume_bundle_format_version"] == 1
    assert evidence["checkpoint_freshness"] == "current"
    assert evidence["basis_fingerprint"].startswith("sha256:")
    assert evidence["omitted_secret_counts"]["work_item"] == 1
    assert evidence["backup_modes"] == ["state", "workspace"]


def test_imp_047_wrong_commit_returns_bounded_failure() -> None:
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


def test_imp_047_real_machine_mode_requires_offline_confirmation() -> None:
    result = _run("--commit-sha", _head(), "--evidence-level", "real-machine")

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["result"] == "fail"
    assert payload["error_stage"] == "environment"
    assert payload["error_class"] == "RuntimeError"
