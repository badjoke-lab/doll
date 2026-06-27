from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/run_imp_054_runtime_continuity.py")


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(Path.cwd() / "src"), str(Path.cwd())))
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


def test_imp_054_ci_evidence_runs_full_synthetic_runtime_drill() -> None:
    result = _run("--commit-sha", _head(), "--evidence-level", "ci")

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["test_id"] == "IMP-054-LOCAL-RUNTIME-CONTINUITY"
    assert payload["result"] == "pass"
    assert payload["evidence_level"] == "ci"
    assert payload["network_mode"] == "synthetic-no-network"
    assert payload["runtime_test_count"] == 12
    assert payload["runtime_test_ids"] == [f"LRUN-{number:03d}" for number in range(1, 13)]
    assert payload["primary_intel_mac_gate"] == "pending"
    assert payload["phase5_gate_complete"] is False
    assert payload["real_runtime_used"] is False
    assert payload["cloud_credentials_used"] is False
    assert payload["external_network_request_used"] is False
    assert payload["model_download_used"] is False
    assert payload["runtime_installation_used"] is False
    assert all(payload["checks"].values())
    assert all(value is False for value in payload["privacy"].values())

    evidence = payload["evidence"]
    assert evidence["runtime_adapter_id"] == "ollama.local"
    assert evidence["runtime_adapter_version"] == "1.0.0"
    assert evidence["runtime_version"] == "0.0.0-test"
    assert evidence["runtime_mode"] == "synthetic"
    assert evidence["model_count"] == 2
    assert len(evidence["model_revision_hashes"]) == 2
    assert all(value.startswith("sha256:") for value in evidence["model_revision_hashes"])
    assert evidence["canonical_turn_count"] == 4
    assert evidence["canonical_event_count"] == 12
    assert evidence["package_format_version"] == 2
    assert evidence["backup_fresh_process_validated"] is True
    assert evidence["fresh_inspection_count"] == 3
    assert evidence["allowed_loopback_socket_attempts"] == 0
    assert evidence["rejected_socket_attempts"] == 0
    assert evidence["ollama_request_count"] > 0
    assert evidence["ollama_stream_count"] > 0
    assert evidence["active_binding_hash"].startswith("sha256:")

    for forbidden in (
        "doll-test-primary",
        "doll-test-fallback",
        "DOLL_LOCAL_OK",
        "DOLL_STREAM_OK",
        "DOLL_SWITCH_OK",
        "/Users/",
        "/home/",
    ):
        assert forbidden not in result.stdout


def test_imp_054_wrong_commit_returns_bounded_failure() -> None:
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


def test_imp_054_real_machine_mode_requires_all_explicit_confirmations() -> None:
    result = _run("--commit-sha", _head(), "--evidence-level", "real-machine")

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["result"] == "fail"
    assert payload["error_stage"] == "environment"
    assert payload["error_class"] == "RuntimeError"
    assert "primary-model" not in result.stdout
    assert "fallback-model" not in result.stdout


def test_imp_054_ci_mode_rejects_machine_only_arguments() -> None:
    result = _run(
        "--commit-sha",
        _head(),
        "--evidence-level",
        "ci",
        "--offline-confirmed",
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["result"] == "fail"
    assert payload["error_stage"] == "environment"
