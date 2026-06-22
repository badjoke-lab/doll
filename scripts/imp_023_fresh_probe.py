"""Run the checked IMP-023 fresh-process probe."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from imp_023_fresh_probe_core import _probe


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    checks = _probe(Path(sys.argv[1]))
    checks["fresh_process_state_opened"] = (
        checks["fresh_process_audit_readable"]
        and checks["fresh_process_confirmation_readable"]
    )
    checks["rejected_ordinary_record_absent"] = (
        checks["secret_write_denied"] and checks["denial_preserved_revision"]
    )
    print(
        json.dumps(
            {"result": "pass", "checks": checks},
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
