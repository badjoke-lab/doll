"""Evaluate and report the IMP-012 continuity acceptance scenario."""

from __future__ import annotations

import argparse
import platform
import tempfile
from pathlib import Path

from imp_012_checks_continuity import evaluate as continuity_checks
from imp_012_checks_state import evaluate as state_checks
from imp_012_common import TEST_ID, utc_now
from imp_012_execution import execute


def run(arguments: argparse.Namespace) -> dict[str, object]:
    started_at = utc_now()
    with tempfile.TemporaryDirectory(prefix="doll-imp-012-") as temporary:
        data = execute(Path(temporary))
        checks = {
            **continuity_checks(data),
            **state_checks(data),
        }
        if not all(checks.values()):
            raise RuntimeError("continuity acceptance failed")
    return {
        "test_id": TEST_ID,
        "result": "pass",
        "commit_sha": arguments.commit_sha,
        "started_at": started_at,
        "completed_at": utc_now(),
        "evidence_level": arguments.evidence_level,
        "operating_system": platform.system(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "network_mode": (
            "disabled-confirmed-by-operator"
            if arguments.offline_confirmed
            else "not-asserted-by-ci"
        ),
        "model_runtime_used": False,
        "cloud_credentials_used": False,
        "checks": checks,
        "limitations": [
            "No model runtime is implemented or tested in Phase 2.",
            "Safety-boundary acceptance remains Phase 3 work.",
            "Windows and Ubuntu evidence remains CI-only beta support.",
        ],
        "privacy": {
            "absolute_paths_in_report": False,
            "username_in_report": False,
            "hostname_in_report": False,
            "sensitive_values_in_report": False,
            "personal_fixtures_in_report": False,
        },
    }
