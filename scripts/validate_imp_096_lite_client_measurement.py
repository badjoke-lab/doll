"""Validate one privacy-reviewed IMP-083 primary Intel Mac measurement for IMP-096."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import cast

TEST_ID = "IMP-083-LITE-CLIENT-MEASUREMENT"
SPECIFICATION_VERSION = "0.2"
MAX_EVIDENCE_BYTES = 256 * 1024
SHA = re.compile(r"^[0-9a-f]{40}$")
_VERSION = re.compile(r"^\d+\.\d+(?:\.\d+)?(?:[-+][A-Za-z0-9._-]+)?$")

_EXPECTED_STEPS = (
    "workspace_initialize",
    "state_initialize",
    "workspace_load",
    "state_read_only_open",
    "doctor_read_only",
)

_TOP_LEVEL_KEYS = frozenset(
    {
        "test_id",
        "specification_version",
        "commit_sha",
        "result",
        "evidence_level",
        "operating_system",
        "architecture",
        "python_version",
        "network_mode",
        "checks",
        "measurement",
        "measured_workload_network_attempt_count",
        "measured_workload_process_attempt_count",
        "measured_workload_process_launch_used",
        "evidence_wrapper_git_process_used",
        "real_machine_evidence",
        "performance_thresholds_defined",
        "external_runtime_memory_measured",
        "model_memory_measured",
        "lite_performance_gate_complete",
        "phase6_gate_complete",
        "lite_v1_complete",
        "privacy",
    }
)

_CHECK_KEYS = frozenset(
    {
        "measurement_schema_valid",
        "measurement_scope_is_client_only",
        "step_order_is_fixed",
        "all_step_durations_non_negative",
        "total_duration_non_negative",
        "workspace_disk_bytes_positive",
        "workspace_file_count_positive",
        "workspace_directory_count_positive",
        "process_peak_rss_available",
        "process_peak_rss_non_negative",
        "process_current_rss_non_negative_when_available",
        "doctor_passed",
        "no_network_attempt",
        "no_process_attempt",
        "external_runtime_memory_excluded",
        "model_memory_excluded",
        "model_execution_not_used",
        "cloud_access_not_used",
        "thresholds_not_invented",
        "lite_performance_gate_not_claimed",
        "phase6_gate_not_claimed",
        "lite_v1_not_claimed",
    }
)

_MEASUREMENT_KEYS = frozenset(
    {
        "schema_version",
        "measurement_scope",
        "operating_system",
        "architecture",
        "python_version",
        "steps",
        "total_duration_ns",
        "process_rss",
        "workspace_disk",
        "doctor_overall_status",
        "state_schema_version",
        "state_revision",
        "state_record_count",
        "synthetic_fixture_created",
        "post_setup_read_only_operations",
        "external_runtime_memory_included",
        "model_memory_included",
        "model_execution_used",
        "network_access_used",
        "cloud_access_used",
        "automatic_download_used",
        "thresholds_applied",
        "lite_performance_gate_complete",
        "phase6_gate_complete",
        "lite_v1_complete",
    }
)

_PRIVACY_KEYS = frozenset(
    {
        "absolute_paths_in_report",
        "usernames_in_report",
        "hostnames_in_report",
        "model_names_in_report",
        "request_or_source_text_in_report",
        "credentials_in_report",
        "secret_values_in_report",
        "workspace_identifiers_in_report",
    }
)


class Imp096EvidenceValidationError(RuntimeError):
    """Raised when submitted IMP-096 evidence is malformed or overclaims acceptance."""


def validate_evidence(payload: object, *, expected_commit_sha: str) -> dict[str, object]:
    """Validate exact IMP-096 real-machine evidence without interpreting thresholds."""

    expected_sha = _sha(expected_commit_sha, "expected commit SHA")
    root = _object(payload, "evidence")
    _exact_keys(root, _TOP_LEVEL_KEYS, "evidence")

    _equal(root, "test_id", TEST_ID)
    _equal(root, "specification_version", SPECIFICATION_VERSION)
    commit_sha = _sha(_string(root, "commit_sha"), "evidence commit SHA")
    if commit_sha != expected_sha:
        raise Imp096EvidenceValidationError("evidence commit SHA does not match expected commit")
    _equal(root, "result", "pass")
    _equal(root, "evidence_level", "real-machine")
    _equal(root, "operating_system", "Darwin")
    architecture = _string(root, "architecture")
    if architecture.casefold() not in {"x86_64", "amd64"}:
        raise Imp096EvidenceValidationError(
            "evidence architecture is not supported primary Intel Mac"
        )
    python_version = _string(root, "python_version")
    if _VERSION.fullmatch(python_version) is None:
        raise Imp096EvidenceValidationError("evidence Python version is invalid")
    _equal(root, "network_mode", "offline-confirmed")

    checks = _object(root.get("checks"), "checks")
    _exact_keys(checks, _CHECK_KEYS, "checks")
    if any(value is not True for value in checks.values()):
        raise Imp096EvidenceValidationError("every IMP-083 measurement check must be true")

    measurement = _object(root.get("measurement"), "measurement")
    _validate_measurement(
        measurement,
        operating_system="Darwin",
        architecture=architecture,
        python_version=python_version,
    )

    _zero(root, "measured_workload_network_attempt_count")
    _zero(root, "measured_workload_process_attempt_count")
    _false(root, "measured_workload_process_launch_used")
    _true(root, "evidence_wrapper_git_process_used")
    _true(root, "real_machine_evidence")
    for key in (
        "performance_thresholds_defined",
        "external_runtime_memory_measured",
        "model_memory_measured",
        "lite_performance_gate_complete",
        "phase6_gate_complete",
        "lite_v1_complete",
    ):
        _false(root, key)

    privacy = _object(root.get("privacy"), "privacy")
    _exact_keys(privacy, _PRIVACY_KEYS, "privacy")
    if any(value is not False for value in privacy.values()):
        raise Imp096EvidenceValidationError("every IMP-096 privacy flag must be false")

    return {
        "result": "pass",
        "validated_commit_sha": commit_sha,
        "evidence_level": "real-machine",
        "measurement_scope": "doll-lite-client-only",
        "performance_thresholds_defined": False,
        "phase6_gate_complete": False,
        "lite_v1_complete": False,
        "manual_privacy_review_required": True,
    }


def load_and_validate_evidence(path: Path, *, expected_commit_sha: str) -> dict[str, object]:
    """Read one bounded regular JSON file and validate its exact evidence contract."""

    if not isinstance(path, Path):
        raise Imp096EvidenceValidationError("evidence path is invalid")
    if path.is_symlink() or not path.is_file():
        raise Imp096EvidenceValidationError("evidence path must be a regular non-symlink file")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise Imp096EvidenceValidationError("evidence file metadata is unavailable") from exc
    if size <= 0 or size > MAX_EVIDENCE_BYTES:
        raise Imp096EvidenceValidationError("evidence file size is outside the accepted bound")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise Imp096EvidenceValidationError("evidence file is unreadable") from exc
    if len(raw) != size:
        raise Imp096EvidenceValidationError("evidence file changed while being read")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise Imp096EvidenceValidationError("evidence file must be strict UTF-8") from exc
    try:
        payload = json.loads(text, parse_constant=_reject_nonstandard_json)
    except (json.JSONDecodeError, ValueError) as exc:
        raise Imp096EvidenceValidationError("evidence file is not strict JSON") from exc
    return validate_evidence(payload, expected_commit_sha=expected_commit_sha)


def _validate_measurement(
    measurement: dict[str, object],
    *,
    operating_system: str,
    architecture: str,
    python_version: str,
) -> None:
    _exact_keys(measurement, _MEASUREMENT_KEYS, "measurement")
    _integer(measurement, "schema_version", minimum=1, exact=1)
    _equal(measurement, "measurement_scope", "doll-lite-client-only")
    _equal(measurement, "operating_system", operating_system)
    _equal(measurement, "architecture", architecture)
    _equal(measurement, "python_version", python_version)

    raw_steps = measurement.get("steps")
    if not isinstance(raw_steps, list) or len(raw_steps) != len(_EXPECTED_STEPS):
        raise Imp096EvidenceValidationError("measurement steps are invalid")
    step_ids: list[str] = []
    for index, value in enumerate(raw_steps):
        step = _object(value, f"measurement step {index}")
        _exact_keys(step, frozenset({"step_id", "duration_ns"}), f"measurement step {index}")
        step_ids.append(_string(step, "step_id"))
        _integer(step, "duration_ns", minimum=0)
    if tuple(step_ids) != _EXPECTED_STEPS:
        raise Imp096EvidenceValidationError("measurement step order is invalid")

    _integer(measurement, "total_duration_ns", minimum=0)

    rss = _object(measurement.get("process_rss"), "process RSS")
    _exact_keys(
        rss,
        frozenset({"source", "available", "current_bytes", "peak_bytes"}),
        "process RSS",
    )
    _equal(rss, "source", "resource-ru_maxrss")
    _true(rss, "available")
    current = rss.get("current_bytes")
    if current is not None:
        _nonnegative_integer_value(current, "process RSS current bytes")
    peak = _nonnegative_integer_value(rss.get("peak_bytes"), "process RSS peak bytes")
    if current is not None and cast(int, current) > peak:
        raise Imp096EvidenceValidationError("process RSS current bytes exceed peak bytes")

    disk = _object(measurement.get("workspace_disk"), "workspace disk")
    _exact_keys(
        disk,
        frozenset({"total_bytes", "file_count", "directory_count"}),
        "workspace disk",
    )
    _integer(disk, "total_bytes", minimum=1)
    _integer(disk, "file_count", minimum=1)
    _integer(disk, "directory_count", minimum=1)

    _equal(measurement, "doctor_overall_status", "pass")
    _integer(measurement, "state_schema_version", minimum=1)
    _integer(measurement, "state_revision", minimum=0)
    _integer(measurement, "state_record_count", minimum=0)
    _true(measurement, "synthetic_fixture_created")
    _true(measurement, "post_setup_read_only_operations")
    for key in (
        "external_runtime_memory_included",
        "model_memory_included",
        "model_execution_used",
        "network_access_used",
        "cloud_access_used",
        "automatic_download_used",
        "thresholds_applied",
        "lite_performance_gate_complete",
        "phase6_gate_complete",
        "lite_v1_complete",
    ):
        _false(measurement, key)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence_path", type=Path)
    parser.add_argument("--expected-commit-sha", required=True)
    return parser.parse_args()


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise Imp096EvidenceValidationError(f"{label} must be a JSON object")
    return cast(dict[str, object], value)


def _exact_keys(value: dict[str, object], expected: frozenset[str], label: str) -> None:
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise Imp096EvidenceValidationError(
            f"{label} keys are invalid (missing={missing}, extra={extra})"
        )


def _string(value: dict[str, object], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise Imp096EvidenceValidationError(f"{key} must be non-empty text")
    return result


def _equal(value: dict[str, object], key: str, expected: object) -> None:
    if value.get(key) != expected or isinstance(value.get(key), bool) != isinstance(expected, bool):
        raise Imp096EvidenceValidationError(f"{key} does not match the accepted value")


def _integer(
    value: dict[str, object],
    key: str,
    *,
    minimum: int,
    exact: int | None = None,
) -> int:
    result = _nonnegative_integer_value(value.get(key), key)
    if result < minimum or (exact is not None and result != exact):
        raise Imp096EvidenceValidationError(f"{key} is outside the accepted range")
    return result


def _nonnegative_integer_value(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise Imp096EvidenceValidationError(f"{label} must be a non-negative integer")
    return value


def _zero(value: dict[str, object], key: str) -> None:
    if _integer(value, key, minimum=0) != 0:
        raise Imp096EvidenceValidationError(f"{key} must be zero")


def _true(value: dict[str, object], key: str) -> None:
    if value.get(key) is not True:
        raise Imp096EvidenceValidationError(f"{key} must be true")


def _false(value: dict[str, object], key: str) -> None:
    if value.get(key) is not False:
        raise Imp096EvidenceValidationError(f"{key} must be false")


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or SHA.fullmatch(value) is None:
        raise Imp096EvidenceValidationError(f"{label} is invalid")
    return value


def _reject_nonstandard_json(value: str) -> object:
    raise ValueError(f"non-standard JSON constant: {value}")


def main() -> int:
    arguments = _arguments()
    try:
        result = load_and_validate_evidence(
            arguments.evidence_path,
            expected_commit_sha=arguments.expected_commit_sha,
        )
    except Imp096EvidenceValidationError as exc:
        print(
            json.dumps(
                {"result": "fail", "error_class": type(exc).__name__, "message": str(exc)},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
