"""Validate privacy-safe IMP-098 primary Intel Mac runtime/model evidence."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import cast

TEST_ID = "IMP-098-LOCAL-RUNTIME-RESOURCE-MEASUREMENT"
MODEL_ID = re.compile(r"^ollama\.model\.[0-9a-f]{64}$")
REVISION = re.compile(r"^sha256-[0-9a-f]{64}$")
SHA = re.compile(r"^[0-9a-f]{40}$")
REPEAT_COUNT = 3


class Imp098EvidenceValidationError(RuntimeError):
    """Raised when proposed IMP-098 real-machine evidence is not acceptable."""


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise Imp098EvidenceValidationError(f"{label} must be a JSON object")
    return cast(dict[str, object], value)


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise Imp098EvidenceValidationError(f"{label} must be a positive integer")
    return value


def _positive_int_list(value: object, length: int, label: str) -> list[int]:
    if not isinstance(value, list) or len(value) != length:
        raise Imp098EvidenceValidationError(f"{label} has invalid length")
    return [_positive_int(item, label) for item in value]


def load_and_validate_evidence(
    path: Path,
    *,
    expected_commit_sha: str,
) -> dict[str, object]:
    if SHA.fullmatch(expected_commit_sha) is None:
        raise Imp098EvidenceValidationError("expected commit SHA is invalid")
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8", errors="strict"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Imp098EvidenceValidationError("evidence file is not valid UTF-8 JSON") from exc
    document = _object(payload, "evidence")

    expected = {
        "test_id": TEST_ID,
        "specification_version": "0.1",
        "commit_sha": expected_commit_sha,
        "result": "pass",
        "evidence_level": "real-machine",
        "operating_system": "Darwin",
        "measurement_scope": "doll-local-runtime-single-model",
        "repeat_count": REPEAT_COUNT,
        "synthetic_observations": False,
        "real_machine_measurement_collected": True,
        "real_machine_measurement_accepted": False,
        "loopback_runtime_request_used": True,
        "external_network_request_used": False,
        "cloud_credentials_used": False,
        "automatic_model_download_used": False,
        "runtime_install_or_start_used": False,
        "measurement_wrapper_process_inspection_used": True,
        "cold_start_measured": False,
    }
    for key, value in expected.items():
        if document.get(key) != value:
            raise Imp098EvidenceValidationError(f"invalid {key}")
    architecture = document.get("architecture")
    if not isinstance(architecture, str) or architecture.casefold() not in {
        "x86_64",
        "amd64",
    }:
        raise Imp098EvidenceValidationError("invalid primary Intel Mac architecture")
    if document.get("network_mode") != "offline-confirmed":
        raise Imp098EvidenceValidationError("real-machine evidence must be offline-confirmed")
    python_version = document.get("python_version")
    if not isinstance(python_version, str) or not python_version:
        raise Imp098EvidenceValidationError("Python version is missing")

    observation = _object(document.get("observation"), "observation")
    runtime_version = observation.get("runtime_version")
    if not isinstance(runtime_version, str) or not runtime_version:
        raise Imp098EvidenceValidationError("runtime version is missing")
    model = _object(observation.get("model"), "model")
    model_id = model.get("model_id")
    revision = model.get("revision")
    if not isinstance(model_id, str) or MODEL_ID.fullmatch(model_id) is None:
        raise Imp098EvidenceValidationError("opaque model identity is invalid")
    if not isinstance(revision, str) or REVISION.fullmatch(revision) is None:
        raise Imp098EvidenceValidationError("model revision is invalid")
    _positive_int(
        model.get("provider_reported_installed_size_bytes"),
        "provider-reported installed model size",
    )

    runtime_rss = _positive_int_list(
        observation.get("runtime_process_tree_rss_samples_bytes"),
        REPEAT_COUNT + 1,
        "runtime process-tree RSS samples",
    )
    process_counts = _positive_int_list(
        observation.get("runtime_process_count_samples"),
        REPEAT_COUNT + 1,
        "runtime process count samples",
    )
    del process_counts
    maximum_rss = _positive_int(
        observation.get("maximum_sampled_runtime_process_tree_rss_bytes"),
        "maximum sampled runtime process-tree RSS",
    )
    if maximum_rss != max(runtime_rss):
        raise Imp098EvidenceValidationError("maximum runtime RSS does not match samples")

    doll_rss = _object(observation.get("doll_process_rss"), "doll process RSS")
    if doll_rss.get("source") != "resource-ru_maxrss":
        raise Imp098EvidenceValidationError("unexpected primary Mac doll RSS source")
    current = doll_rss.get("current_bytes")
    if current is not None and (
        isinstance(current, bool) or not isinstance(current, int) or current < 0
    ):
        raise Imp098EvidenceValidationError("doll current RSS is invalid")
    _positive_int(doll_rss.get("peak_bytes"), "doll peak RSS")

    duration = _object(observation.get("generation_duration"), "generation duration")
    values = _positive_int_list(
        duration.get("values_ns"),
        REPEAT_COUNT,
        "generation durations",
    )
    if duration.get("minimum_ns") != min(values):
        raise Imp098EvidenceValidationError("generation minimum is inconsistent")
    if duration.get("maximum_ns") != max(values):
        raise Imp098EvidenceValidationError("generation maximum is inconsistent")
    if duration.get("mean_floor_ns") != sum(values) // len(values):
        raise Imp098EvidenceValidationError("generation mean is inconsistent")
    if duration.get("spread_ns") != max(values) - min(values):
        raise Imp098EvidenceValidationError("generation spread is inconsistent")
    _positive_int_list(
        observation.get("generation_output_char_counts"),
        REPEAT_COUNT,
        "generation output character counts",
    )

    checks = _object(document.get("checks"), "checks")
    if not checks or not all(value is True for value in checks.values()):
        raise Imp098EvidenceValidationError("all measurement checks must pass")
    claims = _object(document.get("claims"), "claims")
    required_false_claims = {
        "minimum_system_ram_requirement_defined",
        "total_system_peak_memory_measured",
        "gpu_or_metal_memory_requirement_defined",
        "full_lite_installation_disk_requirement_defined",
        "final_user_visible_latency_requirement_defined",
        "cross_machine_performance_supported",
        "supported_or_default_model_selected",
        "full_lite_performance_thresholds_defined",
        "lite_performance_gate_complete",
        "phase6_gate_complete",
        "lite_v1_complete",
    }
    if set(claims) != required_false_claims or any(claims.values()):
        raise Imp098EvidenceValidationError("forbidden performance or release claim detected")
    privacy = _object(document.get("privacy"), "privacy")
    if not privacy or any(value is not False for value in privacy.values()):
        raise Imp098EvidenceValidationError("privacy flags must all be false")

    forbidden_keys = {
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
    }

    def inspect_keys(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in forbidden_keys:
                    raise Imp098EvidenceValidationError(
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
        "measurement_scope": "doll-local-runtime-single-model",
        "repeat_count": REPEAT_COUNT,
        "real_machine_measurement_accepted": False,
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
        result = load_and_validate_evidence(
            arguments.evidence_path,
            expected_commit_sha=arguments.expected_commit_sha,
        )
    except Imp098EvidenceValidationError as exc:
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
