"""Sequential private-manual projection for numbered ChatGPT conversation members."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from doll.chatgpt_export_import import (
    ChatGPTExportImportError,
    _conversation_identity,
    _inventory_conversation,
    _json_depth,
    _load_root,
    _selected_ids,
)
from doll.chatgpt_numbered_aggregation import (
    ChatGPTNumberedAggregationError,
    ChatGPTNumberedMemberManifest,
)

_MEMBER_PATTERN = re.compile(r"^conversations-(?P<index>[0-9]+)\.json$")
_AGGREGATION_FORMAT = "chatgpt-numbered-conversation-members"
_AGGREGATION_VERSION = "1"
_READ_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True, slots=True)
class ChatGPTNumberedPathMember:
    """One explicit numbered member path with a privacy-safe basename label."""

    label: str
    path: Path


@dataclass(frozen=True, slots=True)
class ChatGPTNumberedProjectionResult:
    """Content-free full-set evidence plus bounded selected projection bytes."""

    selected_projection_bytes: bytes
    selected_projection_sha256: str
    aggregate_source_hash: str
    member_set_root_hash: str
    members: tuple[ChatGPTNumberedMemberManifest, ...]
    input_conversation_count: int
    output_conversation_count: int
    exact_duplicate_conversation_count: int
    identity_quarantine_count: int
    identity_quarantine_member_count: int
    aggregate_node_count: int
    aggregate_message_count: int
    aggregate_attachment_reference_count: int
    aggregate_malformed_object_count: int
    aggregate_unknown_field_count: int

    def canonical_summary(self) -> dict[str, object]:
        return {
            "aggregation_format": _AGGREGATION_FORMAT,
            "aggregation_version": _AGGREGATION_VERSION,
            "processing_mode": "sequential-member-selected-projection",
            "aggregate_hash_scope": "identity-valid-first-unique-conversations",
            "aggregate_source_hash": self.aggregate_source_hash,
            "member_set_root_hash": self.member_set_root_hash,
            "member_count": len(self.members),
            "members": [member.canonical_summary() for member in self.members],
            "input_conversation_count": self.input_conversation_count,
            "output_conversation_count": self.output_conversation_count,
            "exact_duplicate_conversation_count": self.exact_duplicate_conversation_count,
            "identity_quarantine_count": self.identity_quarantine_count,
            "identity_quarantine_member_count": self.identity_quarantine_member_count,
            "aggregate_node_count": self.aggregate_node_count,
            "aggregate_message_count": self.aggregate_message_count,
            "aggregate_attachment_reference_count": self.aggregate_attachment_reference_count,
            "aggregate_malformed_object_count": self.aggregate_malformed_object_count,
            "aggregate_unknown_field_count": self.aggregate_unknown_field_count,
            "selected_projection_byte_count": len(self.selected_projection_bytes),
            "selected_projection_sha256": self.selected_projection_sha256,
        }


@dataclass(frozen=True, slots=True)
class _StoredIdentity:
    canonical_sha256: bytes
    offset: int
    byte_count: int


@dataclass(frozen=True, slots=True)
class ChatGPTNumberedSequentialProjector:
    """Validate numbered members sequentially and materialize only a selected projection."""

    max_member_count: int = 128
    max_total_input_bytes: int = 1024 * 1024 * 1024
    max_conversation_count: int = 1_000_000
    max_nesting_depth: int = 96
    max_selected_projection_bytes: int = 16 * 1024 * 1024

    def project(
        self,
        members: tuple[ChatGPTNumberedPathMember, ...],
        selected_conversation_ids: tuple[str, ...],
    ) -> ChatGPTNumberedProjectionResult:
        selected = _selected_ids(selected_conversation_ids)
        ordered = self._ordered_members(members)

        aggregate_hasher = hashlib.sha256()
        aggregate_hasher.update(b"[")
        aggregate_started = False
        selected_parts: list[bytes] = []
        selected_projection_size = 2
        found: set[str] = set()
        identities: dict[str, _StoredIdentity] = {}
        manifests: list[ChatGPTNumberedMemberManifest] = []
        stable_members: list[tuple[Path, int, str]] = []
        total_bytes = 0
        input_count = 0
        output_count = 0
        duplicate_count = 0
        identity_quarantine_count = 0
        identity_quarantine_member_indices: set[int] = set()
        aggregate_node_count = 0
        aggregate_message_count = 0
        aggregate_attachment_count = 0
        aggregate_malformed_count = 0
        aggregate_unknown_count = 0
        write_offset = 0

        with tempfile.TemporaryFile(prefix="doll-imp060-canonical-") as canonical_store:
            for index, member in ordered:
                source_bytes = member.path.read_bytes()
                total_bytes += len(source_bytes)
                if total_bytes > self.max_total_input_bytes:
                    raise ChatGPTNumberedAggregationError(
                        "aggregate numbered input exceeds byte limit"
                    )
                member_sha256 = hashlib.sha256(source_bytes).hexdigest()
                try:
                    root = _load_root(source_bytes)
                    depth = _json_depth(root)
                except (ChatGPTExportImportError, RecursionError) as exc:
                    raise ChatGPTNumberedAggregationError(
                        "numbered member is not a supported JSON conversation list"
                    ) from exc
                if depth > self.max_nesting_depth:
                    raise ChatGPTNumberedAggregationError("numbered member nesting exceeds limit")
                input_count += len(root)
                if input_count > self.max_conversation_count:
                    raise ChatGPTNumberedAggregationError(
                        "aggregate conversation count exceeds limit"
                    )

                manifests.append(
                    ChatGPTNumberedMemberManifest(
                        label=member.label,
                        index=index,
                        byte_count=len(source_bytes),
                        conversation_count=len(root),
                        sha256=member_sha256,
                    )
                )
                stable_members.append((member.path, len(source_bytes), member_sha256))

                for item_index, raw_conversation in enumerate(root):
                    try:
                        conversation, conversation_id = _conversation_identity(
                            raw_conversation,
                            item_index,
                        )
                    except ChatGPTExportImportError as exc:
                        if _is_identityless_conversation(raw_conversation):
                            identity_quarantine_count += 1
                            identity_quarantine_member_indices.add(index)
                            continue

                        raise ChatGPTNumberedAggregationError(
                            "numbered member contains an invalid conversation identity"
                        ) from exc
                    canonical = _canonical_conversation(conversation)
                    canonical_sha256 = hashlib.sha256(canonical).digest()
                    previous = identities.get(conversation_id)
                    if previous is not None:
                        if (
                            previous.canonical_sha256 != canonical_sha256
                            or previous.byte_count != len(canonical)
                            or not _stored_bytes_equal(canonical_store, previous, canonical)
                        ):
                            raise ChatGPTNumberedAggregationError(
                                "conflicting duplicate conversation identity "
                                "across numbered members"
                            )
                        duplicate_count += 1
                        continue

                    canonical_store.seek(write_offset)
                    canonical_store.write(canonical)
                    identities[conversation_id] = _StoredIdentity(
                        canonical_sha256=canonical_sha256,
                        offset=write_offset,
                        byte_count=len(canonical),
                    )
                    write_offset += len(canonical)

                    if aggregate_started:
                        aggregate_hasher.update(b",")
                    aggregate_hasher.update(canonical)
                    aggregate_started = True
                    output_count += 1

                    counts = _inventory_conversation(conversation)
                    aggregate_node_count += counts.node_count
                    aggregate_message_count += counts.message_count
                    aggregate_attachment_count += counts.attachment_reference_count
                    aggregate_malformed_count += counts.malformed_object_count
                    aggregate_unknown_count += counts.unknown_field_count

                    if conversation_id in selected:
                        additional = len(canonical) + (1 if selected_parts else 0)
                        if (
                            selected_projection_size + additional
                            > self.max_selected_projection_bytes
                        ):
                            raise ChatGPTNumberedAggregationError(
                                "selected projection exceeds adapter byte limit"
                            )
                        selected_parts.append(canonical)
                        selected_projection_size += additional
                        found.add(conversation_id)

                del root
                del source_bytes

            missing = selected - found
            if missing:
                raise ChatGPTNumberedAggregationError(
                    "one or more selected conversation ids were not found"
                )

        for path, expected_size, expected_sha256 in stable_members:
            actual_size, actual_sha256 = _hash_path(path)
            if actual_size != expected_size or actual_sha256 != expected_sha256:
                raise ChatGPTNumberedAggregationError(
                    "numbered member changed during sequential projection"
                )

        aggregate_hasher.update(b"]")
        aggregate_source_hash = aggregate_hasher.hexdigest()
        selected_projection_bytes = b"[" + b",".join(selected_parts) + b"]"
        selected_projection_sha256 = hashlib.sha256(selected_projection_bytes).hexdigest()
        member_set_payload = {
            "aggregation_format": _AGGREGATION_FORMAT,
            "aggregation_version": _AGGREGATION_VERSION,
            "members": [member.canonical_summary() for member in manifests],
        }
        member_set_root_hash = hashlib.sha256(
            json.dumps(
                member_set_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()

        return ChatGPTNumberedProjectionResult(
            selected_projection_bytes=selected_projection_bytes,
            selected_projection_sha256=selected_projection_sha256,
            aggregate_source_hash=aggregate_source_hash,
            member_set_root_hash=member_set_root_hash,
            members=tuple(manifests),
            input_conversation_count=input_count,
            output_conversation_count=output_count,
            exact_duplicate_conversation_count=duplicate_count,
            identity_quarantine_count=identity_quarantine_count,
            identity_quarantine_member_count=len(identity_quarantine_member_indices),
            aggregate_node_count=aggregate_node_count,
            aggregate_message_count=aggregate_message_count,
            aggregate_attachment_reference_count=aggregate_attachment_count,
            aggregate_malformed_object_count=aggregate_malformed_count,
            aggregate_unknown_field_count=aggregate_unknown_count,
        )

    def _ordered_members(
        self,
        members: tuple[ChatGPTNumberedPathMember, ...],
    ) -> list[tuple[int, ChatGPTNumberedPathMember]]:
        if not isinstance(members, tuple) or not members:
            raise ChatGPTNumberedAggregationError("numbered path members must be a non-empty tuple")
        if len(members) > self.max_member_count:
            raise ChatGPTNumberedAggregationError("numbered member count exceeds limit")

        parsed: list[tuple[int, ChatGPTNumberedPathMember]] = []
        labels: set[str] = set()
        indices: set[int] = set()
        paths: set[Path] = set()
        declared_total_bytes = 0
        for member in members:
            if not isinstance(member, ChatGPTNumberedPathMember):
                raise ChatGPTNumberedAggregationError("numbered path member type is invalid")
            match = _MEMBER_PATTERN.fullmatch(member.label)
            if match is None:
                raise ChatGPTNumberedAggregationError("numbered member label is unsupported")
            index = int(match.group("index"))
            resolved = member.path.expanduser().resolve()
            if member.label in labels:
                raise ChatGPTNumberedAggregationError("numbered member labels contain duplicates")
            if index in indices:
                raise ChatGPTNumberedAggregationError("numbered member indices contain duplicates")
            if resolved in paths:
                raise ChatGPTNumberedAggregationError("numbered member paths contain duplicates")
            if not resolved.is_file():
                raise ChatGPTNumberedAggregationError("numbered member path is not a file")
            declared_total_bytes += resolved.stat().st_size
            if declared_total_bytes > self.max_total_input_bytes:
                raise ChatGPTNumberedAggregationError("aggregate numbered input exceeds byte limit")
            labels.add(member.label)
            indices.add(index)
            paths.add(resolved)
            parsed.append(
                (
                    index,
                    ChatGPTNumberedPathMember(label=member.label, path=resolved),
                )
            )

        parsed.sort(key=lambda item: item[0])
        ordered_indices = [index for index, _ in parsed]
        if ordered_indices[0] not in {0, 1}:
            raise ChatGPTNumberedAggregationError(
                "numbered member sequence must start at zero or one"
            )
        expected = list(range(ordered_indices[0], ordered_indices[0] + len(parsed)))
        if ordered_indices != expected:
            raise ChatGPTNumberedAggregationError("numbered member sequence contains a gap")
        return parsed


def _is_identityless_conversation(
    raw_conversation: object,
) -> bool:
    return (
        isinstance(raw_conversation, dict)
        and raw_conversation.get("id") is None
        and raw_conversation.get("conversation_id") is None
    )


def _canonical_conversation(conversation: dict[str, object]) -> bytes:
    return json.dumps(
        conversation,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _stored_bytes_equal(
    store: BinaryIO,
    previous: _StoredIdentity,
    candidate: bytes,
) -> bool:
    store.seek(previous.offset)
    position = 0
    while position < previous.byte_count:
        expected = store.read(min(_READ_CHUNK_BYTES, previous.byte_count - position))
        if not expected:
            return False
        if expected != candidate[position : position + len(expected)]:
            return False
        position += len(expected)
    return position == len(candidate)


def _hash_path(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(_READ_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()
