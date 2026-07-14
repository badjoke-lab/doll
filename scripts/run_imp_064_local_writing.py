"""Run the IMP-064 primary Intel Mac local-writing acceptance."""

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

TEST_ID = "IMP-064-LOCAL-WRITING-PRIMARY"
ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs" / "testing" / "phase-6-daily-use-matrix.json"
PROBE = ROOT / "scripts" / "imp_064_local_writing_probe.py"
SHA = re.compile(r"^[0-9a-f]{40}$")
_EXPECTED_EVIDENCE_KEYS = {
    "runtime_mode",
    "target_adapter_id",
    "workflow_mode_count",
    "completed_workflow_count",
    "source_instruction_count_total",
    "source_character_count_total",
    "prompt_untrusted_counts",
    "prompt_injection_finding_count",
    "secret_redaction_count",
    "target_event_count",
    "target_binding_hash",
    "target_runtime_manifest_hash",
    "target_model_manifest_hash",
    "target_model_id_hash",
    "runtime_request_count",
    "allowed_loopback_socket_attempts",
    "rejected_socket_attempts",
    "authority_record_count",
}
_PRIVACY_KEYS = {
    "absolute_paths_in_report",
    "usernames_in_report",
    "hostnames_in_report",
    "native_model_names_in_report",
    "source_identifiers_in_report",
    "request_text_in_report",
    "source_text_in_report",
    "prompt_or_response_text_in_report",
    "secret_values_in_report",
    "credentials_in_report",
    "private_fixture_content_in_report",
}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--evidence-level", choices=("ci", "real-machine"), default="ci")
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


def _has_test(relative: str) -> bool:
    path = ROOT / relative
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
        for node in tree.body
    )


def _accepted_result(workflow: dict[str, Any], gate: dict[str, Any]) -> bool:
    if gate.get("status") == "pending":
        if workflow.get("status") != "ci-pass":
            raise RuntimeError("pending writing gate must remain ci-pass")
        if workflow.get("accepted_real_machine_result") is not None:
            raise RuntimeError("pending writing gate cannot name accepted evidence")
        if gate.get("commit_sha") is not None or gate.get("completed_at") is not None:
            raise RuntimeError("pending writing gate cannot bind machine evidence")
        return False
    if gate.get("status") != "pass" or workflow.get("status") != "pass":
        raise RuntimeError("invalid completed writing gate")
    relative = workflow.get("accepted_real_machine_result")
    if not isinstance(relative, str):
        raise RuntimeError("accepted writing result is missing")
    result_path = ROOT / relative
    if not result_path.is_file():
        raise RuntimeError("accepted writing result file is missing")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    checks = result.get("checks") if isinstance(result, dict) else None
    privacy = result.get("privacy") if isinstance(result, dict) else None
    if (
        not isinstance(checks, dict)
        or not checks
        or not all(value is True for value in checks.values())
        or not isinstance(privacy, dict)
        or set(privacy) != _PRIVACY_KEYS
        or any(privacy.values())
    ):
        raise RuntimeError("accepted writing result checks are invalid")
    expected = {
        "test_id": TEST_ID,
        "result": "pass",
        "evidence_level": "real-machine",
        "operating_system": gate.get("platform"),
        "commit_sha": gate.get("commit_sha"),
        "completed_at": gate.get("completed_at"),
        "network_mode": gate.get("network_mode"),
        "writing_workflow_real_machine_gate": "pass",
        "local_writing_workflow_complete": True,
        "phase6_gate_complete": False,
        "stable_anti_lock_in_claim": False,
    }
    if any(result.get(key) != value for key, value in expected.items()):
        raise RuntimeError("accepted writing result does not match matrix")
    architectures = gate.get("architectures")
    if not isinstance(architectures, list) or result.get("architecture") not in architectures:
        raise RuntimeError("accepted writing architecture is invalid")
    evidence = result.get("evidence")
    if not isinstance(evidence, dict) or set(evidence) != _EXPECTED_EVIDENCE_KEYS:
        raise RuntimeError("accepted writing evidence shape is invalid")
    return True


def _matrix_evidence() -> tuple[dict[str, bool], list[str], bool]:
    matrix: dict[str, Any] = json.loads(MATRIX.read_text(encoding="utf-8"))
    workflow = matrix.get("local_writing_workflow")
    if not isinstance(workflow, dict):
        raise RuntimeError("local writing workflow is missing")
    gate = workflow.get("real_machine_gate")
    limitations = workflow.get("limitations")
    if not isinstance(gate, dict) or gate.get("required") is not True:
        raise RuntimeError("local writing machine gate is missing")
    if gate.get("platform") != "Darwin":
        raise RuntimeError("local writing platform is invalid")
    if gate.get("architectures") != ["x86_64", "amd64"]:
        raise RuntimeError("local writing architectures are invalid")
    if gate.get("network_mode") != "offline-confirmed":
        raise RuntimeError("local writing network mode is invalid")
    if gate.get("minimum_local_models") != 1:
        raise RuntimeError("local writing model requirement is invalid")
    if not isinstance(limitations, list) or not all(
        isinstance(value, str) for value in limitations
    ):
        raise RuntimeError("local writing limitations are invalid")
    status = gate.get("status")
    if status not in {"pending", "pass"}:
        raise RuntimeError("local writing gate status is invalid")
    expected_status = "pass" if status == "pass" else "ci-pass"
    expected_levels = ["ci", "real-machine"] if status == "pass" else ["ci"]
    files = workflow.get("pytest_files")
    if (
        not isinstance(files, list)
        or not files
        or not all(isinstance(value, str) and _has_test(value) for value in files)
    ):
        raise RuntimeError("local writing test evidence is invalid")
    implementation_doc = workflow.get("implementation_doc")
    runbook = workflow.get("runbook")
    stored_complete = _accepted_result(workflow, gate)
    checks = {
        "matrix_schema_valid": matrix.get("schema_version") == 1,
        "phase_identifier_valid": matrix.get("phase") == "6",
        "imp063_workflow_identified": workflow.get("implementation") == "IMP-063",
        "imp064_acceptance_identified": workflow.get("acceptance_implementation") == "IMP-064",
        "workflow_status_matches_machine_gate": workflow.get("status") == expected_status,
        "passed_evidence_levels_match_gate": workflow.get("passed_evidence_levels")
        == expected_levels,
        "required_evidence_levels_valid": workflow.get("required_evidence_levels")
        == ["ci", "real-machine"],
        "machine_gate_declared": status in {"pending", "pass"},
        "stored_machine_evidence_valid": status != "pass" or stored_complete,
        "implementation_document_present": isinstance(implementation_doc, str)
        and (ROOT / implementation_doc).is_file(),
        "private_machine_runbook_present": isinstance(runbook, str) and (ROOT / runbook).is_file(),
        "phase6_nonclaim_preserved": workflow.get("phase6_gate_complete") is False,
        "stable_anti_lock_in_nonclaim_preserved": workflow.get("stable_anti_lock_in_claim")
        is False,
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
    machine = cast(str, arguments.evidence_level) == "real-machine"
    if machine:
        if (
            platform.system() != "Darwin"
            or platform.machine().lower() not in {"x86_64", "amd64"}
            or not arguments.offline_confirmed
            or not arguments.local_only_confirmed
            or not isinstance(arguments.model, str)
            or not arguments.model
        ):
            raise RuntimeError("machine evidence rejected")
    elif any(
        value
        for value in (
            arguments.offline_confirmed,
            arguments.local_only_confirmed,
            arguments.model,
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
        command.extend(["--model", cast(str, arguments.model)])
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
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("local writing probe output is invalid") from exc
    checks = payload.get("checks")
    evidence = payload.get("evidence")
    if result.returncode or payload.get("result") != "pass":
        raise RuntimeError("local writing probe failed")
    if not isinstance(checks, dict) or not all(
        isinstance(key, str) and isinstance(value, bool) for key, value in checks.items()
    ):
        raise RuntimeError("invalid local writing probe checks")
    if not isinstance(evidence, dict) or set(evidence) != _EXPECTED_EVIDENCE_KEYS:
        raise RuntimeError("invalid local writing probe evidence")
    expected_mode = "real-local" if machine else "synthetic"
    if evidence.get("runtime_mode") != expected_mode:
        raise RuntimeError("local writing runtime mode is invalid")
    return cast(dict[str, bool], checks), cast(dict[str, object], evidence)


def main() -> int:
    arguments = _arguments()
    started_at = _now()
    stage = "environment"
    try:
        machine = _machine_mode(arguments)
        stage = "matrix"
        matrix_checks, limitations, stored_complete = _matrix_evidence()
        stage = "writing_probe"
        probe_checks, evidence = _run_probe(arguments, machine=machine)
        checks = {**matrix_checks, **probe_checks}
        if not all(checks.values()):
            raise RuntimeError("local writing acceptance failed")
        gate_complete = machine or stored_complete
        payload: dict[str, object] = {
            "test_id": TEST_ID,
            "specification_version": "0.2",
            "commit_sha": arguments.commit_sha,
            "result": "pass",
            "started_at": started_at,
            "completed_at": _now(),
            "evidence_level": arguments.evidence_level,
            "operating_system": platform.system(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "network_mode": "offline-confirmed" if machine else "synthetic-no-network",
            "checks": checks,
            "real_runtime_used": machine,
            "cloud_credentials_used": False,
            "external_network_request_used": False,
            "model_download_used": False,
            "runtime_installation_used": False,
            "process_launch_used": False,
            "tool_execution_used": False,
            "capability_execution_used": False,
            "preferred_interface_required": False,
            "writing_workflow_real_machine_gate": "pass" if gate_complete else "pending",
            "local_writing_workflow_complete": gate_complete,
            "phase6_gate_complete": False,
            "stable_anti_lock_in_claim": False,
            "evidence": evidence,
            "limitations": limitations,
            "privacy": {
                "absolute_paths_in_report": False,
                "usernames_in_report": False,
                "hostnames_in_report": False,
                "native_model_names_in_report": False,
                "source_identifiers_in_report": False,
                "request_text_in_report": False,
                "source_text_in_report": False,
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
            "stage": stage,
            "error_class": type(exc).__name__,
        }
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 2
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
