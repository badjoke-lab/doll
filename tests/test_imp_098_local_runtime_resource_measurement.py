"""Acceptance tests for IMP-098 local-runtime resource measurement preparation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_imp_098_local_runtime_resource_measurement.py"
VALIDATOR = ROOT / "scripts/validate_imp_098_local_runtime_resource_measurement.py"


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _run_runner(*extra: str) -> subprocess.CompletedProcess[str]:
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


def _run_validator(path: Path, commit_sha: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            str(path),
            "--expected-commit-sha",
            commit_sha,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _real_like_fixture(tmp_path: Path) -> tuple[Path, dict[str, object], str]:
    completed = _run_runner()
    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    payload.update(
        {
            "evidence_level": "real-machine",
            "operating_system": "Darwin",
            "architecture": "x86_64",
            "network_mode": "offline-confirmed",
            "synthetic_observations": False,
            "real_machine_measurement_collected": True,
            "loopback_runtime_request_used": True,
            "measurement_wrapper_process_inspection_used": True,
        }
    )
    path = tmp_path / "imp098-real-like.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path, payload, _head()


def _write(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_imp_098_ci_runner_is_synthetic_and_conservative() -> None:
    completed = _run_runner()

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["result"] == "pass"
    assert payload["evidence_level"] == "ci"
    assert payload["measurement_scope"] == "doll-local-runtime-single-model"
    assert payload["repeat_count"] == 3
    assert payload["synthetic_observations"] is True
    assert payload["real_machine_measurement_collected"] is False
    assert payload["real_machine_measurement_accepted"] is False
    assert payload["loopback_runtime_request_used"] is False
    assert payload["external_network_request_used"] is False
    assert all(payload["checks"].values())
    assert not any(payload["claims"].values())
    assert not any(payload["privacy"].values())
    durations = payload["observation"]["generation_duration"]
    assert len(durations["values_ns"]) == 3
    runtime_rss = payload["observation"]["runtime_process_tree_rss_samples_bytes"]
    assert len(runtime_rss) == 4


def test_imp_098_ci_runner_rejects_machine_confirmation() -> None:
    completed = _run_runner("--offline-confirmed")

    assert completed.returncode == 2
    failure = json.loads(completed.stdout)
    assert failure["result"] == "fail"
    assert failure["stage"] == "environment"


def test_imp_098_validator_accepts_bounded_real_machine_shape(tmp_path: Path) -> None:
    path, _, commit_sha = _real_like_fixture(tmp_path)

    completed = _run_validator(path, commit_sha)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(completed.stdout)
    assert result == {
        "evidence_level": "real-machine",
        "full_lite_performance_thresholds_defined": False,
        "lite_v1_complete": False,
        "manual_privacy_review_required": True,
        "measurement_scope": "doll-local-runtime-single-model",
        "phase6_gate_complete": False,
        "real_machine_measurement_accepted": False,
        "repeat_count": 3,
        "result": "pass",
        "validated_commit_sha": commit_sha,
    }


def test_imp_098_validator_rejects_wrong_commit(tmp_path: Path) -> None:
    path, _, _ = _real_like_fixture(tmp_path)

    completed = _run_validator(path, "0" * 40)

    assert completed.returncode == 2
    failure = json.loads(completed.stdout)
    assert failure["result"] == "fail"
    assert failure["message"] == "invalid commit_sha"


def test_imp_098_validator_rejects_wrong_machine_class(tmp_path: Path) -> None:
    path, payload, commit_sha = _real_like_fixture(tmp_path)
    payload["architecture"] = "arm64"
    _write(path, payload)

    completed = _run_validator(path, commit_sha)

    assert completed.returncode == 2
    failure = json.loads(completed.stdout)
    assert failure["result"] == "fail"
    assert "primary Intel Mac architecture" in failure["message"]


def test_imp_098_validator_rejects_wrong_scope(tmp_path: Path) -> None:
    path, payload, commit_sha = _real_like_fixture(tmp_path)
    payload["measurement_scope"] = "full-system"
    _write(path, payload)

    completed = _run_validator(path, commit_sha)

    assert completed.returncode == 2
    failure = json.loads(completed.stdout)
    assert failure["result"] == "fail"
    assert failure["message"] == "invalid measurement_scope"


def test_imp_098_validator_rejects_invalid_model_identity(tmp_path: Path) -> None:
    path, payload, commit_sha = _real_like_fixture(tmp_path)
    payload["observation"]["model"]["model_id"] = "native-model-name"
    _write(path, payload)

    completed = _run_validator(path, commit_sha)

    assert completed.returncode == 2
    failure = json.loads(completed.stdout)
    assert failure["result"] == "fail"
    assert failure["message"] == "opaque model identity is invalid"


def test_imp_098_validator_rejects_release_overclaim(tmp_path: Path) -> None:
    path, payload, commit_sha = _real_like_fixture(tmp_path)
    payload["claims"]["minimum_system_ram_requirement_defined"] = True
    _write(path, payload)

    completed = _run_validator(path, commit_sha)

    assert completed.returncode == 2
    failure = json.loads(completed.stdout)
    assert failure["result"] == "fail"
    assert "forbidden performance or release claim" in failure["message"]


def test_imp_098_validator_rejects_private_model_name_key(tmp_path: Path) -> None:
    path, payload, commit_sha = _real_like_fixture(tmp_path)
    payload["observation"]["model"]["native_model_name"] = "private-model"
    _write(path, payload)

    completed = _run_validator(path, commit_sha)

    assert completed.returncode == 2
    failure = json.loads(completed.stdout)
    assert failure["result"] == "fail"
    assert "forbidden shareable evidence key" in failure["message"]


def test_imp_098_validator_rejects_inconsistent_runtime_rss(tmp_path: Path) -> None:
    path, payload, commit_sha = _real_like_fixture(tmp_path)
    payload["observation"]["maximum_sampled_runtime_process_tree_rss_bytes"] = 1
    _write(path, payload)

    completed = _run_validator(path, commit_sha)

    assert completed.returncode == 2
    failure = json.loads(completed.stdout)
    assert failure["result"] == "fail"
    assert "maximum runtime RSS does not match samples" in failure["message"]
