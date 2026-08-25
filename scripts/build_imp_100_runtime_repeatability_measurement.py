"""Build a privacy-safe IMP-100 repeatability/variance report from IMP-098 sessions."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import cast

from validate_imp_098_local_runtime_resource_measurement import (
    Imp098EvidenceValidationError,
    load_and_validate_evidence,
)

TEST_ID = "IMP-100-LOCAL-RUNTIME-REPEATABILITY-VARIANCE"
SOURCE_TEST_ID = "IMP-098-LOCAL-RUNTIME-RESOURCE-MEASUREMENT"
SESSION_COUNT = 3
SHA = re.compile(r"^[0-9a-f]{40}$")


class Imp100RepeatabilityBuildError(RuntimeError):
    """Raised when IMP-100 repeatability evidence cannot be built safely."""


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise Imp100RepeatabilityBuildError(f"{label} must be a JSON object")
    return cast(dict[str, object], value)


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise Imp100RepeatabilityBuildError(f"{label} must be a positive integer")
    return value


def _positive_int_list(value: object, length: int, label: str) -> list[int]:
    if not isinstance(value, list) or len(value) != length:
        raise Imp100RepeatabilityBuildError(f"{label} has invalid length")
    return [_positive_int(item, label) for item in value]


def _summary(values: list[int]) -> dict[str, object]:
    return {
        "values": values,
        "minimum": min(values),
        "maximum": max(values),
        "mean_floor": sum(values) // len(values),
        "spread": max(values) - min(values),
    }


def _canonical_architecture(value: object) -> str:
    if not isinstance(value, str) or value.casefold() not in {"x86_64", "amd64"}:
        raise Imp100RepeatabilityBuildError("source architecture is not primary Intel Mac")
    return "x86_64"


def _load_source(
    path: Path, *, expected_commit_sha: str, ordinal: int
) -> tuple[dict[str, object], str]:
    try:
        load_and_validate_evidence(path, expected_commit_sha=expected_commit_sha)
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8", errors="strict"))
    except Imp098EvidenceValidationError as exc:
        raise Imp100RepeatabilityBuildError(
            f"source session {ordinal} failed IMP-098 validation: {exc}"
        ) from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Imp100RepeatabilityBuildError(
            f"source session {ordinal} is not readable UTF-8 JSON"
        ) from exc
    return _object(payload, f"source session {ordinal}"), hashlib.sha256(raw).hexdigest()


def build_repeatability_report(
    source_paths: list[Path],
    *,
    expected_commit_sha: str,
    independent_sessions_confirmed: bool,
    source_privacy_reviewed: bool,
) -> dict[str, object]:
    if SHA.fullmatch(expected_commit_sha) is None:
        raise Imp100RepeatabilityBuildError("expected commit SHA is invalid")
    if len(source_paths) != SESSION_COUNT:
        raise Imp100RepeatabilityBuildError(f"exactly {SESSION_COUNT} source sessions are required")
    if not independent_sessions_confirmed:
        raise Imp100RepeatabilityBuildError(
            "separate measurement-session invocation confirmation is required"
        )
    if not source_privacy_reviewed:
        raise Imp100RepeatabilityBuildError("manual source privacy review confirmation is required")

    sources: list[dict[str, object]] = []
    hashes: list[str] = []
    for ordinal, path in enumerate(source_paths, start=1):
        source, digest = _load_source(
            path,
            expected_commit_sha=expected_commit_sha,
            ordinal=ordinal,
        )
        sources.append(source)
        hashes.append(digest)
    if len(set(hashes)) != SESSION_COUNT:
        raise Imp100RepeatabilityBuildError("source session reports must be byte-distinct")

    first = sources[0]
    first_observation = _object(first.get("observation"), "first observation")
    first_model = _object(first_observation.get("model"), "first model")
    runtime_version = first_observation.get("runtime_version")
    python_version = first.get("python_version")
    model_id = first_model.get("model_id")
    revision = first_model.get("revision")
    model_size = _positive_int(
        first_model.get("provider_reported_installed_size_bytes"),
        "provider-reported installed model size",
    )
    for value, label in [
        (runtime_version, "runtime version"),
        (python_version, "Python version"),
        (model_id, "opaque model id"),
        (revision, "model revision"),
    ]:
        if not isinstance(value, str) or not value:
            raise Imp100RepeatabilityBuildError(f"{label} is missing")

    sessions: list[dict[str, object]] = []
    runtime_maxima: list[int] = []
    doll_peaks: list[int] = []
    duration_positions: list[list[int]] = [[] for _ in range(3)]

    for ordinal, (source, digest) in enumerate(zip(sources, hashes, strict=True), start=1):
        if source.get("test_id") != SOURCE_TEST_ID:
            raise Imp100RepeatabilityBuildError(f"source session {ordinal} has wrong test id")
        if source.get("commit_sha") != expected_commit_sha:
            raise Imp100RepeatabilityBuildError(f"source session {ordinal} has mixed commit")
        if source.get("operating_system") != "Darwin":
            raise Imp100RepeatabilityBuildError(
                f"source session {ordinal} has mixed operating system"
            )
        if _canonical_architecture(source.get("architecture")) != "x86_64":
            raise Imp100RepeatabilityBuildError(f"source session {ordinal} has mixed architecture")
        if source.get("python_version") != python_version:
            raise Imp100RepeatabilityBuildError(
                f"source session {ordinal} has mixed Python version"
            )

        observation = _object(source.get("observation"), f"source session {ordinal} observation")
        model = _object(observation.get("model"), f"source session {ordinal} model")
        if observation.get("runtime_version") != runtime_version:
            raise Imp100RepeatabilityBuildError(
                f"source session {ordinal} has mixed runtime version"
            )
        if model.get("model_id") != model_id or model.get("revision") != revision:
            raise Imp100RepeatabilityBuildError(
                f"source session {ordinal} has mixed model identity"
            )
        if model.get("provider_reported_installed_size_bytes") != model_size:
            raise Imp100RepeatabilityBuildError(f"source session {ordinal} has mixed model size")

        runtime_max = _positive_int(
            observation.get("maximum_sampled_runtime_process_tree_rss_bytes"),
            f"source session {ordinal} maximum runtime RSS",
        )
        doll_rss = _object(
            observation.get("doll_process_rss"),
            f"source session {ordinal} doll RSS",
        )
        doll_peak = _positive_int(
            doll_rss.get("peak_bytes"),
            f"source session {ordinal} doll peak RSS",
        )
        generation_duration = _object(
            observation.get("generation_duration"),
            f"source session {ordinal} generation duration",
        )
        duration_values = _positive_int_list(
            generation_duration.get("values_ns"),
            3,
            f"source session {ordinal} generation durations",
        )
        output_counts = _positive_int_list(
            observation.get("generation_output_char_counts"),
            3,
            f"source session {ordinal} output counts",
        )
        runtime_maxima.append(runtime_max)
        doll_peaks.append(doll_peak)
        for position, duration in enumerate(duration_values):
            duration_positions[position].append(duration)
        sessions.append(
            {
                "session_ordinal": ordinal,
                "source_sha256": digest,
                "maximum_sampled_runtime_process_tree_rss_bytes": runtime_max,
                "doll_process_peak_rss_bytes": doll_peak,
                "generation_duration_values_ns": duration_values,
                "generation_output_char_counts": output_counts,
            }
        )

    checks = {
        "source_session_count_is_fixed": len(sessions) == SESSION_COUNT,
        "source_reports_are_byte_distinct": len(set(hashes)) == SESSION_COUNT,
        "source_sessions_share_commit": all(
            source.get("commit_sha") == expected_commit_sha for source in sources
        ),
        "source_sessions_share_platform": all(
            source.get("operating_system") == "Darwin"
            and _canonical_architecture(source.get("architecture")) == "x86_64"
            for source in sources
        ),
        "source_sessions_share_runtime": all(
            _object(source.get("observation"), "observation").get("runtime_version")
            == runtime_version
            for source in sources
        ),
        "source_sessions_share_model_revision": all(
            _object(
                _object(source.get("observation"), "observation").get("model"),
                "model",
            ).get("revision")
            == revision
            for source in sources
        ),
        "independent_session_invocations_confirmed": independent_sessions_confirmed,
        "source_manual_privacy_review_confirmed": source_privacy_reviewed,
    }
    if not all(checks.values()):
        raise Imp100RepeatabilityBuildError("repeatability build checks did not all pass")

    return {
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
        "identity": {
            "python_version": python_version,
            "runtime_version": runtime_version,
            "model_id": model_id,
            "model_revision": revision,
            "provider_reported_installed_size_bytes": model_size,
        },
        "sessions": sessions,
        "variance": {
            "maximum_sampled_runtime_process_tree_rss_bytes": _summary(runtime_maxima),
            "doll_process_peak_rss_bytes": _summary(doll_peaks),
            "generation_duration_by_position_ns": [
                {"generation_position": position + 1, **_summary(values)}
                for position, values in enumerate(duration_positions)
            ],
        },
        "checks": checks,
        "claims": {
            "minimum_system_ram_requirement_defined": False,
            "total_system_peak_memory_measured": False,
            "gpu_or_metal_memory_requirement_defined": False,
            "full_lite_installation_disk_requirement_defined": False,
            "final_user_visible_latency_requirement_defined": False,
            "cold_start_requirement_defined": False,
            "cross_machine_performance_supported": False,
            "supported_or_default_model_selected": False,
            "repeatability_variance_release_requirement_defined": False,
            "full_lite_performance_thresholds_defined": False,
            "lite_performance_gate_complete": False,
            "accessibility_gate_complete": False,
            "release_candidate_soak_complete": False,
            "phase6_gate_complete": False,
            "lite_v1_complete": False,
        },
        "privacy": {
            "source_file_paths_in_report": False,
            "absolute_paths_in_report": False,
            "credentials_in_report": False,
            "fixed_prompt_text_in_report": False,
            "hostnames_in_report": False,
            "native_model_names_in_report": False,
            "process_command_lines_in_report": False,
            "process_ids_in_report": False,
            "prompt_or_response_text_in_report": False,
            "secret_values_in_report": False,
            "usernames_in_report": False,
            "workspace_identifiers_in_report": False,
            "urls_in_report": False,
            "email_addresses_in_report": False,
        },
    }


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", action="append", type=Path, required=True)
    parser.add_argument("--expected-commit-sha", required=True)
    parser.add_argument("--independent-sessions-confirmed", action="store_true")
    parser.add_argument("--source-privacy-reviewed", action="store_true")
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    try:
        report = build_repeatability_report(
            arguments.source,
            expected_commit_sha=arguments.expected_commit_sha,
            independent_sessions_confirmed=arguments.independent_sessions_confirmed,
            source_privacy_reviewed=arguments.source_privacy_reviewed,
        )
    except Imp100RepeatabilityBuildError as exc:
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
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
