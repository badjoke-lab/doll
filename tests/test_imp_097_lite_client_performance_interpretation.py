"""Acceptance tests for bounded IMP-097 performance interpretation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs" / "testing" / "results"
EVIDENCE = RESULTS / "IMP-096-primary-intel-mac-lite-client-resource-measurement.json"
EXPECTED = RESULTS / "IMP-097-lite-client-performance-interpretation.json"
SCRIPT = ROOT / "scripts/interpret_imp_097_lite_client_performance.py"


def _run(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_imp_097_interpretation_matches_committed_result() -> None:
    completed = _run(EVIDENCE)

    assert completed.returncode == 0, completed.stderr
    actual = json.loads(completed.stdout)
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    assert actual == expected
    assert actual["observed_measurement"] == {
        "process_peak_rss_bytes": 41_291_776,
        "total_duration_ns": 256_372_493,
        "workspace_directory_count": 7,
        "workspace_file_count": 2,
        "workspace_total_bytes": 86_369,
    }
    claims = actual["claims"]
    assert claims["bounded_client_workload_observed_on_primary_intel_mac"] is True
    assert claims["client_only_evidence_interpretation_complete"] is True
    assert claims["full_lite_performance_thresholds_defined"] is False
    assert claims["lite_performance_gate_complete"] is False
    assert claims["phase6_gate_complete"] is False
    assert claims["lite_v1_complete"] is False


def test_imp_097_rejects_source_that_invents_thresholds(tmp_path: Path) -> None:
    payload = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    payload["performance_thresholds_defined"] = True
    tampered = tmp_path / "tampered-evidence.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")

    completed = _run(tampered)

    assert completed.returncode == 2
    failure = json.loads(completed.stdout)
    assert failure["result"] == "fail"
    assert failure["error_class"] == "Imp096EvidenceValidationError"
    assert "performance_thresholds_defined" in failure["message"]
