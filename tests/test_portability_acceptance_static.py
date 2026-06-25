from __future__ import annotations

import ast
import json
from pathlib import Path

MATRIX = Path("docs/testing/phase-4a-portability-matrix.json")
INSPECTOR = Path("scripts/imp_037_export_inspector.py")


def test_phase_4a_matrix_maps_port_004_through_port_012() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    entries = matrix["portability_tests"]

    assert matrix["schema_version"] == 1
    assert matrix["phase"] == "4A"
    assert matrix["phase4a_gate_complete"] is False
    assert matrix["accepted_real_machine_result"] is None
    assert [item["id"] for item in entries] == [f"PORT-{number:03d}" for number in range(4, 13)]
    assert all(item["status"] == "pass" for item in entries)
    assert all(item["pytest_files"] for item in entries)
    assert matrix["real_machine_gate"]["status"] == "pending"
    assert matrix["real_machine_gate"]["platform"] == "Darwin"
    assert matrix["real_machine_gate"]["architectures"] == ["x86_64", "amd64"]


def test_export_inspector_has_no_doll_or_third_party_import() -> None:
    tree = ast.parse(INSPECTOR.read_text(encoding="utf-8"), filename=str(INSPECTOR))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.partition(".")[0] for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module.partition(".")[0])

    assert imports.isdisjoint({"doll", "fastapi", "httpx", "pydantic", "typer"})
