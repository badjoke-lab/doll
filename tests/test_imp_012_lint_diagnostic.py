from __future__ import annotations

import subprocess
import sys


def test_imp_012_lint_diagnostic() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "scripts/imp_012_common.py",
            "scripts/imp_012_fixture.py",
            "scripts/imp_012_scenario.py",
            "scripts/run_imp_012_continuity_acceptance.py",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
