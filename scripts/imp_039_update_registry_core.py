from __future__ import annotations

from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "src/doll/state_package.py"


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one match, found {count}: {old[:80]!r}")
    return text.replace(old, new)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from dataclasses import dataclass\n",
        "from collections.abc import Callable\nfrom dataclasses import dataclass\n",
    )
    text = replace_once(
        text,
        "from doll.state_repository import StateRepository, _validate_record_fields\n",
        "from doll.state_package_registry import (\n"
        "    PACKAGE_SYSTEM_CATEGORIES,\n"
        "    SUPPORTED_PACKAGE_FORMAT_VERSIONS,\n"
        "    AuthoritativeRecordRegistry,\n"
        "    StatePackageRegistryError,\n"
        "    get_authoritative_record_registry,\n"
        ")\n"
        "from doll.state_repository import StateRepository, _validate_record_fields\n",
    )
    text = replace_once(
        text,
        "PACKAGE_FORMAT_VERSION = 2\n"
        "SUPPORTED_PACKAGE_FORMAT_VERSIONS = frozenset({1, PACKAGE_FORMAT_VERSION})\n",
        "PACKAGE_FORMAT_VERSION = 2\n",
    )
    old_inventory = '''_RECORD_PATHS: dict[str, str] = {
    "preference": "records/preferences.jsonl",
    "policy": "records/policies.jsonl",
    "permission": "records/permissions.jsonl",
    "memory": "records/memories.jsonl",
    "claim": "records/claims.jsonl",
    "evidence": "records/evidence.jsonl",
    "inference": "records/inferences.jsonl",
    "trust_assessment": "records/trust-assessments.jsonl",
    "instruction_origin": "records/instruction-origins.jsonl",
    "project": "records/projects.jsonl",
    "decision": "records/decisions.jsonl",
    "artifact": "records/artifacts.jsonl",
    "backup_manifest": "records/backup-manifests.jsonl",
}
_SUPPORTED_RECORD_TYPES = frozenset(_RECORD_PATHS)
_OPTIONAL_RECORD_TYPES = frozenset(
    {
        "backup_manifest",
        "claim",
        "evidence",
        "inference",
        "trust_assessment",
        "instruction_origin",
    }
)
_ALWAYS_MEMBER_PATHS = (
    "manifest.json",
    "records/workspace.json",
    *tuple(
        path
        for record_type, path in _RECORD_PATHS.items()
        if record_type not in _OPTIONAL_RECORD_TYPES
    ),
    "records/audit-events.jsonl",
    "records/migration-history.jsonl",
    "README.txt",
)
'''
    new_inventory = '''_FIXED_MEMBER_PATHS = (
    "manifest.json",
    "records/workspace.json",
    "records/audit-events.jsonl",
    "records/migration-history.jsonl",
    "README.txt",
)
'''
    text = replace_once(text, old_inventory, new_inventory)

    validator_marker = "\n\nclass StatePackageError(StateError):\n"
    validators = '''

_PACKAGE_RECORD_VALIDATORS: dict[str, Callable[[RecordEnvelope], object]] = {
    "preference": _preference_from_record,
    "policy": _policy_from_record,
    "permission": _permission_from_record,
    "memory": _memory_from_record,
    "claim": _claim_from_record,
    "evidence": _evidence_from_record,
    "inference": _inference_from_record,
    "trust_assessment": _trust_assessment_from_record,
    "instruction_origin": _instruction_origin_from_record,
    "project": _project_from_record,
    "decision": _decision_from_record,
    "artifact": _artifact_from_record,
    "backup_manifest": _backup_manifest_from_record,
}
'''
    text = replace_once(text, validator_marker, validators + validator_marker)

    helper_marker = '''class StatePackageImportError(StatePackageError):
    """Raised when staged import cannot be completed safely."""


'''
    helpers = '''class StatePackageImportError(StatePackageError):
    """Raised when staged import cannot be completed safely."""


def _package_record_registry(package_format_version: int) -> AuthoritativeRecordRegistry:
    try:
        return get_authoritative_record_registry(package_format_version)
    except StatePackageRegistryError as exc:
        raise StatePackageValidationError("package format version is unsupported") from exc


def _validate_registry_validators(registry: AuthoritativeRecordRegistry) -> None:
    for category in registry.categories:
        if category.validator_id not in _PACKAGE_RECORD_VALIDATORS:
            raise StatePackageValidationError(
                "registered authoritative record validator is unavailable"
            )


'''
    text = replace_once(text, helper_marker, helpers)
    PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
