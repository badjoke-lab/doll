from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs" / "testing" / "phase-6-shutdown-escape-matrix.json"
RUNNER = ROOT / "scripts" / "run_imp_058_shutdown_escape.py"
INSPECTOR = ROOT / "src" / "doll" / "shutdown_escape_inspector.py"


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(ROOT / "src"), str(ROOT)))
    return subprocess.run(
        [sys.executable, str(RUNNER), "--commit-sha", _head(), *arguments],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_imp_058_matrix_keeps_port_015_at_ci_pass() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    assert matrix["schema_version"] == 1
    assert matrix["phase"] == "6"
    assert matrix["implementation"] == "IMP-058"
    assert matrix["shutdown_escape_gate_complete"] is False
    assert matrix["accepted_real_machine_result"] is None
    assert matrix["portability_tests"] == [
        {
            "id": "PORT-015",
            "status": "ci-pass",
            "description": (
                "A deterministic verified shutdown escape bundle remains inspectable without a "
                "model, network, preferred UI, cloud credential, running doll service, or import "
                "of the doll package."
            ),
            "pytest_files": [
                "tests/test_shutdown_escape.py",
                "tests/test_shutdown_escape_acceptance.py",
                "tests/test_shutdown_escape_coverage.py",
                "tests/test_shutdown_escape_platform_coverage.py",
            ],
            "passed_evidence_levels": ["ci"],
            "required_evidence_levels": ["ci", "real-machine"],
        }
    ]
    gate = matrix["real_machine_gate"]
    assert gate == {
        "required": True,
        "status": "pending",
        "platform": "Darwin",
        "architectures": ["x86_64", "amd64"],
        "minimum_local_models": 0,
        "network_mode": "offline-confirmed",
        "commit_sha": None,
        "completed_at": None,
    }


def test_standalone_inspector_imports_only_standard_library() -> None:
    tree = ast.parse(INSPECTOR.read_text(encoding="utf-8"), filename=str(INSPECTOR))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module.split(".", 1)[0])
    assert imports
    assert "doll" not in imports
    assert imports <= sys.stdlib_module_names


def test_imp_058_ci_runner_passes_without_model_network_or_service() -> None:
    result = _run()
    payload = cast(dict[str, Any], json.loads(result.stdout))

    assert result.returncode == 0, result.stdout
    assert payload["test_id"] == "IMP-058-SHUTDOWN-ESCAPE"
    assert payload["result"] == "pass"
    assert payload["commit_sha"] == _head()
    assert payload["evidence_level"] == "ci"
    assert payload["network_mode"] == "synthetic-no-network"
    assert payload["primary_intel_mac_gate"] == "pending"
    assert payload["shutdown_escape_gate_complete"] is False
    assert payload["phase6_gate_complete"] is False
    assert payload["stable_anti_lock_in_claim"] is False
    assert payload["real_machine_used"] is False
    assert payload["real_runtime_used"] is False
    assert payload["model_execution_used"] is False
    assert payload["cloud_credentials_used"] is False
    assert payload["external_network_request_used"] is False
    assert payload["preferred_interface_required"] is False
    assert payload["doll_service_required"] is False
    assert payload["portability_test_ids"] == ["PORT-015"]
    assert payload["portability_test_count"] == 1
    assert payload["checks"] and all(payload["checks"].values())
    assert payload["privacy"] and not any(payload["privacy"].values())
    evidence = payload["evidence"]
    assert evidence["format"] == "doll-shutdown-escape"
    assert evidence["format_version"] == 1
    assert evidence["runtime_mode"] == "synthetic"
    assert evidence["source_workspace_removed"] is True
    assert evidence["generic_conversation_export"] is True
    assert evidence["resume_bundle_count"] == 1
    assert evidence["omitted_secret_total"] == 1


def test_imp_058_ci_runner_rejects_machine_confirmations() -> None:
    result = _run("--offline-confirmed", "--local-only-confirmed")
    payload = json.loads(result.stdout)

    assert result.returncode == 1
    assert payload["result"] == "fail"
    assert payload["error_stage"] == "environment"
    assert payload["error_class"] == "RuntimeError"
    assert payload["phase6_gate_complete"] is False
    assert payload["stable_anti_lock_in_claim"] is False
