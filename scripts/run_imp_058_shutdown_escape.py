"""Run the IMP-058 Phase 6 shutdown escape acceptance check."""

from __future__ import annotations

import argparse
import ast
import json
import os
import platform
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

TEST_ID = "IMP-058-SHUTDOWN-ESCAPE"
ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs" / "testing" / "phase-6-shutdown-escape-matrix.json"
PROBE = ROOT / "scripts" / "imp_058_shutdown_escape_probe.py"
INSPECTOR = ROOT / "src" / "doll" / "shutdown_escape_inspector.py"
IDS = ("PORT-015",)
SHA = re.compile(r"^[0-9a-f]{40}$")
_EXPECTED_EVIDENCE_KEYS = {
    "format",
    "format_version",
    "bundle_sha256",
    "member_count",
    "record_type_count",
    "record_count_total",
    "omitted_secret_total",
    "recoverable_surface_count",
    "generic_conversation_export",
    "resume_bundle_count",
    "standalone_import_count",
    "runtime_mode",
    "source_workspace_removed",
}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


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


def _has_test(relative: str) -> bool:
    path = ROOT / relative
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
        for node in tree.body
    )


def _inspector_is_standalone() -> bool:
    tree = ast.parse(INSPECTOR.read_text(encoding="utf-8"), filename=str(INSPECTOR))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module.split(".", 1)[0])
    return bool(imports) and "doll" not in imports and imports <= sys.stdlib_module_names


def _accepted_machine_result(matrix: dict[str, Any], gate: dict[str, Any]) -> bool:
    if gate.get("status") == "pending":
        if matrix.get("shutdown_escape_gate_complete") is True:
            raise RuntimeError("pending gate cannot complete shutdown escape")
        if matrix.get("accepted_real_machine_result") is not None:
            raise RuntimeError("pending gate cannot name accepted evidence")
        if gate.get("commit_sha") is not None or gate.get("completed_at") is not None:
            raise RuntimeError("pending gate cannot bind machine evidence")
        return False
    if gate.get("status") != "pass" or matrix.get("shutdown_escape_gate_complete") is not True:
        raise RuntimeError("invalid completed shutdown escape gate")
    relative = matrix.get("accepted_real_machine_result")
    if not isinstance(relative, str):
        raise RuntimeError("accepted machine result is missing")
    result_path = ROOT / relative
    if not result_path.is_file():
        raise RuntimeError("accepted machine result file is missing")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    checks = result.get("checks") if isinstance(result, dict) else None
    if (
        not isinstance(checks, dict)
        or not checks
        or not all(value is True for value in checks.values())
    ):
        raise RuntimeError("accepted machine checks are invalid")
    expected = {
        "test_id": TEST_ID,
        "result": "pass",
        "evidence_level": "real-machine",
        "operating_system": gate.get("platform"),
        "commit_sha": gate.get("commit_sha"),
        "completed_at": gate.get("completed_at"),
        "network_mode": gate.get("network_mode"),
        "primary_intel_mac_gate": "pass",
        "shutdown_escape_gate_complete": True,
    }
    if any(result.get(key) != value for key, value in expected.items()):
        raise RuntimeError("accepted machine result does not match matrix")
    architectures = gate.get("architectures")
    if not isinstance(architectures, list) or result.get("architecture") not in architectures:
        raise RuntimeError("accepted machine architecture is invalid")
    evidence = result.get("evidence")
    if not isinstance(evidence, dict) or set(evidence) != _EXPECTED_EVIDENCE_KEYS:
        raise RuntimeError("accepted machine evidence shape is invalid")
    privacy = result.get("privacy")
    if not isinstance(privacy, dict) or any(value is not False for value in privacy.values()):
        raise RuntimeError("accepted machine privacy flags are invalid")
    return True


def _matrix_evidence() -> tuple[dict[str, bool], list[str], bool]:
    matrix: dict[str, Any] = json.loads(MATRIX.read_text(encoding="utf-8"))
    entries = matrix.get("portability_tests")
    if not isinstance(entries, list):
        raise RuntimeError("invalid shutdown escape matrix")
    ids = tuple(item.get("id") for item in entries if isinstance(item, dict))
    if ids != IDS:
        raise RuntimeError("invalid shutdown escape identifiers")
    gate = matrix.get("real_machine_gate")
    limitations = matrix.get("limitations")
    if not isinstance(gate, dict) or gate.get("required") is not True:
        raise RuntimeError("missing primary-machine gate")
    gate_status = gate.get("status")
    if gate_status not in {"pending", "pass"}:
        raise RuntimeError("invalid primary-machine gate status")
    if gate.get("minimum_local_models") != 0:
        raise RuntimeError("shutdown escape must not require a local model")
    if not isinstance(limitations, list) or not all(
        isinstance(value, str) for value in limitations
    ):
        raise RuntimeError("invalid limitations")

    expected_status = "pass" if gate_status == "pass" else "ci-pass"
    expected_levels = ["ci", "real-machine"] if gate_status == "pass" else ["ci"]
    for item in entries:
        if not isinstance(item, dict) or item.get("status") != expected_status:
            raise RuntimeError("shutdown escape evidence status does not match gate")
        files = item.get("pytest_files")
        if (
            not isinstance(files, list)
            or not files
            or not all(isinstance(value, str) and _has_test(value) for value in files)
        ):
            raise RuntimeError("invalid shutdown escape test evidence")
        if item.get("passed_evidence_levels") != expected_levels:
            raise RuntimeError("invalid passed shutdown escape evidence levels")
        if item.get("required_evidence_levels") != ["ci", "real-machine"]:
            raise RuntimeError("invalid required shutdown escape evidence levels")

    stored_complete = _accepted_machine_result(matrix, gate)
    checks = {
        "matrix_schema_valid": matrix.get("schema_version") == 1,
        "phase_identifier_valid": matrix.get("phase") == "6",
        "portability_identifier_mapped": ids == IDS,
        "portability_entry_executable": len(entries) == 1,
        "entry_status_matches_machine_gate": all(
            isinstance(item, dict) and item.get("status") == expected_status for item in entries
        ),
        "primary_machine_gate_declared": gate_status in {"pending", "pass"},
        "stored_machine_evidence_valid": gate_status != "pass" or stored_complete,
        "standalone_inspector_uses_only_stdlib": _inspector_is_standalone(),
    }
    return checks, cast(list[str], limitations), stored_complete


def _machine_mode(arguments: argparse.Namespace) -> bool:
    if not SHA.fullmatch(arguments.commit_sha) or arguments.commit_sha != _head():
        raise RuntimeError("commit mismatch")
    machine = cast(str, arguments.evidence_level) == "real-machine"
    if machine:
        if (
            platform.system() != "Darwin"
            or platform.machine().lower() not in {"x86_64", "amd64"}
            or not arguments.offline_confirmed
            or not arguments.local_only_confirmed
        ):
            raise RuntimeError("machine evidence rejected")
    elif arguments.offline_confirmed or arguments.local_only_confirmed:
        raise RuntimeError("CI evidence cannot accept real-machine confirmations")
    return machine


def _run_probe(machine: bool) -> tuple[dict[str, bool], dict[str, object]]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(ROOT / "src"), str(ROOT)))
    environment["NO_PROXY"] = "*"
    environment["HTTP_PROXY"] = "http://127.0.0.1:9"
    environment["HTTPS_PROXY"] = "http://127.0.0.1:9"
    result = subprocess.run(
        [
            sys.executable,
            str(PROBE),
            "--mode",
            "real-machine" if machine else "ci",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(result.stdout)
    checks = payload.get("checks")
    evidence = payload.get("evidence")
    if result.returncode or payload.get("result") != "pass":
        raise RuntimeError("shutdown escape probe failed")
    if not isinstance(checks, dict) or not all(
        isinstance(key, str) and isinstance(value, bool) for key, value in checks.items()
    ):
        raise RuntimeError("invalid shutdown escape probe checks")
    if not isinstance(evidence, dict) or set(evidence) != _EXPECTED_EVIDENCE_KEYS:
        raise RuntimeError("invalid shutdown escape probe evidence")
    expected_mode = "real-local" if machine else "synthetic"
    if evidence.get("runtime_mode") != expected_mode:
        raise RuntimeError("shutdown escape runtime mode is invalid")
    return cast(dict[str, bool], checks), cast(dict[str, object], evidence)


def main() -> int:
    arguments = _arguments()
    stage = "environment"
    try:
        machine = _machine_mode(arguments)
        stage = "matrix"
        matrix_checks, limitations, stored_complete = _matrix_evidence()
        stage = "shutdown_escape_probe"
        probe_checks, evidence = _run_probe(machine)
        checks = {**matrix_checks, **probe_checks}
        if not all(checks.values()):
            raise RuntimeError("shutdown escape acceptance failure")
        gate_complete = machine or stored_complete
        payload: dict[str, object] = {
            "test_id": TEST_ID,
            "specification_version": "0.1",
            "commit_sha": arguments.commit_sha,
            "result": "pass",
            "started_at": _now(),
            "completed_at": _now(),
            "evidence_level": arguments.evidence_level,
            "operating_system": platform.system(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "network_mode": "offline-confirmed" if machine else "synthetic-no-network",
            "checks": checks,
            "portability_test_ids": list(IDS),
            "portability_test_count": len(IDS),
            "real_machine_used": machine,
            "real_runtime_used": False,
            "cloud_credentials_used": False,
            "external_network_request_used": False,
            "model_execution_used": False,
            "model_download_used": False,
            "runtime_installation_used": False,
            "preferred_interface_required": False,
            "doll_service_required": False,
            "primary_intel_mac_gate": "pass" if gate_complete else "pending",
            "shutdown_escape_gate_complete": gate_complete,
            "phase6_gate_complete": False,
            "stable_anti_lock_in_claim": False,
            "evidence": evidence,
            "limitations": limitations,
            "privacy": {
                "absolute_paths_in_report": False,
                "usernames_in_report": False,
                "hostnames_in_report": False,
                "native_model_names_in_report": False,
                "record_content_in_report": False,
                "project_names_in_report": False,
                "conversation_text_in_report": False,
                "secret_values_in_report": False,
                "credentials_in_report": False,
            },
        }
        status = 0
    except BaseException as exc:
        payload = {
            "test_id": TEST_ID,
            "commit_sha": arguments.commit_sha,
            "result": "fail",
            "evidence_level": arguments.evidence_level,
            "error_stage": stage,
            "error_class": type(exc).__name__,
            "phase6_gate_complete": False,
            "stable_anti_lock_in_claim": False,
        }
        status = 1
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return status


if __name__ == "__main__":
    sys.exit(main())
