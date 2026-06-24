from __future__ import annotations

import subprocess


def test_strict_mypy_diagnostics_are_empty() -> None:
    result = subprocess.run(
        ["mypy", "src", "tests"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
