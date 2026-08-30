"""Tests for the IMP-104 user-visible local-writing latency measurement slice."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_imp_104_user_visible_latency_measurement.py"
VALIDATOR = ROOT / "scripts" / "validate_imp_104_user_visible_latency_measurement.py"
WORKFLOW_ORDER = ["draft", "revise", "summarize"]


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _run_ci(*extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--commit-sha",
            _head(),
            "--evidence-level",
            "ci",
            *extra,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _real_like_payload() -> dict[str, Any]:
    completed = _run_ci()
    assert completed.returncode == 0, completed.stdout
    payload: dict[str, Any] = json.loads(completed.stdout)
    payload.update(
        {
            "evidence_level": "real-machine",
            "operating_system": "Darwin",
            "architecture": "x86_64",
            "python_version": "3.14.6",
            "network_mode": "offline-confirmed",
            "loopback_runtime_request_used": True,
            "synthetic_observations": False,
            "real_machine_measurement_collected": True,
        }
    )
    payload["observation"]["allowed_loopback_socket_attempts"] = 1
    return payload


def _validate(tmp_path: Path, payload: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps(payload), encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            str(evidence),
            "--expected-commit-sha",
            _head(),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_imp_104_ci_runner_is_synthetic_bounded_and_conservative() -> None:
    completed = _run_ci()
    assert completed.returncode == 0, completed.stdout
    payload = json.loads(completed.stdout)
    observation = payload["observation"]

    assert payload["result"] == "pass"
    assert payload["evidence_level"] == "ci"
    assert payload["measurement_scope"] == "doll-local-writing-completed-response-latency"
    assert payload["timing_clock"] == "time.perf_counter_ns"
    assert payload["timing_boundary"] == "local-writing-execute-to-completed-result"
    assert payload["synthetic_observations"] is True
    assert payload["real_machine_measurement_collected"] is False
    assert payload["real_machine_measurement_accepted"] is False
    assert payload["external_network_request_used"] is False
    assert payload["loopback_runtime_request_used"] is False
    assert observation["workflow_order"] == WORKFLOW_ORDER
    assert observation["completed_workflow_count"] == 3
    assert observation["assistant_event_count"] == 3
    assert observation["canonical_event_count"] == 9
    assert observation["allowed_loopback_socket_attempts"] == 0
    assert observation["rejected_socket_attempts"] == 0
    assert set(observation["completed_response_duration_ns"]) == set(WORKFLOW_ORDER)
    assert all(value > 0 for value in observation["completed_response_duration_ns"].values())
    assert all(payload["checks"].values())
    assert not any(payload["claims"].values())
    assert not any(payload["privacy"].values())


def test_imp_104_ci_runner_rejects_real_machine_inputs() -> None:
    completed = _run_ci("--offline-confirmed")
    assert completed.returncode == 2
    assert json.loads(completed.stdout)["result"] == "fail"


def test_imp_104_runner_rejects_wrong_commit() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--commit-sha",
            "f" * 40,
            "--evidence-level",
            "ci",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    assert "commit mismatch" in json.loads(completed.stdout)["message"]


def test_imp_104_validator_accepts_bounded_real_like_evidence(tmp_path: Path) -> None:
    completed = _validate(tmp_path, _real_like_payload())
    assert completed.returncode == 0, completed.stdout
    result = json.loads(completed.stdout)
    assert result["result"] == "pass"
    assert result["workflow_order"] == WORKFLOW_ORDER
    assert result["first_token_latency_measured"] is False
    assert result["cold_start_latency_measured"] is False
    assert result["final_user_visible_latency_requirement_defined"] is False
    assert result["full_lite_performance_thresholds_defined"] is False
    assert result["phase6_gate_complete"] is False
    assert result["lite_v1_complete"] is False
    assert result["real_machine_measurement_accepted"] is False
    assert result["manual_privacy_review_required"] is True


def test_imp_104_validator_rejects_wrong_commit(tmp_path: Path) -> None:
    payload = _real_like_payload()
    payload["commit_sha"] = "f" * 40
    completed = _validate(tmp_path, payload)
    assert completed.returncode == 2
    assert "commit_sha" in json.loads(completed.stdout)["message"]


def test_imp_104_validator_rejects_non_intel_mac(tmp_path: Path) -> None:
    payload = _real_like_payload()
    payload["architecture"] = "arm64"
    completed = _validate(tmp_path, payload)
    assert completed.returncode == 2


def test_imp_104_validator_rejects_zero_duration(tmp_path: Path) -> None:
    payload = _real_like_payload()
    payload["observation"]["completed_response_duration_ns"]["draft"] = 0
    completed = _validate(tmp_path, payload)
    assert completed.returncode == 2


def test_imp_104_validator_rejects_first_token_claim(tmp_path: Path) -> None:
    payload = _real_like_payload()
    payload["claims"]["first_token_latency_measured"] = True
    completed = _validate(tmp_path, payload)
    assert completed.returncode == 2


def test_imp_104_validator_rejects_final_latency_requirement(tmp_path: Path) -> None:
    payload = _real_like_payload()
    payload["claims"]["final_user_visible_latency_requirement_defined"] = True
    completed = _validate(tmp_path, payload)
    assert completed.returncode == 2


def test_imp_104_validator_rejects_private_model_name_key(tmp_path: Path) -> None:
    payload = _real_like_payload()
    payload["observation"]["model"]["native_model_name"] = "private-name"
    completed = _validate(tmp_path, payload)
    assert completed.returncode == 2


def test_imp_104_validator_rejects_response_text_key(tmp_path: Path) -> None:
    payload = _real_like_payload()
    payload["observation"]["response_text"] = "private response"
    completed = _validate(tmp_path, payload)
    assert completed.returncode == 2


def test_imp_104_validator_rejects_weakened_timing_boundary(tmp_path: Path) -> None:
    payload = _real_like_payload()
    payload["timing_boundary"] = "runtime-call-only"
    completed = _validate(tmp_path, payload)
    assert completed.returncode == 2


def test_imp_104_validator_rejects_synthetic_real_machine_evidence(tmp_path: Path) -> None:
    payload = _real_like_payload()
    payload["synthetic_observations"] = True
    completed = _validate(tmp_path, payload)
    assert completed.returncode == 2
