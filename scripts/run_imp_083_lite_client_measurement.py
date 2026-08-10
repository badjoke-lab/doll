"""Run the IMP-083 Lite client resource measurement harness."""

from __future__ import annotations

import argparse
import getpass
import json
import platform
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from doll.lite_measurement import (
    LITE_CLIENT_MEASUREMENT_SCHEMA_VERSION,
    LiteClientMeasurementError,
    LiteClientResourceMeasurement,
    measure_lite_client_resources,
)

TEST_ID = "IMP-083-LITE-CLIENT-MEASUREMENT"
ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r"^[0-9a-f]{40}$")
_EXPECTED_STEPS = (
    "workspace_initialize",
    "state_initialize",
    "workspace_load",
    "state_read_only_open",
    "doctor_read_only",
)


@dataclass(slots=True)
class _MeasuredWorkloadAuditGuard:
    network_attempt_count: int = 0
    process_attempt_count: int = 0

    def hook(self, event: str, args: tuple[object, ...]) -> None:
        del args
        if event in {"socket.connect", "socket.connect_ex", "socket.getaddrinfo"}:
            self.network_attempt_count += 1
            raise RuntimeError("network access is prohibited during Lite client measurement")
        if event in {
            "subprocess.Popen",
            "os.system",
            "os.posix_spawn",
            "os.posix_spawnp",
            "os.spawn",
        }:
            self.process_attempt_count += 1
            raise RuntimeError("process launch is prohibited during Lite client measurement")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--evidence-level", choices=("ci", "real-machine"), default="ci")
    parser.add_argument("--offline-confirmed", action="store_true")
    parser.add_argument("--local-only-confirmed", action="store_true")
    return parser.parse_args()


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _validate_environment(arguments: argparse.Namespace) -> bool:
    if not SHA.fullmatch(arguments.commit_sha) or arguments.commit_sha != _head():
        raise RuntimeError("commit mismatch")
    machine = cast(str, arguments.evidence_level) == "real-machine"
    if machine:
        if (
            platform.system() != "Darwin"
            or platform.machine().casefold() not in {"x86_64", "amd64"}
            or not arguments.offline_confirmed
            or not arguments.local_only_confirmed
        ):
            raise RuntimeError("real-machine evidence rejected")
    elif arguments.offline_confirmed or arguments.local_only_confirmed:
        raise RuntimeError("CI evidence cannot accept real-machine confirmations")
    return machine


def _measurement_checks(
    measurement: LiteClientResourceMeasurement,
    guard: _MeasuredWorkloadAuditGuard,
) -> dict[str, bool]:
    payload = measurement.to_dict()
    steps = tuple(step.step_id for step in measurement.steps)
    return {
        "measurement_schema_valid": payload.get("schema_version")
        == LITE_CLIENT_MEASUREMENT_SCHEMA_VERSION,
        "measurement_scope_is_client_only": payload.get("measurement_scope")
        == "doll-lite-client-only",
        "step_order_is_fixed": steps == _EXPECTED_STEPS,
        "all_step_durations_non_negative": all(step.duration_ns >= 0 for step in measurement.steps),
        "total_duration_non_negative": measurement.total_duration_ns >= 0,
        "workspace_disk_bytes_positive": measurement.workspace_disk.total_bytes > 0,
        "workspace_file_count_positive": measurement.workspace_disk.file_count > 0,
        "workspace_directory_count_positive": measurement.workspace_disk.directory_count > 0,
        "process_peak_rss_available": measurement.process_rss.peak_bytes is not None,
        "process_peak_rss_non_negative": measurement.process_rss.peak_bytes is not None
        and measurement.process_rss.peak_bytes >= 0,
        "process_current_rss_non_negative_when_available": measurement.process_rss.current_bytes is None
        or measurement.process_rss.current_bytes >= 0,
        "doctor_passed": measurement.doctor_overall_status == "pass",
        "no_network_attempt": guard.network_attempt_count == 0,
        "no_process_attempt": guard.process_attempt_count == 0,
        "external_runtime_memory_excluded": payload.get("external_runtime_memory_included") is False,
        "model_memory_excluded": payload.get("model_memory_included") is False,
        "model_execution_not_used": payload.get("model_execution_used") is False,
        "cloud_access_not_used": payload.get("cloud_access_used") is False,
        "thresholds_not_invented": payload.get("thresholds_applied") is False,
        "lite_performance_gate_not_claimed": payload.get("lite_performance_gate_complete") is False,
        "phase6_gate_not_claimed": payload.get("phase6_gate_complete") is False,
        "lite_v1_not_claimed": payload.get("lite_v1_complete") is False,
    }


def _privacy_flags(payload: dict[str, object]) -> dict[str, bool]:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    candidates: dict[str, str] = {
        "absolute_paths_in_report": str(ROOT),
        "usernames_in_report": getpass.getuser(),
        "hostnames_in_report": platform.node(),
    }
    flags = {
        key: bool(value and value in serialized)
        for key, value in candidates.items()
    }
    flags.update(
        {
            "model_names_in_report": False,
            "request_or_source_text_in_report": False,
            "credentials_in_report": False,
            "secret_values_in_report": False,
            "workspace_identifiers_in_report": False,
        }
    )
    return flags


def main() -> int:
    arguments = _arguments()
    stage = "environment"
    try:
        machine = _validate_environment(arguments)
        guard = _MeasuredWorkloadAuditGuard()
        sys.addaudithook(guard.hook)
        stage = "measurement"
        with tempfile.TemporaryDirectory(prefix="doll-imp083-") as temporary:
            measurement = measure_lite_client_resources(Path(temporary) / "workspace")
        checks = _measurement_checks(measurement, guard)
        if not all(checks.values()):
            raise LiteClientMeasurementError("Lite client measurement checks did not pass")
        stage = "privacy"
        payload: dict[str, object] = {
            "test_id": TEST_ID,
            "specification_version": "0.2",
            "commit_sha": arguments.commit_sha,
            "result": "pass",
            "evidence_level": arguments.evidence_level,
            "operating_system": platform.system(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "network_mode": "offline-confirmed" if machine else "synthetic-guarded-no-network",
            "checks": checks,
            "measurement": measurement.to_dict(),
            "measured_workload_network_attempt_count": guard.network_attempt_count,
            "measured_workload_process_attempt_count": guard.process_attempt_count,
            "measured_workload_process_launch_used": False,
            "evidence_wrapper_git_process_used": True,
            "real_machine_evidence": machine,
            "performance_thresholds_defined": False,
            "external_runtime_memory_measured": False,
            "model_memory_measured": False,
            "lite_performance_gate_complete": False,
            "phase6_gate_complete": False,
            "lite_v1_complete": False,
        }
        privacy = _privacy_flags(payload)
        if any(privacy.values()):
            raise RuntimeError("Lite client measurement report failed privacy validation")
        payload["privacy"] = privacy
    except BaseException as exc:
        failure = {
            "test_id": TEST_ID,
            "commit_sha": arguments.commit_sha,
            "result": "fail",
            "stage": stage,
            "error_class": type(exc).__name__,
        }
        print(json.dumps(failure, sort_keys=True, separators=(",", ":")))
        return 2
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
