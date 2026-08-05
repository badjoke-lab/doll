"""Explicit bounded local CSV inspection and transformation."""

from __future__ import annotations

import csv
import hashlib
import io
import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

LOCAL_CSV_REPORT_SCHEMA_VERSION: Final = 1
LOCAL_CSV_ORIGIN_CLASS: Final = "external_content"
LOCAL_CSV_ACTOR_TYPE: Final = "extractor"
LOCAL_CSV_ACQUISITION_METHOD: Final = "extraction"
LOCAL_CSV_AUTHORITY_CLASS: Final = "untrusted_data"

_MAX_SOURCE_BYTES = 2_097_152
_MAX_ROWS = 10_000
_MAX_COLUMNS = 200
_MAX_CELL_CHARACTERS = 16_384
_MAX_AGGREGATE_CHARACTERS = 4_000_000
_MAX_PREVIEW_ROWS = 100
_MAX_RENAMES = 200
_UTF8_BOM = b"\xef\xbb\xbf"
_DELIMITERS: Final = {
    "comma": ",",
    "tab": "\t",
    "semicolon": ";",
    "pipe": "|",
}
_FORMULA_PREFIXES: Final = frozenset({"=", "+", "-", "@"})


class LocalCsvError(RuntimeError):
    """Base class for bounded local CSV failures."""


class LocalCsvValidationError(LocalCsvError):
    """Raised when CSV input or a transformation request is invalid."""


class LocalCsvReadError(LocalCsvError):
    """Raised when a selected CSV file cannot be read safely."""


@dataclass(frozen=True, slots=True)
class LocalCsvOrigin:
    """Fixed instruction-origin classification for local CSV cells."""

    origin_class: str = LOCAL_CSV_ORIGIN_CLASS
    actor_type: str = LOCAL_CSV_ACTOR_TYPE
    acquisition_method: str = LOCAL_CSV_ACQUISITION_METHOD
    authority_class: str = LOCAL_CSV_AUTHORITY_CLASS

    def to_dict(self) -> dict[str, str]:
        return {
            "origin_class": self.origin_class,
            "actor_type": self.actor_type,
            "acquisition_method": self.acquisition_method,
            "authority_class": self.authority_class,
        }


@dataclass(frozen=True, slots=True)
class LocalCsvTable:
    """One validated, bounded CSV table retained only for the current operation."""

    delimiter_profile: str
    delimiter: str
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    source_byte_count: int
    content_byte_count: int
    character_count: int
    source_sha256: str
    content_sha256: str
    utf8_bom_removed: bool
    blank_cell_count: int
    potential_formula_cell_count: int
    origin: LocalCsvOrigin = LocalCsvOrigin()

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def column_count(self) -> int:
        return len(self.headers)

    def metadata_dict(self) -> dict[str, object]:
        return {
            "schema_version": LOCAL_CSV_REPORT_SCHEMA_VERSION,
            "delimiter_profile": self.delimiter_profile,
            "headers": list(self.headers),
            "row_count": self.row_count,
            "column_count": self.column_count,
            "source_byte_count": self.source_byte_count,
            "content_byte_count": self.content_byte_count,
            "character_count": self.character_count,
            "source_sha256": self.source_sha256,
            "content_sha256": self.content_sha256,
            "utf8_bom_removed": self.utf8_bom_removed,
            "blank_cell_count": self.blank_cell_count,
            "potential_formula_cell_count": self.potential_formula_cell_count,
            "origin": self.origin.to_dict(),
            "source_persisted": False,
            "output_persisted": False,
            "workspace_mutated": False,
            "state_mutated": False,
            "formula_evaluation_used": False,
            "model_execution_used": False,
            "network_access_used": False,
        }


@dataclass(frozen=True, slots=True)
class LocalCsvInspection:
    """Deterministic bounded inspection of one local CSV table."""

    table: LocalCsvTable
    preview_rows: tuple[tuple[str, ...], ...]

    def to_dict(self) -> dict[str, object]:
        payload = self.table.metadata_dict()
        payload["preview_row_count"] = len(self.preview_rows)
        payload["preview_rows"] = [list(row) for row in self.preview_rows]
        return payload


@dataclass(frozen=True, slots=True)
class LocalCsvTransformation:
    """One deterministic non-persistent CSV column transformation."""

    source: LocalCsvTable
    selected_source_headers: tuple[str, ...]
    output_headers: tuple[str, ...]
    output_csv: str
    output_byte_count: int
    output_character_count: int
    output_sha256: str

    def to_dict(self, *, include_output: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": LOCAL_CSV_REPORT_SCHEMA_VERSION,
            "delimiter_profile": self.source.delimiter_profile,
            "selected_source_headers": list(self.selected_source_headers),
            "output_headers": list(self.output_headers),
            "row_count": self.source.row_count,
            "column_count": len(self.output_headers),
            "output_byte_count": self.output_byte_count,
            "output_character_count": self.output_character_count,
            "output_sha256": self.output_sha256,
            "origin": self.source.origin.to_dict(),
            "source_persisted": False,
            "output_persisted": False,
            "source_overwritten": False,
            "workspace_mutated": False,
            "state_mutated": False,
            "formula_evaluation_used": False,
            "model_execution_used": False,
            "network_access_used": False,
        }
        if include_output:
            payload["output_csv"] = self.output_csv
        return payload


@dataclass(frozen=True, slots=True)
class _FileState:
    device: int
    inode: int
    size: int
    modified_ns: int


def read_local_csv(path: Path, *, delimiter_profile: str = "comma") -> LocalCsvTable:
    """Read and validate one explicit local CSV file without persistence."""

    delimiter_name, delimiter = _delimiter(delimiter_profile)
    selected = Path(path)
    if selected.suffix.casefold() != ".csv":
        raise LocalCsvValidationError("local CSV input must use the .csv extension")

    before_path = _path_state(selected)
    if before_path.size > _MAX_SOURCE_BYTES:
        raise LocalCsvValidationError("local CSV exceeds the maximum byte size")

    try:
        with selected.open("rb") as source:
            before_handle = _handle_state(source.fileno())
            if not _same_identity(before_path, before_handle):
                raise LocalCsvReadError("local CSV changed before reading")
            raw = source.read(_MAX_SOURCE_BYTES + 1)
            after_handle = _handle_state(source.fileno())
    except LocalCsvError:
        raise
    except OSError as exc:
        raise LocalCsvReadError("local CSV could not be read") from exc

    if len(raw) > _MAX_SOURCE_BYTES:
        raise LocalCsvValidationError("local CSV exceeds the maximum byte size")
    after_path = _path_state(selected)
    if not _stable_read(before_path, before_handle, after_handle, after_path):
        raise LocalCsvReadError("local CSV changed while being read")

    bom_removed = raw.startswith(_UTF8_BOM)
    content_bytes = raw[len(_UTF8_BOM) :] if bom_removed else raw
    try:
        text = content_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise LocalCsvValidationError("local CSV is not valid UTF-8") from exc
    _validate_text(text)

    headers, rows, aggregate_characters = _parse_csv(text, delimiter)
    if aggregate_characters > _MAX_AGGREGATE_CHARACTERS:
        raise LocalCsvValidationError("local CSV exceeds the aggregate character limit")
    blank_count = sum(cell == "" for row in rows for cell in row)
    formula_count = sum(_potential_formula(cell) for row in rows for cell in row)
    return LocalCsvTable(
        delimiter_profile=delimiter_name,
        delimiter=delimiter,
        headers=headers,
        rows=rows,
        source_byte_count=len(raw),
        content_byte_count=len(content_bytes),
        character_count=len(text),
        source_sha256=hashlib.sha256(raw).hexdigest(),
        content_sha256=hashlib.sha256(content_bytes).hexdigest(),
        utf8_bom_removed=bom_removed,
        blank_cell_count=blank_count,
        potential_formula_cell_count=formula_count,
    )


def inspect_local_csv(
    path: Path,
    *,
    delimiter_profile: str = "comma",
    preview_rows: int = 10,
) -> LocalCsvInspection:
    """Inspect one bounded local CSV table."""

    if isinstance(preview_rows, bool) or not 0 <= preview_rows <= _MAX_PREVIEW_ROWS:
        raise LocalCsvValidationError("CSV preview rows must be between 0 and 100")
    table = read_local_csv(path, delimiter_profile=delimiter_profile)
    return LocalCsvInspection(table=table, preview_rows=table.rows[:preview_rows])


def transform_local_csv(
    path: Path,
    *,
    delimiter_profile: str = "comma",
    selected_columns: tuple[str, ...] = (),
    header_renames: Mapping[str, str] | None = None,
) -> LocalCsvTransformation:
    """Select, reorder, and rename CSV columns without writing a file."""

    table = read_local_csv(path, delimiter_profile=delimiter_profile)
    selected = _selected_headers(table.headers, selected_columns)
    renames = _validated_renames(selected, header_renames or {})
    output_headers = tuple(renames.get(header, header) for header in selected)
    indexes = tuple(table.headers.index(header) for header in selected)
    output_rows = tuple(tuple(row[index] for index in indexes) for row in table.rows)
    output_csv = _write_csv(output_headers, output_rows, table.delimiter)
    output_bytes = output_csv.encode("utf-8")
    return LocalCsvTransformation(
        source=table,
        selected_source_headers=selected,
        output_headers=output_headers,
        output_csv=output_csv,
        output_byte_count=len(output_bytes),
        output_character_count=len(output_csv),
        output_sha256=hashlib.sha256(output_bytes).hexdigest(),
    )


def parse_header_renames(values: tuple[str, ...]) -> dict[str, str]:
    """Parse exact OLD=NEW header-renaming options."""

    if len(values) > _MAX_RENAMES:
        raise LocalCsvValidationError("too many CSV header renames")
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise LocalCsvValidationError("CSV header rename must use OLD=NEW")
        source, target = value.split("=", 1)
        if not source or not target:
            raise LocalCsvValidationError("CSV header rename must use non-blank OLD=NEW")
        if source in result:
            raise LocalCsvValidationError("duplicate CSV header rename source")
        result[source] = target
    return result


def _parse_csv(
    text: str,
    delimiter: str,
) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...], int]:
    try:
        reader = csv.reader(
            io.StringIO(text, newline=""),
            delimiter=delimiter,
            strict=True,
        )
        parsed = list(reader)
    except csv.Error as exc:
        raise LocalCsvValidationError("local CSV syntax is invalid") from exc
    if not parsed:
        raise LocalCsvValidationError("local CSV must contain a header row")
    headers = tuple(parsed[0])
    _validate_headers(headers)
    if len(headers) > _MAX_COLUMNS:
        raise LocalCsvValidationError("local CSV exceeds the column limit")
    if len(parsed) - 1 > _MAX_ROWS:
        raise LocalCsvValidationError("local CSV exceeds the row limit")

    rows: list[tuple[str, ...]] = []
    aggregate = sum(len(header) for header in headers)
    for parsed_row in parsed[1:]:
        row = tuple(parsed_row)
        if len(row) != len(headers):
            raise LocalCsvValidationError("local CSV contains a non-rectangular row")
        for cell in row:
            if len(cell) > _MAX_CELL_CHARACTERS:
                raise LocalCsvValidationError("local CSV cell exceeds the character limit")
            aggregate += len(cell)
            if aggregate > _MAX_AGGREGATE_CHARACTERS:
                raise LocalCsvValidationError("local CSV exceeds the aggregate character limit")
        rows.append(row)
    return headers, tuple(rows), aggregate


def _validate_headers(headers: tuple[str, ...]) -> None:
    if not headers:
        raise LocalCsvValidationError("local CSV header row must not be empty")
    seen: set[str] = set()
    for header in headers:
        if not header.strip():
            raise LocalCsvValidationError("local CSV headers must not be blank")
        if len(header) > _MAX_CELL_CHARACTERS:
            raise LocalCsvValidationError("local CSV header exceeds the character limit")
        if header in seen:
            raise LocalCsvValidationError("local CSV headers must be unique")
        seen.add(header)


def _selected_headers(
    headers: tuple[str, ...],
    selected_columns: tuple[str, ...],
) -> tuple[str, ...]:
    if not selected_columns:
        return headers
    if len(selected_columns) > _MAX_COLUMNS:
        raise LocalCsvValidationError("too many selected CSV columns")
    if len(set(selected_columns)) != len(selected_columns):
        raise LocalCsvValidationError("selected CSV columns must be unique")
    unknown = tuple(column for column in selected_columns if column not in headers)
    if unknown:
        raise LocalCsvValidationError("selected CSV column does not exist")
    return selected_columns


def _validated_renames(
    selected_headers: tuple[str, ...],
    renames: Mapping[str, str],
) -> dict[str, str]:
    if len(renames) > _MAX_RENAMES:
        raise LocalCsvValidationError("too many CSV header renames")
    result: dict[str, str] = {}
    for source, target in renames.items():
        if source not in selected_headers:
            raise LocalCsvValidationError("CSV header rename source is not selected")
        if not target.strip():
            raise LocalCsvValidationError("CSV output headers must not be blank")
        if len(target) > _MAX_CELL_CHARACTERS:
            raise LocalCsvValidationError("CSV output header exceeds the character limit")
        result[source] = target
    output_headers = tuple(result.get(header, header) for header in selected_headers)
    if len(set(output_headers)) != len(output_headers):
        raise LocalCsvValidationError("CSV output headers must be unique")
    return result


def _write_csv(
    headers: tuple[str, ...],
    rows: tuple[tuple[str, ...], ...],
    delimiter: str,
) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=delimiter, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()


def _delimiter(value: str) -> tuple[str, str]:
    normalized = value.strip().casefold()
    delimiter = _DELIMITERS.get(normalized)
    if delimiter is None:
        raise LocalCsvValidationError("unsupported CSV delimiter profile")
    return normalized, delimiter


def _potential_formula(value: str) -> int:
    stripped = value.lstrip(" \t")
    return int(bool(stripped) and stripped[0] in _FORMULA_PREFIXES)


def _validate_text(text: str) -> None:
    if "\x00" in text:
        raise LocalCsvValidationError("local CSV contains a NUL byte")
    for character in text:
        codepoint = ord(character)
        if codepoint < 32 and character not in {"\n", "\r", "\t"}:
            raise LocalCsvValidationError("local CSV contains a prohibited control character")
        if codepoint == 127:
            raise LocalCsvValidationError("local CSV contains a prohibited control character")


def _path_state(path: Path) -> _FileState:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise LocalCsvReadError("local CSV is unavailable") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise LocalCsvValidationError("local CSV symlinks are not supported")
    if not stat.S_ISREG(metadata.st_mode):
        raise LocalCsvValidationError("local CSV must be a regular file")
    return _state_from_stat(metadata)


def _handle_state(file_descriptor: int) -> _FileState:
    try:
        metadata = os.fstat(file_descriptor)
    except OSError as exc:
        raise LocalCsvReadError("local CSV state could not be verified") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise LocalCsvValidationError("local CSV must be a regular file")
    return _state_from_stat(metadata)


def _state_from_stat(metadata: os.stat_result) -> _FileState:
    return _FileState(
        device=int(metadata.st_dev),
        inode=int(metadata.st_ino),
        size=int(metadata.st_size),
        modified_ns=int(metadata.st_mtime_ns),
    )


def _same_identity(left: _FileState, right: _FileState) -> bool:
    return left.device == right.device and left.inode == right.inode


def _stable_read(
    before_path: _FileState,
    before_handle: _FileState,
    after_handle: _FileState,
    after_path: _FileState,
) -> bool:
    states = (before_path, before_handle, after_handle, after_path)
    first = states[0]
    return all(
        _same_identity(first, current)
        and first.size == current.size
        and first.modified_ns == current.modified_ns
        for current in states[1:]
    )


__all__ = [
    "LOCAL_CSV_ACQUISITION_METHOD",
    "LOCAL_CSV_ACTOR_TYPE",
    "LOCAL_CSV_AUTHORITY_CLASS",
    "LOCAL_CSV_ORIGIN_CLASS",
    "LOCAL_CSV_REPORT_SCHEMA_VERSION",
    "LocalCsvError",
    "LocalCsvInspection",
    "LocalCsvOrigin",
    "LocalCsvReadError",
    "LocalCsvTable",
    "LocalCsvTransformation",
    "LocalCsvValidationError",
    "inspect_local_csv",
    "parse_header_renames",
    "read_local_csv",
    "transform_local_csv",
]
