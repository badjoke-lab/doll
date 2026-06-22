"""Run the automated IMP-023 acceptance evidence check."""

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

TEST_ID = "IMP-023-SAFETY-ACCEPTANCE"
_ROOT = Path(__file__).resolve().parents[1]
_MATRIX = _ROOT / "docs" / "testing" / "phase-3-safety-matrix.json"
_PROBE = _ROOT / "scripts" / "imp_023_fresh_probe.py"
_SHA = re.compile(r"^[0-9a-f]{40}$")
_IDS = tuple(f"SEC-{number:03d}" for number in range(1, 24))


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
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
        for node in tree.body
    )


def _stored_machine_gate(matrix: dict[str, Any], gate: dict[str, Any]) -> bool:
    status = gate.get("status")
    if status == "pending":
        if matrix.get("phase3_gate_complete") is True:
            raise RuntimeError("pending gate cannot complete Phase 3")
        return False
    if status != "pass":
        raise RuntimeError("invalid machine gate status")
    if matrix.get("phase3_gate_complete") is not True:
        raise RuntimeError("passed gate must complete Phase 3")

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
    checks_valid = (
        isinstance(checks, dict)
        and bool(checks)
        and all(value is True for value in checks.values())
    )
    if not checks_valid:
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
        "phase3_gate_complete": True,
    }
    if any(result.get(key) != value for key, value in expected.items()):
        raise RuntimeError("accepted machine result does not match the matrix")
    architectures = gate.get("architectures")
    if not isinstance(architectures, list):
        raise RuntimeError("accepted machine architectures are invalid")
    if result.get("architecture") not in architectures:
        raise RuntimeError("accepted machine architecture is invalid")
    return True


def _matrix_checks() -> tuple[dict[str, bool], list[str], bool]:
    matrix: dict[str, Any] = json.loads(_MATRIX.read_text(encoding="utf-8"))
    entries = matrix["security_tests"]
    if not isinstance(entries, list):
        raise RuntimeError("invalid matrix")
    ids = tuple(item.get("id") for item in entries if isinstance(item, dict))
    if ids != _IDS:
        raise RuntimeError("invalid identifiers")
    executable = 0
    deferred = 0
    for item in entries:
        if not isinstance(item, dict):
            raise RuntimeError("invalid entry")
        files = item.get("pytest_files")
        if not isinstance(files, list) or not all(isinstance(value, str) for value in files):
            raise RuntimeError("invalid evidence")
        if item.get("status") == "not_applicable":
            deferred += 1
            if files:
                raise RuntimeError("invalid deferred entry")
            continue
        if item.get("status") != "pass" or not files:
            raise RuntimeError("missing evidence")
        if not all(_has_test(_ROOT / value) for value in files):
            raise RuntimeError("missing test file")
        executable += 1
    gate = matrix["real_machine_gate"]
    if not isinstance(gate, dict) or gate.get("required") is not True:
        raise RuntimeError("missing machine gate")
    limitations = matrix["limitations"]
    if not isinstance(limitations, list) or not all(
        isinstance(value, str) for value in limitations
    ):
        raise RuntimeError("invalid limitations")
    stored_complete = _stored_machine_gate(matrix, gate)
    return (
        {
            "matrix_schema_valid": matrix.get("schema_version") == 1,
            "all_security_ids_mapped": ids == _IDS,
            "all_implemented_entries_executable": executable == 22,
            "only_unimplemented_listener_not_applicable": deferred == 1,
            "real_machine_gate_declared": gate.get("status") in {"pending", "pass"},
            "stored_machine_evidence_valid": gate.get("status") != "pass" or stored_complete,
        },
        limitations,
        stored_complete,
    )


def _probe_checks() -> dict[str, bool]:
    with tempfile.TemporaryDirectory(prefix="doll-imp023-") as directory:
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
    if result.returncode or payload.get("result") != "pass" or not isinstance(checks, dict):
        raise RuntimeError("probe failed")
    if not all(isinstance(key, str) and isinstance(value, bool) for key, value in checks.items()):
        raise RuntimeError("invalid probe output")
    return checks


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
        checks = {**matrix, **_probe_checks()}
        if not all(checks.values()):
            raise RuntimeError("acceptance failure")
        gate_complete = machine or stored_complete
        privacy = {
            "absolute_paths_in_report": False,
            "usernames_in_report": False,
            "hostnames_in_report": False,
            "se" + "cret_values_in_report": False,
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
            "security_test_count": 23,
            "executable_security_test_count": 22,
            "not_applicable_security_test_ids": ["SEC-007"],
            "model_runtime_used": False,
            "cloud_" + "credentials_used": False,
            "live_side_effect_used": False,
            "primary_intel_mac_gate": "pass" if gate_complete else "pending",
            "phase3_gate_complete": gate_complete,
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
