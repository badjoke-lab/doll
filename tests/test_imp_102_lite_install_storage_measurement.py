"""Tests for the IMP-102 Lite installation/model-storage measurement slice."""

from __future__ import annotations

import json
import runpy
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_imp_102_lite_install_storage_measurement.py"
VALIDATOR = ROOT / "scripts" / "validate_imp_102_lite_install_storage_measurement.py"


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
    assert completed.returncode == 0, completed.stderr
    payload: dict[str, Any] = json.loads(completed.stdout)
    payload.update(
        {
            "evidence_level": "real-machine",
            "operating_system": "Darwin",
            "architecture": "x86_64",
            "python_version": "3.14.6",
            "network_mode": "offline-confirmed",
            "loopback_runtime_request_used": True,
            "dependency_installation_performed": True,
            "synthetic_observations": False,
            "real_machine_measurement_collected": True,
        }
    )
    observation = payload["observation"]
    observation["uv_version"] = "uv 0.12.7"
    observation["runtime_version"] = "0.33.1"
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


def test_imp_102_ci_runner_is_synthetic_and_conservative() -> None:
    completed = _run_ci()
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)

    assert payload["result"] == "pass"
    assert payload["evidence_level"] == "ci"
    assert payload["synthetic_observations"] is True
    assert payload["dependency_installation_performed"] is False
    assert payload["external_network_request_used"] is False
    assert payload["observation"]["lite_python_installation"]["optional_extras"] == [
        "ocr",
        "pdf",
    ]
    assert payload["observation"]["runtime_installation"] == {"measured": False}
    assert all(payload["checks"].values())
    assert not any(payload["claims"].values())
    assert not any(payload["privacy"].values())


def test_imp_102_ci_runner_rejects_real_machine_inputs() -> None:
    completed = _run_ci("--offline-confirmed")
    assert completed.returncode == 2
    assert json.loads(completed.stdout)["result"] == "fail"


def test_imp_102_install_command_is_locked_offline_non_dev_and_non_editable() -> None:
    namespace = runpy.run_path(str(RUNNER))
    command = namespace["_install_command"]()
    assert command == [
        "uv",
        "sync",
        "--no-dev",
        "--all-extras",
        "--locked",
        "--offline",
        "--no-editable",
    ]


def test_imp_102_validator_accepts_bounded_real_like_evidence(tmp_path: Path) -> None:
    completed = _validate(tmp_path, _real_like_payload())
    assert completed.returncode == 0, completed.stdout
    result = json.loads(completed.stdout)
    assert result["result"] == "pass"
    assert result["runtime_installation_measured"] is False
    assert result["full_install_disk_requirement_defined"] is False
    assert result["phase6_gate_complete"] is False
    assert result["lite_v1_complete"] is False


def test_imp_102_validator_accepts_explicit_runtime_root_aggregate(tmp_path: Path) -> None:
    payload = _real_like_payload()
    payload["observation"]["runtime_installation"] = {
        "measured": True,
        "tree": {
            "regular_file_count": 12,
            "directory_count": 4,
            "symlink_count": 1,
            "other_entry_count": 0,
            "logical_bytes": 8_000_000,
            "allocated_bytes": 8_100_000,
            "allocated_bytes_source": "stat-st_blocks-times-512",
            "symlink_target_bytes_included": False,
        },
    }
    completed = _validate(tmp_path, payload)
    assert completed.returncode == 0, completed.stdout
    assert json.loads(completed.stdout)["runtime_installation_measured"] is True


def test_imp_102_validator_rejects_wrong_commit(tmp_path: Path) -> None:
    payload = _real_like_payload()
    payload["commit_sha"] = "f" * 40
    completed = _validate(tmp_path, payload)
    assert completed.returncode == 2
    assert "commit_sha" in json.loads(completed.stdout)["message"]


def test_imp_102_validator_rejects_dev_dependency_scope(tmp_path: Path) -> None:
    payload = _real_like_payload()
    payload["observation"]["lite_python_installation"]["dev_dependencies_included"] = True
    completed = _validate(tmp_path, payload)
    assert completed.returncode == 2


def test_imp_102_validator_rejects_zero_install_bytes(tmp_path: Path) -> None:
    payload = _real_like_payload()
    payload["observation"]["lite_python_installation"]["tree"]["logical_bytes"] = 0
    completed = _validate(tmp_path, payload)
    assert completed.returncode == 2


def test_imp_102_validator_rejects_broader_disk_claim(tmp_path: Path) -> None:
    payload = _real_like_payload()
    payload["claims"]["complete_local_stack_disk_footprint_measured"] = True
    completed = _validate(tmp_path, payload)
    assert completed.returncode == 2


def test_imp_102_validator_rejects_private_model_name_key(tmp_path: Path) -> None:
    payload = _real_like_payload()
    payload["observation"]["model"]["native_model_name"] = "private-name"
    completed = _validate(tmp_path, payload)
    assert completed.returncode == 2


def test_imp_102_validator_rejects_runtime_root_path_key(tmp_path: Path) -> None:
    payload = _real_like_payload()
    payload["observation"]["runtime_installation"] = {
        "measured": False,
        "runtime_install_root": "/private/example",
    }
    completed = _validate(tmp_path, payload)
    assert completed.returncode == 2
