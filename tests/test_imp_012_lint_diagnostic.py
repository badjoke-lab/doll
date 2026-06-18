from __future__ import annotations

import subprocess
import sys


def test_imp_012_format_diagnostic() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "format",
            "--diff",
            "scripts",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
