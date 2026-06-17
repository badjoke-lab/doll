"""Run the IMP-011 state and workspace restore drill on the primary Intel Mac."""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from doll import state, workspace
from doll.artifact import WorkspaceFileService
from doll.backup import create_state_backup, create_workspace_backup
from doll.memory import ConfirmedMemoryService
from doll.restore import restore_state_backup, restore_workspace_backup
from doll.settings import PreferenceService

_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_ARTIFACT_BYTES = b"IMP-011 Intel Mac restore drill\n"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument(
        "--offline-confirmed",
        action="store_true",
        help="Confirm that network access was disabled before starting the drill.",
    )
    return parser.parse_args()


def _current_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _require_environment(arguments: argparse.Namespace) -> None:
    if platform.system() != "Darwin":
        raise RuntimeError("the IMP-011 real-machine drill requires macOS")
    if platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("the IMP-011 real-machine drill requires an Intel Mac")
    if not arguments.offline_confirmed:
        raise RuntimeError("rerun with --offline-confirmed after disabling network access")
    if not _COMMIT_PATTERN.fullmatch(arguments.commit_sha):
        raise RuntimeError("commit SHA must be exactly 40 lowercase hexadecimal characters")
    if _current_head() != arguments.commit_sha:
        raise RuntimeError("the checked-out commit does not match --commit-sha")


def _run(arguments: argparse.Namespace) -> dict[str, object]:
    started_at = _utc_now()
    with tempfile.TemporaryDirectory(prefix="doll-imp-011-drill-") as temporary:
        root = Path(temporary)
        source = workspace.initialize_workspace(root / "source")
        with state.initialize_state_repository(source.root):
            pass

        with state.open_state_repository(source.root) as repository:
            preference = PreferenceService(repository).create(
                key="output.language",
                value={"language": "日本語"},
                description="IMP-011 restore drill preference",
                operation_id="imp-011-drill-preference",
            )
            ConfirmedMemoryService(repository).create(
                subject="IMP-011 continuity",
                content="Restore must preserve authoritative state without a model runtime.",
                operation_id="imp-011-drill-memory",
            )
            artifact = WorkspaceFileService(repository).create_text(
                managed_path="drill/restore.txt",
                text=_ARTIFACT_BYTES.decode("utf-8"),
                title="IMP-011 restore drill artifact",
                operation_id="imp-011-drill-artifact",
            )

        state_backup_path = root / "state-backup.zip"
        state_backup = create_state_backup(
            source.root,
            state_backup_path,
            operation_id="imp-011-drill-state-backup",
        )
        workspace_backup_path = root / "workspace-backup.zip"
        workspace_backup = create_workspace_backup(
            source.root,
            workspace_backup_path,
            operation_id="imp-011-drill-workspace-backup",
        )

        restored_state = restore_state_backup(state_backup_path, root / "restored-state")
        restored_workspace = restore_workspace_backup(
            workspace_backup_path,
            root / "restored-workspace",
        )

        with state.open_state_repository(root / "restored-state", read_only=True) as repository:
            state_preference = PreferenceService(repository).get(preference.record_id)
            state_artifact = WorkspaceFileService(repository).verify(artifact.artifact_id)
        with state.open_state_repository(root / "restored-workspace", read_only=True) as repository:
            workspace_preference = PreferenceService(repository).get(preference.record_id)
            workspace_artifact = WorkspaceFileService(repository).verify(artifact.artifact_id)

        state_artifact_path = root / "restored-state" / "artifacts" / "drill" / "restore.txt"
        workspace_artifact_path = (
            root / "restored-workspace" / "artifacts" / "drill" / "restore.txt"
        )
        state_bytes = state_artifact_path.read_bytes()
        workspace_bytes = workspace_artifact_path.read_bytes()

        checks = {
            "state_fresh_process_validated": restored_state.fresh_process_validated,
            "workspace_fresh_process_validated": restored_workspace.fresh_process_validated,
            "state_revision_advanced_by_import": (
                restored_state.restored_state_revision
                == state_backup.inspection.source_state_revision + 1
            ),
            "workspace_revision_preserved": (
                restored_workspace.restored_state_revision
                == workspace_backup.inspection.source_state_revision
            ),
            "state_preference_preserved": state_preference.value == {"language": "日本語"},
            "workspace_preference_preserved": (
                workspace_preference.value == {"language": "日本語"}
            ),
            "state_artifact_hash_verified": state_artifact.actual_hash == artifact.content_hash,
            "workspace_artifact_hash_verified": (
                workspace_artifact.actual_hash == artifact.content_hash
            ),
            "state_artifact_bytes_preserved": state_bytes == _ARTIFACT_BYTES,
            "workspace_artifact_bytes_preserved": workspace_bytes == _ARTIFACT_BYTES,
        }
        if not all(checks.values()):
            raise RuntimeError("one or more restore-drill checks failed")

        return {
            "test_id": "IMP-011-INTEL-MAC-RESTORE-DRILL",
            "result": "pass",
            "commit_sha": arguments.commit_sha,
            "started_at": started_at,
            "completed_at": _utc_now(),
            "evidence_level": "real-machine",
            "operating_system": platform.system(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "network_mode": "disabled-confirmed-by-operator",
            "model_runtime_used": False,
            "cloud_credentials_used": False,
            "checks": checks,
            "state_backup": {
                "source_revision": state_backup.inspection.source_state_revision,
                "restored_revision": restored_state.restored_state_revision,
                "record_count": restored_state.record_count,
                "artifact_count": restored_state.artifact_count,
            },
            "workspace_backup": {
                "source_revision": workspace_backup.inspection.source_state_revision,
                "restored_revision": restored_workspace.restored_state_revision,
                "record_count": restored_workspace.record_count,
                "artifact_count": restored_workspace.artifact_count,
            },
            "privacy": {
                "absolute_paths_in_report": False,
                "username_in_report": False,
                "hostname_in_report": False,
                "secret_values_in_report": False,
            },
        }


def main() -> int:
    arguments = _parse_arguments()
    try:
        _require_environment(arguments)
        report = _run(arguments)
    except BaseException as exc:
        print(
            json.dumps(
                {
                    "test_id": "IMP-011-INTEL-MAC-RESTORE-DRILL",
                    "result": "fail",
                    "commit_sha": arguments.commit_sha,
                    "completed_at": _utc_now(),
                    "error_class": type(exc).__name__,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
