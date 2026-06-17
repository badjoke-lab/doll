from __future__ import annotations

import subprocess
import sys


def test_ruff_diagnostic() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "src", "tests"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
