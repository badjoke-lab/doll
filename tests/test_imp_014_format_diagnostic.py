from __future__ import annotations

import subprocess
import sys


def test_imp_014_format_diagnostic() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "format",
            "--diff",
            "src/doll/secret_detection.py",
            "src/doll/diagnostics.py",
            "src/doll/cli.py",
            "tests/test_secret_detection.py",
            "tests/test_diagnostics.py",
            "tests/test_cli_secret_redaction.py",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
