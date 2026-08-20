"""Interpret accepted IMP-096 Lite-client evidence without inventing release thresholds."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

from validate_imp_096_lite_client_measurement import (
    Imp096EvidenceValidationError,
    load_and_validate_evidence,
)

EXPECTED_MEASURED_SHA = "b57ebe6fb4a7620901b95b49f6743b71ae1026f7"
INTERPRETATION_SCHEMA_VERSION = 1
TEST_ID = "IMP-097-LITE-CLIENT-PERFORMANCE-INTERPRETATION"

_REQUIRED_FUTURE_EVIDENCE = (
    "representative-local-runtime-and-model-resource-measurement",
    "repeatability-and-variance-evidence",
    "full-install-and-model-storage-measurement",
    "user-visible-latency-workload-measurement",
    "release-candidate-soak-disk-growth-evidence",
)


class Imp097PerformanceInterpretationError(RuntimeError):
    """Raised when accepted evidence cannot be interpreted safely."""


def interpret_evidence(path: Path) -> dict[str, object]:
    """Return one conservative deterministic interpretation of accepted IMP-096 evidence."""

    validated = load_and_validate_evidence(
        path,
        expected_commit_sha=EXPECTED_MEASURED_SHA,
    )
    payload = _read_validated_payload(path)
    measurement = _object(payload.get("measurement"), "measurement")
    process_rss = _object(measurement.get("process_rss"), "process RSS")
    workspace_disk = _object(measurement.get("workspace_disk"), "workspace disk")

    return {
        "schema_version": INTERPRETATION_SCHEMA_VERSION,
        "test_id": TEST_ID,
        "result": "pass",
        "source_test_id": payload["test_id"],
        "source_commit_sha": validated["validated_commit_sha"],
        "source_evidence_level": validated["evidence_level"],
        "measurement_scope": validated["measurement_scope"],
        "operating_system": payload["operating_system"],
        "architecture": payload["architecture"],
        "python_version": payload["python_version"],
        "observed_measurement": {
            "total_duration_ns": measurement["total_duration_ns"],
            "process_peak_rss_bytes": process_rss["peak_bytes"],
            "workspace_total_bytes": workspace_disk["total_bytes"],
            "workspace_file_count": workspace_disk["file_count"],
            "workspace_directory_count": workspace_disk["directory_count"],
        },
        "claims": {
            "bounded_client_workload_observed_on_primary_intel_mac": True,
            "client_only_evidence_interpretation_complete": True,
            "minimum_ram_requirement_defined": False,
            "full_install_disk_requirement_defined": False,
            "user_visible_latency_requirement_defined": False,
            "external_runtime_memory_requirement_defined": False,
            "model_memory_requirement_defined": False,
            "gpu_memory_requirement_defined": False,
            "total_system_resource_requirement_defined": False,
            "cross_machine_generalization_supported": False,
            "full_lite_performance_thresholds_defined": False,
            "lite_performance_gate_complete": False,
            "phase6_gate_complete": False,
            "lite_v1_complete": False,
            "accessibility_gate_complete": False,
            "release_candidate_soak_complete": False,
        },
        "required_future_evidence": list(_REQUIRED_FUTURE_EVIDENCE),
    }


def _read_validated_payload(path: Path) -> dict[str, object]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise Imp097PerformanceInterpretationError(
            "validated evidence could not be reread"
        ) from exc
    try:
        payload = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Imp097PerformanceInterpretationError(
            "validated evidence changed before interpretation"
        ) from exc
    return _object(payload, "evidence")


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise Imp097PerformanceInterpretationError(f"{label} must be a JSON object")
    return cast(dict[str, object], value)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence_path", type=Path)
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    try:
        result = interpret_evidence(arguments.evidence_path)
    except (Imp096EvidenceValidationError, Imp097PerformanceInterpretationError) as exc:
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
