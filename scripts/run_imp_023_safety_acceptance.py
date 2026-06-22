"""Run the model-independent IMP-023 Phase 3 safety acceptance probe."""

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

TEST_ID = "IMP-023-SAFETY-ACCEPTANCE"
SPECIFICATION_VERSION = "0.1"
_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_ROOT = Path(__file__).resolve().parents[1]
_MATRIX = _ROOT / "docs" / "testing" / "phase-3-safety-matrix.json"
_FRESH_PROBE = _ROOT / "scripts" / "imp_023_fresh_probe.py"
_REQUIRED_IDS = tuple(f"SEC-{index:03d}" for index in range(1, 24))


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument(
        "--evidence-level",
        choices=("ci", "real-machine"),
        default="ci",
    )
    parser.add_argument("--offline-confirmed", action="store_true")
    return parser.parse_args()


def _head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def _check_environment(arguments: argparse.Namespace) -> None:
    if not _COMMIT_PATTERN.fullmatch(arguments.commit_sha):
        raise RuntimeError("invalid commit SHA")
    if _head() != arguments.commit_sha:
        raise RuntimeError("checked-out commit mismatch")
    if arguments.evidence_level != "real-machine":
        return
    if platform.system() != "Darwin":
        raise RuntimeError("real-machine evidence requires macOS")
    if platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("real-machine evidence requires Intel")
    if not arguments.offline_confirmed:
        raise RuntimeError("offline confirmation required")


def _load_matrix() -> dict[str, object]:
    payload = json.loads(_MATRIX.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("safety matrix must be an object")
    return payload


def _contains_tests(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
        for node in tree.body
    )


def _validate_matrix(matrix: dict[str, object]) -> dict[str, bool]:
    entries = matrix.get("security_tests")
    if not isinstance(entries, list):
        raise RuntimeError("safety matrix entries are missing")
    ids = tuple(entry.get("id") for entry in entries if isinstance(entry, dict))
    if ids != _REQUIRED_IDS:
        raise RuntimeError("safety matrix must cover SEC-001 through SEC-023 exactly once")

    executable = 0
    not_applicable = 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise RuntimeError("safety matrix entry is invalid")
        status = entry.get("status")
        note = entry.get("scope_note")
        files = entry.get("pytest_files")
        if not isinstance(note, str) or not note.strip():
            raise RuntimeError("safety matrix scope note is missing")
        if not isinstance(files, list) or not all(
            isinstance(item, str) for item in files
        ):
            raise RuntimeError("safety matrix pytest files are invalid")
        if status == "not_applicable":
            not_applicable += 1
            if files:
                raise RuntimeError(
                    "not-applicable matrix entry must not claim pytest evidence"
                )
            continue
        if status != "pass" or not files:
            raise RuntimeError("blocking safety entry lacks executable evidence")
        for relative in files:
            path = _ROOT / relative
            if not path.is_file() or not _contains_tests(path):
                raise RuntimeError(
                    "safety matrix references missing executable tests"
                )
        executable += 1

    gate = matrix.get("real_machine_gate")
    if not isinstance(gate, dict) or gate.get("status") != "pending":
        raise RuntimeError("real-machine gate must remain pending in repository evidence")
    return {
        "matrix_schema_valid": matrix.get("schema_version") == 1,
        "all_security_ids_mapped": ids == _REQUIRED_IDS,
        "all_implemented_entries_executable": executable == 22,
        "only_unimplemented_listener_not_applicable": not_applicable == 1,
        "real_machine_gate_declared": gate.get("required") is True,
    }


def _fresh_process_probe() -> dict[str, bool]:
    with tempfile.TemporaryDirectory(prefix="doll-imp023-") as temporary:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(_ROOT / "src")
        completed = subprocess.run(
            [sys.executable, str(_FRESH_PROBE), temporary],
            cwd=_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
    payload = json.loads(completed.stdout)
    if completed.returncode != 0 or payload.get("result") != "pass":
        raise RuntimeError("fresh-process safety probe failed")
    checks = payload.get("checks")
    if not isinstance(checks, dict):
        raise RuntimeError("fresh-process safety probe returned invalid evidence")
    if not all(isinstance(key, str) for key in checks):
        raise RuntimeError("fresh-process safety check names are invalid")
    if not all(isinstance(value, bool) for value in checks.values()):
        raise RuntimeError("fresh-process safety check values are invalid")
    return checks


def _build_report(
    arguments: argparse.Namespace,
    matrix: dict[str, object],
    checks: dict[str, bool],
    started_at: str,
) -> dict[str, object]:
    if not all(checks.values()):
        raise RuntimeError("one or more safety acceptance checks failed")
    real_machine = arguments.evidence_level == "real-machine"
    limitations = matrix.get("limitations")
    if not isinstance(limitations, list) or not all(
        isinstance(item, str) for item in limitations
    ):
        raise RuntimeError("safety matrix limitations are invalid")
    return {
        "test_id": TEST_ID,
        "specification_version": SPECIFICATION_VERSION,
        "commit_sha": arguments.commit_sha,
        "result": "pass",
        "started_at": started_at,
        "completed_at": _utc_now(),
        "evidence_level": arguments.evidence_level,
        "operating_system": platform.system(),
        "architecture": platform.machine(),
        "network_mode": (
            "offline-confirmed" if real_machine else "no-network-path-in-probe"
        ),
        "checks": checks,
        "security_test_count": 23,
        "executable_security_test_count": 22,
        "not_applicable_security_test_ids": ["SEC-007"],
        "model_runtime_used": False,
        "cloud_credentials_used": False,
        "live_side_effect_used": False,
        "primary_intel_mac_gate": "pass" if real_machine else "pending",
        "phase3_gate_complete": real_machine,
        "limitations": limitations,
        "privacy": {
            "absolute_paths_in_report": False,
            "usernames_in_report": False,
            "hostnames_in_report": False,
            "secret_values_in_report": False,
            "private_fixture_content_in_report": False,
        },
    }


def main() -> int:
    arguments = _arguments()
    started_at = _utc_now()
    error_stage = "environment"
    try:
        _check_environment(arguments)
        error_stage = "matrix"
        matrix = _load_matrix()
        matrix_checks = _validate_matrix(matrix)
        error_stage = "fresh_process"
        fresh_checks = _fresh_process_probe()
        error_stage = "report"
        report = _build_report(
            arguments,
            matrix,
            {**matrix_checks, **fresh_checks},
            started_at,
        )
    except BaseException as exc:
        print(
            json.dumps(
                {
                    "test_id": TEST_ID,
                    "commit_sha": arguments.commit_sha,
                    "result": "fail",
                    "completed_at": _utc_now(),
                    "error_stage": error_stage,
                    "error_class": type(exc).__name__,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
