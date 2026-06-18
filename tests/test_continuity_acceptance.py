from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/run_imp_012_continuity_acceptance.py")


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path.cwd() / "src")
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def test_imp_012_continuity_acceptance_passes() -> None:
    result = _run("--commit-sha", _head(), "--evidence-level", "ci")
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["result"] == "pass"
    assert payload["test_id"] == "IMP-012-CONTINUITY-ACCEPTANCE"
    assert payload["model_runtime_used"] is False
    assert payload["cloud_credentials_used"] is False
    assert all(payload["checks"].values())
    assert all(value is False for value in payload["privacy"].values())


def test_imp_012_failure_report_is_bounded() -> None:
    result = _run(
        "--commit-sha",
        "0123456789abcdef0123456789abcdef01234567",
        "--evidence-level",
        "ci",
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert set(payload) == {
        "commit_sha",
        "completed_at",
        "error_class",
        "result",
        "test_id",
    }
    assert payload["result"] == "fail"
