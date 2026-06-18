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
            "scripts/run_imp_012_continuity_acceptance.py",
            "tests/test_continuity_acceptance.py",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
