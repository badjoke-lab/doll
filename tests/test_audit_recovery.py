from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from doll import state, state_db, state_migrations, workspace
from doll.audit import AuditError, AuditService


def test_read_only_schema_one_requires_writable_migration(tmp_path: Path) -> None:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    database_path = initialized.root / "state" / state.STATE_DATABASE_NAME
    connection = state_db._connect(database_path, read_only=False)
    try:
        state_db._bootstrap(connection, str(initialized.record.workspace_id))
        state_migrations._apply_migration(connection, state_db.MIGRATION_0001)
    finally:
        connection.close()

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(AuditError, match="writable mode"):
            AuditService(repository).list()


def test_missing_audit_table_is_reported_as_corrupt_state(tmp_path: Path) -> None:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root) as repository:
        repository.connection.execute(
            "ALTER TABLE audit_events RENAME TO audit_events_missing"
        )
        with pytest.raises(state.StateCorruptError, match="unreadable"):
            AuditService(repository).list()


def test_invalid_persisted_event_is_rejected_on_read(tmp_path: Path) -> None:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root) as repository:
        repository.connection.execute(
            """
            INSERT INTO audit_events (
                event_id,
                operation_id,
                occurred_at,
                actor_type,
                action,
                result,
                metadata_json
            ) VALUES (?, 'operation-invalid', 'not-utc', 'system', 'audit.invalid', 'failed', '{}')
            """,
            (str(uuid4()),),
        )
        with pytest.raises(state.StateCorruptError, match="invalid data"):
            AuditService(repository).list()
