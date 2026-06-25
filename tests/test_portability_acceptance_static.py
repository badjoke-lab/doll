from __future__ import annotations

import ast
import json
from pathlib import Path

MATRIX = Path("docs/testing/phase-4a-portability-matrix.json")
INSPECTOR = Path("scripts/imp_037_export_inspector.py")


def test_phase_4a_matrix_maps_port_004_through_port_012() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    entries = matrix["portability_tests"]
    result_path = Path(matrix["accepted_real_machine_result"])
    result = json.loads(result_path.read_text(encoding="utf-8"))

    assert matrix["schema_version"] == 1
    assert matrix["phase"] == "4A"
    assert matrix["phase4a_gate_complete"] is True
    assert result_path == Path("docs/testing/results/IMP-037-primary-intel-mac-2026-06-25.json")
    assert [item["id"] for item in entries] == [f"PORT-{number:03d}" for number in range(4, 13)]
    assert all(item["status"] == "pass" for item in entries)
    assert all(item["pytest_files"] for item in entries)
    assert entries[1]["evidence_levels"] == [
        "integration",
        "fresh_process",
        "primary_real_machine",
    ]

    gate = matrix["real_machine_gate"]
    assert gate == {
        "required": True,
        "status": "pass",
        "platform": "Darwin",
        "architectures": ["x86_64", "amd64"],
        "network_mode": "offline-confirmed",
        "commit_sha": "839a4ca7a37753fadf81c3e8e79f140e6d66bc03",
        "completed_at": "2026-06-25T14:30:11.994929Z",
    }
    assert result["result"] == "pass"
    assert result["evidence_level"] == "real-machine"
    assert result["operating_system"] == "Darwin"
    assert result["architecture"] == "x86_64"
    assert result["network_mode"] == "offline-confirmed"
    assert result["commit_sha"] == gate["commit_sha"]
    assert result["completed_at"] == gate["completed_at"]
    assert result["primary_intel_mac_gate"] == "pass"
    assert result["phase4a_gate_complete"] is True
    assert result["stable_anti_lock_in_claim"] is False
    assert all(result["checks"].values())


def test_export_inspector_has_no_doll_or_third_party_import() -> None:
    tree = ast.parse(INSPECTOR.read_text(encoding="utf-8"), filename=str(INSPECTOR))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.partition(".")[0] for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module.partition(".")[0])

    assert imports.isdisjoint({"doll", "fastapi", "httpx", "pydantic", "typer"})
