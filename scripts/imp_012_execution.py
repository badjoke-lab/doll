"""Execute the model-independent continuity lifecycle for IMP-012."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from doll.backup import (
    create_state_backup,
    create_workspace_backup,
    inspect_backup,
    verify_backup,
)
from doll.restore import restore_state_backup, restore_workspace_backup
from doll.state_package import (
    import_state_package,
    inspect_state_package,
    verify_state_package,
)
from imp_012_common import fresh_status
from imp_012_fixture import refusal_checks, restart_checks, seed


def execute(root: Path) -> dict[str, Any]:
    source = seed(root / "source")
    source_root = source["workspace"].root
    restart, read_only_denied, package, exported = restart_checks(source)

    inspected = inspect_state_package(package)
    verified = verify_state_package(package)
    imported_root = root / "imported"
    imported = import_state_package(package, imported_root)

    state_path = root / "state-backup.zip"
    state_backup = create_state_backup(
        source_root,
        state_path,
        operation_id="imp-012-state-backup",
    )
    workspace_path = root / "workspace-backup.zip"
    workspace_backup = create_workspace_backup(
        source_root,
        workspace_path,
        operation_id="imp-012-workspace-backup",
    )
    state_inspection = inspect_backup(state_path)
    workspace_inspection = inspect_backup(workspace_path)
    verify_backup(state_path)
    verify_backup(workspace_path)

    state_root = root / "restored-state"
    workspace_root = root / "restored-workspace"
    restored_state = restore_state_backup(state_path, state_root)
    restored_workspace = restore_workspace_backup(workspace_path, workspace_root)

    fresh_roots = (source_root, imported_root, state_root, workspace_root)
    fresh = [fresh_status(path) for path in fresh_roots]
    expected = {
        "preferences": 1,
        "policies": 1,
        "permissions": 1,
        "memories": 1,
        "projects": 1,
        "decisions": 1,
        "artifacts": 1,
    }
    counts_match = all(
        all(payload[key] == value for key, value in expected.items())
        for payload in fresh
    )

    relative = Path("artifacts") / "acceptance" / "continuity-日本語.txt"
    bytes_by_root = [(path / relative).read_bytes() for path in fresh_roots]
    populated_refused, tampered_refused, preserved = refusal_checks(
        workspace_path,
        root,
    )
    return {
        "source": source,
        "restart": restart,
        "read_only_denied": read_only_denied,
        "exported": exported,
        "inspected": inspected,
        "verified": verified,
        "imported": imported,
        "state_backup": state_backup,
        "workspace_backup": workspace_backup,
        "state_inspection": state_inspection,
        "workspace_inspection": workspace_inspection,
        "restored_state": restored_state,
        "restored_workspace": restored_workspace,
        "counts_match": counts_match,
        "bytes_by_root": bytes_by_root,
        "populated_refused": populated_refused,
        "tampered_refused": tampered_refused,
        "preserved": preserved,
    }
