"""Acceptance tests for IMP-100 local-runtime repeatability/variance preparation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
SOURCE_RUNNER = ROOT / "scripts/run_imp_098_local_runtime_resource_measurement.py"
BUILDER = ROOT / "scripts/build_imp_100_runtime_repeatability_measurement.py"
VALIDATOR = ROOT / "scripts/validate_imp_100_runtime_repeatability_measurement.py"


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _source_payload() -> dict[str, object]:
    completed = subprocess.run(
        [
            sys.executable,
            str(SOURCE_RUNNER),
            "--commit-sha",
            _head(),
            "--evidence-level",
            "ci",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = cast(dict[str, object], json.loads(completed.stdout))
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
    return payload


def _write_source(tmp_path: Path, ordinal: int) -> Path:
    payload = _source_payload()
    observation = cast(dict[str, object], payload["observation"])
    runtime_rss = [
        10_000_000 + ordinal,
        900_000_000 + ordinal * 1_000_000,
        910_000_000 + ordinal * 1_000_000,
        920_000_000 + ordinal * 1_000_000,
    ]
    observation["runtime_process_tree_rss_samples_bytes"] = runtime_rss
    observation["maximum_sampled_runtime_process_tree_rss_bytes"] = max(runtime_rss)
    observation["runtime_process_count_samples"] = [1, 2, 2, 2]
    doll_rss = cast(dict[str, object], observation["doll_process_rss"])
    doll_rss.update(
        {
            "source": "resource-ru_maxrss",
            "current_bytes": None,
            "peak_bytes": 35_000_000 + ordinal * 100_000,
        }
    )
    durations = [
        6_000_000_000 + ordinal * 100_000_000,
        120_000_000 + ordinal * 1_000_000,
        140_000_000 + ordinal * 1_000_000,
    ]
    duration = cast(dict[str, object], observation["generation_duration"])
    duration.update(
        {
            "values_ns": durations,
            "minimum_ns": min(durations),
            "maximum_ns": max(durations),
            "mean_floor_ns": sum(durations) // len(durations),
            "spread_ns": max(durations) - min(durations),
        }
    )
    observation["generation_output_char_counts"] = [2, 2, 2]
    path = tmp_path / f"session-{ordinal}.json"
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def _sources(tmp_path: Path) -> list[Path]:
    return [_write_source(tmp_path, ordinal) for ordinal in range(1, 4)]


def _run_builder(
    sources: list[Path],
    *,
    expected_commit_sha: str | None = None,
    confirmations: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(BUILDER),
        "--expected-commit-sha",
        expected_commit_sha or _head(),
    ]
    for source in sources:
        command.extend(["--source", str(source)])
    if confirmations:
        command.extend(["--independent-sessions-confirmed", "--source-privacy-reviewed"])
    return subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_validator(
    path: Path,
    *,
    expected_commit_sha: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            str(path),
            "--expected-commit-sha",
            expected_commit_sha or _head(),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_imp_100_builder_aggregates_three_distinct_sessions(tmp_path: Path) -> None:
    completed = _run_builder(_sources(tmp_path))

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["result"] == "pass"
    assert payload["evidence_level"] == "real-machine"
    assert payload["measurement_scope"] == ("doll-local-runtime-single-model-repeatability")
    assert payload["session_count"] == 3
    assert payload["real_machine_repeatability_collected"] is True
    assert payload["real_machine_repeatability_accepted"] is False
    assert payload["separate_measurement_session_invocations_confirmed"] is True
    assert payload["source_manual_privacy_review_confirmed"] is True
    assert len({session["source_sha256"] for session in payload["sessions"]}) == 3
    runtime_summary = payload["variance"]["maximum_sampled_runtime_process_tree_rss_bytes"]
    assert runtime_summary["values"] == [921_000_000, 922_000_000, 923_000_000]
    assert runtime_summary["spread"] == 2_000_000
    first_generation = payload["variance"]["generation_duration_by_position_ns"][0]
    assert first_generation["values"] == [
        6_100_000_000,
        6_200_000_000,
        6_300_000_000,
    ]
    assert first_generation["spread"] == 200_000_000
    assert all(payload["checks"].values())
    assert not any(payload["claims"].values())
    assert not any(payload["privacy"].values())


def test_imp_100_validator_accepts_builder_output(tmp_path: Path) -> None:
    built = _run_builder(_sources(tmp_path))
    assert built.returncode == 0, built.stdout + built.stderr
    report = tmp_path / "imp100.json"
    report.write_text(built.stdout, encoding="utf-8")

    completed = _run_validator(report)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(completed.stdout) == {
        "evidence_level": "real-machine",
        "full_lite_performance_thresholds_defined": False,
        "lite_v1_complete": False,
        "manual_privacy_review_required": True,
        "measurement_scope": "doll-local-runtime-single-model-repeatability",
        "phase6_gate_complete": False,
        "real_machine_repeatability_accepted": False,
        "repeatability_variance_release_requirement_defined": False,
        "result": "pass",
        "session_count": 3,
        "validated_commit_sha": _head(),
    }


def test_imp_100_builder_requires_three_source_sessions(tmp_path: Path) -> None:
    completed = _run_builder(_sources(tmp_path)[:2])

    assert completed.returncode == 2
    failure = json.loads(completed.stdout)
    assert failure["result"] == "fail"
    assert failure["message"] == "exactly 3 source sessions are required"


def test_imp_100_builder_requires_operator_confirmations(tmp_path: Path) -> None:
    completed = _run_builder(_sources(tmp_path), confirmations=False)

    assert completed.returncode == 2
    failure = json.loads(completed.stdout)
    assert failure["result"] == "fail"
    assert "invocation confirmation" in failure["message"]


def test_imp_100_builder_rejects_mixed_model_revision(tmp_path: Path) -> None:
    sources = _sources(tmp_path)
    payload = json.loads(sources[2].read_text(encoding="utf-8"))
    observation = cast(dict[str, object], payload["observation"])
    model = cast(dict[str, object], observation["model"])
    model["revision"] = "sha256-" + "0" * 64
    sources[2].write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    completed = _run_builder(sources)

    assert completed.returncode == 2
    failure = json.loads(completed.stdout)
    assert failure["result"] == "fail"
    assert "mixed model identity" in failure["message"]


def test_imp_100_builder_rejects_unreviewable_source_privacy(tmp_path: Path) -> None:
    sources = _sources(tmp_path)
    payload = json.loads(sources[1].read_text(encoding="utf-8"))
    privacy = cast(dict[str, object], payload["privacy"])
    privacy["hostnames_in_report"] = True
    sources[1].write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    completed = _run_builder(sources)

    assert completed.returncode == 2
    failure = json.loads(completed.stdout)
    assert failure["result"] == "fail"
    assert "privacy flags must all be false" in failure["message"]


def test_imp_100_validator_rejects_wrong_commit(tmp_path: Path) -> None:
    built = _run_builder(_sources(tmp_path))
    assert built.returncode == 0, built.stdout + built.stderr
    report = tmp_path / "imp100.json"
    report.write_text(built.stdout, encoding="utf-8")

    completed = _run_validator(report, expected_commit_sha="0" * 40)

    assert completed.returncode == 2
    failure = json.loads(completed.stdout)
    assert failure["result"] == "fail"
    assert failure["message"] == "invalid commit_sha"


def test_imp_100_validator_rejects_release_overclaim(tmp_path: Path) -> None:
    built = _run_builder(_sources(tmp_path))
    assert built.returncode == 0, built.stdout + built.stderr
    payload = json.loads(built.stdout)
    payload["claims"]["minimum_system_ram_requirement_defined"] = True
    report = tmp_path / "imp100.json"
    report.write_text(json.dumps(payload), encoding="utf-8")

    completed = _run_validator(report)

    assert completed.returncode == 2
    failure = json.loads(completed.stdout)
    assert failure["result"] == "fail"
    assert "forbidden performance or release claim" in failure["message"]


def test_imp_100_validator_rejects_inconsistent_variance(tmp_path: Path) -> None:
    built = _run_builder(_sources(tmp_path))
    assert built.returncode == 0, built.stdout + built.stderr
    payload = json.loads(built.stdout)
    payload["variance"]["doll_process_peak_rss_bytes"]["spread"] = 1
    report = tmp_path / "imp100.json"
    report.write_text(json.dumps(payload), encoding="utf-8")

    completed = _run_validator(report)

    assert completed.returncode == 2
    failure = json.loads(completed.stdout)
    assert failure["result"] == "fail"
    assert "doll RSS variance spread is inconsistent" in failure["message"]


def test_imp_100_validator_rejects_private_source_path_key(tmp_path: Path) -> None:
    built = _run_builder(_sources(tmp_path))
    assert built.returncode == 0, built.stdout + built.stderr
    payload = json.loads(built.stdout)
    payload["sessions"][0]["source_path"] = "/private/source.json"
    report = tmp_path / "imp100.json"
    report.write_text(json.dumps(payload), encoding="utf-8")

    completed = _run_validator(report)

    assert completed.returncode == 2
    failure = json.loads(completed.stdout)
    assert failure["result"] == "fail"
    assert "unexpected fields" in failure["message"]
