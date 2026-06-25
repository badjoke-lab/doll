from __future__ import annotations

import subprocess


def test_imp_037_locked_format_diff_is_empty() -> None:
    result = subprocess.run(
        ["ruff", "format", "--diff", "."],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
