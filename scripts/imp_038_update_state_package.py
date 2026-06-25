from __future__ import annotations

from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "src/doll/state_package.py"


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"expected one match for {old!r}")
    return text.replace(old, new)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "PACKAGE_FORMAT_VERSION = 1\n",
        "PACKAGE_FORMAT_VERSION = 2\n"
        "SUPPORTED_PACKAGE_FORMAT_VERSIONS = frozenset({1, PACKAGE_FORMAT_VERSION})\n",
    )
    marker = 'class StatePackageError(StateError):\n'
    registry = '''_PACKAGE_FORMAT_REQUIRED_FIELDS: dict[int, frozenset[str]] = {
    version: frozenset(
        {
            "package_format_version",
            "workspace_id",
            "exported_at",
            "source_product_version",
            "source_workspace_schema_version",
            "source_state_schema_version",
            "state_revision",
            "included_categories",
            "excluded_categories",
            "record_counts",
            "audit_event_count",
            "migration_history_count",
            "authoritative_file_count",
            "total_payload_size_bytes",
            "checksum_algorithm",
            "encryption_state",
            "omitted_secret_counts",
            "external_references",
            "compatibility_notes",
        }
    )
    for version in SUPPORTED_PACKAGE_FORMAT_VERSIONS
}


'''
    text = replace_once(text, marker, registry + marker)
    text = replace_once(
        text,
        '"Import requires package format version 1 and a supported state schema."',
        '"Import supports package format versions 1 and 2 with a supported state schema."',
    )
    validation_marker = "def _validate_package_payloads(\n"
    validation = '''def _validate_package_format_version(manifest: dict[str, object]) -> int:
    version = _required_positive_int(manifest, "package_format_version")
    required_fields = _PACKAGE_FORMAT_REQUIRED_FIELDS.get(version)
    if required_fields is None:
        raise StatePackageValidationError("package format version is unsupported")
    if required_fields.difference(manifest):
        raise StatePackageValidationError(
            f"package format version {version} manifest is incomplete"
        )
    return version


'''
    text = replace_once(text, validation_marker, validation + validation_marker)
    text = replace_once(
        text,
        '    if manifest.get("package_format_version") != PACKAGE_FORMAT_VERSION:\n'
        '        raise StatePackageValidationError("package format version is unsupported")\n',
        "    package_format_version = _validate_package_format_version(manifest)\n",
    )
    text = replace_once(
        text,
        "        package_format_version=PACKAGE_FORMAT_VERSION,\n",
        "        package_format_version=package_format_version,\n",
    )
    text = replace_once(
        text,
        '                        "package_format_version": PACKAGE_FORMAT_VERSION,\n',
        '                        "package_format_version": data.inspection.package_format_version,\n',
    )
    text = replace_once(text, '        b"Format version: 1\\n"\n', '        f"Format version: {PACKAGE_FORMAT_VERSION}\\n"\n')
    text = replace_once(text, '        b"Doll State Package\\n"\n', '        "Doll State Package\\n"\n')
    text = replace_once(text, '        b"This archive contains data only. Do not execute package content.\\n"\n', '        "This archive contains data only. Do not execute package content.\\n"\n')
    text = replace_once(text, '        b"Verify checksums.json before import.\\n"\n', '        "Verify checksums.json before import.\\n"\n')
    text = replace_once(text, '        b"Secret records are omitted from unencrypted packages.\\n"\n    )', '        "Secret records are omitted from unencrypted packages.\\n"\n    ).encode("utf-8")')
    PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
