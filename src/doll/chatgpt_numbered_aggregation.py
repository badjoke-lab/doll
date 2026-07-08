"""Deterministic offline aggregation for numbered ChatGPT conversation JSON members."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from doll.chatgpt_export_import import (
    ChatGPTExportImportError,
    _conversation_identity,
    _json_depth,
    _load_root,
)

_MEMBER_PATTERN = re.compile(r"^conversations-(?P<index>[0-9]+)\.json$")
_AGGREGATION_FORMAT = "chatgpt-numbered-conversation-members"
_AGGREGATION_VERSION = "1"


class ChatGPTNumberedAggregationError(ChatGPTExportImportError):
    """Raised when numbered ChatGPT conversation members cannot be aggregated safely."""


@dataclass(frozen=True, slots=True)
class ChatGPTNumberedMember:
    """One explicitly supplied numbered member with a privacy-safe basename label."""

    label: str
    source_bytes: bytes


@dataclass(frozen=True, slots=True)
class ChatGPTNumberedMemberManifest:
    """Content-free integrity metadata for one numbered member."""

    label: str
    index: int
    byte_count: int
    conversation_count: int
    sha256: str

    def canonical_summary(self) -> dict[str, object]:
        return {
            "label": self.label,
            "index": self.index,
            "byte_count": self.byte_count,
            "conversation_count": self.conversation_count,
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class ChatGPTNumberedAggregationResult:
    """Deterministic aggregate bytes plus content-free member evidence."""

    aggregated_bytes: bytes
    aggregate_source_hash: str
    member_set_root_hash: str
    members: tuple[ChatGPTNumberedMemberManifest, ...]
    input_conversation_count: int
    output_conversation_count: int
    exact_duplicate_conversation_count: int

    def canonical_summary(self) -> dict[str, object]:
        return {
            "aggregation_format": _AGGREGATION_FORMAT,
            "aggregation_version": _AGGREGATION_VERSION,
            "aggregate_source_hash": self.aggregate_source_hash,
            "member_set_root_hash": self.member_set_root_hash,
            "member_count": len(self.members),
            "members": [member.canonical_summary() for member in self.members],
            "input_conversation_count": self.input_conversation_count,
            "output_conversation_count": self.output_conversation_count,
            "exact_duplicate_conversation_count": self.exact_duplicate_conversation_count,
        }


@dataclass(frozen=True, slots=True)
class ChatGPTNumberedConversationAggregator:
    """Aggregate explicit numbered members without filesystem discovery or network access."""

    max_member_count: int = 128
    max_total_input_bytes: int = 256 * 1024 * 1024
    max_conversation_count: int = 1_000_000
    max_nesting_depth: int = 96

    def aggregate(
        self,
        members: tuple[ChatGPTNumberedMember, ...],
    ) -> ChatGPTNumberedAggregationResult:
        if not isinstance(members, tuple) or not members:
            raise ChatGPTNumberedAggregationError("numbered members must be a non-empty tuple")
        if len(members) > self.max_member_count:
            raise ChatGPTNumberedAggregationError("numbered member count exceeds limit")

        parsed: list[tuple[int, ChatGPTNumberedMember]] = []
        labels: set[str] = set()
        indices: set[int] = set()
        total_bytes = 0
        for member in members:
            if not isinstance(member, ChatGPTNumberedMember):
                raise ChatGPTNumberedAggregationError("numbered member type is invalid")
            match = _MEMBER_PATTERN.fullmatch(member.label)
            if match is None:
                raise ChatGPTNumberedAggregationError("numbered member label is unsupported")
            index = int(match.group("index"))
            if member.label in labels:
                raise ChatGPTNumberedAggregationError("numbered member labels contain duplicates")
            if index in indices:
                raise ChatGPTNumberedAggregationError("numbered member indices contain duplicates")
            if not isinstance(member.source_bytes, bytes) or not member.source_bytes:
                raise ChatGPTNumberedAggregationError("numbered member bytes are invalid")
            labels.add(member.label)
            indices.add(index)
            total_bytes += len(member.source_bytes)
            if total_bytes > self.max_total_input_bytes:
                raise ChatGPTNumberedAggregationError("aggregate numbered input exceeds byte limit")
            parsed.append((index, member))

        parsed.sort(key=lambda item: item[0])
        ordered_indices = [index for index, _ in parsed]
        if ordered_indices[0] not in {0, 1}:
            raise ChatGPTNumberedAggregationError("numbered member sequence must start at zero or one")
        expected = list(range(ordered_indices[0], ordered_indices[0] + len(ordered_indices)))
        if ordered_indices != expected:
            raise ChatGPTNumberedAggregationError("numbered member sequence contains a gap")

        manifests: list[ChatGPTNumberedMemberManifest] = []
        aggregated: list[object] = []
        identities: dict[str, bytes] = {}
        input_count = 0
        duplicate_count = 0

        for index, member in parsed:
            try:
                root = _load_root(member.source_bytes)
                depth = _json_depth(root)
            except (ChatGPTExportImportError, RecursionError) as exc:
                raise ChatGPTNumberedAggregationError(
                    "numbered member is not a supported JSON conversation list"
                ) from exc
            if depth > self.max_nesting_depth:
                raise ChatGPTNumberedAggregationError("numbered member nesting exceeds limit")
            input_count += len(root)
            if input_count > self.max_conversation_count:
                raise ChatGPTNumberedAggregationError("aggregate conversation count exceeds limit")

            manifests.append(
                ChatGPTNumberedMemberManifest(
                    label=member.label,
                    index=index,
                    byte_count=len(member.source_bytes),
                    conversation_count=len(root),
                    sha256=hashlib.sha256(member.source_bytes).hexdigest(),
                )
            )

            for item_index, raw_conversation in enumerate(root):
                try:
                    _, conversation_id = _conversation_identity(raw_conversation, item_index)
                except ChatGPTExportImportError as exc:
                    raise ChatGPTNumberedAggregationError(
                        "numbered member contains an invalid conversation identity"
                    ) from exc
                canonical = json.dumps(
                    raw_conversation,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
                previous = identities.get(conversation_id)
                if previous is None:
                    identities[conversation_id] = canonical
                    aggregated.append(raw_conversation)
                elif previous == canonical:
                    duplicate_count += 1
                else:
                    raise ChatGPTNumberedAggregationError(
                        "conflicting duplicate conversation identity across numbered members"
                    )

        aggregated_bytes = json.dumps(
            aggregated,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        aggregate_source_hash = hashlib.sha256(aggregated_bytes).hexdigest()
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

        return ChatGPTNumberedAggregationResult(
            aggregated_bytes=aggregated_bytes,
            aggregate_source_hash=aggregate_source_hash,
            member_set_root_hash=member_set_root_hash,
            members=tuple(manifests),
            input_conversation_count=input_count,
            output_conversation_count=len(aggregated),
            exact_duplicate_conversation_count=duplicate_count,
        )
