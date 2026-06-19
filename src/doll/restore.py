"""Public alias for the backup restore implementation module."""

from __future__ import annotations

import os as os
import shutil as shutil
import subprocess as subprocess
import sys
import zlib
from pathlib import Path
from typing import Any

from doll import restore_impl as _implementation
from doll.backup import BackupInspection as BackupInspection
from doll.backup import BackupIntegrityError as BackupIntegrityError
from doll.backup import BackupValidationError as BackupValidationError
from doll.backup import _read_regular_file as _read_regular_file
from doll.backup import verify_backup as verify_backup
from doll.restore_impl import _STATE_MEMBER as _STATE_MEMBER
from doll.restore_impl import RestoreConflictError as RestoreConflictError
from doll.restore_impl import RestoreError as RestoreError
from doll.restore_impl import RestorePublicationError as RestorePublicationError
from doll.restore_impl import RestoreResult as RestoreResult
from doll.restore_impl import RestoreValidation as RestoreValidation
from doll.restore_impl import RestoreValidationError as RestoreValidationError
from doll.restore_impl import _fsync_directory as _fsync_directory
from doll.restore_impl import _publish_target as _publish_target
from doll.restore_impl import _read_verified_members as _read_verified_members
from doll.restore_impl import _rollback_restore as _rollback_restore
from doll.restore_impl import _stage_state_restore as _stage_state_restore
from doll.restore_impl import _stage_workspace_restore as _stage_workspace_restore
from doll.restore_impl import _validate_in_fresh_process as _validate_in_fresh_process
from doll.restore_impl import _write_new_file as _write_new_file
from doll.restore_impl import validate_restored_workspace as validate_restored_workspace
from doll.state_package import import_state_package as import_state_package


def _count(connection: Any, query: str) -> int:
    return _implementation._count(connection, query)


_original_restore_state_backup = _implementation.restore_state_backup
_original_restore_workspace_backup = _implementation.restore_workspace_backup


def _restore_state_backup_with_boundary(backup_path: Path, target: Path) -> RestoreResult:
    try:
        return _original_restore_state_backup(backup_path, target)
    except zlib.error as exc:
        raise BackupValidationError("backup ZIP is unreadable") from exc


def _restore_workspace_backup_with_boundary(backup_path: Path, target: Path) -> RestoreResult:
    try:
        return _original_restore_workspace_backup(backup_path, target)
    except zlib.error as exc:
        raise BackupValidationError("backup ZIP is unreadable") from exc


restore_state_backup = _restore_state_backup_with_boundary
restore_workspace_backup = _restore_workspace_backup_with_boundary
_implementation.restore_state_backup = restore_state_backup
_implementation.restore_workspace_backup = restore_workspace_backup
sys.modules[__name__] = _implementation
