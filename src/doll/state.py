"""Public state repository contracts for doll."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

STATE_DATABASE_NAME = "doll-state.sqlite3"
CURRENT_SCHEMA_VERSION = 1

RecordStatus = Literal["active", "archived", "superseded", "deleted", "invalid"]
RecordProvenance = Literal[
    "user-created",
    "user-confirmed",
    "imported",
    "model-proposed",
    "system-generated",
    "migrated",
    "restored",
]
RecordSensitivity = Literal["public", "internal", "personal", "sensitive", "secret"]

_ALLOWED_STATUSES = frozenset({"active", "archived", "superseded", "deleted", "invalid"})
_ALLOWED_PROVENANCE = frozenset(
    {
        "user-created",
        "user-confirmed",
        "imported",
        "model-proposed",
        "system-generated",
        "migrated",
        "restored",
    }
)
_ALLOWED_SENSITIVITY = frozenset({"public", "internal", "personal", "sensitive", "secret"})


class StateError(RuntimeError):
    """Base class for state repository failures."""


class StateExistsError(StateError):
    """Raised when a state database already exists."""


class StateNotInitializedError(StateError):
    """Raised when an initialized workspace has no state database."""


class StateCorruptError(StateError):
    """Raised when required state metadata is missing or inconsistent."""


class FutureSchemaVersionError(StateError):
    """Raised when the database schema is newer than this doll version supports."""


class MigrationError(StateError):
    """Raised when a schema migration fails and is rolled back."""


class ReadOnlyStateError(StateError):
    """Raised when a write is attempted through a read-only repository."""


class StaleRevisionError(StateError):
    """Raised when an update uses an outdated record revision."""


class StateRevisionMismatchError(StateError):
    """Raised when workspace and database revisions cannot be safely reconciled."""


class RecordValidationError(StateError):
    """Raised when a common record envelope field is invalid."""


@dataclass(frozen=True, slots=True)
class Migration:
    """One deterministic schema transition."""

    migration_id: str
    from_version: int
    to_version: int
    statements: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StateStatus:
    """Inspectable repository status with no identifying host data."""

    workspace_id: str
    schema_version: int
    state_revision: int
    record_count: int
    read_only: bool
    database_path: Path


@dataclass(frozen=True, slots=True)
class RecordEnvelope:
    """Physical foundation for authoritative doll records."""

    id: str
    record_type: str
    schema_version: int
    created_at: str
    updated_at: str
    revision: int
    status: RecordStatus
    provenance: RecordProvenance
    sensitivity: RecordSensitivity
    title: str | None
    metadata: dict[str, object]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


from doll.state_migrations import MIGRATIONS, apply_migrations  # noqa: E402
from doll.state_repository import StateRepository  # noqa: E402
from doll.state_schema import initialize_state_repository, open_state_repository  # noqa: E402

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "MIGRATIONS",
    "STATE_DATABASE_NAME",
    "FutureSchemaVersionError",
    "Migration",
    "MigrationError",
    "ReadOnlyStateError",
    "RecordEnvelope",
    "RecordProvenance",
    "RecordSensitivity",
    "RecordStatus",
    "RecordValidationError",
    "StaleRevisionError",
    "StateCorruptError",
    "StateError",
    "StateExistsError",
    "StateNotInitializedError",
    "StateRepository",
    "StateRevisionMismatchError",
    "StateStatus",
    "apply_migrations",
    "initialize_state_repository",
    "open_state_repository",
]
