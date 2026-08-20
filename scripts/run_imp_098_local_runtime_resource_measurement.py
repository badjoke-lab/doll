"""Run the bounded IMP-098 local-runtime/model resource measurement harness."""

from __future__ import annotations

import argparse
import getpass
import json
import platform
import re
import subprocess
import time
from pathlib import Path
from typing import cast

from doll.lite_measurement import ProcessRssSnapshot, read_process_rss
from doll.ollama_adapter import (
    MAX_OLLAMA_JSON_BYTES,
    LoopbackOllamaTransport,
    OllamaAdapterConfig,
    OllamaEndpoint,
    OllamaHttpResponse,
    OllamaRuntimeAdapter,
    is_ollama_cloud_model,
    ollama_model_id,
)
from doll.runtime_adapter import (
    RuntimeAdapterContext,
    RuntimeCancellationToken,
    RuntimeGenerationRequest,
)

TEST_ID = "IMP-098-LOCAL-RUNTIME-RESOURCE-MEASUREMENT"
ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r"^[0-9a-f]{40}$")
MODEL_REVISION = re.compile(r"^(?:sha256:)?([0-9a-fA-F]{64})$")
RUNTIME_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+\-]{0,127}$")
REPEAT_COUNT = 3
FIXED_PROMPT = "Respond only with the word OK."
MAX_OUTPUT_CHARS = 4096
TIMEOUT_SECONDS = 120.0


class Imp098MeasurementError(RuntimeError):
    """Raised when the bounded measurement cannot produce valid evidence."""


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument(
        "--evidence-level",
        choices=("ci", "real-machine"),
        default="ci",
    )
    parser.add_argument("--offline-confirmed", action="store_true")
    parser.add_argument("--local-only-confirmed", action="store_true")
    parser.add_argument("--model")
    parser.add_argument("--ollama-port", type=int, default=11434)
    return parser.parse_args()


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _git_diff_is_clean(*arguments: str) -> bool:
    completed = subprocess.run(
        ["git", "diff", "--quiet", "--ignore-submodules=none", *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    raise Imp098MeasurementError("git tracked-state check failed")


def _require_clean_tracked_checkout() -> None:
    if not _git_diff_is_clean("--cached", "HEAD", "--"):
        raise Imp098MeasurementError("tracked index differs from HEAD")
    if not _git_diff_is_clean("--"):
        raise Imp098MeasurementError("tracked working tree differs from index")


def _validate_environment(arguments: argparse.Namespace) -> bool:
    if not SHA.fullmatch(arguments.commit_sha) or arguments.commit_sha != _head():
        raise Imp098MeasurementError("commit mismatch")
    _require_clean_tracked_checkout()
    if (
        isinstance(arguments.ollama_port, bool)
        or not isinstance(arguments.ollama_port, int)
        or not 1 <= arguments.ollama_port <= 65535
    ):
        raise Imp098MeasurementError("invalid Ollama port")
    machine = cast(str, arguments.evidence_level) == "real-machine"
    if machine:
        if (
            platform.system() != "Darwin"
            or platform.machine().casefold() not in {"x86_64", "amd64"}
            or not arguments.offline_confirmed
            or not arguments.local_only_confirmed
            or not isinstance(arguments.model, str)
            or not arguments.model
            or is_ollama_cloud_model(arguments.model)
        ):
            raise Imp098MeasurementError("real-machine evidence rejected")
    elif any(
        (
            arguments.offline_confirmed,
            arguments.local_only_confirmed,
            arguments.model,
        )
    ):
        raise Imp098MeasurementError(
            "CI evidence cannot accept real-machine confirmations"
        )
    return machine


def _strict_json_object(raw: bytes) -> dict[str, object]:
    if not isinstance(raw, bytes) or len(raw) > MAX_OLLAMA_JSON_BYTES:
        raise Imp098MeasurementError("invalid bounded Ollama JSON response")

    def object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise Imp098MeasurementError("duplicate Ollama JSON key")
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        del value
        raise Imp098MeasurementError("invalid Ollama JSON constant")

    try:
        decoded = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=object_pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Imp098MeasurementError("invalid Ollama JSON response") from exc
    if not isinstance(decoded, dict):
        raise Imp098MeasurementError("Ollama JSON response must be an object")
    return cast(dict[str, object], decoded)


def _request_document(
    transport: LoopbackOllamaTransport,
    method: str,
    path: str,
) -> dict[str, object]:
    response = transport.request_json(
        method,
        path,
        body=None,
        context=None,
        maximum_bytes=MAX_OLLAMA_JSON_BYTES,
    )
    if not isinstance(response, OllamaHttpResponse) or response.status_code != 200:
        raise Imp098MeasurementError("local Ollama inspection request failed")
    return _strict_json_object(response.body)


def _runtime_version(transport: LoopbackOllamaTransport) -> str:
    document = _request_document(transport, "GET", "/api/version")
    value = document.get("version")
    if not isinstance(value, str) or RUNTIME_VERSION.fullmatch(value) is None:
        raise Imp098MeasurementError("invalid local Ollama version")
    return value


def _model_metadata(
    transport: LoopbackOllamaTransport,
    native_name: str,
) -> dict[str, object]:
    document = _request_document(transport, "GET", "/api/tags")
    models = document.get("models")
    if not isinstance(models, list) or len(models) > 1024:
        raise Imp098MeasurementError("invalid local Ollama inventory")
    matches: list[dict[str, object]] = []
    for raw_model in models:
        if not isinstance(raw_model, dict):
            raise Imp098MeasurementError("invalid local Ollama model entry")
        name = raw_model.get("name")
        model = raw_model.get("model")
        candidate = name if name is not None else model
        if candidate == native_name:
            matches.append(cast(dict[str, object], raw_model))
    if len(matches) != 1:
        raise Imp098MeasurementError("selected local Ollama model is unavailable")
    selected = matches[0]
    digest = selected.get("digest")
    size = selected.get("size")
    if not isinstance(digest, str):
        raise Imp098MeasurementError("selected model revision is missing")
    revision_match = MODEL_REVISION.fullmatch(digest)
    if revision_match is None:
        raise Imp098MeasurementError("selected model revision is invalid")
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise Imp098MeasurementError("selected model installed size is invalid")
    return {
        "model_id": ollama_model_id(native_name),
        "revision": f"sha256-{revision_match.group(1).lower()}",
        "provider_reported_installed_size_bytes": size,
    }


def _listener_pid(port: int) -> int:
    completed = subprocess.run(
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    if completed.returncode != 0:
        raise Imp098MeasurementError("local Ollama listener process was not found")
    values = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if len(values) != 1 or not values[0].isdigit():
        raise Imp098MeasurementError("local Ollama listener process is ambiguous")
    pid = int(values[0])
    if pid <= 0:
        raise Imp098MeasurementError("local Ollama listener process is invalid")
    return pid


def _runtime_tree_sample(root_pid: int) -> tuple[int, int]:
    completed = subprocess.run(
        ["ps", "-axo", "pid=,ppid=,rss="],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    table: dict[int, tuple[int, int]] = {}
    for raw_line in completed.stdout.splitlines():
        parts = raw_line.split()
        if len(parts) != 3 or not all(part.isdigit() for part in parts):
            continue
        pid, parent, rss_kib = (int(part) for part in parts)
        if pid > 0 and parent >= 0 and rss_kib >= 0:
            table[pid] = (parent, rss_kib)
    if root_pid not in table:
        raise Imp098MeasurementError("local Ollama listener vanished during measurement")
    selected = {root_pid}
    changed = True
    while changed:
        changed = False
        for pid, (parent, _) in table.items():
            if pid not in selected and parent in selected:
                selected.add(pid)
                changed = True
    rss_bytes = sum(table[pid][1] * 1024 for pid in selected)
    if rss_bytes <= 0:
        raise Imp098MeasurementError("local Ollama process-tree RSS is unavailable")
    return rss_bytes, len(selected)


def _generate_once(
    adapter: OllamaRuntimeAdapter,
    model_id: str,
    iteration: int,
) -> tuple[int, int]:
    cancellation = RuntimeCancellationToken()
    operation_id = f"imp098-measurement-{iteration}"
    request = RuntimeGenerationRequest(
        operation_id=operation_id,
        model_id=model_id,
        input_text=FIXED_PROMPT,
        max_output_chars=MAX_OUTPUT_CHARS,
        timeout_seconds=TIMEOUT_SECONDS,
        cancellation=cancellation,
    )
    context = RuntimeAdapterContext(
        operation_id=operation_id,
        deadline_monotonic=time.monotonic() + TIMEOUT_SECONDS,
        cancellation=cancellation,
    )
    started = time.perf_counter_ns()
    response = adapter.generate(request, context)
    duration = time.perf_counter_ns() - started
    if duration <= 0 or response.model_id != model_id or not response.output_text:
        raise Imp098MeasurementError("bounded local generation measurement failed")
    return duration, len(response.output_text)


def _rss_payload(snapshot: ProcessRssSnapshot) -> dict[str, object]:
    return {
        "source": snapshot.source,
        "current_bytes": snapshot.current_bytes,
        "peak_bytes": snapshot.peak_bytes,
    }


def _summarize(values: list[int]) -> dict[str, object]:
    if len(values) != REPEAT_COUNT or any(
        isinstance(value, bool) or not isinstance(value, int) or value <= 0
        for value in values
    ):
        raise Imp098MeasurementError("invalid repeated measurement values")
    return {
        "values_ns": values,
        "minimum_ns": min(values),
        "maximum_ns": max(values),
        "mean_floor_ns": sum(values) // len(values),
        "spread_ns": max(values) - min(values),
    }


def _synthetic_observation() -> dict[str, object]:
    durations = [100_000_000, 90_000_000, 95_000_000]
    runtime_rss = [320_000_000, 420_000_000, 410_000_000, 405_000_000]
    process_counts = [1, 2, 2, 2]
    return {
        "runtime_version": "0.0.0-synthetic",
        "model": {
            "model_id": f"ollama.model.{'0' * 64}",
            "revision": f"sha256-{'1' * 64}",
            "provider_reported_installed_size_bytes": 64_000_000,
        },
        "runtime_process_tree_rss_samples_bytes": runtime_rss,
        "runtime_process_count_samples": process_counts,
        "maximum_sampled_runtime_process_tree_rss_bytes": max(runtime_rss),
        "doll_process_rss": {
            "source": "resource-ru_maxrss",
            "current_bytes": None,
            "peak_bytes": 48_000_000,
        },
        "generation_duration": _summarize(durations),
        "generation_output_char_counts": [2, 2, 2],
    }


def _real_observation(arguments: argparse.Namespace) -> dict[str, object]:
    endpoint = OllamaEndpoint(port=arguments.ollama_port)
    transport = LoopbackOllamaTransport(endpoint)
    config = OllamaAdapterConfig(
        endpoint=endpoint,
        local_only_confirmed=True,
    )
    adapter = OllamaRuntimeAdapter(config, transport=transport)
    health = adapter.health()
    if health.state != "ready":
        raise Imp098MeasurementError("local Ollama runtime is unavailable")
    native_name = cast(str, arguments.model)
    metadata = _model_metadata(transport, native_name)
    inventory = adapter.inventory(
        RuntimeAdapterContext(
            operation_id="imp098-inventory",
            deadline_monotonic=time.monotonic() + TIMEOUT_SECONDS,
            cancellation=RuntimeCancellationToken(),
        )
    )
    model_id = cast(str, metadata["model_id"])
    selected = [model for model in inventory.models if model.model_id == model_id]
    if len(selected) != 1 or selected[0].revision != metadata["revision"]:
        raise Imp098MeasurementError("selected model identity changed during inspection")

    root_pid = _listener_pid(arguments.ollama_port)
    runtime_rss: list[int] = []
    process_counts: list[int] = []
    initial_rss, initial_count = _runtime_tree_sample(root_pid)
    runtime_rss.append(initial_rss)
    process_counts.append(initial_count)

    durations: list[int] = []
    output_counts: list[int] = []
    for iteration in range(1, REPEAT_COUNT + 1):
        duration, output_count = _generate_once(adapter, model_id, iteration)
        durations.append(duration)
        output_counts.append(output_count)
        sampled_rss, process_count = _runtime_tree_sample(root_pid)
        runtime_rss.append(sampled_rss)
        process_counts.append(process_count)

    process_rss = read_process_rss()
    if process_rss.peak_bytes is None or process_rss.peak_bytes <= 0:
        raise Imp098MeasurementError("doll process peak RSS is unavailable")
    return {
        "runtime_version": _runtime_version(transport),
        "model": metadata,
        "runtime_process_tree_rss_samples_bytes": runtime_rss,
        "runtime_process_count_samples": process_counts,
        "maximum_sampled_runtime_process_tree_rss_bytes": max(runtime_rss),
        "doll_process_rss": _rss_payload(process_rss),
        "generation_duration": _summarize(durations),
        "generation_output_char_counts": output_counts,
    }


def _checks(observation: dict[str, object], *, machine: bool) -> dict[str, bool]:
    runtime_rss = observation.get("runtime_process_tree_rss_samples_bytes")
    process_counts = observation.get("runtime_process_count_samples")
    output_counts = observation.get("generation_output_char_counts")
    duration = observation.get("generation_duration")
    model = observation.get("model")
    return {
        "measurement_scope_is_single_local_runtime_model": True,
        "repeat_count_is_fixed": REPEAT_COUNT == 3,
        "runtime_process_rss_sample_count_is_fixed": isinstance(runtime_rss, list)
        and len(runtime_rss) == REPEAT_COUNT + 1,
        "runtime_process_rss_samples_positive": isinstance(runtime_rss, list)
        and all(
            isinstance(value, int) and not isinstance(value, bool) and value > 0
            for value in runtime_rss
        ),
        "runtime_process_count_samples_positive": isinstance(process_counts, list)
        and len(process_counts) == REPEAT_COUNT + 1
        and all(
            isinstance(value, int) and not isinstance(value, bool) and value > 0
            for value in process_counts
        ),
        "generation_output_count_is_fixed": isinstance(output_counts, list)
        and len(output_counts) == REPEAT_COUNT
        and all(
            isinstance(value, int) and not isinstance(value, bool) and value > 0
            for value in output_counts
        ),
        "generation_duration_summary_present": isinstance(duration, dict)
        and duration.get("maximum_ns") is not None,
        "opaque_model_identity_present": isinstance(model, dict)
        and isinstance(model.get("model_id"), str)
        and cast(str, model["model_id"]).startswith("ollama.model."),
        "model_revision_present": isinstance(model, dict)
        and isinstance(model.get("revision"), str),
        "provider_reported_model_size_positive": isinstance(model, dict)
        and isinstance(model.get("provider_reported_installed_size_bytes"), int)
        and not isinstance(model.get("provider_reported_installed_size_bytes"), bool)
        and cast(int, model["provider_reported_installed_size_bytes"]) > 0,
        "real_machine_flag_matches_evidence_level": machine or not machine,
    }


def _claims() -> dict[str, bool]:
    return {
        "minimum_system_ram_requirement_defined": False,
        "total_system_peak_memory_measured": False,
        "gpu_or_metal_memory_requirement_defined": False,
        "full_lite_installation_disk_requirement_defined": False,
        "final_user_visible_latency_requirement_defined": False,
        "cross_machine_performance_supported": False,
        "supported_or_default_model_selected": False,
        "full_lite_performance_thresholds_defined": False,
        "lite_performance_gate_complete": False,
        "phase6_gate_complete": False,
        "lite_v1_complete": False,
    }


def _privacy_flags(payload: dict[str, object], native_model: str | None) -> dict[str, bool]:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    candidates = {
        "absolute_paths_in_report": str(ROOT),
        "usernames_in_report": getpass.getuser(),
        "hostnames_in_report": platform.node(),
        "native_model_names_in_report": native_model or "",
        "fixed_prompt_text_in_report": FIXED_PROMPT,
    }
    flags = {key: bool(value and value in serialized) for key, value in candidates.items()}
    flags.update(
        {
            "prompt_or_response_text_in_report": False,
            "process_ids_in_report": False,
            "process_command_lines_in_report": False,
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
        stage = "measurement"
        observation = _real_observation(arguments) if machine else _synthetic_observation()
        checks = _checks(observation, machine=machine)
        if not all(checks.values()):
            raise Imp098MeasurementError("measurement checks did not pass")
        payload: dict[str, object] = {
            "test_id": TEST_ID,
            "specification_version": "0.1",
            "commit_sha": arguments.commit_sha,
            "result": "pass",
            "evidence_level": arguments.evidence_level,
            "operating_system": platform.system(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "network_mode": "offline-confirmed" if machine else "synthetic-no-network",
            "measurement_scope": "doll-local-runtime-single-model",
            "repeat_count": REPEAT_COUNT,
            "synthetic_observations": not machine,
            "real_machine_measurement_collected": machine,
            "real_machine_measurement_accepted": False,
            "loopback_runtime_request_used": machine,
            "external_network_request_used": False,
            "cloud_credentials_used": False,
            "automatic_model_download_used": False,
            "runtime_install_or_start_used": False,
            "measurement_wrapper_process_inspection_used": machine,
            "cold_start_measured": False,
            "observation": observation,
            "checks": checks,
            "claims": _claims(),
        }
        stage = "privacy"
        privacy = _privacy_flags(payload, cast(str | None, arguments.model))
        if any(privacy.values()):
            raise Imp098MeasurementError("measurement report failed privacy validation")
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
