"""Separate synthetic CI evidence from final real-machine satisfaction."""

from __future__ import annotations

from pathlib import Path

TARGET = Path("scripts/run_imp_057_local_portability.py")

OLD = '''def _matrix_evidence() -> tuple[dict[str, bool], list[str], bool]:
    matrix: dict[str, Any] = json.loads(MATRIX.read_text(encoding="utf-8"))
    entries = matrix.get("portability_tests")
    if not isinstance(entries, list):
        raise RuntimeError("invalid local-portability matrix")
    ids = tuple(item.get("id") for item in entries if isinstance(item, dict))
    if ids != IDS:
        raise RuntimeError("invalid local-portability identifiers")
    for item in entries:
        if not isinstance(item, dict) or item.get("status") != "pass":
            raise RuntimeError("missing local-portability evidence")
        files = item.get("pytest_files")
        levels = item.get("evidence_levels")
        if (
            not isinstance(files, list)
            or not files
            or not all(isinstance(value, str) and _has_test(value) for value in files)
        ):
            raise RuntimeError("invalid local-portability test evidence")
        if levels != ["ci", "real-machine"]:
            raise RuntimeError("invalid local-portability evidence levels")
    gate = matrix.get("real_machine_gate")
    limitations = matrix.get("limitations")
    if not isinstance(gate, dict) or gate.get("required") is not True:
        raise RuntimeError("missing primary-machine gate")
    if gate.get("minimum_local_models") != 1:
        raise RuntimeError("invalid minimum local-model requirement")
    if not isinstance(limitations, list) or not all(
        isinstance(value, str) for value in limitations
    ):
        raise RuntimeError("invalid limitations")
    stored_complete = _accepted_machine_result(matrix, gate)
    checks = {
        "matrix_schema_valid": matrix.get("schema_version") == 1,
        "phase_identifier_valid": matrix.get("phase") == "6",
        "all_local_portability_ids_mapped": ids == IDS,
        "all_local_portability_entries_executable": len(entries) == len(IDS),
        "primary_machine_gate_declared": gate.get("status") in {"pending", "pass"},
        "stored_machine_evidence_valid": gate.get("status") != "pass" or stored_complete,
        "alternate_inspector_excludes_capture_runtime": _inspector_excludes_capture_runtime(),
    }
    return checks, cast(list[str], limitations), stored_complete
'''

NEW = '''def _matrix_evidence() -> tuple[dict[str, bool], list[str], bool]:
    matrix: dict[str, Any] = json.loads(MATRIX.read_text(encoding="utf-8"))
    entries = matrix.get("portability_tests")
    if not isinstance(entries, list):
        raise RuntimeError("invalid local-portability matrix")
    ids = tuple(item.get("id") for item in entries if isinstance(item, dict))
    if ids != IDS:
        raise RuntimeError("invalid local-portability identifiers")
    gate = matrix.get("real_machine_gate")
    limitations = matrix.get("limitations")
    if not isinstance(gate, dict) or gate.get("required") is not True:
        raise RuntimeError("missing primary-machine gate")
    gate_status = gate.get("status")
    if gate_status not in {"pending", "pass"}:
        raise RuntimeError("invalid primary-machine gate status")
    if gate.get("minimum_local_models") != 1:
        raise RuntimeError("invalid minimum local-model requirement")
    if not isinstance(limitations, list) or not all(
        isinstance(value, str) for value in limitations
    ):
        raise RuntimeError("invalid limitations")

    expected_entry_status = "pass" if gate_status == "pass" else "ci-pass"
    expected_passed_levels = ["ci", "real-machine"] if gate_status == "pass" else ["ci"]
    for item in entries:
        if not isinstance(item, dict) or item.get("status") != expected_entry_status:
            raise RuntimeError("local-portability evidence status does not match gate")
        files = item.get("pytest_files")
        if (
            not isinstance(files, list)
            or not files
            or not all(isinstance(value, str) and _has_test(value) for value in files)
        ):
            raise RuntimeError("invalid local-portability test evidence")
        if item.get("passed_evidence_levels") != expected_passed_levels:
            raise RuntimeError("invalid passed local-portability evidence levels")
        if item.get("required_evidence_levels") != ["ci", "real-machine"]:
            raise RuntimeError("invalid required local-portability evidence levels")

    stored_complete = _accepted_machine_result(matrix, gate)
    checks = {
        "matrix_schema_valid": matrix.get("schema_version") == 1,
        "phase_identifier_valid": matrix.get("phase") == "6",
        "all_local_portability_ids_mapped": ids == IDS,
        "all_local_portability_entries_executable": len(entries) == len(IDS),
        "entry_status_matches_machine_gate": all(
            isinstance(item, dict) and item.get("status") == expected_entry_status
            for item in entries
        ),
        "primary_machine_gate_declared": gate_status in {"pending", "pass"},
        "stored_machine_evidence_valid": gate_status != "pass" or stored_complete,
        "alternate_inspector_excludes_capture_runtime": _inspector_excludes_capture_runtime(),
    }
    return checks, cast(list[str], limitations), stored_complete
'''


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    if text.count(OLD) != 1:
        raise RuntimeError("unexpected IMP-057 matrix evidence patch context")
    TARGET.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
