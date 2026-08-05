"""Explicit deterministic read-only full-text search over local Doll State."""

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from doll.state import STATE_DATABASE_NAME, StateCorruptError, open_state_repository
from doll.state_repository import StateRepository
from doll.workspace import load_workspace

LOCAL_SEARCH_REPORT_SCHEMA_VERSION = 1
LOCAL_SEARCH_MODE = "unicode-nfkc-casefold-substring-and"

_MAX_QUERY_CHARS = 240
_MAX_QUERY_TERMS = 12
_MAX_RECORD_TYPE_CHARS = 128
_MAX_RESULTS = 100
_MAX_SCANNED_RECORDS = 10_000
_MAX_MATCHES_PER_HIT = 3
_MAX_SNIPPET_CHARS = 160
_MAX_FIELD_PATH_CHARS = 160
_RECORD_TYPE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,127}$")


class LocalSearchError(RuntimeError):
    """Base class for explicit local-search failures."""


class LocalSearchValidationError(LocalSearchError):
    """Raised when a caller supplies an invalid bounded search request."""


class LocalSearchUnavailableError(LocalSearchError):
    """Raised when immutable local state cannot be searched safely."""


@dataclass(frozen=True, slots=True)
class LocalSearchMatch:
    """One bounded textual field match within an authoritative record."""

    field_path: str
    snippet: str

    def to_dict(self) -> dict[str, object]:
        return {
            "field_path": self.field_path,
            "snippet": self.snippet,
        }


@dataclass(frozen=True, slots=True)
class LocalSearchHit:
    """One deterministic non-secret active-record search result."""

    record_id: str
    record_type: str
    sensitivity: str
    title: str | None
    matches: tuple[LocalSearchMatch, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "record_id": self.record_id,
            "record_type": self.record_type,
            "sensitivity": self.sensitivity,
            "title": self.title,
            "matches": [match.to_dict() for match in self.matches],
        }


@dataclass(frozen=True, slots=True)
class LocalSearchReport:
    """Content-bounded deterministic report for one explicit local query."""

    record_type_filter: str | None
    scanned_records: int
    scan_truncated: bool
    hits: tuple[LocalSearchHit, ...]

    @property
    def result_count(self) -> int:
        return len(self.hits)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": LOCAL_SEARCH_REPORT_SCHEMA_VERSION,
            "search_mode": LOCAL_SEARCH_MODE,
            "record_type_filter": self.record_type_filter,
            "scanned_records": self.scanned_records,
            "scan_truncated": self.scan_truncated,
            "result_count": self.result_count,
            "hits": [hit.to_dict() for hit in self.hits],
        }


def search_workspace(
    path: Path | None,
    query: str,
    *,
    record_type: str | None = None,
    limit: int = 20,
) -> LocalSearchReport:
    """Search one workspace through immutable read-only SQLite access."""

    workspace = load_workspace(path)
    database_path = workspace.root / "state" / STATE_DATABASE_NAME
    if _has_pending_sqlite_journal(database_path):
        raise LocalSearchUnavailableError(
            "authoritative state has an active SQLite journal; close active doll processes"
        )
    with open_state_repository(
        workspace.root,
        read_only=True,
        immutable=True,
    ) as repository:
        return search_local_state(
            repository,
            query,
            record_type=record_type,
            limit=limit,
        )


def search_local_state(
    repository: StateRepository,
    query: str,
    *,
    record_type: str | None = None,
    limit: int = 20,
) -> LocalSearchReport:
    """Search active non-secret records without mutation, models, tools, or network."""

    if not repository.read_only:
        raise LocalSearchValidationError("local search requires a read-only repository")
    terms = _validate_query(query)
    normalized_record_type = _validate_record_type(record_type)
    _validate_limit(limit)

    statement = """
        SELECT
            id,
            record_type,
            sensitivity,
            title,
            metadata_json,
            updated_at
        FROM records
        WHERE status = 'active'
          AND sensitivity <> 'secret'
    """
    parameters: list[object] = []
    if normalized_record_type is not None:
        statement += " AND record_type = ?"
        parameters.append(normalized_record_type)
    statement += " ORDER BY updated_at DESC, id ASC LIMIT ?"
    parameters.append(_MAX_SCANNED_RECORDS + 1)

    try:
        rows = repository.connection.execute(statement, parameters).fetchall()
    except sqlite3.DatabaseError as exc:
        raise StateCorruptError("authoritative records could not be searched") from exc

    scan_truncated = len(rows) > _MAX_SCANNED_RECORDS
    scanned_rows = rows[:_MAX_SCANNED_RECORDS]
    candidates: list[tuple[int, int, int, LocalSearchHit]] = []
    for row_index, row in enumerate(scanned_rows):
        hit, title_term_count, matched_field_count = _match_row(row, terms)
        if hit is not None:
            candidates.append(
                (
                    title_term_count,
                    matched_field_count,
                    row_index,
                    hit,
                )
            )

    candidates.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return LocalSearchReport(
        record_type_filter=normalized_record_type,
        scanned_records=len(scanned_rows),
        scan_truncated=scan_truncated,
        hits=tuple(item[3] for item in candidates[:limit]),
    )


def _match_row(
    row: sqlite3.Row,
    terms: tuple[str, ...],
) -> tuple[LocalSearchHit | None, int, int]:
    title = cast(str | None, row["title"])
    metadata = _load_metadata(cast(str, row["metadata_json"]))
    fields: list[tuple[str, str]] = []
    if title is not None:
        fields.append(("title", title))
    fields.extend(_iter_text_fields(metadata, "metadata"))

    matched_terms: set[str] = set()
    matches: list[LocalSearchMatch] = []
    title_term_count = 0
    for field_path, raw_text in fields:
        display_text = _normalize_display_text(raw_text)
        if not display_text:
            continue
        folded_text = display_text.casefold()
        field_terms = tuple(term for term in terms if term in folded_text)
        if not field_terms:
            continue
        matched_terms.update(field_terms)
        if field_path == "title":
            title_term_count = len(field_terms)
        matches.append(
            LocalSearchMatch(
                field_path=_bound_field_path(field_path),
                snippet=_make_snippet(display_text, field_terms),
            )
        )

    if any(term not in matched_terms for term in terms):
        return None, 0, 0
    matches.sort(key=lambda match: (match.field_path != "title", match.field_path))
    bounded_matches = tuple(matches[:_MAX_MATCHES_PER_HIT])
    return (
        LocalSearchHit(
            record_id=cast(str, row["id"]),
            record_type=cast(str, row["record_type"]),
            sensitivity=cast(str, row["sensitivity"]),
            title=title,
            matches=bounded_matches,
        ),
        title_term_count,
        len(matches),
    )


def _validate_query(query: str) -> tuple[str, ...]:
    if not isinstance(query, str):
        raise LocalSearchValidationError("search query must be text")
    if any(ord(character) < 32 or ord(character) == 127 for character in query):
        raise LocalSearchValidationError("search query contains a control character")
    normalized = _normalize_display_text(query)
    if not normalized:
        raise LocalSearchValidationError("search query must not be blank")
    if len(normalized) > _MAX_QUERY_CHARS:
        raise LocalSearchValidationError("search query exceeds the maximum length")
    raw_terms = normalized.split(" ")
    if len(raw_terms) > _MAX_QUERY_TERMS:
        raise LocalSearchValidationError("search query contains too many terms")
    return tuple(dict.fromkeys(term.casefold() for term in raw_terms))


def _validate_record_type(record_type: str | None) -> str | None:
    if record_type is None:
        return None
    normalized = record_type.strip().lower()
    if not normalized or len(normalized) > _MAX_RECORD_TYPE_CHARS:
        raise LocalSearchValidationError("record type filter is invalid")
    if _RECORD_TYPE_PATTERN.fullmatch(normalized) is None:
        raise LocalSearchValidationError("record type filter is invalid")
    return normalized


def _validate_limit(limit: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= _MAX_RESULTS:
        raise LocalSearchValidationError("search result limit must be between 1 and 100")


def _load_metadata(raw: str) -> dict[str, object]:
    try:
        value = json.loads(raw, parse_constant=_reject_nonstandard_json)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise StateCorruptError("record metadata is unreadable") from exc
    if not isinstance(value, dict):
        raise StateCorruptError("record metadata is not an object")
    return cast(dict[str, object], value)


def _iter_text_fields(value: object, path: str) -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
        return
    if isinstance(value, dict):
        for key in sorted(value):
            if not isinstance(key, str):
                continue
            component = _safe_field_component(key)
            yield from _iter_text_fields(value[key], f"{path}.{component}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            yield from _iter_text_fields(item, f"{path}[{index}]")


def _normalize_display_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.split())


def _make_snippet(value: str, terms: tuple[str, ...]) -> str:
    folded = value.casefold()
    starts = [position for term in terms if (position := folded.find(term)) >= 0]
    first = min(starts) if starts else 0
    start = max(0, first - 48)
    end = min(len(value), start + _MAX_SNIPPET_CHARS)
    if end - start < _MAX_SNIPPET_CHARS and start > 0:
        start = max(0, end - _MAX_SNIPPET_CHARS)
    snippet = value[start:end]
    if start > 0:
        snippet = f"…{snippet}"
    if end < len(value):
        snippet = f"{snippet}…"
    return snippet


def _safe_field_component(value: str) -> str:
    normalized = _normalize_display_text(
        "".join(
            "?" if ord(character) < 32 or ord(character) == 127 else character
            for character in value
        )
    )
    if not normalized:
        return "?"
    if len(normalized) > 48:
        return f"{normalized[:47]}…"
    return normalized


def _bound_field_path(value: str) -> str:
    if len(value) <= _MAX_FIELD_PATH_CHARS:
        return value
    return f"…{value[-(_MAX_FIELD_PATH_CHARS - 1) :]}"


def _has_pending_sqlite_journal(database_path: Path) -> bool:
    for suffix in ("-wal", "-journal"):
        candidate = Path(f"{database_path}{suffix}")
        try:
            if candidate.is_file() and candidate.stat().st_size > 0:
                return True
        except OSError:
            return True
    return False


def _reject_nonstandard_json(value: str) -> object:
    raise ValueError(f"non-standard JSON constant: {value}")


__all__ = [
    "LOCAL_SEARCH_MODE",
    "LOCAL_SEARCH_REPORT_SCHEMA_VERSION",
    "LocalSearchError",
    "LocalSearchHit",
    "LocalSearchMatch",
    "LocalSearchReport",
    "LocalSearchUnavailableError",
    "LocalSearchValidationError",
    "search_local_state",
    "search_workspace",
]
