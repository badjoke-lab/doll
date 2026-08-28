"""Acceptance tests for IMP-101 primary Intel Mac repeatability evidence."""

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
    / "IMP-101-primary-intel-mac-local-runtime-repeatability-variance.json"
)
MEASURED_SHA = "a861e4bfd85214c6337bb188c3318e90846f5ebf"
SOURCE_HASHES = [
    "8b8f7f081d43f87491436e7cc0764d64e834f5629f5914e313537593d14a47b2",
    "3ea6d716fcc4bdd151d317a258960620c09aaa6d207ed55c623478ead8598d36",
    "1f38aa7a186b824b119f5f2a87dd9e191638017a7bcc2d55d3f95ad014b7c547",
]


def test_imp_101_primary_intel_mac_repeatability_evidence_passes_validator() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_imp_100_runtime_repeatability_measurement.py",
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
        "measurement_scope": "doll-local-runtime-single-model-repeatability",
        "phase6_gate_complete": False,
        "real_machine_repeatability_accepted": False,
        "repeatability_variance_release_requirement_defined": False,
        "result": "pass",
        "session_count": 3,
        "validated_commit_sha": MEASURED_SHA,
    }


def test_imp_101_committed_repeatability_values_remain_exact() -> None:
    payload = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    sessions = payload["sessions"]
    variance = payload["variance"]

    assert [session["source_sha256"] for session in sessions] == SOURCE_HASHES
    assert payload["identity"]["runtime_version"] == "0.33.1"
    assert payload["identity"]["provider_reported_installed_size_bytes"] == 986_061_892
    assert [session["maximum_sampled_runtime_process_tree_rss_bytes"] for session in sessions] == [
        1_202_470_912,
        1_203_814_400,
        1_137_139_712,
    ]
    assert [session["doll_process_peak_rss_bytes"] for session in sessions] == [
        34_045_952,
        35_110_912,
        34_877_440,
    ]
    assert [session["generation_duration_values_ns"] for session in sessions] == [
        [10_589_242_907, 388_068_715, 389_179_518],
        [268_770_737, 206_806_131, 153_366_166],
        [855_706_395, 178_651_404, 205_712_268],
    ]
    assert variance["maximum_sampled_runtime_process_tree_rss_bytes"]["spread"] == 66_674_688
    assert variance["doll_process_peak_rss_bytes"]["spread"] == 1_064_960
    assert variance["generation_duration_by_position_ns"][0]["spread"] == 10_320_472_170
    assert payload["real_machine_repeatability_collected"] is True
    assert payload["real_machine_repeatability_accepted"] is False
    assert not any(payload["claims"].values())
    assert not any(payload["privacy"].values())
