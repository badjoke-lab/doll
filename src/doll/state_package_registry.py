"""Versioned authoritative record inventory for Doll State packages."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from types import MappingProxyType

_RECORD_TYPE = re.compile(r"^[a-z][a-z0-9_]*$")
_VALIDATOR_ID = re.compile(r"^[a-z][a-z0-9_]*$")

PACKAGE_SYSTEM_CATEGORIES = frozenset({"audit_events", "migration_history", "authoritative_files"})


class StatePackageRegistryError(ValueError):
    """Raised when a package record registry definition or lookup is invalid."""


@dataclass(frozen=True, slots=True)
class AuthoritativeRecordCategory:
    """One authoritative JSONL record category permitted by a package format."""

    record_type: str
    member_path: str
    required_member: bool
    validator_id: str

    def __post_init__(self) -> None:
        if not _RECORD_TYPE.fullmatch(self.record_type):
            raise StatePackageRegistryError("record registry type is invalid")
        if not _VALIDATOR_ID.fullmatch(self.validator_id):
            raise StatePackageRegistryError("record registry validator identity is invalid")
        if not isinstance(self.required_member, bool):
            raise StatePackageRegistryError("record registry required-member flag is invalid")
        if "\\" in self.member_path or "\x00" in self.member_path:
            raise StatePackageRegistryError("record registry member path is unsafe")
        path = PurePosixPath(self.member_path)
        if (
            path.is_absolute()
            or not path.parts
            or path.parts[0] != "records"
            or any(part in {"", ".", ".."} for part in path.parts)
            or path.suffix != ".jsonl"
        ):
            raise StatePackageRegistryError("record registry member path is invalid")


@dataclass(frozen=True, slots=True)
class AuthoritativeRecordRegistry:
    """Immutable authoritative record inventory for one package format version."""

    package_format_version: int
    categories: tuple[AuthoritativeRecordCategory, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.package_format_version, int)
            or isinstance(self.package_format_version, bool)
            or self.package_format_version < 1
        ):
            raise StatePackageRegistryError("package registry version is invalid")
        if not self.categories:
            raise StatePackageRegistryError("package registry must contain categories")
        record_types = [category.record_type for category in self.categories]
        member_paths = [category.member_path for category in self.categories]
        if len(record_types) != len(set(record_types)):
            raise StatePackageRegistryError("package registry contains duplicate record types")
        if len(member_paths) != len(set(member_paths)):
            raise StatePackageRegistryError("package registry contains duplicate member paths")

    @property
    def by_record_type(self) -> Mapping[str, AuthoritativeRecordCategory]:
        return MappingProxyType({category.record_type: category for category in self.categories})

    @property
    def record_types(self) -> frozenset[str]:
        return frozenset(category.record_type for category in self.categories)

    @property
    def required_member_paths(self) -> frozenset[str]:
        return frozenset(
            category.member_path for category in self.categories if category.required_member
        )

    @property
    def optional_member_paths(self) -> frozenset[str]:
        return frozenset(
            category.member_path for category in self.categories if not category.required_member
        )


_CURRENT_RECORD_CATEGORIES = (
    AuthoritativeRecordCategory("preference", "records/preferences.jsonl", True, "preference"),
    AuthoritativeRecordCategory("policy", "records/policies.jsonl", True, "policy"),
    AuthoritativeRecordCategory("permission", "records/permissions.jsonl", True, "permission"),
    AuthoritativeRecordCategory("memory", "records/memories.jsonl", True, "memory"),
    AuthoritativeRecordCategory("claim", "records/claims.jsonl", False, "claim"),
    AuthoritativeRecordCategory("evidence", "records/evidence.jsonl", False, "evidence"),
    AuthoritativeRecordCategory("inference", "records/inferences.jsonl", False, "inference"),
    AuthoritativeRecordCategory(
        "trust_assessment",
        "records/trust-assessments.jsonl",
        False,
        "trust_assessment",
    ),
    AuthoritativeRecordCategory(
        "instruction_origin",
        "records/instruction-origins.jsonl",
        False,
        "instruction_origin",
    ),
    AuthoritativeRecordCategory("project", "records/projects.jsonl", True, "project"),
    AuthoritativeRecordCategory("decision", "records/decisions.jsonl", True, "decision"),
    AuthoritativeRecordCategory("artifact", "records/artifacts.jsonl", True, "artifact"),
    AuthoritativeRecordCategory(
        "backup_manifest",
        "records/backup-manifests.jsonl",
        False,
        "backup_manifest",
    ),
)

_V2_RECORD_CATEGORIES = (
    *_CURRENT_RECORD_CATEGORIES,
    AuthoritativeRecordCategory(
        "work_item",
        "records/work-items.jsonl",
        False,
        "work_item",
    ),
    AuthoritativeRecordCategory(
        "procedure",
        "records/procedures.jsonl",
        False,
        "procedure",
    ),
    AuthoritativeRecordCategory(
        "project_checkpoint",
        "records/project-checkpoints.jsonl",
        False,
        "project_checkpoint",
    ),
    AuthoritativeRecordCategory(
        "runtime_manifest",
        "records/runtime-manifests.jsonl",
        False,
        "runtime_manifest",
    ),
    AuthoritativeRecordCategory(
        "model_manifest",
        "records/model-manifests.jsonl",
        False,
        "model_manifest",
    ),
    AuthoritativeRecordCategory(
        "model_binding",
        "records/model-bindings.jsonl",
        False,
        "model_binding",
    ),
    AuthoritativeRecordCategory(
        "conversation",
        "records/conversations.jsonl",
        False,
        "conversation",
    ),
    AuthoritativeRecordCategory(
        "conversation_event",
        "records/conversation-events.jsonl",
        False,
        "conversation_event",
    ),
)

PACKAGE_RECORD_REGISTRIES: Mapping[int, AuthoritativeRecordRegistry] = MappingProxyType(
    {
        1: AuthoritativeRecordRegistry(1, _CURRENT_RECORD_CATEGORIES),
        2: AuthoritativeRecordRegistry(2, _V2_RECORD_CATEGORIES),
    }
)
SUPPORTED_PACKAGE_FORMAT_VERSIONS = frozenset(PACKAGE_RECORD_REGISTRIES)


def get_authoritative_record_registry(
    package_format_version: int,
) -> AuthoritativeRecordRegistry:
    """Return the immutable registry for one supported package format."""

    try:
        return PACKAGE_RECORD_REGISTRIES[package_format_version]
    except (KeyError, TypeError) as exc:
        raise StatePackageRegistryError("package format version is unsupported") from exc
