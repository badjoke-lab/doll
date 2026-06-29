"""Optional State Package v2 categories for canonical portability records."""

from __future__ import annotations

from doll.state_package_registry import AuthoritativeRecordCategory

PORTABILITY_RECORD_CATEGORIES = (
    AuthoritativeRecordCategory(
        "source_environment",
        "records/source-environments.jsonl",
        False,
        "source_environment",
    ),
    AuthoritativeRecordCategory(
        "portability_import_batch",
        "records/portability-import-batches.jsonl",
        False,
        "portability_import_batch",
    ),
    AuthoritativeRecordCategory(
        "portability_mapping_report",
        "records/portability-mapping-reports.jsonl",
        False,
        "portability_mapping_report",
    ),
    AuthoritativeRecordCategory(
        "portability_loss",
        "records/portability-losses.jsonl",
        False,
        "portability_loss",
    ),
    AuthoritativeRecordCategory(
        "portability_source_mapping",
        "records/portability-source-mappings.jsonl",
        False,
        "portability_source_mapping",
    ),
    AuthoritativeRecordCategory(
        "portability_quarantine",
        "records/portability-quarantines.jsonl",
        False,
        "portability_quarantine",
    ),
    AuthoritativeRecordCategory(
        "portability_original_source",
        "records/portability-original-sources.jsonl",
        False,
        "portability_original_source",
    ),
)

PORTABILITY_RECORD_TYPES = frozenset(
    category.record_type for category in PORTABILITY_RECORD_CATEGORIES
)
