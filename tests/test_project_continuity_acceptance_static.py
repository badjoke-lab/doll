from __future__ import annotations

import ast
import json
from pathlib import Path

MATRIX = Path("docs/testing/phase-4b-project-continuity-matrix.json")
INSPECTOR = Path("scripts/imp_047_bundle_inspector.py")


def test_phase_4b_matrix_maps_proj_001_through_proj_012_with_gate_complete() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    entries = matrix["project_tests"]
    result_path = Path(matrix["accepted_real_machine_result"])
    result = json.loads(result_path.read_text(encoding="utf-8"))

    assert matrix["schema_version"] == 1
    assert matrix["phase"] == "4B"
    assert matrix["phase4b_gate_complete"] is True
    assert result_path == Path("docs/testing/results/IMP-047-primary-intel-mac-2026-06-26.json")
    assert [item["id"] for item in entries] == [f"PROJ-{number:03d}" for number in range(1, 13)]
    assert all(item["status"] == "pass" for item in entries)
    assert all(item["pytest_files"] for item in entries)
    assert entries[0]["evidence_levels"][-1] == "primary_real_machine"
    assert entries[8]["evidence_levels"][-1] == "primary_real_machine"

    gate = matrix["real_machine_gate"]
    assert gate == {
        "required": True,
        "status": "pass",
        "platform": "Darwin",
        "architectures": ["x86_64", "amd64"],
        "network_mode": "offline-confirmed",
        "commit_sha": "ddb58d041e505556910930724d0cf2fd03afe7d3",
        "completed_at": "2026-06-26T12:37:23.396078Z",
    }
    assert result["result"] == "pass"
    assert result["evidence_level"] == "real-machine"
    assert result["operating_system"] == "Darwin"
    assert result["architecture"] == "x86_64"
    assert result["python_version"] == "3.12.13"
    assert result["network_mode"] == "offline-confirmed"
    assert result["commit_sha"] == gate["commit_sha"]
    assert result["completed_at"] == gate["completed_at"]
    assert result["primary_intel_mac_gate"] == "pass"
    assert result["phase4b_gate_complete"] is True
    assert result["project_test_count"] == 12
    assert all(result["checks"].values())
    assert all(value is False for value in result["privacy"].values())


def test_resume_bundle_inspector_has_no_doll_or_third_party_import() -> None:
    tree = ast.parse(INSPECTOR.read_text(encoding="utf-8"), filename=str(INSPECTOR))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.partition(".")[0] for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module.partition(".")[0])

    assert imports.isdisjoint({"doll", "fastapi", "httpx", "pydantic", "typer"})
