"""Acceptance tests for IMP-099 primary Intel Mac runtime/model evidence."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "docs"
    / "testing"
    / "results"
    / "IMP-099-primary-intel-mac-local-runtime-resource-measurement.json"
)
MEASURED_SHA = "7e99fadbf0e9d6c4ed9c5f200de9be8b79ce1b6c"


def test_imp_099_primary_intel_mac_runtime_resource_evidence_passes_validator() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_imp_098_local_runtime_resource_measurement.py",
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
        "full_lite_performance_thresholds_defined": False,
        "lite_v1_complete": False,
        "manual_privacy_review_required": True,
        "measurement_scope": "doll-local-runtime-single-model",
        "phase6_gate_complete": False,
        "real_machine_measurement_accepted": False,
        "repeat_count": 3,
        "result": "pass",
        "validated_commit_sha": MEASURED_SHA,
    }


def test_imp_099_committed_measurement_values_remain_exact() -> None:
    payload = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    observation = payload["observation"]

    assert observation["model"]["provider_reported_installed_size_bytes"] == 986_061_892
    assert observation["maximum_sampled_runtime_process_tree_rss_bytes"] == 1_252_057_088
    assert observation["doll_process_rss"]["peak_bytes"] == 36_093_952
    assert observation["generation_duration"]["values_ns"] == [
        6_763_389_867,
        129_910_556,
        147_618_618,
    ]
    assert payload["real_machine_measurement_collected"] is True
    assert payload["real_machine_measurement_accepted"] is False
    assert not any(payload["claims"].values())
    assert not any(payload["privacy"].values())
