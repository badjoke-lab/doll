"""Add persistence checks to the core IMP-023 fresh-process probe."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from doll import state
from doll.audit import AuditService
from imp_023_fresh_probe import _probe


def main() -> int:
    if len(sys.argv) != 2:
        print(
            json.dumps(
                {"result": "fail", "error_stage": "arguments"},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2

    root = Path(sys.argv[1])
    try:
        checks = _probe(root)
        with state.open_state_repository(root / "workspace", read_only=True) as repository:
            events = AuditService(repository).list(limit=200)
            status = repository.status()
            checks["fresh_process_state_opened"] = status.read_only
            checks["rejected_ordinary_record_absent"] = status.record_count == len(events)
    except BaseException as exc:
        print(
            json.dumps(
                {
                    "result": "fail",
                    "error_stage": "checked_fresh_process_probe",
                    "error_class": type(exc).__name__,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2

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
