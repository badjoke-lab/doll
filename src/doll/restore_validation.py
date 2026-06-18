"""Fresh-process validator for one restored Doll workspace."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from doll.restore import validate_restored_workspace


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--schema-version", type=int, required=True)
    parser.add_argument("--state-revision", type=int, required=True)
    arguments = parser.parse_args()
    try:
        result = validate_restored_workspace(
            arguments.workspace,
            expected_workspace_id=arguments.workspace_id,
            expected_schema_version=arguments.schema_version,
            expected_state_revision=arguments.state_revision,
        )
    except BaseException as exc:
        print(type(exc).__name__)
        return 2
    print(
        json.dumps(
            {
                "workspace_id": result.workspace_id,
                "schema_version": result.schema_version,
                "state_revision": result.state_revision,
                "record_count": result.record_count,
                "artifact_count": result.artifact_count,
                "backup_inventory_count": result.backup_inventory_count,
                "audit_event_count": result.audit_event_count,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
