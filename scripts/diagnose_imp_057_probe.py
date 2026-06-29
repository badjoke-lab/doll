"""Diagnostic wrapper for the IMP-057 synthetic migration probe."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from imp_057_local_portability_probe import SYNTHETIC_MODEL, run


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="doll-imp057-diagnostic-") as directory:
        checks, evidence = run(
            Path(directory),
            mode="ci",
            model_name=SYNTHETIC_MODEL,
            ollama_port=11434,
        )
    print(json.dumps({"checks": checks, "evidence": evidence}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
