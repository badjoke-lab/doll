from __future__ import annotations

import subprocess
import sys


def test_imp_013_format_diagnostic() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "format",
            "--diff",
            "src/doll/secret_policy.py",
            "tests/test_secret_policy.py",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
