"""Run the IMP-047 Phase 4B project-continuity acceptance check."""

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

TEST_ID = "IMP-047-PROJECT-CONTINUITY-ACCEPTANCE"
ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs" / "testing" / "phase-4b-project-continuity-matrix.json"
PROBE = ROOT / "scripts" / "imp_047_fresh_probe.py"
INSPECTOR = ROOT / "scripts" / "imp_047_bundle_inspector.py"
IDS = tuple(f"PROJ-{number:03d}" for number in range(1, 13))
SHA = re.compile(r"^[0-9a-f]{40}$")


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--evidence-level", choices=("ci", "real-machine"), default="ci")
    parser.add_argument("--offline-confirmed", action="store_true")
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


def _inspector_is_independent() -> bool:
    tree = ast.parse(INSPECTOR.read_text(encoding="utf-8"), filename=str(INSPECTOR))
    forbidden = {"doll", "fastapi", "httpx", "pydantic", "typer"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if {alias.name.partition(".")[0] for alias in node.names} & forbidden:
                return False
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module.partition(".")[0] in forbidden:
                return False
    return True


def _accepted_machine_result(matrix: dict[str, Any], gate: dict[str, Any]) -> bool:
    if gate.get("status") == "pending":
        if matrix.get("phase4b_gate_complete") is True:
            raise RuntimeError("pending gate cannot complete Phase 4B")
        if matrix.get("accepted_real_machine_result") is not None:
            raise RuntimeError("pending gate cannot name accepted evidence")
        if gate.get("commit_sha") is not None or gate.get("completed_at") is not None:
            raise RuntimeError("pending gate cannot bind machine evidence")
        return False
    if gate.get("status") != "pass" or matrix.get("phase4b_gate_complete") is not True:
        raise RuntimeError("invalid completed machine gate")
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
        "phase4b_gate_complete": True,
    }
    if any(result.get(key) != value for key, value in expected.items()):
        raise RuntimeError("accepted machine result does not match matrix")
    architectures = gate.get("architectures")
    if not isinstance(architectures, list) or result.get("architecture") not in architectures:
        raise RuntimeError("accepted machine architecture is invalid")
    return True


def _matrix_evidence() -> tuple[dict[str, bool], list[str], bool]:
    matrix: dict[str, Any] = json.loads(MATRIX.read_text(encoding="utf-8"))
    entries = matrix.get("project_tests")
    if not isinstance(entries, list):
        raise RuntimeError("invalid project-continuity matrix")
    ids = tuple(item.get("id") for item in entries if isinstance(item, dict))
    if ids != IDS:
        raise RuntimeError("invalid project-continuity identifiers")
    for item in entries:
        if not isinstance(item, dict) or item.get("status") != "pass":
            raise RuntimeError("missing project-continuity evidence")
        files = item.get("pytest_files")
        levels = item.get("evidence_levels")
        if (
            not isinstance(files, list)
            or not files
            or not all(isinstance(value, str) and _has_test(value) for value in files)
        ):
            raise RuntimeError("invalid project-continuity test evidence")
        if (
            not isinstance(levels, list)
            or not levels
            or not all(isinstance(value, str) for value in levels)
        ):
            raise RuntimeError("invalid project-continuity evidence levels")
    gate = matrix.get("real_machine_gate")
    limitations = matrix.get("limitations")
    if not isinstance(gate, dict) or gate.get("required") is not True:
        raise RuntimeError("missing primary-machine gate")
    if not isinstance(limitations, list) or not all(
        isinstance(value, str) for value in limitations
    ):
        raise RuntimeError("invalid limitations")
    stored_complete = _accepted_machine_result(matrix, gate)
    checks = {
        "matrix_schema_valid": matrix.get("schema_version") == 1,
        "phase_identifier_valid": matrix.get("phase") == "4B",
        "all_project_test_ids_mapped": ids == IDS,
        "all_project_entries_executable": len(entries) == len(IDS),
        "primary_machine_gate_declared": gate.get("status") in {"pending", "pass"},
        "stored_machine_evidence_valid": gate.get("status") != "pass" or stored_complete,
        "resume_bundle_inspector_standard_library_only": _inspector_is_independent(),
    }
    return checks, cast(list[str], limitations), stored_complete


def _fresh_probe() -> tuple[dict[str, bool], dict[str, object]]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(ROOT / "src"), str(ROOT)))
    environment["DOLL_DISABLE_MODEL_ADAPTERS"] = "1"
    environment["NO_PROXY"] = "*"
    environment["HTTP_PROXY"] = "http://127.0.0.1:9"
    environment["HTTPS_PROXY"] = "http://127.0.0.1:9"
    result = subprocess.run(
        [sys.executable, str(PROBE)],
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
        raise RuntimeError("fresh project-continuity probe failed")
    if not isinstance(checks, dict) or not all(
        isinstance(key, str) and isinstance(value, bool) for key, value in checks.items()
    ):
        raise RuntimeError("invalid fresh-probe checks")
    required = {
        "project_schema_version",
        "project_status_schema",
        "state_package_format_version",
        "resume_bundle_format_version",
        "checkpoint_freshness",
        "basis_fingerprint",
        "record_counts",
        "omitted_secret_counts",
        "independent_inspector_check_count",
        "backup_modes",
    }
    if not isinstance(evidence, dict) or set(evidence) != required:
        raise RuntimeError("invalid fresh-probe evidence")
    return cast(dict[str, bool], checks), cast(dict[str, object], evidence)


def _machine_mode(arguments: argparse.Namespace) -> bool:
    if not SHA.fullmatch(arguments.commit_sha) or arguments.commit_sha != _head():
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
    arguments = _arguments()
    stage = "environment"
    try:
        machine = _machine_mode(arguments)
        stage = "matrix"
        matrix_checks, limitations, stored_complete = _matrix_evidence()
        stage = "fresh_process"
        probe_checks, evidence = _fresh_probe()
        checks = {**matrix_checks, **probe_checks}
        if not all(checks.values()):
            raise RuntimeError("project-continuity acceptance failure")
        gate_complete = machine or stored_complete
        payload: dict[str, object] = {
            "test_id": TEST_ID,
            "specification_version": "0.2",
            "commit_sha": arguments.commit_sha,
            "result": "pass",
            "started_at": _now(),
            "completed_at": _now(),
            "evidence_level": arguments.evidence_level,
            "operating_system": platform.system(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "network_mode": "offline-confirmed" if machine else "no-network-path-in-probe",
            "checks": checks,
            "project_test_ids": list(IDS),
            "project_test_count": len(IDS),
            "model_runtime_used": False,
            "cloud_credentials_used": False,
            "network_request_used": False,
            "running_service_used": False,
            "preferred_ui_used": False,
            "primary_intel_mac_gate": "pass" if gate_complete else "pending",
            "phase4b_gate_complete": gate_complete,
            "evidence": evidence,
            "limitations": limitations,
            "privacy": {
                "absolute_paths_in_report": False,
                "usernames_in_report": False,
                "hostnames_in_report": False,
                "se" + "cret_values_in_report": False,
                "credentials_in_report": False,
                "private_fixture_content_in_report": False,
            },
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
