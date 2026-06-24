"""Deterministic provider-independent export bundles for canonical conversations."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from uuid import UUID, uuid5

from doll.portability import PortabilityContractError
from doll.portability_records import ExportBatchRecord, MappingReportRecord
from doll.state import ConversationEventRecord, ConversationRecord
from doll.workspace_files import (
    DEFAULT_MAX_ARTIFACT_BYTES,
    PublishedWorkspaceFile,
    publish_new_workspace_file,
    validate_managed_path,
)

_GENERIC_EXPORT_FORMAT = "doll-generic-export"
_GENERIC_EXPORT_VERSION = "1"
_DEFAULT_ADAPTER_ID = "doll-generic-export"
_DEFAULT_ADAPTER_VERSION = "1"
_MAX_OBJECT_COUNT = 100_000
_MAX_TOTAL_BYTES = 64 * 1024 * 1024
_MAX_MARKDOWN_BYTES = 16 * 1024 * 1024
_FILE_ORDER = (
    "manifest.json",
    "records.json",
    "records.jsonl",
    "transcript.md",
    "checksums.sha256",
)
_PAYLOAD_FILES = ("records.json", "records.jsonl", "transcript.md")
_MEDIA_TYPES = {
    "manifest.json": "application/json",
    "records.json": "application/json",
    "records.jsonl": "application/x-ndjson",
    "transcript.md": "text/markdown; charset=utf-8",
    "checksums.sha256": "text/plain; charset=utf-8",
}
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+\-]{0,127}$")


class GenericExportError(PortabilityContractError):
    """Raised when canonical records cannot produce a safe generic export."""


@dataclass(frozen=True, slots=True)
class GenericExportFile:
    """One immutable generated file in a generic export bundle."""

    name: str
    media_type: str
    content: bytes
    sha256: str

    @property
    def size_bytes(self) -> int:
        return len(self.content)

    def canonical_metadata(self) -> dict[str, object]:
        return {
            "name": self.name,
            "media_type": self.media_type,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class GenericExportBundle:
    """Complete deterministic in-memory export result."""

    export_batch: ExportBatchRecord
    mapping_report: MappingReportRecord
    files: tuple[GenericExportFile, ...]

    def __post_init__(self) -> None:
        names = tuple(item.name for item in self.files)
        if names != _FILE_ORDER:
            raise GenericExportError("generic export file ordering is invalid")
        if len(names) != len(set(names)):
            raise GenericExportError("generic export file names contain duplicates")

    def file(self, name: str) -> GenericExportFile:
        for item in self.files:
            if item.name == name:
                return item
        raise KeyError(name)

    def canonical_summary(self) -> dict[str, object]:
        return {
            "export_batch_id": self.export_batch.export_batch_id,
            "export_batch": self.export_batch.canonical_metadata(),
            "mapping_report_id": self.mapping_report.mapping_report_id,
            "mapping_report": self.mapping_report.canonical_metadata(),
            "files": [item.canonical_metadata() for item in self.files],
        }


@dataclass(frozen=True, slots=True)
class ManagedGenericExportFile:
    """One generated export file published below the workspace artifacts root."""

    name: str
    managed_path: str
    size_bytes: int
    content_hash: str


@dataclass(frozen=True, slots=True)
class ManagedGenericExport:
    """Immutable metadata for a successfully published generic export bundle."""

    export_batch_id: str
    managed_prefix: str
    files: tuple[ManagedGenericExportFile, ...]


@dataclass(frozen=True, slots=True)
class GenericExportBuilder:
    """Build and optionally publish deterministic generic conversation exports."""

    target_adapter_id: str = _DEFAULT_ADAPTER_ID
    target_adapter_version: str = _DEFAULT_ADAPTER_VERSION
    max_object_count: int = _MAX_OBJECT_COUNT
    max_file_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES
    max_total_bytes: int = _MAX_TOTAL_BYTES
    max_markdown_bytes: int = _MAX_MARKDOWN_BYTES

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "target_adapter_id",
            _validate_identifier("target adapter id", self.target_adapter_id),
        )
        object.__setattr__(
            self,
            "target_adapter_version",
            _validate_version("target adapter version", self.target_adapter_version),
        )
        for name, value, maximum in (
            ("object count limit", self.max_object_count, _MAX_OBJECT_COUNT),
            ("file byte limit", self.max_file_bytes, DEFAULT_MAX_ARTIFACT_BYTES),
            ("total byte limit", self.max_total_bytes, _MAX_TOTAL_BYTES),
            ("Markdown byte limit", self.max_markdown_bytes, _MAX_MARKDOWN_BYTES),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
                raise GenericExportError(f"{name} is outside the supported range")

    def build(
        self,
        conversations: Sequence[ConversationRecord],
        events: Sequence[ConversationEventRecord],
        *,
        export_batch_id: str,
        started_at: str,
        completed_at: str,
    ) -> GenericExportBundle:
        """Return byte-identical files for equivalent canonical input and context."""

        batch_uuid = _canonical_uuid("export batch id", export_batch_id)
        canonical_conversations, canonical_events = _validate_graph(
            conversations,
            events,
            max_object_count=self.max_object_count,
        )
        records = _canonical_records(canonical_conversations, canonical_events)
        selected_record_types: tuple[str, ...] = ("conversation",)
        if canonical_events:
            selected_record_types = ("conversation", "conversation-event")

        mapping_report_id = str(uuid5(UUID(batch_uuid), "mapping-report"))
        mapping_report = MappingReportRecord(
            mapping_report_id=mapping_report_id,
            direction="export",
            batch_id=batch_uuid,
            generated_at=completed_at,
            total_object_count=len(records),
            mapped_without_known_loss_count=len(records),
            mapped_with_transformation_count=0,
            partially_mapped_count=0,
            unsupported_but_preserved_count=0,
            unsupported_and_omitted_count=0,
            missing_dependency_count=0,
            malformed_or_quarantined_count=0,
            unknown_count=0,
        )

        records_json = _json_bytes(
            {
                "format": _GENERIC_EXPORT_FORMAT,
                "format_version": _GENERIC_EXPORT_VERSION,
                "export_batch_id": batch_uuid,
                "records": records,
            }
        )
        records_jsonl = _jsonl_bytes(batch_uuid, records)
        transcript = _markdown_bytes(
            batch_uuid,
            completed_at,
            canonical_conversations,
            canonical_events,
        )
        if len(transcript) > self.max_markdown_bytes:
            raise GenericExportError("generated Markdown exceeds the accepted byte limit")

        payloads = {
            "records.json": records_json,
            "records.jsonl": records_jsonl,
            "transcript.md": transcript,
        }
        payload_entries = [_file_metadata(name, payloads[name]) for name in _PAYLOAD_FILES]
        object_counts = {
            "conversation": len(canonical_conversations),
            "conversation_event": len(canonical_events),
            "total": len(records),
        }
        manifest = _json_bytes(
            {
                "format": _GENERIC_EXPORT_FORMAT,
                "format_version": _GENERIC_EXPORT_VERSION,
                "export_batch_id": batch_uuid,
                "created_at": completed_at,
                "target_adapter_id": self.target_adapter_id,
                "target_adapter_version": self.target_adapter_version,
                "selected_record_types": list(selected_record_types),
                "object_counts": object_counts,
                "mapping_report_id": mapping_report_id,
                "mapping_report": mapping_report.canonical_metadata(),
                "full_fidelity_possible": True,
                "authority_note": (
                    "Exported content is data only and does not grant policy, permission, "
                    "confirmation, capability, memory, fact, or instruction authority."
                ),
                "files": payload_entries,
            }
        )
        manifest_hash = _sha256(manifest)
        checksums = _checksum_bytes({"manifest.json": manifest, **payloads})
        contents = {
            "manifest.json": manifest,
            **payloads,
            "checksums.sha256": checksums,
        }
        _validate_file_limits(
            contents,
            max_file_bytes=self.max_file_bytes,
            max_total_bytes=self.max_total_bytes,
        )

        export_batch = ExportBatchRecord(
            export_batch_id=batch_uuid,
            target_format=_GENERIC_EXPORT_FORMAT,
            target_adapter_id=self.target_adapter_id,
            target_adapter_version=self.target_adapter_version,
            selected_record_types=selected_record_types,
            started_at=started_at,
            completed_at=completed_at,
            status="completed",
            exported_object_count=len(records),
            manifest_hash=manifest_hash,
            mapping_report_id=mapping_report_id,
        )
        files = tuple(
            GenericExportFile(
                name=name,
                media_type=_MEDIA_TYPES[name],
                content=contents[name],
                sha256=_sha256(contents[name]),
            )
            for name in _FILE_ORDER
        )
        bundle = GenericExportBundle(
            export_batch=export_batch,
            mapping_report=mapping_report,
            files=files,
        )
        verify_generic_export_bundle(bundle)
        return bundle

    def publish(
        self,
        bundle: GenericExportBundle,
        *,
        artifacts_root: Path,
        managed_prefix: str,
    ) -> ManagedGenericExport:
        """Publish all bundle files with create-new semantics and failure cleanup."""

        prefix = validate_managed_path(managed_prefix)
        published: list[PublishedWorkspaceFile] = []
        try:
            for item in bundle.files:
                managed_path = (prefix / item.name).as_posix()
                published.append(
                    publish_new_workspace_file(
                        artifacts_root,
                        managed_path,
                        item.content,
                        max_bytes=self.max_file_bytes,
                    )
                )
        except BaseException:
            cleanup_error: BaseException | None = None
            for published_item in reversed(published):
                try:
                    published_item.cleanup()
                except BaseException as exc:  # pragma: no cover - defensive OS failure
                    cleanup_error = cleanup_error or exc
            if cleanup_error is not None:
                raise GenericExportError(
                    "generic export publication failed and cleanup was incomplete"
                ) from cleanup_error
            raise

        result_files = tuple(
            ManagedGenericExportFile(
                name=bundle_file.name,
                managed_path=published_file.managed_path,
                size_bytes=published_file.size_bytes,
                content_hash=published_file.content_hash,
            )
            for bundle_file, published_file in zip(bundle.files, published, strict=True)
        )
        for published_item in published:
            published_item.close()
        return ManagedGenericExport(
            export_batch_id=bundle.export_batch.export_batch_id,
            managed_prefix=prefix.as_posix(),
            files=result_files,
        )


def verify_generic_export_bundle(bundle: GenericExportBundle) -> None:
    """Fail closed if generated files disagree with their manifest or checksums."""

    files = {item.name: item for item in bundle.files}
    if tuple(files) != _FILE_ORDER:
        raise GenericExportError("generic export file set is invalid")
    for item in files.values():
        if not _SHA256_PATTERN.fullmatch(item.sha256) or item.sha256 != _sha256(item.content):
            raise GenericExportError("generic export file digest is invalid")

    checksums = _parse_checksums(files["checksums.sha256"].content)
    expected_checksum_names = {"manifest.json", *_PAYLOAD_FILES}
    if set(checksums) != expected_checksum_names:
        raise GenericExportError("checksum declarations are incomplete")
    for name, digest in checksums.items():
        if digest != files[name].sha256:
            raise GenericExportError("checksum declaration does not match file content")

    manifest = _load_json_object(files["manifest.json"].content, "manifest")
    if manifest.get("format") != _GENERIC_EXPORT_FORMAT:
        raise GenericExportError("manifest format is invalid")
    if manifest.get("format_version") != _GENERIC_EXPORT_VERSION:
        raise GenericExportError("manifest version is invalid")
    if manifest.get("export_batch_id") != bundle.export_batch.export_batch_id:
        raise GenericExportError("manifest export batch identifier is invalid")
    if bundle.export_batch.manifest_hash != files["manifest.json"].sha256:
        raise GenericExportError("export batch manifest hash is invalid")

    declared_files = manifest.get("files")
    if not isinstance(declared_files, list):
        raise GenericExportError("manifest file declarations are invalid")
    expected_entries = [_file_metadata(name, files[name].content) for name in _PAYLOAD_FILES]
    if declared_files != expected_entries:
        raise GenericExportError("manifest file declarations do not match payloads")

    records_document = _load_json_object(files["records.json"].content, "records JSON")
    records = records_document.get("records")
    if not isinstance(records, list):
        raise GenericExportError("records JSON records are invalid")
    jsonl_records = _parse_jsonl_records(
        files["records.jsonl"].content, bundle.export_batch.export_batch_id
    )
    if records != jsonl_records:
        raise GenericExportError("JSON and JSONL records differ")


def _validate_graph(
    conversations: Sequence[ConversationRecord],
    events: Sequence[ConversationEventRecord],
    *,
    max_object_count: int,
) -> tuple[tuple[ConversationRecord, ...], tuple[ConversationEventRecord, ...]]:
    if isinstance(conversations, (str, bytes)) or isinstance(events, (str, bytes)):
        raise GenericExportError("generic export inputs must be record sequences")
    conversation_values = tuple(conversations)
    event_values = tuple(events)
    if not conversation_values:
        raise GenericExportError("generic export requires at least one conversation")
    if len(conversation_values) + len(event_values) > max_object_count:
        raise GenericExportError("generic export object count exceeds the accepted limit")
    if any(not isinstance(item, ConversationRecord) for item in conversation_values):
        raise GenericExportError("generic export contains an invalid conversation record")
    if any(not isinstance(item, ConversationEventRecord) for item in event_values):
        raise GenericExportError("generic export contains an invalid conversation event record")

    conversation_by_id = _unique_by_id(
        conversation_values,
        lambda item: item.conversation_id,
        "conversation",
    )
    event_by_id = _unique_by_id(event_values, lambda item: item.event_id, "conversation event")
    if set(conversation_by_id) & set(event_by_id):
        raise GenericExportError("conversation and event identifiers must be globally distinct")

    for event in event_by_id.values():
        if event.conversation_id not in conversation_by_id:
            raise GenericExportError("conversation event references an unavailable conversation")
        for parent_id in event.parent_event_ids:
            parent = event_by_id.get(parent_id)
            if parent is None:
                raise GenericExportError("conversation event parent is unavailable")
            if parent.conversation_id != event.conversation_id:
                raise GenericExportError(
                    "conversation event parent belongs to another conversation"
                )
    _reject_event_cycles(event_by_id)
    return (
        tuple(conversation_by_id[key] for key in sorted(conversation_by_id)),
        tuple(event_by_id[key] for key in sorted(event_by_id)),
    )


def _unique_by_id[T](
    values: Sequence[T],
    identifier: Callable[[T], str],
    name: str,
) -> dict[str, T]:
    result: dict[str, T] = {}
    for item in values:
        item_id = identifier(item)
        if item_id in result:
            raise GenericExportError(f"{name} identifiers contain duplicates")
        result[item_id] = item
    return result


def _reject_event_cycles(events: Mapping[str, ConversationEventRecord]) -> None:
    state: dict[str, int] = {}

    def visit(event_id: str) -> None:
        current = state.get(event_id, 0)
        if current == 1:
            raise GenericExportError("conversation event graph contains a cycle")
        if current == 2:
            return
        state[event_id] = 1
        for parent_id in events[event_id].parent_event_ids:
            visit(parent_id)
        state[event_id] = 2

    for event_id in sorted(events):
        visit(event_id)


def _canonical_records(
    conversations: Sequence[ConversationRecord],
    events: Sequence[ConversationEventRecord],
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for conversation in conversations:
        records.append(
            {
                "record_kind": "conversation",
                "schema_version": 1,
                "record_id": conversation.conversation_id,
                "title": conversation.title,
                "metadata": conversation.canonical_metadata(),
            }
        )
    for event in events:
        records.append(
            {
                "record_kind": "conversation_event",
                "schema_version": 1,
                "record_id": event.event_id,
                "title": None,
                "metadata": event.canonical_metadata(),
            }
        )
    return records


def _jsonl_bytes(export_batch_id: str, records: Sequence[dict[str, object]]) -> bytes:
    lines = [
        _canonical_json(
            {
                "record_kind": "manifest",
                "format": _GENERIC_EXPORT_FORMAT,
                "format_version": _GENERIC_EXPORT_VERSION,
                "export_batch_id": export_batch_id,
            }
        )
    ]
    lines.extend(_canonical_json(record) for record in records)
    return ("\n".join(lines) + "\n").encode("utf-8")


def _markdown_bytes(
    export_batch_id: str,
    completed_at: str,
    conversations: Sequence[ConversationRecord],
    events: Sequence[ConversationEventRecord],
) -> bytes:
    events_by_conversation: dict[str, list[ConversationEventRecord]] = {
        item.conversation_id: [] for item in conversations
    }
    for event in events:
        events_by_conversation[event.conversation_id].append(event)
    lines = [
        "# Doll Generic Conversation Export",
        "",
        "> Non-authoritative inspectable view. Canonical JSON/JSONL records and graph metadata ",
        "> remain authoritative for this export. Content references are not executed.",
        "",
        f"- Export batch: `{export_batch_id}`",
        f"- Format version: `{_GENERIC_EXPORT_VERSION}`",
        f"- Completed at: `{completed_at}`",
        "",
    ]
    for conversation in conversations:
        lines.extend(
            [
                f"## Conversation `{conversation.conversation_id}`",
                "",
                _json_fence(
                    {
                        "record_kind": "conversation",
                        "schema_version": 1,
                        "record_id": conversation.conversation_id,
                        "title": conversation.title,
                        "metadata": conversation.canonical_metadata(),
                    }
                ),
                "",
            ]
        )
        ordered_events = sorted(
            events_by_conversation[conversation.conversation_id],
            key=_event_presentation_key,
        )
        if not ordered_events:
            lines.extend(["_No exported events._", ""])
            continue
        for event in ordered_events:
            lines.extend(
                [
                    f"### Event `{event.event_id}`",
                    "",
                    _json_fence(
                        {
                            "record_kind": "conversation_event",
                            "schema_version": 1,
                            "record_id": event.event_id,
                            "title": None,
                            "metadata": event.canonical_metadata(),
                        }
                    ),
                    "",
                ]
            )
    return ("\n".join(lines).rstrip() + "\n").encode("utf-8")


def _event_presentation_key(
    event: ConversationEventRecord,
) -> tuple[int, int, str, str]:
    return (
        1 if event.sequence_hint is None else 0,
        event.sequence_hint or 0,
        event.occurred_at or "",
        event.event_id,
    )


def _json_fence(value: object) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
    maximum_run = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, maximum_run + 1)
    return f"{fence}json\n{text}\n{fence}"


def _file_metadata(name: str, content: bytes) -> dict[str, object]:
    return {
        "name": name,
        "media_type": _MEDIA_TYPES[name],
        "size_bytes": len(content),
        "sha256": _sha256(content),
    }


def _checksum_bytes(files: Mapping[str, bytes]) -> bytes:
    lines = [f"{_sha256(files[name])}  {name}" for name in sorted(files)]
    return ("\n".join(lines) + "\n").encode("ascii")


def _parse_checksums(content: bytes) -> dict[str, str]:
    try:
        text = content.decode("ascii", errors="strict")
    except UnicodeDecodeError as exc:
        raise GenericExportError("checksum file is not ASCII") from exc
    result: dict[str, str] = {}
    for line in text.splitlines():
        if not line:
            continue
        digest, separator, name = line.partition("  ")
        if (
            not separator
            or not _SHA256_PATTERN.fullmatch(digest)
            or name
            not in {
                "manifest.json",
                *_PAYLOAD_FILES,
            }
        ):
            raise GenericExportError("checksum declaration is invalid")
        if name in result:
            raise GenericExportError("checksum declarations contain duplicates")
        result[name] = digest
    return result


def _parse_jsonl_records(content: bytes, export_batch_id: str) -> list[object]:
    try:
        lines = content.decode("utf-8", errors="strict").splitlines()
    except UnicodeDecodeError as exc:
        raise GenericExportError("records JSONL is not valid UTF-8") from exc
    if not lines:
        raise GenericExportError("records JSONL is empty")
    manifest = _load_json_text(lines[0], "records JSONL manifest")
    if not isinstance(manifest, dict) or manifest != {
        "record_kind": "manifest",
        "format": _GENERIC_EXPORT_FORMAT,
        "format_version": _GENERIC_EXPORT_VERSION,
        "export_batch_id": export_batch_id,
    }:
        raise GenericExportError("records JSONL manifest is invalid")
    return [_load_json_text(line, "records JSONL record") for line in lines[1:]]


def _load_json_object(content: bytes, name: str) -> dict[str, object]:
    try:
        text = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise GenericExportError(f"{name} is not valid UTF-8") from exc
    value = _load_json_text(text, name)
    if not isinstance(value, dict):
        raise GenericExportError(f"{name} must be an object")
    return cast(dict[str, object], value)


def _load_json_text(text: str, name: str) -> object:
    try:
        return cast(object, json.loads(text, parse_constant=_reject_json_constant))
    except (json.JSONDecodeError, ValueError) as exc:
        raise GenericExportError(f"{name} is invalid") from exc


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"non-standard JSON constant: {value}")


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise GenericExportError("generic export value is not canonical JSON") from exc


def _json_bytes(value: object) -> bytes:
    return (_canonical_json(value) + "\n").encode("utf-8")


def _canonical_uuid(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise GenericExportError(f"{name} must be text")
    try:
        canonical = str(UUID(value))
    except (ValueError, AttributeError) as exc:
        raise GenericExportError(f"{name} is invalid") from exc
    if canonical != value:
        raise GenericExportError(f"{name} must use canonical UUID text")
    return canonical


def _validate_identifier(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise GenericExportError(f"{name} must be text")
    normalized = value.strip().lower()
    if not _IDENTIFIER_PATTERN.fullmatch(normalized):
        raise GenericExportError(f"{name} is invalid")
    return normalized


def _validate_version(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise GenericExportError(f"{name} must be text")
    normalized = value.strip()
    if not _VERSION_PATTERN.fullmatch(normalized):
        raise GenericExportError(f"{name} is invalid")
    return normalized


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _validate_file_limits(
    files: Mapping[str, bytes],
    *,
    max_file_bytes: int,
    max_total_bytes: int,
) -> None:
    if any(len(content) > max_file_bytes for content in files.values()):
        raise GenericExportError("generated export file exceeds the accepted byte limit")
    if sum(len(content) for content in files.values()) > max_total_bytes:
        raise GenericExportError("generated export exceeds the accepted total byte limit")


__all__ = [
    "GenericExportBuilder",
    "GenericExportBundle",
    "GenericExportError",
    "GenericExportFile",
    "ManagedGenericExport",
    "ManagedGenericExportFile",
    "verify_generic_export_bundle",
]
