"""Validate privacy-safe IMP-100 local-runtime repeatability/variance evidence."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import cast

TEST_ID = "IMP-100-LOCAL-RUNTIME-REPEATABILITY-VARIANCE"
SOURCE_TEST_ID = "IMP-098-LOCAL-RUNTIME-RESOURCE-MEASUREMENT"
MODEL_ID = re.compile(r"^ollama\.model\.[0-9a-f]{64}$")
REVISION = re.compile(r"^sha256-[0-9a-f]{64}$")
SHA = re.compile(r"^[0-9a-f]{40}$")
SOURCE_HASH = re.compile(r"^[0-9a-f]{64}$")
SESSION_COUNT = 3


class Imp100RepeatabilityValidationError(RuntimeError):
    """Raised when proposed IMP-100 repeatability evidence is unacceptable."""


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise Imp100RepeatabilityValidationError(f"{label} must be a JSON object")
    return cast(dict[str, object], value)


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise Imp100RepeatabilityValidationError(f"{label} must be a positive integer")
    return value


def _positive_int_list(value: object, length: int, label: str) -> list[int]:
    if not isinstance(value, list) or len(value) != length:
        raise Imp100RepeatabilityValidationError(f"{label} has invalid length")
    return [_positive_int(item, label) for item in value]


def _validate_summary(value: object, expected_values: list[int], label: str) -> None:
    summary = _object(value, label)
    if summary.get("values") != expected_values:
        raise Imp100RepeatabilityValidationError(f"{label} values are inconsistent")
    expected = {
        "minimum": min(expected_values),
        "maximum": max(expected_values),
        "mean_floor": sum(expected_values) // len(expected_values),
        "spread": max(expected_values) - min(expected_values),
    }
    for key, expected_value in expected.items():
        if summary.get(key) != expected_value:
            raise Imp100RepeatabilityValidationError(f"{label} {key} is inconsistent")
    if set(summary) != {"values", "minimum", "maximum", "mean_floor", "spread"}:
        raise Imp100RepeatabilityValidationError(f"{label} has unexpected fields")


def load_and_validate_repeatability_evidence(
    path: Path,
    *,
    expected_commit_sha: str,
) -> dict[str, object]:
    if SHA.fullmatch(expected_commit_sha) is None:
        raise Imp100RepeatabilityValidationError("expected commit SHA is invalid")
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Imp100RepeatabilityValidationError("evidence file is not valid UTF-8 JSON") from exc
    document = _object(payload, "evidence")

    expected = {
        "test_id": TEST_ID,
        "specification_version": "0.1",
        "commit_sha": expected_commit_sha,
        "result": "pass",
        "evidence_level": "real-machine",
        "operating_system": "Darwin",
        "architecture": "x86_64",
        "measurement_scope": "doll-local-runtime-single-model-repeatability",
        "source_measurement_test_id": SOURCE_TEST_ID,
        "session_count": SESSION_COUNT,
        "separate_measurement_session_invocations_confirmed": True,
        "source_manual_privacy_review_confirmed": True,
        "real_machine_repeatability_collected": True,
        "real_machine_repeatability_accepted": False,
        "cold_start_repeatability_measured": False,
    }
    for key, value in expected.items():
        if document.get(key) != value:
            raise Imp100RepeatabilityValidationError(f"invalid {key}")

    identity = _object(document.get("identity"), "identity")
    if set(identity) != {
        "python_version",
        "runtime_version",
        "model_id",
        "model_revision",
        "provider_reported_installed_size_bytes",
    }:
        raise Imp100RepeatabilityValidationError("identity has unexpected fields")
    for key in ["python_version", "runtime_version"]:
        value = identity.get(key)
        if not isinstance(value, str) or not value:
            raise Imp100RepeatabilityValidationError(f"identity {key} is missing")
    model_id = identity.get("model_id")
    revision = identity.get("model_revision")
    if not isinstance(model_id, str) or MODEL_ID.fullmatch(model_id) is None:
        raise Imp100RepeatabilityValidationError("opaque model identity is invalid")
    if not isinstance(revision, str) or REVISION.fullmatch(revision) is None:
        raise Imp100RepeatabilityValidationError("model revision is invalid")
    _positive_int(
        identity.get("provider_reported_installed_size_bytes"),
        "provider-reported installed model size",
    )

    sessions_value = document.get("sessions")
    if not isinstance(sessions_value, list) or len(sessions_value) != SESSION_COUNT:
        raise Imp100RepeatabilityValidationError("invalid session count")
    sessions = [_object(item, "session") for item in sessions_value]
    source_hashes: list[str] = []
    runtime_maxima: list[int] = []
    doll_peaks: list[int] = []
    duration_positions: list[list[int]] = [[] for _ in range(3)]
    for ordinal, session in enumerate(sessions, start=1):
        if set(session) != {
            "session_ordinal",
            "source_sha256",
            "maximum_sampled_runtime_process_tree_rss_bytes",
            "doll_process_peak_rss_bytes",
            "generation_duration_values_ns",
            "generation_output_char_counts",
        }:
            raise Imp100RepeatabilityValidationError(f"session {ordinal} has unexpected fields")
        if session.get("session_ordinal") != ordinal:
            raise Imp100RepeatabilityValidationError("session ordinals are inconsistent")
        source_hash = session.get("source_sha256")
        if not isinstance(source_hash, str) or SOURCE_HASH.fullmatch(source_hash) is None:
            raise Imp100RepeatabilityValidationError("source report hash is invalid")
        source_hashes.append(source_hash)
        runtime_maxima.append(
            _positive_int(
                session.get("maximum_sampled_runtime_process_tree_rss_bytes"),
                f"session {ordinal} maximum runtime RSS",
            )
        )
        doll_peaks.append(
            _positive_int(
                session.get("doll_process_peak_rss_bytes"),
                f"session {ordinal} doll peak RSS",
            )
        )
        durations = _positive_int_list(
            session.get("generation_duration_values_ns"),
            3,
            f"session {ordinal} generation durations",
        )
        _positive_int_list(
            session.get("generation_output_char_counts"),
            3,
            f"session {ordinal} output character counts",
        )
        for position, duration in enumerate(durations):
            duration_positions[position].append(duration)
    if len(set(source_hashes)) != SESSION_COUNT:
        raise Imp100RepeatabilityValidationError("source report hashes must be distinct")

    variance = _object(document.get("variance"), "variance")
    if set(variance) != {
        "maximum_sampled_runtime_process_tree_rss_bytes",
        "doll_process_peak_rss_bytes",
        "generation_duration_by_position_ns",
    }:
        raise Imp100RepeatabilityValidationError("variance has unexpected fields")
    _validate_summary(
        variance.get("maximum_sampled_runtime_process_tree_rss_bytes"),
        runtime_maxima,
        "runtime RSS variance",
    )
    _validate_summary(
        variance.get("doll_process_peak_rss_bytes"),
        doll_peaks,
        "doll RSS variance",
    )
    duration_summaries = variance.get("generation_duration_by_position_ns")
    if not isinstance(duration_summaries, list) or len(duration_summaries) != 3:
        raise Imp100RepeatabilityValidationError("generation duration variance is invalid")
    for position, (summary_value, values) in enumerate(
        zip(duration_summaries, duration_positions, strict=True),
        start=1,
    ):
        summary = _object(summary_value, f"generation position {position}")
        if summary.get("generation_position") != position:
            raise Imp100RepeatabilityValidationError(
                "generation duration positions are inconsistent"
            )
        comparable = dict(summary)
        comparable.pop("generation_position")
        _validate_summary(
            comparable,
            values,
            f"generation position {position} variance",
        )

    checks = _object(document.get("checks"), "checks")
    if not checks or not all(value is True for value in checks.values()):
        raise Imp100RepeatabilityValidationError("all repeatability checks must pass")
    claims = _object(document.get("claims"), "claims")
    required_false_claims = {
        "minimum_system_ram_requirement_defined",
        "total_system_peak_memory_measured",
        "gpu_or_metal_memory_requirement_defined",
        "full_lite_installation_disk_requirement_defined",
        "final_user_visible_latency_requirement_defined",
        "cold_start_requirement_defined",
        "cross_machine_performance_supported",
        "supported_or_default_model_selected",
        "repeatability_variance_release_requirement_defined",
        "full_lite_performance_thresholds_defined",
        "lite_performance_gate_complete",
        "accessibility_gate_complete",
        "release_candidate_soak_complete",
        "phase6_gate_complete",
        "lite_v1_complete",
    }
    if set(claims) != required_false_claims or any(claims.values()):
        raise Imp100RepeatabilityValidationError("forbidden performance or release claim detected")
    privacy = _object(document.get("privacy"), "privacy")
    required_privacy_flags = {
        "source_file_paths_in_report",
        "absolute_paths_in_report",
        "credentials_in_report",
        "fixed_prompt_text_in_report",
        "hostnames_in_report",
        "native_model_names_in_report",
        "process_command_lines_in_report",
        "process_ids_in_report",
        "prompt_or_response_text_in_report",
        "secret_values_in_report",
        "usernames_in_report",
        "workspace_identifiers_in_report",
        "urls_in_report",
        "email_addresses_in_report",
    }
    if set(privacy) != required_privacy_flags or any(
        value is not False for value in privacy.values()
    ):
        raise Imp100RepeatabilityValidationError("privacy flags must all be false")

    forbidden_keys = {
        "source_path",
        "source_paths",
        "native_model_name",
        "prompt",
        "prompt_text",
        "response",
        "response_text",
        "pid",
        "command_line",
        "hostname",
        "username",
        "absolute_path",
        "email",
        "url",
    }

    def inspect_keys(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in forbidden_keys:
                    raise Imp100RepeatabilityValidationError(
                        f"forbidden shareable evidence key: {key}"
                    )
                inspect_keys(child)
        elif isinstance(value, list):
            for child in value:
                inspect_keys(child)

    inspect_keys(document)
    return {
        "result": "pass",
        "validated_commit_sha": expected_commit_sha,
        "evidence_level": "real-machine",
        "measurement_scope": "doll-local-runtime-single-model-repeatability",
        "session_count": SESSION_COUNT,
        "real_machine_repeatability_accepted": False,
        "repeatability_variance_release_requirement_defined": False,
        "full_lite_performance_thresholds_defined": False,
        "phase6_gate_complete": False,
        "lite_v1_complete": False,
        "manual_privacy_review_required": True,
    }


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence_path", type=Path)
    parser.add_argument("--expected-commit-sha", required=True)
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    try:
        result = load_and_validate_repeatability_evidence(
            arguments.evidence_path,
            expected_commit_sha=arguments.expected_commit_sha,
        )
    except Imp100RepeatabilityValidationError as exc:
        print(
            json.dumps(
                {
                    "result": "fail",
                    "error_class": type(exc).__name__,
                    "message": str(exc),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
