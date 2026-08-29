"""Acceptance tests for IMP-103 primary Intel Mac Lite storage evidence."""

from __future__ import annotations

import hashlib
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
    / "IMP-103-primary-intel-mac-lite-install-storage-measurement.json"
)
MEASURED_SHA = "a323aa0958387dcd746fa9ef9fa95eb519da1e54"
EVIDENCE_SHA256 = "b6378bd247ccf0576da6e474548fe725e8077e1156ba5c6ec0ec727b9301323a"


def test_imp_103_primary_intel_mac_lite_storage_evidence_passes_validator() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_imp_102_lite_install_storage_measurement.py",
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
        "full_install_disk_requirement_defined": False,
        "full_lite_performance_thresholds_defined": False,
        "lite_v1_complete": False,
        "manual_privacy_review_required": True,
        "measurement_scope": "doll-lite-python-install-selected-model-storage",
        "phase6_gate_complete": False,
        "real_machine_measurement_accepted": False,
        "result": "pass",
        "runtime_installation_measured": False,
        "validated_commit_sha": MEASURED_SHA,
    }


def test_imp_103_committed_lite_storage_values_remain_exact() -> None:
    evidence_text = EVIDENCE.read_text(encoding="utf-8")
    canonical_evidence_bytes = evidence_text.encode("utf-8")
    payload = json.loads(evidence_text)
    installation = payload["observation"]["lite_python_installation"]
    tree = installation["tree"]
    model = payload["observation"]["model"]

    # Text-mode reading normalizes a Windows checkout's CRLF back to the
    # repository/upload LF representation before checking the source digest.
    assert hashlib.sha256(canonical_evidence_bytes).hexdigest() == EVIDENCE_SHA256
    assert payload["commit_sha"] == MEASURED_SHA
    assert payload["operating_system"] == "Darwin"
    assert payload["architecture"] == "x86_64"
    assert payload["python_version"] == "3.14.6"
    assert payload["observation"]["uv_version"] == "uv 0.11.21"
    assert payload["observation"]["runtime_version"] == "0.33.2"
    assert installation["profile"] == "lite-python-no-dev-all-extras"
    assert installation["optional_extras"] == ["ocr", "pdf"]
    assert installation["dependency_source_mode"] == "locked-offline-local-cache"
    assert installation["editable_install_used"] is False
    assert installation["dev_dependencies_included"] is False
    assert tree["regular_file_count"] == 2029
    assert tree["directory_count"] == 1135
    assert tree["symlink_count"] == 3
    assert tree["logical_bytes"] == 64_426_153
    assert tree["allocated_bytes"] == 69_378_048
    assert tree["symlink_target_bytes_included"] is False
    assert model["provider_reported_installed_size_bytes"] == 986_061_892
    assert payload["observation"]["runtime_installation"] == {"measured": False}
    assert payload["real_machine_measurement_collected"] is True
    assert payload["real_machine_measurement_accepted"] is False
    assert payload["temporary_installation_cleaned"] is True
    assert all(payload["checks"].values())
    assert not any(payload["claims"].values())
    assert not any(payload["privacy"].values())
