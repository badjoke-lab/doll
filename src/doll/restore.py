"""Public alias for the backup restore implementation module."""

from __future__ import annotations

import os as os
import subprocess as subprocess
import sys

from doll import restore_impl as _implementation
from doll.backup import (
    BackupInspection as BackupInspection,
    BackupIntegrityError as BackupIntegrityError,
)
from doll.restore_impl import (
    RestoreConflictError as RestoreConflictError,
    RestoreError as RestoreError,
    RestorePublicationError as RestorePublicationError,
    RestoreResult as RestoreResult,
    RestoreValidation as RestoreValidation,
    RestoreValidationError as RestoreValidationError,
    _STATE_MEMBER as _STATE_MEMBER,
    _count as _count,
    _fsync_directory as _fsync_directory,
    _publish_target as _publish_target,
    _read_regular_file as _read_regular_file,
    _read_verified_members as _read_verified_members,
    _stage_state_restore as _stage_state_restore,
    _stage_workspace_restore as _stage_workspace_restore,
    _validate_in_fresh_process as _validate_in_fresh_process,
    _write_new_file as _write_new_file,
    import_state_package as import_state_package,
    restore_state_backup as restore_state_backup,
    restore_workspace_backup as restore_workspace_backup,
    validate_restored_workspace as validate_restored_workspace,
    verify_backup as verify_backup,
)

sys.modules[__name__] = _implementation
