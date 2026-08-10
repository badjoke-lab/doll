from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write_text(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one marker, found {count}")
    return text.replace(old, new, 1)


# 1. Public project status.
status_path = ROOT / "website/project-status.json"
status = json.loads(status_path.read_text(encoding="utf-8"))
phase = status["phase"]
if phase.get("next_implementation") != 81:
    raise SystemExit("project status next implementation is not IMP-081")
phase["next_implementation"] = 82
message = status["model_runtime"]["message"]
message = replace_once(
    message,
    "Phase 6 is in progress through IMP-080.",
    "Phase 6 is in progress through IMP-081.",
    "project status phase marker",
)
message = replace_once(
    message,
    "PDF writing attachment integration, and OCR image writing attachment integration are implemented.",
    "PDF writing attachment integration, OCR image writing attachment integration, and CSV writing attachment integration are implemented.",
    "project status implemented attachment list",
)
message = replace_once(
    message,
    "PDF OCR/scanned-PDF fallback, CSV and multiple-attachment writing integration, accessibility presentation",
    "PDF OCR/scanned-PDF fallback, multiple-attachment writing integration, accessibility presentation",
    "project status remaining attachment list",
)
status["model_runtime"]["message"] = message
status["last_reviewed"] = "2026-08-11"
status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# 2. Phase 6 daily-use matrix.
matrix_path = ROOT / "docs/testing/phase-6-daily-use-matrix.json"
matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
if "csv_writing_attachment_extension" in matrix:
    raise SystemExit("CSV writing attachment extension already exists")
matrix["csv_writing_attachment_extension"] = {
    "implementation": "IMP-081",
    "status": "ci-pass",
    "description": "One explicit local UTF-8 CSV can replace inline, text/Markdown, PDF, or OCR primary source material for revise, summarize, or translate after bounded IMP-075 transformation while remaining data-only untrusted writing material.",
    "pytest_files": [
        "tests/test_imp_081_csv_writing_attachment.py",
        "tests/test_imp_075_local_csv.py",
        "tests/test_local_writing_workflow.py",
    ],
    "passed_evidence_levels": ["ci"],
    "required_evidence_levels": ["ci"],
    "selection_mode": "explicit-single-file",
    "allowed_extensions": [".csv"],
    "supported_modes": ["revise", "summarize", "translate"],
    "draft_primary_source_allowed": False,
    "exactly_one_primary_source": True,
    "primary_source_forms": ["inline", "document", "pdf", "ocr", "csv"],
    "reader_implementation": "IMP-075",
    "delimiter_profiles": ["comma", "tab", "semicolon", "pipe"],
    "caller_ordered_column_selection": True,
    "column_reordering": True,
    "header_renaming": True,
    "formula_evaluation": False,
    "formula_like_cells_preserved_as_text": True,
    "maximum_writing_source_characters": 16000,
    "strict_utf8": True,
    "utf8_bom_handling": "remove-and-report",
    "symlinks_allowed": False,
    "automatic_file_discovery": False,
    "persistent_document_record": False,
    "source_record_created": False,
    "artifact_created": False,
    "persistent_index": False,
    "semantic_retrieval": False,
    "model_selected_context": False,
    "network_access": False,
    "cloud_access": False,
    "process_launch": False,
    "shell_execution": False,
    "capability_execution": False,
    "origin_class": "external_content",
    "actor_type": "extractor",
    "acquisition_method": "extraction",
    "authority_class": "untrusted_data",
    "phase6_gate_complete": False,
    "lite_v1_complete": False,
    "stable_anti_lock_in_claim": False,
    "implementation_doc": "docs/implementation/imp-081-csv-writing-attachment.md",
}
matrix_path.write_text(json.dumps(matrix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# 3. Controlled roadmap/source specification.
roadmap_path = "docs/spec/09-development-roadmap.md"
roadmap = load_text(roadmap_path)
roadmap = replace_once(
    roadmap,
    "Phase 6 local AI portability and daily-use integration is in progress through IMP-080;",
    "Phase 6 local AI portability and daily-use integration is in progress through IMP-081;",
    "roadmap phase progress",
)
roadmap = replace_once(
    roadmap,
    "- the next bounded implementation receives IMP-081 only when a new implementation issue is opened;",
    "- IMP-081 composes one explicitly selected local UTF-8 CSV through the bounded IMP-075 transformation path into revise, summarize, and translate as the primary data-only writing source while preserving the exactly-one-primary-source contract;\n- IMP-081 is assigned to Issue #245;\n- the IMP-081 CSV writing-attachment extension passes at the `ci` evidence level and does not broaden accepted primary real-machine evidence;\n- the next bounded implementation receives IMP-082 only when a new implementation issue is opened;",
    "roadmap implementation ledger",
)
section = """

### IMP-081 — Explicit CSV writing attachment

Status: implemented with deterministic synthetic CI evidence.

Extended the accepted local writing workflow with one optional caller-selected UTF-8 CSV primary source. `revise`, `summarize`, and `translate` now require exactly one of inline source text, one explicit text/Markdown document, one explicit PDF, one explicit OCR image, or one explicit CSV. `draft` remains source-free. Existing inline, document, PDF, and OCR source behavior is preserved.

The workflow validates source-form selection, CSV option types, operation identity, conversation target, capacity, active binding, and runtime declaration before reading or transforming the selected CSV. The CSV then passes only through the unchanged IMP-075 bounded transformation boundary, including regular non-symlink file validation, strict UTF-8 and deterministic BOM handling, explicit comma/tab/semicolon/pipe delimiter profiles, rectangular parsing, bounded source/row/column/cell limits, exact caller-ordered column selection and reordering, and exact header renaming. Formula-like cells remain visible strings and are never evaluated or executed.

Only the deterministic transformed CSV text becomes writing material. It must satisfy the existing 16,000-character writing-source limit before a writing-source InstructionOrigin is created. The transformed CSV remains data-only `external_content` through `extractor` / `extraction` with `untrusted_data` authority. The current user request remains the only task-authority instruction. CSV cell content cannot change writing mode, target language, permissions, confirmation, capability authority, binding state, memory, project state, decisions, completion authority, or other authoritative state.

The content-free writing result identifies `csv` source kind and exposes only the selected delimiter profile, source and transformed hashes/byte counts, BOM-removal state, row and source/output column counts, blank-cell count, potential-formula-cell count, transformed output byte/character count and hash, plus the existing writing-source character count. Native path, filename, header or cell text, prompt text, generated response text, credentials, and secrets are not added to the result.

Dedicated acceptance covers BOM/semicolon parsing, caller-selected column order and header renaming, formula-like text preservation without execution, source-form conflicts, invalid option shapes, target-before-transform ordering, transform errors before source-origin creation, missing-column and writing-limit failure, hostile CSV instructions, runtime failure, path privacy, exact source-file preservation, and the accepted writing-source newline normalization contract. Standard CI passes on Ubuntu, macOS, and Windows; Windows coverage remains above the unchanged 95% project threshold. IMP-081 does not broaden the accepted IMP-064 primary Intel Mac real-machine evidence.

IMP-081 does not establish formula execution, spreadsheet formats such as XLSX/ODS, multiple attachments, mixed primary sources, draft reference attachments, attachment persistence, SourceRecord creation, artifact publication, persistent indexing, automatic file discovery, semantic retrieval, embeddings, ranking, model-selected context, Web retrieval, process or shell execution, tools, capability execution, network or cloud access, target-specific export, accessibility presentation, Lite performance acceptance, the release-candidate soak, complete Phase 6, Lite v1.0 completion, or stable general anti-lock-in.
"""
roadmap = replace_once(
    roadmap,
    "\nSubsequent daily-use work may expand CSV and multiple-attachment writing integration, cross-platform OCR adapters, accessibility presentation, Lite performance measurements, and soak testing.",
    section + "\nSubsequent daily-use work may expand multiple-attachment writing integration, cross-platform OCR adapters, accessibility presentation, Lite performance measurements, and soak testing.",
    "roadmap IMP-081 section insertion",
)
write_text(roadmap_path, roadmap)

# 4. Public status checker must enforce the new synchronized state.
checker_path = "scripts/check-public-site-status.mjs"
checker = load_text(checker_path)
checker = replace_once(
    checker,
    'status.phase?.next_implementation === 81,\n  "project-status.json must mark Phase 6 in progress through IMP-080 with IMP-081 next",',
    'status.phase?.next_implementation === 82,\n  "project-status.json must mark Phase 6 in progress through IMP-081 with IMP-082 next",',
    "checker next implementation",
)
checker = replace_once(
    checker,
    'status.model_runtime.message.includes("through IMP-080") &&',
    'status.model_runtime.message.includes("through IMP-081") &&',
    "checker phase message",
)
checker = replace_once(
    checker,
    'status.model_runtime.message.includes("OCR image writing attachment integration") &&',
    'status.model_runtime.message.includes("OCR image writing attachment integration") &&\n    status.model_runtime.message.includes("CSV writing attachment integration") &&',
    "checker CSV integration marker",
)
checker = replace_once(
    checker,
    '"project-status.json must describe IMP-080 without broadening accepted real-machine evidence",',
    '"project-status.json must describe IMP-081 without broadening accepted real-machine evidence",',
    "checker assertion label",
)
write_text(checker_path, checker)
