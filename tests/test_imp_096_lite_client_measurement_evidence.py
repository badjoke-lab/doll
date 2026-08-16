"""Deterministic validation coverage for IMP-096 real-machine measurement evidence."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

_SHA = "a" * 40


def _load_validator() -> ModuleType:
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "validate_imp_096_lite_client_measurement.py"
    )
    spec = importlib.util.spec_from_file_location("_imp096_evidence_validator", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _checks() -> dict[str, bool]:
    return {
        "measurement_schema_valid": True,
        "measurement_scope_is_client_only": True,
        "step_order_is_fixed": True,
        "all_step_durations_non_negative": True,
        "total_duration_non_negative": True,
        "workspace_disk_bytes_positive": True,
        "workspace_file_count_positive": True,
        "workspace_directory_count_positive": True,
        "process_peak_rss_available": True,
        "process_peak_rss_non_negative": True,
        "process_current_rss_non_negative_when_available": True,
        "doctor_passed": True,
        "no_network_attempt": True,
        "no_process_attempt": True,
        "external_runtime_memory_excluded": True,
        "model_memory_excluded": True,
        "model_execution_not_used": True,
        "cloud_access_not_used": True,
        "thresholds_not_invented": True,
        "lite_performance_gate_not_claimed": True,
        "phase6_gate_not_claimed": True,
        "lite_v1_not_claimed": True,
    }


def _measurement() -> dict[str, object]:
    return {
        "schema_version": 1,
        "measurement_scope": "doll-lite-client-only",
        "operating_system": "Darwin",
        "architecture": "x86_64",
        "python_version": "3.12.13",
        "steps": [
            {"step_id": "workspace_initialize", "duration_ns": 10},
            {"step_id": "state_initialize", "duration_ns": 20},
            {"step_id": "workspace_load", "duration_ns": 30},
            {"step_id": "state_read_only_open", "duration_ns": 40},
            {"step_id": "doctor_read_only", "duration_ns": 50},
        ],
        "total_duration_ns": 200,
        "process_rss": {
            "source": "resource-ru_maxrss",
            "available": True,
            "current_bytes": None,
            "peak_bytes": 80_000_000,
        },
        "workspace_disk": {
            "total_bytes": 100_000,
            "file_count": 12,
            "directory_count": 8,
        },
        "doctor_overall_status": "pass",
        "state_schema_version": 3,
        "state_revision": 0,
        "state_record_count": 0,
        "synthetic_fixture_created": True,
        "post_setup_read_only_operations": True,
        "external_runtime_memory_included": False,
        "model_memory_included": False,
        "model_execution_used": False,
        "network_access_used": False,
        "cloud_access_used": False,
        "automatic_download_used": False,
        "thresholds_applied": False,
        "lite_performance_gate_complete": False,
        "phase6_gate_complete": False,
        "lite_v1_complete": False,
    }


def _privacy() -> dict[str, bool]:
    return {
        "absolute_paths_in_report": False,
        "usernames_in_report": False,
        "hostnames_in_report": False,
        "model_names_in_report": False,
        "request_or_source_text_in_report": False,
        "credentials_in_report": False,
        "secret_values_in_report": False,
        "workspace_identifiers_in_report": False,
    }


def _payload() -> dict[str, object]:
    return {
        "test_id": "IMP-083-LITE-CLIENT-MEASUREMENT",
        "specification_version": "0.2",
        "commit_sha": _SHA,
        "result": "pass",
        "evidence_level": "real-machine",
        "operating_system": "Darwin",
        "architecture": "x86_64",
        "python_version": "3.12.13",
        "network_mode": "offline-confirmed",
        "checks": _checks(),
        "measurement": _measurement(),
        "measured_workload_network_attempt_count": 0,
        "measured_workload_process_attempt_count": 0,
        "measured_workload_process_launch_used": False,
        "evidence_wrapper_git_process_used": True,
        "real_machine_evidence": True,
        "performance_thresholds_defined": False,
        "external_runtime_memory_measured": False,
        "model_memory_measured": False,
        "lite_performance_gate_complete": False,
        "phase6_gate_complete": False,
        "lite_v1_complete": False,
        "privacy": _privacy(),
    }


def _error(validator: ModuleType) -> type[Exception]:
    return cast(type[Exception], validator.Imp096EvidenceValidationError)


def test_imp_096_accepts_exact_real_machine_contract_without_release_overclaim() -> None:
    validator = _load_validator()
    result = validator.validate_evidence(_payload(), expected_commit_sha=_SHA)

    assert result == {
        "result": "pass",
        "validated_commit_sha": _SHA,
        "evidence_level": "real-machine",
        "measurement_scope": "doll-lite-client-only",
        "performance_thresholds_defined": False,
        "phase6_gate_complete": False,
        "lite_v1_complete": False,
        "manual_privacy_review_required": True,
    }


def test_imp_096_rejects_wrong_identity_machine_or_commit() -> None:
    validator = _load_validator()
    cases = (
        ("test_id", "wrong", "test_id"),
        ("specification_version", "9", "specification_version"),
        ("commit_sha", "b" * 40, "commit SHA"),
        ("result", "fail", "result"),
        ("evidence_level", "ci", "evidence_level"),
        ("operating_system", "Linux", "operating_system"),
        ("architecture", "arm64", "architecture"),
        ("python_version", "private version text", "Python version"),
        ("network_mode", "synthetic-guarded-no-network", "network_mode"),
    )
    for field, replacement, message in cases:
        payload = _payload()
        payload[field] = replacement
        with pytest.raises(_error(validator), match=message):
            validator.validate_evidence(payload, expected_commit_sha=_SHA)

    with pytest.raises(_error(validator), match="expected commit SHA"):
        validator.validate_evidence(_payload(), expected_commit_sha="not-a-sha")


def test_imp_096_requires_exact_top_level_checks_and_privacy_contract() -> None:
    validator = _load_validator()

    payload = _payload()
    payload["unexpected"] = "not accepted"
    with pytest.raises(_error(validator), match="evidence keys are invalid"):
        validator.validate_evidence(payload, expected_commit_sha=_SHA)

    payload = _payload()
    checks = cast(dict[str, bool], payload["checks"])
    checks["doctor_passed"] = False
    with pytest.raises(_error(validator), match="every IMP-083 measurement check"):
        validator.validate_evidence(payload, expected_commit_sha=_SHA)

    payload = _payload()
    checks = cast(dict[str, bool], payload["checks"])
    checks.pop("doctor_passed")
    with pytest.raises(_error(validator), match="checks keys are invalid"):
        validator.validate_evidence(payload, expected_commit_sha=_SHA)

    payload = _payload()
    privacy = cast(dict[str, bool], payload["privacy"])
    privacy["hostnames_in_report"] = True
    with pytest.raises(_error(validator), match="privacy flag"):
        validator.validate_evidence(payload, expected_commit_sha=_SHA)

    payload = _payload()
    privacy = cast(dict[str, bool], payload["privacy"])
    privacy["invented_flag"] = False
    with pytest.raises(_error(validator), match="privacy keys are invalid"):
        validator.validate_evidence(payload, expected_commit_sha=_SHA)


def test_imp_096_rejects_network_process_and_release_claim_changes() -> None:
    validator = _load_validator()

    payload = _payload()
    payload["measured_workload_network_attempt_count"] = 1
    with pytest.raises(_error(validator), match="must be zero"):
        validator.validate_evidence(payload, expected_commit_sha=_SHA)

    payload = _payload()
    payload["measured_workload_process_attempt_count"] = True
    with pytest.raises(_error(validator), match="non-negative integer"):
        validator.validate_evidence(payload, expected_commit_sha=_SHA)

    for field in (
        "measured_workload_process_launch_used",
        "performance_thresholds_defined",
        "external_runtime_memory_measured",
        "model_memory_measured",
        "lite_performance_gate_complete",
        "phase6_gate_complete",
        "lite_v1_complete",
    ):
        payload = _payload()
        payload[field] = True
        with pytest.raises(_error(validator), match="must be false"):
            validator.validate_evidence(payload, expected_commit_sha=_SHA)

    payload = _payload()
    payload["evidence_wrapper_git_process_used"] = False
    with pytest.raises(_error(validator), match="must be true"):
        validator.validate_evidence(payload, expected_commit_sha=_SHA)

    payload = _payload()
    payload["real_machine_evidence"] = False
    with pytest.raises(_error(validator), match="must be true"):
        validator.validate_evidence(payload, expected_commit_sha=_SHA)


def test_imp_096_validates_fixed_measurement_shape_order_and_nonclaims() -> None:
    validator = _load_validator()

    payload = _payload()
    measurement = cast(dict[str, object], payload["measurement"])
    measurement["extra"] = False
    with pytest.raises(_error(validator), match="measurement keys are invalid"):
        validator.validate_evidence(payload, expected_commit_sha=_SHA)

    payload = _payload()
    measurement = cast(dict[str, object], payload["measurement"])
    steps = cast(list[dict[str, object]], measurement["steps"])
    steps[0], steps[1] = steps[1], steps[0]
    with pytest.raises(_error(validator), match="step order"):
        validator.validate_evidence(payload, expected_commit_sha=_SHA)

    payload = _payload()
    measurement = cast(dict[str, object], payload["measurement"])
    steps = cast(list[dict[str, object]], measurement["steps"])
    steps[0]["duration_ns"] = -1
    with pytest.raises(_error(validator), match="non-negative integer"):
        validator.validate_evidence(payload, expected_commit_sha=_SHA)

    payload = _payload()
    measurement = cast(dict[str, object], payload["measurement"])
    measurement["operating_system"] = "Linux"
    with pytest.raises(_error(validator), match="operating_system"):
        validator.validate_evidence(payload, expected_commit_sha=_SHA)

    payload = _payload()
    measurement = cast(dict[str, object], payload["measurement"])
    measurement["thresholds_applied"] = True
    with pytest.raises(_error(validator), match="must be false"):
        validator.validate_evidence(payload, expected_commit_sha=_SHA)


def test_imp_096_validates_rss_disk_and_state_measurements() -> None:
    validator = _load_validator()

    payload = _payload()
    rss = cast(dict[str, object], cast(dict[str, object], payload["measurement"])["process_rss"])
    rss["source"] = "unavailable"
    with pytest.raises(_error(validator), match="source"):
        validator.validate_evidence(payload, expected_commit_sha=_SHA)

    payload = _payload()
    rss = cast(dict[str, object], cast(dict[str, object], payload["measurement"])["process_rss"])
    rss["peak_bytes"] = None
    with pytest.raises(_error(validator), match="peak bytes"):
        validator.validate_evidence(payload, expected_commit_sha=_SHA)

    payload = _payload()
    rss = cast(dict[str, object], cast(dict[str, object], payload["measurement"])["process_rss"])
    rss["current_bytes"] = 90
    rss["peak_bytes"] = 80
    with pytest.raises(_error(validator), match="exceed peak"):
        validator.validate_evidence(payload, expected_commit_sha=_SHA)

    payload = _payload()
    disk = cast(dict[str, object], cast(dict[str, object], payload["measurement"])["workspace_disk"])
    disk["total_bytes"] = 0
    with pytest.raises(_error(validator), match="outside the accepted range"):
        validator.validate_evidence(payload, expected_commit_sha=_SHA)

    payload = _payload()
    measurement = cast(dict[str, object], payload["measurement"])
    measurement["state_revision"] = -1
    with pytest.raises(_error(validator), match="non-negative integer"):
        validator.validate_evidence(payload, expected_commit_sha=_SHA)


def test_imp_096_file_loader_is_bounded_strict_and_symlink_safe(tmp_path: Path) -> None:
    validator = _load_validator()
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps(_payload(), sort_keys=True), encoding="utf-8")
    assert validator.load_and_validate_evidence(
        evidence,
        expected_commit_sha=_SHA,
    )["result"] == "pass"

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{", encoding="utf-8")
    with pytest.raises(_error(validator), match="strict JSON"):
        validator.load_and_validate_evidence(malformed, expected_commit_sha=_SHA)

    nonstandard = tmp_path / "nonstandard.json"
    nonstandard.write_text('{"value":NaN}', encoding="utf-8")
    with pytest.raises(_error(validator), match="strict JSON"):
        validator.load_and_validate_evidence(nonstandard, expected_commit_sha=_SHA)

    binary = tmp_path / "binary.json"
    binary.write_bytes(b"\xff\xfe")
    with pytest.raises(_error(validator), match="strict UTF-8"):
        validator.load_and_validate_evidence(binary, expected_commit_sha=_SHA)

    empty = tmp_path / "empty.json"
    empty.write_bytes(b"")
    with pytest.raises(_error(validator), match="size"):
        validator.load_and_validate_evidence(empty, expected_commit_sha=_SHA)

    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"x" * (validator.MAX_EVIDENCE_BYTES + 1))
    with pytest.raises(_error(validator), match="size"):
        validator.load_and_validate_evidence(oversized, expected_commit_sha=_SHA)

    link = tmp_path / "evidence-link.json"
    try:
        link.symlink_to(evidence)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(_error(validator), match="regular non-symlink"):
        validator.load_and_validate_evidence(link, expected_commit_sha=_SHA)


def test_imp_096_file_loader_rejects_non_path_and_changed_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validator = _load_validator()
    with pytest.raises(_error(validator), match="path is invalid"):
        validator.load_and_validate_evidence(cast(Path, "evidence.json"), expected_commit_sha=_SHA)

    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps(_payload()), encoding="utf-8")
    original_read = Path.read_bytes

    def shorter_read(self: Path) -> bytes:
        data = original_read(self)
        return data[:-1] if self == evidence else data

    monkeypatch.setattr(Path, "read_bytes", shorter_read)
    with pytest.raises(_error(validator), match="changed while being read"):
        validator.load_and_validate_evidence(evidence, expected_commit_sha=_SHA)
