"""Validate bounded IMP-104 primary Intel Mac user-visible latency evidence."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, cast

TEST_ID = "IMP-104-USER-VISIBLE-LOCAL-WRITING-LATENCY-MEASUREMENT"
SHA = re.compile(r"^[0-9a-f]{40}$")
OPAQUE_MODEL_ID = re.compile(r"^ollama\.model\.[0-9a-f]{64}$")
REVISION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+\-]{0,191}$")
RUNTIME_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+\-]{0,127}$")
WORKFLOW_ORDER = ("draft", "revise", "summarize")

TOP_LEVEL_KEYS = {
    "test_id",
    "specification_version",
    "commit_sha",
    "result",
    "evidence_level",
    "operating_system",
    "architecture",
    "python_version",
    "network_mode",
    "measurement_scope",
    "timing_clock",
    "timing_boundary",
    "runtime_preflight_included_in_duration",
    "workspace_setup_included_in_duration",
    "binding_setup_included_in_duration",
    "loopback_runtime_request_used",
    "external_network_request_used",
    "cloud_credentials_used",
    "automatic_model_download_used",
    "runtime_install_or_start_used",
    "synthetic_observations",
    "real_machine_measurement_collected",
    "real_machine_measurement_accepted",
    "observation",
    "checks",
    "claims",
    "privacy",
}
OBSERVATION_KEYS = {
    "runtime_version",
    "model",
    "workflow_order",
    "completed_response_duration_ns",
    "completed_workflow_count",
    "assistant_event_count",
    "canonical_event_count",
    "prompt_injection_finding_count",
    "secret_redaction_count",
    "runtime_request_count",
    "allowed_loopback_socket_attempts",
    "rejected_socket_attempts",
}
MODEL_KEYS = {"model_id", "revision"}
CHECK_KEYS = {
    "measurement_scope_is_bounded_local_writing",
    "workflow_order_is_exact",
    "three_workflows_completed",
    "three_assistant_events_created",
    "canonical_event_count_is_nine",
    "durations_are_positive",
    "selected_model_identity_is_opaque",
    "runtime_requests_are_bounded",
    "no_rejected_socket_attempt",
    "ci_uses_no_socket",
    "real_machine_uses_loopback",
}
CLAIM_KEYS = {
    "final_user_visible_latency_requirement_defined",
    "first_token_latency_measured",
    "streaming_latency_measured",
    "cold_start_latency_measured",
    "cold_start_classified",
    "generation_throughput_requirement_defined",
    "supported_or_default_model_selected",
    "cross_machine_performance_supported",
    "full_lite_performance_thresholds_defined",
    "lite_performance_gate_complete",
    "accessibility_gate_complete",
    "release_candidate_soak_complete",
    "phase6_gate_complete",
    "lite_v1_complete",
}
PRIVACY_KEYS = {
    "absolute_paths_in_report",
    "usernames_in_report",
    "hostnames_in_report",
    "native_model_names_in_report",
    "source_identifiers_in_report",
    "request_text_in_report",
    "source_text_in_report",
    "prompt_text_in_report",
    "response_text_in_report",
    "process_ids_in_report",
    "process_command_lines_in_report",
    "credentials_in_report",
    "secret_values_in_report",
    "workspace_identifiers_in_report",
    "urls_in_report",
    "email_addresses_in_report",
}


class Imp104ValidationError(RuntimeError):
    """Raised when IMP-104 evidence violates the accepted boundary."""


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--expected-commit-sha", required=True)
    return parser.parse_args()


def _object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise Imp104ValidationError(f"{name} must be an object")
    return cast(dict[str, Any], value)


def _exact_keys(value: dict[str, Any], expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise Imp104ValidationError(f"{name} keys are invalid")


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise Imp104ValidationError(f"{name} must be a positive integer")
    return value


def _nonnegative_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise Imp104ValidationError(f"{name} must be a non-negative integer")
    return value


def _read(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise Imp104ValidationError("evidence file cannot be read") from exc
    if not raw or len(raw) > 131_072:
        raise Imp104ValidationError("evidence file size is invalid")

    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise Imp104ValidationError("duplicate JSON key")
            result[key] = value
        return result

    try:
        decoded = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                Imp104ValidationError(f"invalid JSON constant: {value}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Imp104ValidationError("evidence JSON is invalid") from exc
    return _object(decoded, "evidence")


def _validate(payload: dict[str, Any], expected_commit_sha: str) -> dict[str, object]:
    if SHA.fullmatch(expected_commit_sha) is None:
        raise Imp104ValidationError("expected commit SHA is invalid")
    _exact_keys(payload, TOP_LEVEL_KEYS, "top-level")
    if payload["test_id"] != TEST_ID or payload["specification_version"] != "0.1":
        raise Imp104ValidationError("measurement identity is invalid")
    if payload["result"] != "pass":
        raise Imp104ValidationError("measurement result is not pass")
    if payload["commit_sha"] != expected_commit_sha:
        raise Imp104ValidationError("commit_sha does not match expected commit")
    if payload["evidence_level"] != "real-machine":
        raise Imp104ValidationError("evidence must be real-machine")
    if payload["operating_system"] != "Darwin" or str(payload["architecture"]).casefold() not in {
        "x86_64",
        "amd64",
    }:
        raise Imp104ValidationError("primary Intel Mac platform is required")
    if not isinstance(payload["python_version"], str) or not payload["python_version"]:
        raise Imp104ValidationError("python_version is invalid")
    if payload["network_mode"] != "offline-confirmed":
        raise Imp104ValidationError("offline network mode is required")
    if payload["measurement_scope"] != "doll-local-writing-completed-response-latency":
        raise Imp104ValidationError("measurement scope is invalid")
    if payload["timing_clock"] != "time.perf_counter_ns":
        raise Imp104ValidationError("timing clock is invalid")
    if payload["timing_boundary"] != "local-writing-execute-to-completed-result":
        raise Imp104ValidationError("timing boundary is invalid")
    for key in (
        "runtime_preflight_included_in_duration",
        "workspace_setup_included_in_duration",
        "binding_setup_included_in_duration",
    ):
        if payload[key] is not False:
            raise Imp104ValidationError(f"{key} must remain false")
    if payload["loopback_runtime_request_used"] is not True:
        raise Imp104ValidationError("real-machine evidence must use loopback runtime requests")
    for key in (
        "external_network_request_used",
        "cloud_credentials_used",
        "automatic_model_download_used",
        "runtime_install_or_start_used",
        "synthetic_observations",
        "real_machine_measurement_accepted",
    ):
        if payload[key] is not False:
            raise Imp104ValidationError(f"{key} must remain false")
    if payload["real_machine_measurement_collected"] is not True:
        raise Imp104ValidationError("real-machine measurement was not collected")

    observation = _object(payload["observation"], "observation")
    _exact_keys(observation, OBSERVATION_KEYS, "observation")
    runtime_version = observation["runtime_version"]
    if not isinstance(runtime_version, str) or RUNTIME_VERSION.fullmatch(runtime_version) is None:
        raise Imp104ValidationError("runtime_version is invalid")
    model = _object(observation["model"], "model")
    _exact_keys(model, MODEL_KEYS, "model")
    if not isinstance(model["model_id"], str) or OPAQUE_MODEL_ID.fullmatch(model["model_id"]) is None:
        raise Imp104ValidationError("model_id must be opaque")
    if not isinstance(model["revision"], str) or REVISION.fullmatch(model["revision"]) is None:
        raise Imp104ValidationError("model revision is invalid")
    if observation["workflow_order"] != list(WORKFLOW_ORDER):
        raise Imp104ValidationError("workflow order is invalid")
    durations = _object(
        observation["completed_response_duration_ns"],
        "completed_response_duration_ns",
    )
    if set(durations) != set(WORKFLOW_ORDER):
        raise Imp104ValidationError("duration modes are invalid")
    duration_values = {
        mode: _positive_int(durations[mode], f"duration {mode}") for mode in WORKFLOW_ORDER
    }
    if _positive_int(observation["completed_workflow_count"], "completed_workflow_count") != 3:
        raise Imp104ValidationError("completed workflow count must be 3")
    if _positive_int(observation["assistant_event_count"], "assistant_event_count") != 3:
        raise Imp104ValidationError("assistant event count must be 3")
    if _positive_int(observation["canonical_event_count"], "canonical_event_count") != 9:
        raise Imp104ValidationError("canonical event count must be 9")
    _nonnegative_int(
        observation["prompt_injection_finding_count"],
        "prompt_injection_finding_count",
    )
    _nonnegative_int(observation["secret_redaction_count"], "secret_redaction_count")
    _positive_int(observation["runtime_request_count"], "runtime_request_count")
    _positive_int(
        observation["allowed_loopback_socket_attempts"],
        "allowed_loopback_socket_attempts",
    )
    if _nonnegative_int(observation["rejected_socket_attempts"], "rejected_socket_attempts") != 0:
        raise Imp104ValidationError("rejected socket attempts must be zero")

    checks = _object(payload["checks"], "checks")
    _exact_keys(checks, CHECK_KEYS, "checks")
    if not all(value is True for value in checks.values()):
        raise Imp104ValidationError("all measurement checks must be true")
    claims = _object(payload["claims"], "claims")
    _exact_keys(claims, CLAIM_KEYS, "claims")
    if any(value is not False for value in claims.values()):
        raise Imp104ValidationError("broader latency/performance claims must remain false")
    privacy = _object(payload["privacy"], "privacy")
    _exact_keys(privacy, PRIVACY_KEYS, "privacy")
    if any(value is not False for value in privacy.values()):
        raise Imp104ValidationError("privacy flags must all remain false")

    return {
        "result": "pass",
        "validated_commit_sha": expected_commit_sha,
        "evidence_level": "real-machine",
        "measurement_scope": payload["measurement_scope"],
        "workflow_order": list(WORKFLOW_ORDER),
        "completed_response_duration_ns": duration_values,
        "first_token_latency_measured": False,
        "cold_start_latency_measured": False,
        "final_user_visible_latency_requirement_defined": False,
        "full_lite_performance_thresholds_defined": False,
        "phase6_gate_complete": False,
        "lite_v1_complete": False,
        "real_machine_measurement_accepted": False,
        "manual_privacy_review_required": True,
    }


def main() -> int:
    arguments = _arguments()
    try:
        payload = _read(arguments.evidence)
        result = _validate(payload, arguments.expected_commit_sha)
    except Imp104ValidationError as exc:
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
