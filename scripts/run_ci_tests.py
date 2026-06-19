"""Run pytest in CI while preserving a downloadable diagnostic log."""

from __future__ import annotations

import base64
import subprocess
import sys
from pathlib import Path

from build_final_spec import build, repository_root

OUTPUT_PATH = Path("pytest-output.txt")


def main() -> int:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=short"],
        capture_output=True,
        text=True,
        check=False,
    )
    output = completed.stdout + completed.stderr
    generated = base64.b64encode(build(repository_root()).encode("utf-8")).decode("ascii")
    diagnostic = (
        output
        + "\nDOLL_FINAL_SPEC_BASE64_BEGIN\n"
        + generated
        + "\nDOLL_FINAL_SPEC_BASE64_END\n"
    )
    OUTPUT_PATH.write_text(diagnostic, encoding="utf-8")
    lines = output.splitlines()
    visible_lines = lines[-20:] if completed.returncode == 0 else lines[-60:]
    print("\n".join(visible_lines))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
