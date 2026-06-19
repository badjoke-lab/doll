import subprocess
import sys


def test_restore_mypy_diagnostic() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "src/doll/restore.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
