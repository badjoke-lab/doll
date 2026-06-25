from __future__ import annotations

import subprocess


def test_imp_037_ruff_diagnostics_are_empty() -> None:
    result = subprocess.run(
        ["ruff", "check", "."],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
