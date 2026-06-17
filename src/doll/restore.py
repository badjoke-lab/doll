"""Public alias for the backup restore implementation module."""

from __future__ import annotations

import os as os
import subprocess as subprocess
import sys

from doll.backup import (
    BackupInspection as BackupInspection,
)
from doll.backup import (
    BackupIntegrityError as BackupIntegrityError,
)
from doll.restore_impl import (
    _STATE_MEMBER as _STATE_MEMBER,
)
from doll.restore_impl import (
    RestoreConflictError as RestoreConflictError,
)
from doll.restore_impl import (
    RestoreError as RestoreError,
)
from doll.restore_impl import (
    RestorePublicationError as RestorePublicationError,
)
from doll.restore_impl import (
    RestoreResult as RestoreResult,
)
from doll.restore_impl import (
    RestoreValidation as RestoreValidation,
)
from doll.restore_impl import (
    RestoreValidationError as RestoreValidationError,
)
from doll.restore_impl import (
    _count as _count,
)
from doll.restore_impl import (
    _fsync_directory as _fsync_directory,
)
from doll.restore_impl import (
    _publish_target as _publish_target,
)
from doll.restore_impl import (
    _read_regular_file as _read_regular_file,
)
from doll.restore_impl import (
    _read_verified_members as _read_verified_members,
)
from doll.restore_impl import (
    _stage_state_restore as _stage_state_restore,
)
from doll.restore_impl import (
    _stage_workspace_restore as _stage_workspace_restore,
)
from doll.restore_impl import (
    _validate_in_fresh_process as _validate_in_fresh_process,
)
from doll.restore_impl import (
    _write_new_file as _write_new_file,
)
from doll.restore_impl import (
    import_state_package as import_state_package,
)
from doll.restore_impl import (
    restore_state_backup as restore_state_backup,
)
from doll.restore_impl import (
    restore_workspace_backup as restore_workspace_backup,
)
from doll.restore_impl import (
    validate_restored_workspace as validate_restored_workspace,
)
from doll.restore_impl import (
    verify_backup as verify_backup,
)

from doll import restore_impl as _implementation

sys.modules[__name__] = _implementation
