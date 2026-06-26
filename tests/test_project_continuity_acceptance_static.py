from __future__ import annotations

import ast
import json
from pathlib import Path

MATRIX = Path("docs/testing/phase-4b-project-continuity-matrix.json")
INSPECTOR = Path("scripts/imp_047_bundle_inspector.py")


def test_phase_4b_matrix_maps_proj_001_through_proj_012_with_gate_pending() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    entries = matrix["project_tests"]

    assert matrix["schema_version"] == 1
    assert matrix["phase"] == "4B"
    assert matrix["phase4b_gate_complete"] is False
    assert matrix["accepted_real_machine_result"] is None
    assert [item["id"] for item in entries] == [f"PROJ-{number:03d}" for number in range(1, 13)]
    assert all(item["status"] == "pass" for item in entries)
    assert all(item["pytest_files"] for item in entries)
    assert entries[0]["evidence_levels"][-1] == "primary_real_machine_pending"
    assert entries[8]["evidence_levels"][-1] == "primary_real_machine_pending"
    assert matrix["real_machine_gate"] == {
        "required": True,
        "status": "pending",
        "platform": "Darwin",
        "architectures": ["x86_64", "amd64"],
        "network_mode": "offline-confirmed",
        "commit_sha": None,
        "completed_at": None,
    }


def test_resume_bundle_inspector_has_no_doll_or_third_party_import() -> None:
    tree = ast.parse(INSPECTOR.read_text(encoding="utf-8"), filename=str(INSPECTOR))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.partition(".")[0] for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module.partition(".")[0])

    assert imports.isdisjoint({"doll", "fastapi", "httpx", "pydantic", "typer"})
