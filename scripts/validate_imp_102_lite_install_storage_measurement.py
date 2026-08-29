"""Validate privacy-safe IMP-102 Lite installation/model-storage evidence."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import cast

TEST_ID = "IMP-102-LITE-INSTALL-MODEL-STORAGE-MEASUREMENT"
MODEL_ID = re.compile(r"^ollama\.model\.[0-9a-f]{64}$")
REVISION = re.compile(r"^sha256-[0-9a-f]{64}$")
SHA = re.compile(r"^[0-9a-f]{40}$")
UV_VERSION = re.compile(r"^uv [0-9][A-Za-z0-9._+\-]{0,63}$")
RUNTIME_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+\-]{0,127}$")


class Imp102EvidenceValidationError(RuntimeError):
    """Raised when proposed IMP-102 real-machine evidence is unacceptable."""


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise Imp102EvidenceValidationError(f"{label} must be a JSON object")
    return cast(dict[str, object], value)


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise Imp102EvidenceValidationError(f"{label} must be a positive integer")
    return value


def _nonnegative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise Imp102EvidenceValidationError(f"{label} must be a non-negative integer")
    return value


def _validate_tree(value: object, label: str) -> None:
    tree = _object(value, label)
    expected_fields = {
        "regular_file_count",
        "directory_count",
        "symlink_count",
        "other_entry_count",
        "logical_bytes",
        "allocated_bytes",
        "allocated_bytes_source",
        "symlink_target_bytes_included",
    }
    if set(tree) != expected_fields:
        raise Imp102EvidenceValidationError(f"{label} has unexpected fields")
    _positive_int(tree.get("regular_file_count"), f"{label} regular file count")
    _nonnegative_int(tree.get("directory_count"), f"{label} directory count")
    _nonnegative_int(tree.get("symlink_count"), f"{label} symlink count")
    _nonnegative_int(tree.get("other_entry_count"), f"{label} other entry count")
    _positive_int(tree.get("logical_bytes"), f"{label} logical bytes")
    allocated = tree.get("allocated_bytes")
    source = tree.get("allocated_bytes_source")
    if allocated is None:
        if source is not None:
            raise Imp102EvidenceValidationError(f"{label} allocated-byte source is inconsistent")
    else:
        _positive_int(allocated, f"{label} allocated bytes")
        if source != "stat-st_blocks-times-512":
            raise Imp102EvidenceValidationError(f"{label} allocated-byte source is invalid")
    if tree.get("symlink_target_bytes_included") is not False:
        raise Imp102EvidenceValidationError(f"{label} must exclude symlink target bytes")


def load_and_validate_evidence(
    path: Path,
    *,
    expected_commit_sha: str,
) -> dict[str, object]:
    if SHA.fullmatch(expected_commit_sha) is None:
        raise Imp102EvidenceValidationError("expected commit SHA is invalid")
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Imp102EvidenceValidationError("evidence file is not valid UTF-8 JSON") from exc
    document = _object(payload, "evidence")

    expected = {
        "test_id": TEST_ID,
        "specification_version": "0.1",
        "commit_sha": expected_commit_sha,
        "result": "pass",
        "evidence_level": "real-machine",
        "operating_system": "Darwin",
        "measurement_scope": "doll-lite-python-install-selected-model-storage",
        "network_mode": "offline-confirmed",
        "loopback_runtime_request_used": True,
        "external_network_request_used": False,
        "cloud_credentials_used": False,
        "automatic_model_download_used": False,
        "runtime_install_or_start_used": False,
        "dependency_installation_performed": True,
        "dependency_installation_network_allowed": False,
        "temporary_installation_cleaned": True,
        "synthetic_observations": False,
        "real_machine_measurement_collected": True,
        "real_machine_measurement_accepted": False,
    }
    for key, expected_value in expected.items():
        if document.get(key) != expected_value:
            raise Imp102EvidenceValidationError(f"invalid {key}")

    architecture = document.get("architecture")
    if not isinstance(architecture, str) or architecture.casefold() not in {"x86_64", "amd64"}:
        raise Imp102EvidenceValidationError("invalid primary Intel Mac architecture")
    python_version = document.get("python_version")
    if not isinstance(python_version, str) or not python_version:
        raise Imp102EvidenceValidationError("Python version is missing")

    observation = _object(document.get("observation"), "observation")
    if set(observation) != {
        "uv_version",
        "lite_python_installation",
        "runtime_version",
        "runtime_installation",
        "model",
    }:
        raise Imp102EvidenceValidationError("observation has unexpected fields")
    uv_version = observation.get("uv_version")
    runtime_version = observation.get("runtime_version")
    if not isinstance(uv_version, str) or UV_VERSION.fullmatch(uv_version) is None:
        raise Imp102EvidenceValidationError("invalid uv version")
    if not isinstance(runtime_version, str) or RUNTIME_VERSION.fullmatch(runtime_version) is None:
        raise Imp102EvidenceValidationError("invalid runtime version")

    installation = _object(observation.get("lite_python_installation"), "Lite installation")
    if set(installation) != {
        "profile",
        "optional_extras",
        "dependency_source_mode",
        "editable_install_used",
        "dev_dependencies_included",
        "tree",
        "verification",
    }:
        raise Imp102EvidenceValidationError("Lite installation has unexpected fields")
    if installation.get("profile") != "lite-python-no-dev-all-extras":
        raise Imp102EvidenceValidationError("invalid Lite installation profile")
    if installation.get("optional_extras") != ["ocr", "pdf"]:
        raise Imp102EvidenceValidationError("Lite optional extras are incomplete")
    if installation.get("dependency_source_mode") != "locked-offline-local-cache":
        raise Imp102EvidenceValidationError("Lite dependency source mode is invalid")
    if installation.get("editable_install_used") is not False:
        raise Imp102EvidenceValidationError("editable installation is not accepted")
    if installation.get("dev_dependencies_included") is not False:
        raise Imp102EvidenceValidationError("dev dependencies are not accepted")
    _validate_tree(installation.get("tree"), "Lite installation tree")
    verification = _object(installation.get("verification"), "Lite installation verification")
    required_verification = {
        "doll_importable",
        "pdf_adapter_dependency_present",
        "ocr_adapter_dependency_present",
        "dev_tools_absent",
    }
    if set(verification) != required_verification or any(
        value is not True for value in verification.values()
    ):
        raise Imp102EvidenceValidationError("Lite installation verification failed")

    runtime_installation = _object(
        observation.get("runtime_installation"), "runtime installation"
    )
    measured = runtime_installation.get("measured")
    if measured is False:
        if set(runtime_installation) != {"measured"}:
            raise Imp102EvidenceValidationError("unmeasured runtime installation has extra fields")
    elif measured is True:
        if set(runtime_installation) != {"measured", "tree"}:
            raise Imp102EvidenceValidationError("runtime installation has unexpected fields")
        _validate_tree(runtime_installation.get("tree"), "runtime installation tree")
    else:
        raise Imp102EvidenceValidationError("runtime installation measurement flag is invalid")

    model = _object(observation.get("model"), "model")
    if set(model) != {
        "model_id",
        "revision",
        "provider_reported_installed_size_bytes",
    }:
        raise Imp102EvidenceValidationError("model has unexpected fields")
    model_id = model.get("model_id")
    revision = model.get("revision")
    if not isinstance(model_id, str) or MODEL_ID.fullmatch(model_id) is None:
        raise Imp102EvidenceValidationError("opaque model identity is invalid")
    if not isinstance(revision, str) or REVISION.fullmatch(revision) is None:
        raise Imp102EvidenceValidationError("model revision is invalid")
    _positive_int(
        model.get("provider_reported_installed_size_bytes"),
        "provider-reported installed model size",
    )

    checks = _object(document.get("checks"), "checks")
    if not checks or not all(value is True for value in checks.values()):
        raise Imp102EvidenceValidationError("all measurement checks must pass")

    claims = _object(document.get("claims"), "claims")
    required_false_claims = {
        "final_minimum_disk_requirement_defined",
        "full_install_disk_requirement_defined",
        "final_minimum_ram_requirement_defined",
        "total_system_peak_memory_measured",
        "gpu_or_metal_memory_requirement_defined",
        "installer_package_manager_cache_footprint_measured",
        "arbitrary_workspace_growth_measured",
        "all_model_storage_requirements_defined",
        "complete_local_stack_disk_footprint_measured",
        "cross_machine_performance_supported",
        "supported_or_default_model_selected",
        "user_visible_latency_requirement_defined",
        "release_candidate_soak_complete",
        "accessibility_gate_complete",
        "full_lite_performance_thresholds_defined",
        "lite_performance_gate_complete",
        "phase6_gate_complete",
        "lite_v1_complete",
    }
    if set(claims) != required_false_claims or any(claims.values()):
        raise Imp102EvidenceValidationError("forbidden disk, performance, or release claim detected")

    privacy = _object(document.get("privacy"), "privacy")
    required_privacy_flags = {
        "absolute_paths_in_report",
        "temporary_paths_in_report",
        "source_paths_in_report",
        "file_names_in_report",
        "runtime_install_member_names_in_report",
        "native_model_names_in_report",
        "usernames_in_report",
        "hostnames_in_report",
        "credentials_in_report",
        "secret_values_in_report",
        "process_ids_in_report",
        "process_command_lines_in_report",
        "urls_in_report",
        "email_addresses_in_report",
        "workspace_identifiers_in_report",
    }
    if set(privacy) != required_privacy_flags or any(
        value is not False for value in privacy.values()
    ):
        raise Imp102EvidenceValidationError("privacy flags must all be false")

    forbidden_keys = {
        "source_path",
        "source_paths",
        "runtime_install_root",
        "temporary_path",
        "absolute_path",
        "file_name",
        "file_names",
        "native_model_name",
        "pid",
        "command_line",
        "hostname",
        "username",
        "email",
        "url",
        "credential",
        "secret",
    }

    def inspect_keys(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in forbidden_keys:
                    raise Imp102EvidenceValidationError(
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
        "measurement_scope": "doll-lite-python-install-selected-model-storage",
        "runtime_installation_measured": measured,
        "real_machine_measurement_accepted": False,
        "full_install_disk_requirement_defined": False,
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
    except Imp102EvidenceValidationError as exc:
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
