"""Run pytest in CI while preserving a downloadable diagnostic log."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

OUTPUT_PATH = Path("pytest-output.txt")


def main() -> int:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=short"],
        capture_output=True,
        text=True,
        check=False,
    )
    output = completed.stdout + completed.stderr
    OUTPUT_PATH.write_text(output, encoding="utf-8")
    lines = output.splitlines()
    visible_lines = lines[-20:] if completed.returncode == 0 else lines[-60:]
    print("\n".join(visible_lines))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
