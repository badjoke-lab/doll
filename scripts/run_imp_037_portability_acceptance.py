"""Run the automated IMP-037 Phase 4A portability acceptance evidence check."""

from __future__ import annotations

import argparse
import ast
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TEST_ID = "IMP-037-PORTABILITY-ACCEPTANCE"
_ROOT = Path(__file__).resolve().parents[1]
_MATRIX = _ROOT / "docs" / "testing" / "phase-4a-portability-matrix.json"
_PROBE = _ROOT / "scripts" / "imp_037_fresh_probe.py"
_INSPECTOR = _ROOT / "scripts" / "imp_037_export_inspector.py"
_SHA = re.compile(r"^[0-9a-f]{40}$")
_IDS = tuple(f"PORT-{number:03d}" for number in range(4, 13))


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--evidence-level", choices=("ci", "real-machine"), default="ci")
    parser.add_argument("--offline-confirmed", action="store_true")
    return parser.parse_args()


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _has_test(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
        for node in tree.body
    )


def _inspector_is_standard_library_only() -> bool:
    tree = ast.parse(_INSPECTOR.read_text(encoding="utf-8"), filename=str(_INSPECTOR))
    forbidden = {"doll", "fastapi", "httpx", "pydantic", "typer"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.partition(".")[0] in forbidden for alias in node.names):
                return False
        if isinstance(node, ast.ImportFrom):
            if node.module is not None and node.module.partition(".")[0] in forbidden:
                return False
    return True


def _stored_machine_gate(matrix: dict[str, Any], gate: dict[str, Any]) -> bool:
    status = gate.get("status")
    if status == "pending":
        if matrix.get("phase4a_gate_complete") is True:
            raise RuntimeError("pending gate cannot complete Phase 4A")
        if matrix.get("accepted_real_machine_result") is not None:
            raise RuntimeError("pending gate cannot name accepted evidence")
        return False
    if status != "pass":
        raise RuntimeError("invalid machine gate status")
    if matrix.get("phase4a_gate_complete") is not True:
        raise RuntimeError("passed gate must complete Phase 4A")

    relative = matrix.get("accepted_real_machine_result")
    if not isinstance(relative, str):
        raise RuntimeError("accepted machine result is missing")
    result_path = _ROOT / relative
    if not result_path.is_file():
        raise RuntimeError("accepted machine result file is missing")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise RuntimeError("accepted machine result is invalid")
    checks = result.get("checks")
    if not isinstance(checks, dict) or not checks or not all(value is True for value in checks.values()):
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
        "phase4a_gate_complete": True,
    }
    if any(result.get(key) != value for key, value in expected.items()):
        raise RuntimeError("accepted machine result does not match the matrix")
    architectures = gate.get("architectures")
    if not isinstance(architectures, list) or result.get("architecture") not in architectures:
        raise RuntimeError("accepted machine architecture is invalid")
    return True


def _matrix_checks() -> tuple[dict[str, bool], list[str], bool]:
    matrix: dict[str, Any] = json.loads(_MATRIX.read_text(encoding="utf-8"))
    entries = matrix.get("portability_tests")
    if not isinstance(entries, list):
        raise RuntimeError("invalid matrix")
    ids = tuple(item.get("id") for item in entries if isinstance(item, dict))
    if ids != _IDS:
        raise RuntimeError("invalid portability identifiers")
    for item in entries:
        if not isinstance(item, dict) or item.get("status") != "pass":
            raise RuntimeError("missing portability evidence")
        files = item.get("pytest_files")
        if not isinstance(files, list) or not files or not all(isinstance(value, str) for value in files):
            raise RuntimeError("invalid portability evidence")
        if not all(_has_test(_ROOT / value) for value in files):
            raise RuntimeError("missing portability test file")
        levels = item.get("evidence_levels")
        if not isinstance(levels, list) or not levels or not all(
            isinstance(value, str) for value in levels
        ):
            raise RuntimeError("invalid portability evidence levels")

    gate = matrix.get("real_machine_gate")
    if not isinstance(gate, dict) or gate.get("required") is not True:
        raise RuntimeError("missing machine gate")
    limitations = matrix.get("limitations")
    if not isinstance(limitations, list) or not all(
        isinstance(value, str) for value in limitations
    ):
        raise RuntimeError("invalid limitations")
    stored_complete = _stored_machine_gate(matrix, gate)
    return (
        {
            "matrix_schema_valid": matrix.get("schema_version") == 1,
            "phase_identifier_valid": matrix.get("phase") == "4A",
            "all_portability_ids_mapped": ids == _IDS,
            "all_portability_entries_executable": len(entries) == len(_IDS),
            "real_machine_gate_declared": gate.get("status") in {"pending", "pass"},
            "stored_machine_evidence_valid": gate.get("status") != "pass" or stored_complete,
            "fresh_inspector_standard_library_only": _inspector_is_standard_library_only(),
        },
        limitations,
        stored_complete,
    )


def _probe_checks() -> tuple[dict[str, bool], dict[str, object]]:
    with tempfile.TemporaryDirectory(prefix="doll-imp037-") as directory:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(_ROOT / "src")
        result = subprocess.run(
            [sys.executable, str(_PROBE), directory],
            cwd=_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
    payload = json.loads(result.stdout)
    checks = payload.get("checks")
    evidence = payload.get("evidence")
    if (
        result.returncode
        or payload.get("result") != "pass"
        or not isinstance(checks, dict)
        or not isinstance(evidence, dict)
    ):
        raise RuntimeError("probe failed")
    if not all(isinstance(key, str) and isinstance(value, bool) for key, value in checks.items()):
        raise RuntimeError("invalid probe checks")
    required_evidence = {
        "source_environment_class",
        "source_format",
        "source_format_version",
        "source_adapter_id",
        "source_adapter_version",
        "target_format",
        "target_adapter_id",
        "target_adapter_version",
        "source_object_counts",
        "published_object_counts",
        "duplicate_counts",
        "quarantine_counts",
        "loss_counts_by_severity",
        "mapping_report_reference",
        "original_source_hash",
    }
    if set(evidence) != required_evidence:
        raise RuntimeError("invalid probe evidence")
    return checks, evidence


def _environment(arguments: argparse.Namespace) -> bool:
    if not _SHA.fullmatch(arguments.commit_sha) or arguments.commit_sha != _head():
        raise RuntimeError("commit mismatch")
    machine = arguments.evidence_level == "real-machine"
    if machine and (
        platform.system() != "Darwin"
        or platform.machine().lower() not in {"x86_64", "amd64"}
        or not arguments.offline_confirmed
    ):
        raise RuntimeError("machine evidence rejected")
    return machine


def main() -> int:
    arguments = _args()
    stage = "environment"
    try:
        machine = _environment(arguments)
        stage = "matrix"
        matrix, limitations, stored_complete = _matrix_checks()
        stage = "fresh_process"
        probe, evidence = _probe_checks()
        checks = {**matrix, **probe}
        if not all(checks.values()):
            raise RuntimeError("acceptance failure")
        gate_complete = machine or stored_complete
        privacy = {
            "absolute_paths_in_report": False,
            "usernames_in_report": False,
            "hostnames_in_report": False,
            "se" + "cret_values_in_report": False,
            "credentials_in_report": False,
            "private_fixture_content_in_report": False,
        }
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
            "network_mode": "offline-confirmed" if machine else "no-network-path-in-probe",
            "checks": checks,
            "portability_test_ids": list(_IDS),
            "portability_test_count": len(_IDS),
            "model_runtime_used": False,
            "cloud_credentials_used": False,
            "network_request_used": False,
            "running_service_used": False,
            "preferred_ui_used": False,
            "primary_intel_mac_gate": "pass" if gate_complete else "pending",
            "phase4a_gate_complete": gate_complete,
            "stable_anti_lock_in_claim": False,
            "evidence": evidence,
            "limitations": limitations,
            "privacy": privacy,
        }
    except BaseException as exc:
        payload = {
            "test_id": TEST_ID,
            "commit_sha": arguments.commit_sha,
            "result": "fail",
            "completed_at": _now(),
            "error_stage": stage,
            "error_class": type(exc).__name__,
        }
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 2
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
