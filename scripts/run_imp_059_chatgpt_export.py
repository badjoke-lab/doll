"""Run the IMP-059 bounded ChatGPT conversations.json acceptance check."""

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

TEST_ID = "IMP-059-CHATGPT-CONVERSATIONS-JSON"
ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs" / "testing" / "phase-6-chatgpt-history-matrix.json"
PROBE = ROOT / "scripts" / "imp_059_chatgpt_export_probe.py"
ADAPTER = ROOT / "src" / "doll" / "chatgpt_export_import.py"
IDS = ("PORT-014",)
SHA = re.compile(r"^[0-9a-f]{40}$")
_EXPECTED_EVIDENCE_KEYS = {
    "source_environment_class",
    "source_format",
    "source_format_version",
    "source_adapter_id",
    "source_adapter_version",
    "source_root_hash",
    "conversation_count",
    "selected_conversation_count",
    "selected_message_count",
    "source_object_count",
    "published_object_count",
    "duplicate_object_count",
    "quarantine_count",
    "material_loss_count",
    "mapping_report_reference",
    "generic_export_manifest_hash",
    "shutdown_escape_sha256",
    "runtime_mode",
}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit-sha", required=True)
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


def _adapter_excludes_network_and_process_imports() -> bool:
    tree = ast.parse(ADAPTER.read_text(encoding="utf-8"), filename=str(ADAPTER))
    forbidden = {"httpx", "requests", "socket", "subprocess", "urllib"}
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module.split(".", 1)[0])
    return not bool(imports & forbidden)


def _matrix_evidence() -> tuple[dict[str, bool], list[str]]:
    matrix: dict[str, Any] = json.loads(MATRIX.read_text(encoding="utf-8"))
    entries = matrix.get("portability_tests")
    gate = matrix.get("private_manual_gate")
    limitations = matrix.get("limitations")
    if not isinstance(entries, list) or len(entries) != 1:
        raise RuntimeError("invalid ChatGPT history matrix")
    ids = tuple(item.get("id") for item in entries if isinstance(item, dict))
    if ids != IDS:
        raise RuntimeError("invalid ChatGPT portability identifiers")
    item = entries[0]
    if not isinstance(item, dict):
        raise RuntimeError("invalid ChatGPT portability entry")
    if item.get("status") != "ci-pass":
        raise RuntimeError("PORT-014 must remain ci-pass before private manual evidence")
    if item.get("passed_evidence_levels") != ["ci"]:
        raise RuntimeError("invalid passed ChatGPT evidence levels")
    if item.get("required_evidence_levels") != ["ci", "private-manual"]:
        raise RuntimeError("invalid required ChatGPT evidence levels")
    files = item.get("pytest_files")
    if (
        not isinstance(files, list)
        or not files
        or not all(isinstance(value, str) and _has_test(value) for value in files)
    ):
        raise RuntimeError("invalid ChatGPT source-adapter test evidence")
    if not isinstance(gate, dict) or gate.get("required") is not True:
        raise RuntimeError("missing private manual gate")
    if gate.get("status") != "pending":
        raise RuntimeError("private manual gate must remain pending")
    if gate.get("commit_sha") is not None or gate.get("completed_at") is not None:
        raise RuntimeError("pending private gate cannot bind evidence")
    if matrix.get("accepted_private_manual_result") is not None:
        raise RuntimeError("pending private gate cannot name accepted evidence")
    if matrix.get("chatgpt_history_gate_complete") is not False:
        raise RuntimeError("ChatGPT history gate cannot be complete before private evidence")
    if not isinstance(limitations, list) or not all(
        isinstance(value, str) for value in limitations
    ):
        raise RuntimeError("invalid ChatGPT history limitations")
    checks = {
        "matrix_schema_valid": matrix.get("schema_version") == 1,
        "phase_identifier_valid": matrix.get("phase") == "6",
        "implementation_identifier_valid": matrix.get("implementation") == "IMP-059",
        "portability_identifier_mapped": ids == IDS,
        "port014_foundation_complete": matrix.get("port014_foundation_complete") is True,
        "private_manual_gate_pending": gate.get("status") == "pending",
        "chatgpt_history_gate_incomplete": matrix.get("chatgpt_history_gate_complete") is False,
        "adapter_excludes_network_and_process_imports": (
            _adapter_excludes_network_and_process_imports()
        ),
    }
    return checks, cast(list[str], limitations)


def _run_probe() -> tuple[dict[str, bool], dict[str, object]]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(ROOT / "src"), str(ROOT)))
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
        raise RuntimeError("ChatGPT export probe failed")
    if not isinstance(checks, dict) or not all(
        isinstance(key, str) and isinstance(value, bool) for key, value in checks.items()
    ):
        raise RuntimeError("invalid ChatGPT export probe checks")
    if not isinstance(evidence, dict) or set(evidence) != _EXPECTED_EVIDENCE_KEYS:
        raise RuntimeError("invalid ChatGPT export probe evidence")
    if evidence.get("runtime_mode") != "synthetic":
        raise RuntimeError("ChatGPT export probe runtime mode is invalid")
    return cast(dict[str, bool], checks), cast(dict[str, object], evidence)


def main() -> int:
    arguments = _arguments()
    stage = "environment"
    try:
        if not SHA.fullmatch(arguments.commit_sha) or arguments.commit_sha != _head():
            raise RuntimeError("commit mismatch")
        stage = "matrix"
        matrix_checks, limitations = _matrix_evidence()
        stage = "chatgpt_export_probe"
        probe_checks, evidence = _run_probe()
        checks = {**matrix_checks, **probe_checks}
        if not all(checks.values()):
            raise RuntimeError("ChatGPT export acceptance failure")
        payload: dict[str, object] = {
            "test_id": TEST_ID,
            "specification_version": "0.1",
            "commit_sha": arguments.commit_sha,
            "result": "pass",
            "started_at": _now(),
            "completed_at": _now(),
            "evidence_level": "ci",
            "operating_system": platform.system(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "network_mode": "synthetic-no-network",
            "checks": checks,
            "portability_test_ids": list(IDS),
            "portability_test_count": len(IDS),
            "real_machine_used": False,
            "real_runtime_used": False,
            "model_execution_used": False,
            "model_download_used": False,
            "runtime_installation_used": False,
            "cloud_credentials_used": False,
            "external_network_request_used": False,
            "preferred_interface_required": False,
            "private_source_used": False,
            "port014_foundation_complete": True,
            "chatgpt_history_gate_complete": False,
            "phase6_gate_complete": False,
            "stable_anti_lock_in_claim": False,
            "evidence": evidence,
            "limitations": limitations,
            "privacy": {
                "absolute_paths_in_report": False,
                "usernames_in_report": False,
                "hostnames_in_report": False,
                "provider_account_ids_in_report": False,
                "conversation_ids_in_report": False,
                "titles_in_report": False,
                "prompt_or_response_text_in_report": False,
                "native_model_names_in_report": False,
                "secret_values_in_report": False,
                "credentials_in_report": False,
                "private_fixture_content_in_report": False,
            },
        }
        status = 0
    except BaseException as exc:
        payload = {
            "test_id": TEST_ID,
            "commit_sha": arguments.commit_sha,
            "result": "fail",
            "error_stage": stage,
            "error_class": type(exc).__name__,
            "chatgpt_history_gate_complete": False,
            "phase6_gate_complete": False,
            "stable_anti_lock_in_claim": False,
        }
        status = 1
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
