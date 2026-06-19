from __future__ import annotations

import subprocess
import sys


def test_restore_lint_diagnostic() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "src/doll/restore.py",
            "tests/test_restore_decompression_boundary.py",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
