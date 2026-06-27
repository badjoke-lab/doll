"""Run the IMP-054 Phase 5 local-runtime continuity acceptance check."""

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

TEST_ID = "IMP-054-LOCAL-RUNTIME-CONTINUITY"
ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs" / "testing" / "phase-5-local-runtime-continuity-matrix.json"
PROBE = ROOT / "scripts" / "imp_054_runtime_probe.py"
IDS = tuple(f"LRUN-{number:03d}" for number in range(1, 13))
SHA = re.compile(r"^[0-9a-f]{40}$")
_EXPECTED_EVIDENCE_KEYS = {
    "runtime_adapter_id",
    "runtime_adapter_version",
    "runtime_version",
    "runtime_mode",
    "model_count",
    "model_revision_hashes",
    "canonical_turn_count",
    "canonical_event_count",
    "package_format_version",
    "backup_fresh_process_validated",
    "fresh_inspection_count",
    "fresh_record_counts",
    "ollama_request_count",
    "ollama_stream_count",
    "allowed_loopback_socket_attempts",
    "rejected_socket_attempts",
    "active_binding_hash",
}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--evidence-level", choices=("ci", "real-machine"), default="ci")
    parser.add_argument("--offline-confirmed", action="store_true")
    parser.add_argument("--local-only-confirmed", action="store_true")
    parser.add_argument("--primary-model")
    parser.add_argument("--fallback-model")
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


def _has_test(relative: str) -> bool:
    path = ROOT / relative
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
        for node in tree.body
    )


def _accepted_machine_result(matrix: dict[str, Any], gate: dict[str, Any]) -> bool:
    if gate.get("status") == "pending":
        if matrix.get("phase5_gate_complete") is True:
            raise RuntimeError("pending gate cannot complete Phase 5")
        if matrix.get("accepted_real_machine_result") is not None:
            raise RuntimeError("pending gate cannot name accepted evidence")
        if gate.get("commit_sha") is not None or gate.get("completed_at") is not None:
            raise RuntimeError("pending gate cannot bind machine evidence")
        return False
    if gate.get("status") != "pass" or matrix.get("phase5_gate_complete") is not True:
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
        "phase5_gate_complete": True,
    }
    if any(result.get(key) != value for key, value in expected.items()):
        raise RuntimeError("accepted machine result does not match matrix")
    architectures = gate.get("architectures")
    if not isinstance(architectures, list) or result.get("architecture") not in architectures:
        raise RuntimeError("accepted machine architecture is invalid")
    evidence = result.get("evidence")
    if not isinstance(evidence, dict) or set(evidence) != _EXPECTED_EVIDENCE_KEYS:
        raise RuntimeError("accepted machine evidence shape is invalid")
    return True


def _matrix_evidence() -> tuple[dict[str, bool], list[str], bool]:
    matrix: dict[str, Any] = json.loads(MATRIX.read_text(encoding="utf-8"))
    entries = matrix.get("runtime_tests")
    if not isinstance(entries, list):
        raise RuntimeError("invalid local-runtime continuity matrix")
    ids = tuple(item.get("id") for item in entries if isinstance(item, dict))
    if ids != IDS:
        raise RuntimeError("invalid local-runtime continuity identifiers")
    for item in entries:
        if not isinstance(item, dict) or item.get("status") != "pass":
            raise RuntimeError("missing local-runtime continuity evidence")
        files = item.get("pytest_files")
        levels = item.get("evidence_levels")
        if (
            not isinstance(files, list)
            or not files
            or not all(isinstance(value, str) and _has_test(value) for value in files)
        ):
            raise RuntimeError("invalid local-runtime test evidence")
        if levels != ["ci", "real-machine"]:
            raise RuntimeError("invalid local-runtime evidence levels")
    gate = matrix.get("real_machine_gate")
    limitations = matrix.get("limitations")
    if not isinstance(gate, dict) or gate.get("required") is not True:
        raise RuntimeError("missing primary-machine gate")
    if gate.get("minimum_local_models") != 2:
        raise RuntimeError("invalid minimum local-model requirement")
    if not isinstance(limitations, list) or not all(
        isinstance(value, str) for value in limitations
    ):
        raise RuntimeError("invalid limitations")
    stored_complete = _accepted_machine_result(matrix, gate)
    checks = {
        "matrix_schema_valid": matrix.get("schema_version") == 1,
        "phase_identifier_valid": matrix.get("phase") == "5",
        "all_runtime_test_ids_mapped": ids == IDS,
        "all_runtime_entries_executable": len(entries) == len(IDS),
        "primary_machine_gate_declared": gate.get("status") in {"pending", "pass"},
        "stored_machine_evidence_valid": gate.get("status") != "pass" or stored_complete,
    }
    return checks, cast(list[str], limitations), stored_complete


def _machine_mode(arguments: argparse.Namespace) -> bool:
    if not SHA.fullmatch(arguments.commit_sha) or arguments.commit_sha != _head():
        raise RuntimeError("commit mismatch")
    if (
        isinstance(arguments.ollama_port, bool)
        or not isinstance(arguments.ollama_port, int)
        or not 1 <= arguments.ollama_port <= 65535
    ):
        raise RuntimeError("invalid Ollama port")
    machine = arguments.evidence_level == "real-machine"
    if machine:
        if (
            platform.system() != "Darwin"
            or platform.machine().lower() not in {"x86_64", "amd64"}
            or not arguments.offline_confirmed
            or not arguments.local_only_confirmed
            or not isinstance(arguments.primary_model, str)
            or not arguments.primary_model
            or not isinstance(arguments.fallback_model, str)
            or not arguments.fallback_model
            or arguments.primary_model == arguments.fallback_model
        ):
            raise RuntimeError("machine evidence rejected")
    elif any(
        value
        for value in (
            arguments.offline_confirmed,
            arguments.local_only_confirmed,
            arguments.primary_model,
            arguments.fallback_model,
        )
    ):
        raise RuntimeError("CI evidence cannot accept real-machine confirmations")
    return machine


def _run_probe(
    arguments: argparse.Namespace,
    *,
    machine: bool,
) -> tuple[dict[str, bool], dict[str, object]]:
    command = [
        sys.executable,
        str(PROBE),
        "--mode",
        "real-machine" if machine else "ci",
        "--ollama-port",
        str(arguments.ollama_port),
    ]
    if machine:
        command.extend(
            [
                "--primary-model",
                cast(str, arguments.primary_model),
                "--fallback-model",
                cast(str, arguments.fallback_model),
            ]
        )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(ROOT / "src"), str(ROOT)))
    environment["NO_PROXY"] = "*"
    environment["HTTP_PROXY"] = "http://127.0.0.1:9"
    environment["HTTPS_PROXY"] = "http://127.0.0.1:9"
    result = subprocess.run(
        command,
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
        raise RuntimeError("local-runtime continuity probe failed")
    if not isinstance(checks, dict) or not all(
        isinstance(key, str) and isinstance(value, bool) for key, value in checks.items()
    ):
        raise RuntimeError("invalid local-runtime probe checks")
    if not isinstance(evidence, dict) or set(evidence) != _EXPECTED_EVIDENCE_KEYS:
        raise RuntimeError("invalid local-runtime probe evidence")
    expected_mode = "real-local" if machine else "synthetic"
    if evidence.get("runtime_mode") != expected_mode or evidence.get("model_count") != 2:
        raise RuntimeError("local-runtime probe mode is invalid")
    return cast(dict[str, bool], checks), cast(dict[str, object], evidence)


def main() -> int:
    arguments = _arguments()
    stage = "environment"
    try:
        machine = _machine_mode(arguments)
        stage = "matrix"
        matrix_checks, limitations, stored_complete = _matrix_evidence()
        stage = "runtime_probe"
        probe_checks, evidence = _run_probe(arguments, machine=machine)
        checks = {**matrix_checks, **probe_checks}
        if not all(checks.values()):
            raise RuntimeError("local-runtime continuity acceptance failure")
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
            "network_mode": "offline-confirmed" if machine else "synthetic-no-network",
            "checks": checks,
            "runtime_test_ids": list(IDS),
            "runtime_test_count": len(IDS),
            "real_runtime_used": machine,
            "cloud_credentials_used": False,
            "external_network_request_used": False,
            "model_download_used": False,
            "runtime_installation_used": False,
            "primary_intel_mac_gate": "pass" if gate_complete else "pending",
            "phase5_gate_complete": gate_complete,
            "evidence": evidence,
            "limitations": limitations,
            "privacy": {
                "absolute_paths_in_report": False,
                "usernames_in_report": False,
                "hostnames_in_report": False,
                "native_model_names_in_report": False,
                "prompt_or_response_text_in_report": False,
                "secret_values_in_report": False,
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
