"""Run the bounded IMP-102 Lite installation/model-storage measurement harness."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import cast

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
from doll.runtime_adapter import RuntimeAdapterContext, RuntimeCancellationToken

TEST_ID = "IMP-102-LITE-INSTALL-MODEL-STORAGE-MEASUREMENT"
ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r"^[0-9a-f]{40}$")
MODEL_REVISION = re.compile(r"^(?:sha256:)?([0-9a-fA-F]{64})$")
RUNTIME_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+\-]{0,127}$")
UV_VERSION = re.compile(r"^uv [0-9][A-Za-z0-9._+\-]{0,63}$")
MAX_TREE_ENTRIES = 250_000
MAX_TREE_LOGICAL_BYTES = 100 * 1024 * 1024 * 1024
TIMEOUT_SECONDS = 600


class Imp102MeasurementError(RuntimeError):
    """Raised when the bounded storage measurement cannot produce valid evidence."""


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
    parser.add_argument("--runtime-install-root", type=Path)
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
    raise Imp102MeasurementError("git tracked-state check failed")


def _require_clean_tracked_checkout() -> None:
    if not _git_diff_is_clean("--cached", "HEAD", "--"):
        raise Imp102MeasurementError("tracked index differs from HEAD")
    if not _git_diff_is_clean("--"):
        raise Imp102MeasurementError("tracked working tree differs from index")


def _validate_environment(arguments: argparse.Namespace) -> bool:
    if SHA.fullmatch(arguments.commit_sha) is None or arguments.commit_sha != _head():
        raise Imp102MeasurementError("commit mismatch")
    _require_clean_tracked_checkout()
    if (
        isinstance(arguments.ollama_port, bool)
        or not isinstance(arguments.ollama_port, int)
        or not 1 <= arguments.ollama_port <= 65535
    ):
        raise Imp102MeasurementError("invalid Ollama port")

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
            raise Imp102MeasurementError("real-machine evidence rejected")
        runtime_root = arguments.runtime_install_root
        if runtime_root is not None:
            candidate = runtime_root.expanduser()
            if not candidate.exists() or candidate.is_symlink():
                raise Imp102MeasurementError("explicit runtime installation root is invalid")
    elif any(
        (
            arguments.offline_confirmed,
            arguments.local_only_confirmed,
            arguments.model,
            arguments.runtime_install_root,
        )
    ):
        raise Imp102MeasurementError("CI evidence cannot accept real-machine inputs")
    return machine


def _strict_json_object(raw: bytes) -> dict[str, object]:
    if not isinstance(raw, bytes) or len(raw) > MAX_OLLAMA_JSON_BYTES:
        raise Imp102MeasurementError("invalid bounded Ollama JSON response")

    def object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise Imp102MeasurementError("duplicate Ollama JSON key")
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        del value
        raise Imp102MeasurementError("invalid Ollama JSON constant")

    try:
        decoded = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=object_pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Imp102MeasurementError("invalid Ollama JSON response") from exc
    if not isinstance(decoded, dict):
        raise Imp102MeasurementError("Ollama JSON response must be an object")
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
        raise Imp102MeasurementError("local Ollama inspection request failed")
    return _strict_json_object(response.body)


def _runtime_version(transport: LoopbackOllamaTransport) -> str:
    document = _request_document(transport, "GET", "/api/version")
    value = document.get("version")
    if not isinstance(value, str) or RUNTIME_VERSION.fullmatch(value) is None:
        raise Imp102MeasurementError("invalid local Ollama version")
    return value


def _model_metadata(
    transport: LoopbackOllamaTransport,
    native_name: str,
) -> dict[str, object]:
    document = _request_document(transport, "GET", "/api/tags")
    models = document.get("models")
    if not isinstance(models, list) or len(models) > 1024:
        raise Imp102MeasurementError("invalid local Ollama inventory")
    matches: list[dict[str, object]] = []
    for raw_model in models:
        if not isinstance(raw_model, dict):
            raise Imp102MeasurementError("invalid local Ollama model entry")
        name = raw_model.get("name")
        model = raw_model.get("model")
        candidate = name if name is not None else model
        if candidate == native_name:
            matches.append(cast(dict[str, object], raw_model))
    if len(matches) != 1:
        raise Imp102MeasurementError("selected local Ollama model is unavailable")
    selected = matches[0]
    digest = selected.get("digest")
    size = selected.get("size")
    if not isinstance(digest, str):
        raise Imp102MeasurementError("selected model revision is missing")
    revision_match = MODEL_REVISION.fullmatch(digest)
    if revision_match is None:
        raise Imp102MeasurementError("selected model revision is invalid")
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise Imp102MeasurementError("selected model installed size is invalid")
    return {
        "model_id": ollama_model_id(native_name),
        "revision": f"sha256-{revision_match.group(1).lower()}",
        "provider_reported_installed_size_bytes": size,
    }


def _tree_measurement(root: Path) -> dict[str, object]:
    if not root.exists() or root.is_symlink():
        raise Imp102MeasurementError("measurement root is unavailable")

    regular_file_count = 0
    directory_count = 0
    symlink_count = 0
    other_entry_count = 0
    logical_bytes = 0
    allocated_bytes = 0
    allocated_supported = True
    entries_seen = 0

    pending = [root]
    if root.is_file():
        pending = []
        stat = root.stat(follow_symlinks=False)
        regular_file_count = 1
        logical_bytes = stat.st_size
        blocks = getattr(stat, "st_blocks", None)
        if isinstance(blocks, int) and blocks >= 0:
            allocated_bytes = blocks * 512
        else:
            allocated_supported = False
    else:
        directory_count = 1

    while pending:
        current = pending.pop()
        try:
            children = list(os.scandir(current))
        except OSError as exc:
            raise Imp102MeasurementError("measurement tree cannot be inspected") from exc
        for entry in children:
            entries_seen += 1
            if entries_seen > MAX_TREE_ENTRIES:
                raise Imp102MeasurementError("measurement tree entry limit exceeded")
            try:
                if entry.is_symlink():
                    symlink_count += 1
                    continue
                if entry.is_dir(follow_symlinks=False):
                    directory_count += 1
                    pending.append(Path(entry.path))
                    continue
                if entry.is_file(follow_symlinks=False):
                    stat = entry.stat(follow_symlinks=False)
                    regular_file_count += 1
                    logical_bytes += stat.st_size
                    blocks = getattr(stat, "st_blocks", None)
                    if isinstance(blocks, int) and blocks >= 0:
                        allocated_bytes += blocks * 512
                    else:
                        allocated_supported = False
                    if logical_bytes > MAX_TREE_LOGICAL_BYTES:
                        raise Imp102MeasurementError("measurement tree byte limit exceeded")
                    continue
                other_entry_count += 1
            except OSError as exc:
                raise Imp102MeasurementError("measurement tree changed during inspection") from exc

    if regular_file_count <= 0 or logical_bytes <= 0:
        raise Imp102MeasurementError("measurement tree contains no regular-file bytes")
    return {
        "regular_file_count": regular_file_count,
        "directory_count": directory_count,
        "symlink_count": symlink_count,
        "other_entry_count": other_entry_count,
        "logical_bytes": logical_bytes,
        "allocated_bytes": allocated_bytes if allocated_supported else None,
        "allocated_bytes_source": "stat-st_blocks-times-512" if allocated_supported else None,
        "symlink_target_bytes_included": False,
    }


def _uv_version() -> str:
    try:
        completed = subprocess.run(
            ["uv", "--version"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise Imp102MeasurementError("uv is unavailable") from exc
    value = completed.stdout.strip()
    if UV_VERSION.fullmatch(value) is None:
        raise Imp102MeasurementError("unexpected uv version output")
    return value


def _install_command() -> list[str]:
    return [
        "uv",
        "sync",
        "--no-dev",
        "--all-extras",
        "--locked",
        "--offline",
        "--no-editable",
    ]


def _verify_lite_environment(environment_root: Path) -> None:
    python_executable = environment_root / "bin" / "python"
    if not python_executable.is_file():
        raise Imp102MeasurementError("fresh Lite environment Python is unavailable")
    probe = (
        "import importlib.util as u;"
        "required=('doll','pypdf','ocrmac');"
        "forbidden=('pytest','ruff','mypy');"
        "missing=[n for n in required if u.find_spec(n) is None];"
        "present=[n for n in forbidden if u.find_spec(n) is not None];"
        "raise SystemExit(2 if missing or present else 0)"
    )
    completed = subprocess.run(
        [str(python_executable), "-c", probe],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise Imp102MeasurementError("fresh Lite dependency boundary verification failed")


def _fresh_lite_environment_measurement() -> tuple[str, dict[str, object]]:
    uv_version = _uv_version()
    temporary_path: Path | None = None
    observation: dict[str, object] | None = None
    with tempfile.TemporaryDirectory(prefix="doll-imp102-") as raw_directory:
        temporary_path = Path(raw_directory)
        environment_root = temporary_path / "venv"
        environment = os.environ.copy()
        environment["UV_PROJECT_ENVIRONMENT"] = str(environment_root)
        environment["UV_OFFLINE"] = "1"
        environment["UV_NO_PROGRESS"] = "1"
        try:
            completed = subprocess.run(
                _install_command(),
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
                timeout=TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise Imp102MeasurementError("offline locked Lite installation failed") from exc
        if completed.returncode != 0:
            raise Imp102MeasurementError("offline locked Lite installation failed")
        _verify_lite_environment(environment_root)
        observation = {
            "profile": "lite-python-no-dev-all-extras",
            "optional_extras": ["ocr", "pdf"],
            "dependency_source_mode": "locked-offline-local-cache",
            "editable_install_used": False,
            "dev_dependencies_included": False,
            "tree": _tree_measurement(environment_root),
            "verification": {
                "doll_importable": True,
                "pdf_adapter_dependency_present": True,
                "ocr_adapter_dependency_present": True,
                "dev_tools_absent": True,
            },
        }
    if temporary_path is None or temporary_path.exists() or observation is None:
        raise Imp102MeasurementError("temporary Lite installation cleanup failed")
    return uv_version, observation


def _runtime_installation_measurement(path: Path | None) -> dict[str, object]:
    if path is None:
        return {"measured": False}
    return {
        "measured": True,
        "tree": _tree_measurement(path.expanduser()),
    }


def _synthetic_observation() -> dict[str, object]:
    return {
        "uv_version": "uv 0.0.0-synthetic",
        "lite_python_installation": {
            "profile": "lite-python-no-dev-all-extras",
            "optional_extras": ["ocr", "pdf"],
            "dependency_source_mode": "locked-offline-local-cache",
            "editable_install_used": False,
            "dev_dependencies_included": False,
            "tree": {
                "regular_file_count": 500,
                "directory_count": 100,
                "symlink_count": 8,
                "other_entry_count": 0,
                "logical_bytes": 125_000_000,
                "allocated_bytes": 130_000_000,
                "allocated_bytes_source": "stat-st_blocks-times-512",
                "symlink_target_bytes_included": False,
            },
            "verification": {
                "doll_importable": True,
                "pdf_adapter_dependency_present": True,
                "ocr_adapter_dependency_present": True,
                "dev_tools_absent": True,
            },
        },
        "runtime_version": "0.0.0-synthetic",
        "runtime_installation": {"measured": False},
        "model": {
            "model_id": f"ollama.model.{'0' * 64}",
            "revision": f"sha256-{'1' * 64}",
            "provider_reported_installed_size_bytes": 64_000_000,
        },
    }


def _real_observation(arguments: argparse.Namespace) -> dict[str, object]:
    uv_version, installation = _fresh_lite_environment_measurement()
    endpoint = OllamaEndpoint(port=arguments.ollama_port)
    transport = LoopbackOllamaTransport(endpoint)
    adapter = OllamaRuntimeAdapter(
        OllamaAdapterConfig(endpoint=endpoint, local_only_confirmed=True),
        transport=transport,
    )
    if adapter.health().state != "ready":
        raise Imp102MeasurementError("local Ollama runtime is unavailable")
    native_name = cast(str, arguments.model)
    metadata = _model_metadata(transport, native_name)
    inventory = adapter.inventory(
        RuntimeAdapterContext(
            operation_id="imp102-inventory",
            deadline_monotonic=time.monotonic() + 30,
            cancellation=RuntimeCancellationToken(),
        )
    )
    selected = [model for model in inventory.models if model.model_id == metadata["model_id"]]
    if len(selected) != 1 or selected[0].revision != metadata["revision"]:
        raise Imp102MeasurementError("selected model identity changed during inspection")
    return {
        "uv_version": uv_version,
        "lite_python_installation": installation,
        "runtime_version": _runtime_version(transport),
        "runtime_installation": _runtime_installation_measurement(
            arguments.runtime_install_root
        ),
        "model": metadata,
    }


def _checks(observation: dict[str, object], *, machine: bool) -> dict[str, bool]:
    installation = cast(dict[str, object], observation["lite_python_installation"])
    tree = cast(dict[str, object], installation["tree"])
    model = cast(dict[str, object], observation["model"])
    runtime_installation = cast(dict[str, object], observation["runtime_installation"])
    return {
        "measurement_scope_is_bounded": True,
        "lite_profile_excludes_dev_dependencies": installation.get("dev_dependencies_included")
        is False,
        "all_supported_optional_lite_extras_requested": installation.get("optional_extras")
        == ["ocr", "pdf"],
        "dependency_install_is_locked_and_offline": installation.get("dependency_source_mode")
        == "locked-offline-local-cache",
        "lite_installation_bytes_positive": isinstance(tree.get("logical_bytes"), int)
        and cast(int, tree["logical_bytes"]) > 0,
        "symlink_targets_are_not_counted": tree.get("symlink_target_bytes_included") is False,
        "selected_model_identity_is_opaque": isinstance(model.get("model_id"), str)
        and cast(str, model["model_id"]).startswith("ollama.model."),
        "selected_model_storage_is_positive": isinstance(
            model.get("provider_reported_installed_size_bytes"), int
        )
        and cast(int, model["provider_reported_installed_size_bytes"]) > 0,
        "runtime_installation_scope_is_explicit": runtime_installation.get("measured")
        in {True, False},
        "real_machine_flag_matches_evidence_level": machine
        == (platform.system() == "Darwin" and platform.machine().casefold() in {"x86_64", "amd64"})
        if machine
        else True,
    }


def _claims() -> dict[str, bool]:
    return {
        "final_minimum_disk_requirement_defined": False,
        "full_install_disk_requirement_defined": False,
        "final_minimum_ram_requirement_defined": False,
        "total_system_peak_memory_measured": False,
        "gpu_or_metal_memory_requirement_defined": False,
        "installer_package_manager_cache_footprint_measured": False,
        "arbitrary_workspace_growth_measured": False,
        "all_model_storage_requirements_defined": False,
        "complete_local_stack_disk_footprint_measured": False,
        "cross_machine_performance_supported": False,
        "supported_or_default_model_selected": False,
        "user_visible_latency_requirement_defined": False,
        "release_candidate_soak_complete": False,
        "accessibility_gate_complete": False,
        "full_lite_performance_thresholds_defined": False,
        "lite_performance_gate_complete": False,
        "phase6_gate_complete": False,
        "lite_v1_complete": False,
    }


def _privacy() -> dict[str, bool]:
    return {
        "absolute_paths_in_report": False,
        "temporary_paths_in_report": False,
        "source_paths_in_report": False,
        "file_names_in_report": False,
        "runtime_install_member_names_in_report": False,
        "native_model_names_in_report": False,
        "usernames_in_report": False,
        "hostnames_in_report": False,
        "credentials_in_report": False,
        "secret_values_in_report": False,
        "process_ids_in_report": False,
        "process_command_lines_in_report": False,
        "urls_in_report": False,
        "email_addresses_in_report": False,
        "workspace_identifiers_in_report": False,
    }


def main() -> int:
    arguments = _arguments()
    try:
        machine = _validate_environment(arguments)
        observation = _real_observation(arguments) if machine else _synthetic_observation()
        payload = {
            "test_id": TEST_ID,
            "specification_version": "0.1",
            "commit_sha": arguments.commit_sha,
            "result": "pass",
            "evidence_level": "real-machine" if machine else "ci",
            "operating_system": platform.system() if machine else "synthetic",
            "architecture": platform.machine() if machine else "synthetic",
            "python_version": platform.python_version() if machine else "synthetic",
            "measurement_scope": "doll-lite-python-install-selected-model-storage",
            "network_mode": "offline-confirmed" if machine else "synthetic-no-io",
            "loopback_runtime_request_used": machine,
            "external_network_request_used": False,
            "cloud_credentials_used": False,
            "automatic_model_download_used": False,
            "runtime_install_or_start_used": False,
            "dependency_installation_performed": machine,
            "dependency_installation_network_allowed": False,
            "temporary_installation_cleaned": True,
            "synthetic_observations": not machine,
            "real_machine_measurement_collected": machine,
            "real_machine_measurement_accepted": False,
            "observation": observation,
            "checks": _checks(observation, machine=machine),
            "claims": _claims(),
            "privacy": _privacy(),
        }
    except (Imp102MeasurementError, OSError, subprocess.SubprocessError) as exc:
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
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
