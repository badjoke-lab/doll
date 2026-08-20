from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/testing/results/IMP-096-primary-intel-mac-lite-client-resource-measurement.json"
MEASURED_SHA = "b57ebe6fb4a7620901b95b49f6743b71ae1026f7"


def test_imp_096_primary_intel_mac_evidence_passes_deterministic_validator() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_imp_096_lite_client_measurement.py",
            str(EVIDENCE),
            "--expected-commit-sha",
            MEASURED_SHA,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert json.loads(completed.stdout) == {
        "evidence_level": "real-machine",
        "lite_v1_complete": False,
        "manual_privacy_review_required": True,
        "measurement_scope": "doll-lite-client-only",
        "performance_thresholds_defined": False,
        "phase6_gate_complete": False,
        "result": "pass",
        "validated_commit_sha": MEASURED_SHA,
    }
