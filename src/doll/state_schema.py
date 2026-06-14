"""State repository initialization and opening operations."""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from doll.state import (
    CURRENT_SCHEMA_VERSION,
    MIGRATIONS,
    Migration,
    StateExistsError,
    StateNotInitializedError,
    StateRevisionMismatchError,
)
from doll.state_db import (
    _bootstrap,
    _configure_write_journal,
    _connect,
    _database_path,
    _validate_database_identity,
)
from doll.state_migrations import apply_migrations
from doll.workspace import (
    InitializedWorkspace,
    WorkspaceRevisionError,
    load_workspace,
    update_workspace_state_revision,
)

if TYPE_CHECKING:
    from doll.state_repository import StateRepository


def _sync_workspace_revision(
    workspace: InitializedWorkspace,
    database_revision: int,
) -> None:
    if workspace.record.state_revision > database_revision:
        raise StateRevisionMismatchError(
            "workspace state revision is ahead of the authoritative database"
        )
    if workspace.record.state_revision < database_revision:
        try:
            update_workspace_state_revision(workspace.root, database_revision)
        except WorkspaceRevisionError as exc:
            raise StateRevisionMismatchError(
                "workspace state revision could not be synchronized"
            ) from exc


def initialize_state_repository(
    path: Path | None = None,
    *,
    migrations: Iterable[Migration] = MIGRATIONS,
) -> StateRepository:
    """Create and migrate a new state repository inside an initialized workspace."""

    from doll.state_repository import StateRepository

    workspace = load_workspace(path)
    database_path = _database_path(workspace)
    if database_path.exists():
        raise StateExistsError(f"state database already exists: {database_path}")

    connection = _connect(database_path, read_only=False)
    try:
        _bootstrap(connection, str(workspace.record.workspace_id))
        apply_migrations(connection, migrations)
        _configure_write_journal(connection)
        if os.name != "nt":  # pragma: no branch
            database_path.chmod(0o600)
        repository = StateRepository(
            workspace=workspace,
            database_path=database_path,
            connection=connection,
            read_only=False,
        )
        _sync_workspace_revision(workspace, repository.status().state_revision)
        return repository
    except BaseException:
        connection.close()
        raise


def open_state_repository(
    path: Path | None = None,
    *,
    read_only: bool = False,
    migrations: Iterable[Migration] = MIGRATIONS,
) -> StateRepository:
    """Open an existing state repository, optionally without any write capability."""

    from doll.state_repository import StateRepository

    workspace = load_workspace(path)
    database_path = _database_path(workspace)
    if not database_path.is_file():
        raise StateNotInitializedError(f"state database does not exist: {database_path}")

    connection = _connect(database_path, read_only=read_only)
    try:
        schema_version, state_revision = _validate_database_identity(connection, workspace)
        if not read_only:
            _configure_write_journal(connection)
        if not read_only and schema_version < CURRENT_SCHEMA_VERSION:
            apply_migrations(connection, migrations)
            _, state_revision = _validate_database_identity(connection, workspace)
        if not read_only:
            _sync_workspace_revision(workspace, state_revision)
            workspace = load_workspace(workspace.root)
        return StateRepository(
            workspace=workspace,
            database_path=database_path,
            connection=connection,
            read_only=read_only,
        )
    except BaseException:
        connection.close()
        raise
