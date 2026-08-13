"""Optional rebuildable lexical index for confirmed local memory."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast
from uuid import UUID

from doll.memory import ConfirmedMemoryInfo, ConfirmedMemoryService, MemoryCorruptError
from doll.state_repository import StateRepository

MemoryLexicalFieldClass = Literal["subject", "content", "metadata"]

MEMORY_LEXICAL_INDEX_SCHEMA_VERSION = 1
MEMORY_LEXICAL_INDEX_ALGORITHM_ID = "memory-exact-token-inverted"
MEMORY_LEXICAL_INDEX_ALGORITHM_VERSION = "1"
MEMORY_LEXICAL_INDEX_QUERY_MODE = "unicode-nfkc-casefold-exact-token-and"
MEMORY_LEXICAL_INDEX_RELATIVE_PATH = Path("temporary/recall-index/memory-lexical-v1.sqlite3")

_MAX_QUERY_CHARS = 240
_MAX_QUERY_TERMS = 12
_MAX_RESULTS = 100
_MAX_INDEXED_MEMORIES = 10_000
_MAX_TOKENS_PER_MEMORY = 4_096
_MAX_TOKEN_CHARS = 240
_MAX_POSTINGS = 1_000_000
_FIELD_ORDER: dict[MemoryLexicalFieldClass, int] = {
    "subject": 0,
    "content": 1,
    "metadata": 2,
}


class RecallIndexError(RuntimeError):
    """Base class for rebuildable recall-index failures."""


class RecallIndexValidationError(RecallIndexError):
    """Raised when an index request or workspace path is unsafe."""


class RecallIndexUnavailableError(RecallIndexError):
    """Raised when a requested index does not exist or cannot be opened safely."""


class RecallIndexCorruptError(RecallIndexError):
    """Raised when index bytes or internal counts are invalid."""


class RecallIndexUnsupportedError(RecallIndexError):
    """Raised when an index schema or algorithm version is unsupported."""


class RecallIndexStaleError(RecallIndexError):
    """Raised when an index does not describe the current authoritative state revision."""


class RecallIndexLimitError(RecallIndexError):
    """Raised when bounded index construction would exceed its fixed posting limits."""


@dataclass(frozen=True, slots=True)
class MemoryLexicalIndexInspection:
    """Validated non-authoritative metadata for one published lexical index."""

    schema_version: int
    algorithm_id: str
    algorithm_version: str
    workspace_id: str
    source_state_revision: int
    indexed_memory_count: int
    posting_count: int
    scan_truncated: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "algorithm_id": self.algorithm_id,
            "algorithm_version": self.algorithm_version,
            "workspace_id": self.workspace_id,
            "source_state_revision": self.source_state_revision,
            "indexed_memory_count": self.indexed_memory_count,
            "posting_count": self.posting_count,
            "scan_truncated": self.scan_truncated,
            "index_relative_path": MEMORY_LEXICAL_INDEX_RELATIVE_PATH.as_posix(),
        }


@dataclass(frozen=True, slots=True)
class MemoryLexicalIndexHit:
    """One exact-token candidate returned by the disposable index."""

    memory_id: str
    memory_revision: int
    source_rank: int

    def to_dict(self) -> dict[str, object]:
        return {
            "memory_id": self.memory_id,
            "memory_revision": self.memory_revision,
            "source_rank": self.source_rank,
        }


@dataclass(frozen=True, slots=True)
class MemoryLexicalIndexQueryReport:
    """Bounded deterministic exact-token query result over one validated index."""

    source_state_revision: int
    indexed_memory_count: int
    posting_count: int
    scan_truncated: bool
    term_count: int
    hits: tuple[MemoryLexicalIndexHit, ...]

    @property
    def result_count(self) -> int:
        return len(self.hits)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": MEMORY_LEXICAL_INDEX_SCHEMA_VERSION,
            "algorithm_id": MEMORY_LEXICAL_INDEX_ALGORITHM_ID,
            "algorithm_version": MEMORY_LEXICAL_INDEX_ALGORITHM_VERSION,
            "query_mode": MEMORY_LEXICAL_INDEX_QUERY_MODE,
            "source_state_revision": self.source_state_revision,
            "indexed_memory_count": self.indexed_memory_count,
            "posting_count": self.posting_count,
            "scan_truncated": self.scan_truncated,
            "term_count": self.term_count,
            "result_count": self.result_count,
            "hits": [hit.to_dict() for hit in self.hits],
        }


def memory_lexical_index_path(repository: StateRepository) -> Path:
    """Return the fixed private sidecar path without creating or opening it."""

    return repository.workspace.root / MEMORY_LEXICAL_INDEX_RELATIVE_PATH


def build_memory_lexical_index(repository: StateRepository) -> MemoryLexicalIndexInspection:
    """Atomically rebuild the optional sidecar from a read-only authoritative snapshot."""

    _require_read_only(repository)
    source_status = repository.status()
    _validate_repository_identity(repository)
    index_path = memory_lexical_index_path(repository)
    index_directory = _prepare_index_directory(repository)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".memory-lexical-v1.",
        suffix=".tmp",
        dir=index_directory,
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    connection: sqlite3.Connection | None = None
    try:
        _restrict_file(temporary_path)
        connection = sqlite3.connect(temporary_path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("PRAGMA synchronous = FULL")
        _create_index_schema(connection)
        indexed_memory_count, posting_count, scan_truncated = _populate_index(
            repository,
            connection,
        )
        if repository.status().state_revision != source_status.state_revision:
            raise RecallIndexStaleError("authoritative state changed during index construction")
        connection.execute(
            """
            INSERT INTO index_metadata (
                singleton,
                schema_version,
                algorithm_id,
                algorithm_version,
                workspace_id,
                source_state_revision,
                indexed_memory_count,
                posting_count,
                scan_truncated
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                MEMORY_LEXICAL_INDEX_SCHEMA_VERSION,
                MEMORY_LEXICAL_INDEX_ALGORITHM_ID,
                MEMORY_LEXICAL_INDEX_ALGORITHM_VERSION,
                source_status.workspace_id,
                source_status.state_revision,
                indexed_memory_count,
                posting_count,
                int(scan_truncated),
            ),
        )
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity is None or integrity[0] != "ok":
            raise RecallIndexCorruptError("new lexical index failed SQLite integrity check")
        connection.close()
        connection = None
        _fsync_file(temporary_path)
        if os.path.lexists(index_path) and (index_path.is_symlink() or not index_path.is_file()):
            raise RecallIndexValidationError("existing lexical index path is unsafe")
        os.replace(temporary_path, index_path)
        _restrict_file(index_path)
        return inspect_memory_lexical_index(repository)
    except RecallIndexError:
        raise
    except (OSError, sqlite3.DatabaseError, MemoryCorruptError) as exc:
        raise RecallIndexUnavailableError("memory lexical index could not be built safely") from exc
    finally:
        if connection is not None:
            connection.close()
        temporary_path.unlink(missing_ok=True)


def inspect_memory_lexical_index(repository: StateRepository) -> MemoryLexicalIndexInspection:
    """Verify index integrity, contract identity, workspace binding, and freshness."""

    _require_read_only(repository)
    _validate_repository_identity(repository)
    connection = _open_index_read_only(repository)
    try:
        inspection = _validate_open_index(connection)
        status = repository.status()
        if inspection.workspace_id != status.workspace_id:
            raise RecallIndexValidationError("memory lexical index belongs to another workspace")
        if inspection.source_state_revision != status.state_revision:
            raise RecallIndexStaleError("memory lexical index is stale for current Doll State")
        return inspection
    finally:
        connection.close()


def query_memory_lexical_index(
    repository: StateRepository,
    query: str,
    *,
    limit: int = 20,
) -> MemoryLexicalIndexQueryReport:
    """Query the optional exact-token sidecar without changing authoritative state."""

    _require_read_only(repository)
    _validate_repository_identity(repository)
    terms = _validate_query(query)
    _validate_limit(limit)
    connection = _open_index_read_only(repository)
    try:
        inspection = _validate_open_index(connection)
        status = repository.status()
        if inspection.workspace_id != status.workspace_id:
            raise RecallIndexValidationError("memory lexical index belongs to another workspace")
        if inspection.source_state_revision != status.state_revision:
            raise RecallIndexStaleError("memory lexical index is stale for current Doll State")

        placeholders = ",".join("?" for _ in terms)
        rows = connection.execute(
            f"""
            SELECT m.memory_id, m.memory_revision, m.source_rank
            FROM indexed_memories AS m
            JOIN token_postings AS p ON p.memory_id = m.memory_id
            WHERE p.token IN ({placeholders})
            GROUP BY m.memory_id, m.memory_revision, m.source_rank
            HAVING COUNT(DISTINCT p.token) = ?
            ORDER BY m.source_rank ASC, m.memory_id ASC
            LIMIT ?
            """,
            (*terms, len(terms), limit),
        ).fetchall()
        memory_service = ConfirmedMemoryService(repository)
        hits: list[MemoryLexicalIndexHit] = []
        for row in rows:
            memory_id = cast(str, row["memory_id"])
            memory_revision = cast(int, row["memory_revision"])
            try:
                memory = memory_service.get(memory_id)
            except (KeyError, MemoryCorruptError) as exc:
                raise RecallIndexCorruptError(
                    "memory lexical index references invalid authoritative memory"
                ) from exc
            if (
                memory.revision != memory_revision
                or memory.status != "active"
                or memory.sensitivity == "secret"
            ):
                raise RecallIndexCorruptError(
                    "memory lexical index binding disagrees with authoritative memory"
                )
            hits.append(
                MemoryLexicalIndexHit(
                    memory_id=memory_id,
                    memory_revision=memory_revision,
                    source_rank=cast(int, row["source_rank"]),
                )
            )
        return MemoryLexicalIndexQueryReport(
            source_state_revision=inspection.source_state_revision,
            indexed_memory_count=inspection.indexed_memory_count,
            posting_count=inspection.posting_count,
            scan_truncated=inspection.scan_truncated,
            term_count=len(terms),
            hits=tuple(hits),
        )
    except RecallIndexError:
        raise
    except sqlite3.DatabaseError as exc:
        raise RecallIndexCorruptError("memory lexical index query failed") from exc
    finally:
        connection.close()


def discard_memory_lexical_index(repository: StateRepository) -> bool:
    """Delete only the disposable sidecar; authoritative memory remains untouched."""

    _require_read_only(repository)
    _validate_repository_identity(repository)
    index_path = memory_lexical_index_path(repository)
    _validate_index_parent(repository)
    if not os.path.lexists(index_path):
        return False
    if index_path.is_symlink() or not index_path.is_file():
        raise RecallIndexValidationError("memory lexical index path is unsafe")
    try:
        index_path.unlink()
    except OSError as exc:
        raise RecallIndexUnavailableError("memory lexical index could not be removed") from exc
    return True


def _populate_index(
    repository: StateRepository,
    connection: sqlite3.Connection,
) -> tuple[int, int, bool]:
    try:
        rows = repository.connection.execute(
            """
            SELECT id
            FROM records
            WHERE record_type = 'memory'
              AND status = 'active'
              AND sensitivity <> 'secret'
            ORDER BY updated_at DESC, id ASC
            LIMIT ?
            """,
            (_MAX_INDEXED_MEMORIES + 1,),
        ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise RecallIndexCorruptError("authoritative memory inventory is unreadable") from exc

    scan_truncated = len(rows) > _MAX_INDEXED_MEMORIES
    selected_rows = rows[:_MAX_INDEXED_MEMORIES]
    memory_service = ConfirmedMemoryService(repository)
    posting_count = 0
    connection.execute("BEGIN IMMEDIATE")
    try:
        for source_rank, row in enumerate(selected_rows, start=1):
            memory = memory_service.get(cast(str, row[0]))
            if memory.status != "active" or memory.sensitivity == "secret":
                raise RecallIndexCorruptError(
                    "authoritative memory changed while lexical index was being built"
                )
            postings = _memory_postings(memory)
            if len(postings) > _MAX_TOKENS_PER_MEMORY:
                raise RecallIndexLimitError("one memory exceeds the lexical index token bound")
            if posting_count + len(postings) > _MAX_POSTINGS:
                raise RecallIndexLimitError("lexical index exceeds the posting bound")
            connection.execute(
                """
                INSERT INTO indexed_memories (memory_id, memory_revision, source_rank)
                VALUES (?, ?, ?)
                """,
                (memory.record_id, memory.revision, source_rank),
            )
            connection.executemany(
                """
                INSERT INTO token_postings (token, memory_id, field_class)
                VALUES (?, ?, ?)
                """,
                ((token, memory.record_id, field_class) for token, field_class in postings),
            )
            posting_count += len(postings)
        connection.execute("COMMIT")
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    return len(selected_rows), posting_count, scan_truncated


def _memory_postings(
    memory: ConfirmedMemoryInfo,
) -> tuple[tuple[str, MemoryLexicalFieldClass], ...]:
    postings: set[tuple[str, MemoryLexicalFieldClass]] = set()
    for token in _text_tokens(memory.subject):
        postings.add((token, "subject"))
    for token in _text_tokens(memory.content):
        postings.add((token, "content"))
    metadata_values = (
        "confirmed",
        memory.source_type,
        memory.confirmation_state,
        memory.valid_from,
        memory.valid_until,
        memory.source_reference,
        memory.model_manifest_id,
        memory.runtime_adapter_id,
        memory.session_id,
        memory.origin_operation_id,
        *memory.related_memory_ids,
        *memory.contradicts_memory_ids,
    )
    for value in metadata_values:
        if isinstance(value, str):
            for token in _text_tokens(value):
                postings.add((token, "metadata"))
    return tuple(
        sorted(
            postings,
            key=lambda item: (item[0], _FIELD_ORDER[item[1]]),
        )
    )


def _text_tokens(value: str) -> tuple[str, ...]:
    normalized = _normalize_text(value)
    if not normalized:
        return ()
    return tuple(
        dict.fromkeys(term for term in normalized.split(" ") if 0 < len(term) <= _MAX_TOKEN_CHARS)
    )


def _normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def _validate_query(query: str) -> tuple[str, ...]:
    if not isinstance(query, str):
        raise RecallIndexValidationError("lexical index query must be text")
    if any(ord(character) < 32 or ord(character) == 127 for character in query):
        raise RecallIndexValidationError("lexical index query contains a control character")
    normalized = _normalize_text(query)
    if not normalized:
        raise RecallIndexValidationError("lexical index query must not be blank")
    if len(normalized) > _MAX_QUERY_CHARS:
        raise RecallIndexValidationError("lexical index query exceeds the maximum length")
    raw_terms = normalized.split(" ")
    if len(raw_terms) > _MAX_QUERY_TERMS:
        raise RecallIndexValidationError("lexical index query contains too many terms")
    terms = tuple(dict.fromkeys(raw_terms))
    if any(len(term) > _MAX_TOKEN_CHARS for term in terms):
        raise RecallIndexValidationError("lexical index query term exceeds the token bound")
    return terms


def _validate_limit(limit: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= _MAX_RESULTS:
        raise RecallIndexValidationError("lexical index result limit must be between 1 and 100")


def _require_read_only(repository: StateRepository) -> None:
    if not repository.read_only:
        raise RecallIndexValidationError("memory lexical index requires a read-only repository")


def _validate_repository_identity(repository: StateRepository) -> None:
    status = repository.status()
    if (
        str(repository.workspace.record.workspace_id) != status.workspace_id
        or repository.workspace.record.state_revision != status.state_revision
    ):
        raise RecallIndexValidationError(
            "workspace identity and Doll State revision are inconsistent"
        )


def _prepare_index_directory(repository: StateRepository) -> Path:
    index_directory = _validate_index_parent(repository)
    if not index_directory.exists():
        try:
            index_directory.mkdir(mode=0o700)
        except OSError as exc:
            raise RecallIndexUnavailableError(
                "memory lexical index directory could not be created"
            ) from exc
    if index_directory.is_symlink() or not index_directory.is_dir():
        raise RecallIndexValidationError("memory lexical index directory is unsafe")
    if os.name != "nt":
        try:
            index_directory.chmod(0o700)
        except OSError as exc:
            raise RecallIndexUnavailableError(
                "memory lexical index directory permissions could not be restricted"
            ) from exc
    return index_directory


def _validate_index_parent(repository: StateRepository) -> Path:
    temporary_root = repository.workspace.root / "temporary"
    if temporary_root.is_symlink() or not temporary_root.is_dir():
        raise RecallIndexValidationError("workspace temporary directory is unsafe")
    index_directory = temporary_root / "recall-index"
    if os.path.lexists(index_directory) and (
        index_directory.is_symlink() or not index_directory.is_dir()
    ):
        raise RecallIndexValidationError("memory lexical index directory is unsafe")
    return index_directory


def _open_index_read_only(repository: StateRepository) -> sqlite3.Connection:
    index_path = memory_lexical_index_path(repository)
    _validate_index_parent(repository)
    if not os.path.lexists(index_path):
        raise RecallIndexUnavailableError("memory lexical index does not exist")
    if index_path.is_symlink() or not index_path.is_file():
        raise RecallIndexValidationError("memory lexical index path is unsafe")
    try:
        connection = sqlite3.connect(
            f"{index_path.resolve().as_uri()}?mode=ro&immutable=1",
            uri=True,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        return connection
    except (OSError, sqlite3.DatabaseError) as exc:
        raise RecallIndexUnavailableError("memory lexical index could not be opened") from exc


def _validate_open_index(connection: sqlite3.Connection) -> MemoryLexicalIndexInspection:
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity is None or integrity[0] != "ok":
            raise RecallIndexCorruptError("memory lexical index failed SQLite integrity check")
        user_version_row = connection.execute("PRAGMA user_version").fetchone()
        if user_version_row is None:
            raise RecallIndexCorruptError("memory lexical index user version is missing")
        user_version = cast(int, user_version_row[0])
        row = connection.execute(
            """
            SELECT
                schema_version,
                algorithm_id,
                algorithm_version,
                workspace_id,
                source_state_revision,
                indexed_memory_count,
                posting_count,
                scan_truncated
            FROM index_metadata
            WHERE singleton = 1
            """
        ).fetchone()
        if row is None:
            raise RecallIndexCorruptError("memory lexical index metadata is missing")
        schema_version = cast(int, row["schema_version"])
        algorithm_id = cast(str, row["algorithm_id"])
        algorithm_version = cast(str, row["algorithm_version"])
        if (
            user_version != MEMORY_LEXICAL_INDEX_SCHEMA_VERSION
            or schema_version != MEMORY_LEXICAL_INDEX_SCHEMA_VERSION
            or algorithm_id != MEMORY_LEXICAL_INDEX_ALGORITHM_ID
            or algorithm_version != MEMORY_LEXICAL_INDEX_ALGORITHM_VERSION
        ):
            raise RecallIndexUnsupportedError("memory lexical index version is unsupported")
        workspace_id = cast(str, row["workspace_id"])
        try:
            UUID(workspace_id)
        except ValueError as exc:
            raise RecallIndexCorruptError("memory lexical index workspace ID is invalid") from exc
        source_state_revision = cast(int, row["source_state_revision"])
        indexed_memory_count = cast(int, row["indexed_memory_count"])
        posting_count = cast(int, row["posting_count"])
        scan_truncated_value = cast(int, row["scan_truncated"])
        if (
            source_state_revision < 0
            or indexed_memory_count < 0
            or indexed_memory_count > _MAX_INDEXED_MEMORIES
            or posting_count < 0
            or posting_count > _MAX_POSTINGS
            or scan_truncated_value not in {0, 1}
        ):
            raise RecallIndexCorruptError("memory lexical index metadata is out of bounds")
        actual_memories = connection.execute("SELECT COUNT(*) FROM indexed_memories").fetchone()
        actual_postings = connection.execute("SELECT COUNT(*) FROM token_postings").fetchone()
        if (
            actual_memories is None
            or actual_postings is None
            or cast(int, actual_memories[0]) != indexed_memory_count
            or cast(int, actual_postings[0]) != posting_count
        ):
            raise RecallIndexCorruptError("memory lexical index counts do not match metadata")
        return MemoryLexicalIndexInspection(
            schema_version=schema_version,
            algorithm_id=algorithm_id,
            algorithm_version=algorithm_version,
            workspace_id=workspace_id,
            source_state_revision=source_state_revision,
            indexed_memory_count=indexed_memory_count,
            posting_count=posting_count,
            scan_truncated=bool(scan_truncated_value),
        )
    except RecallIndexError:
        raise
    except (IndexError, KeyError, TypeError, ValueError, sqlite3.DatabaseError) as exc:
        raise RecallIndexCorruptError("memory lexical index is unreadable") from exc


def _create_index_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        f"""
        PRAGMA user_version = {MEMORY_LEXICAL_INDEX_SCHEMA_VERSION};
        CREATE TABLE index_metadata (
            singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
            schema_version INTEGER NOT NULL,
            algorithm_id TEXT NOT NULL,
            algorithm_version TEXT NOT NULL,
            workspace_id TEXT NOT NULL,
            source_state_revision INTEGER NOT NULL,
            indexed_memory_count INTEGER NOT NULL,
            posting_count INTEGER NOT NULL,
            scan_truncated INTEGER NOT NULL CHECK (scan_truncated IN (0, 1))
        );
        CREATE TABLE indexed_memories (
            memory_id TEXT PRIMARY KEY,
            memory_revision INTEGER NOT NULL CHECK (memory_revision >= 1),
            source_rank INTEGER NOT NULL CHECK (source_rank >= 1)
        );
        CREATE TABLE token_postings (
            token TEXT NOT NULL,
            memory_id TEXT NOT NULL,
            field_class TEXT NOT NULL CHECK (field_class IN ('subject', 'content', 'metadata')),
            PRIMARY KEY (token, memory_id, field_class),
            FOREIGN KEY (memory_id) REFERENCES indexed_memories(memory_id) ON DELETE CASCADE
        );
        CREATE INDEX token_postings_memory_idx ON token_postings(memory_id);
        """
    )


def _restrict_file(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        path.chmod(0o600)
    except OSError as exc:
        raise RecallIndexUnavailableError(
            "memory lexical index file permissions could not be restricted"
        ) from exc


def _fsync_file(path: Path) -> None:
    flags = os.O_RDWR | cast(int, getattr(os, "O_BINARY", 0))
    try:
        descriptor = os.open(path, flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise RecallIndexUnavailableError("memory lexical index could not be synchronized") from exc


__all__ = [
    "MEMORY_LEXICAL_INDEX_ALGORITHM_ID",
    "MEMORY_LEXICAL_INDEX_ALGORITHM_VERSION",
    "MEMORY_LEXICAL_INDEX_QUERY_MODE",
    "MEMORY_LEXICAL_INDEX_RELATIVE_PATH",
    "MEMORY_LEXICAL_INDEX_SCHEMA_VERSION",
    "MemoryLexicalIndexHit",
    "MemoryLexicalIndexInspection",
    "MemoryLexicalIndexQueryReport",
    "RecallIndexCorruptError",
    "RecallIndexError",
    "RecallIndexLimitError",
    "RecallIndexStaleError",
    "RecallIndexUnavailableError",
    "RecallIndexUnsupportedError",
    "RecallIndexValidationError",
    "build_memory_lexical_index",
    "discard_memory_lexical_index",
    "inspect_memory_lexical_index",
    "memory_lexical_index_path",
    "query_memory_lexical_index",
]
