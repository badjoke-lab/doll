from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one marker, found {count}")
    return text.replace(old, new, 1)


# Public status.
status_path = ROOT / "website/project-status.json"
status = json.loads(status_path.read_text(encoding="utf-8"))
if status["phase"].get("next_implementation") != 82:
    raise SystemExit("project status does not have IMP-082 next")
status["phase"]["next_implementation"] = 83
message = status["model_runtime"]["message"]
message = replace_once(
    message,
    "Phase 6 is in progress through IMP-081.",
    "Phase 6 is in progress through IMP-082.",
    "status progress",
)
message = replace_once(
    message,
    "OCR image writing attachment integration, and CSV writing attachment integration are implemented.",
    "OCR image writing attachment integration, CSV writing attachment integration, and multiple-attachment writing integration are implemented.",
    "status implemented list",
)
message = replace_once(
    message,
    "PDF OCR/scanned-PDF fallback, multiple-attachment writing integration, accessibility presentation",
    "PDF OCR/scanned-PDF fallback, accessibility presentation",
    "status remaining list",
)
status["model_runtime"]["message"] = message
status["last_reviewed"] = "2026-08-11"
status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# Daily-use matrix.
matrix_path = ROOT / "docs/testing/phase-6-daily-use-matrix.json"
matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
if "multiple_writing_attachment_extension" in matrix:
    raise SystemExit("multiple attachment matrix entry already exists")
matrix["multiple_writing_attachment_extension"] = {
    "implementation": "IMP-082",
    "status": "ci-pass",
    "description": "Two to four explicit caller-ordered local document, PDF, OCR-image, or CSV attachments can become separate data-only untrusted writing sources for revise, summarize, or translate while reusing existing source-specific boundaries.",
    "pytest_files": [
        "tests/test_imp_082_multiple_writing_attachments.py",
        "tests/test_local_writing_workflow.py",
        "tests/test_imp_078_text_markdown_writing_attachment.py",
        "tests/test_imp_079_pdf_writing_attachment.py",
        "tests/test_imp_080_ocr_image_writing_attachment.py",
        "tests/test_imp_081_csv_writing_attachment.py",
    ],
    "passed_evidence_levels": ["ci"],
    "required_evidence_levels": ["ci"],
    "selection_mode": "explicit-ordered-multiple-files",
    "minimum_attachments": 2,
    "maximum_attachments": 4,
    "supported_attachment_kinds": ["document", "pdf", "ocr", "csv"],
    "supported_modes": ["revise", "summarize", "translate"],
    "draft_attachments_allowed": False,
    "caller_order_preserved": True,
    "legacy_primary_source_mixing_allowed": False,
    "maximum_aggregate_writing_source_characters": 16000,
    "target_preflight_before_attachment_read": True,
    "all_attachments_prepared_before_origin_creation": True,
    "all_source_operation_ids_preflighted_before_origin_creation": True,
    "one_instruction_origin_per_attachment": True,
    "source_specific_boundaries": {
        "document": "IMP-074",
        "csv": "IMP-075",
        "pdf": "IMP-076",
        "ocr": "IMP-077",
    },
    "origin_class": "external_content",
    "actor_type": "extractor",
    "authority_class": "untrusted_data",
    "data_only": True,
    "per_source_acquisition_method_preserved": True,
    "automatic_file_discovery": False,
    "directory_traversal": False,
    "globbing": False,
    "attachment_persistence": False,
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
    "primary_intel_mac_real_machine_evidence": False,
    "phase6_gate_complete": False,
    "lite_v1_complete": False,
    "stable_anti_lock_in_claim": False,
    "implementation_doc": "docs/implementation/imp-082-multiple-writing-attachments.md",
}
matrix_path.write_text(json.dumps(matrix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# Controlled roadmap/specification source.
roadmap_path = "docs/spec/09-development-roadmap.md"
roadmap = read(roadmap_path)
roadmap = replace_once(
    roadmap,
    "Phase 6 local AI portability and daily-use integration is in progress through IMP-081;",
    "Phase 6 local AI portability and daily-use integration is in progress through IMP-082;",
    "roadmap progress",
)
roadmap = replace_once(
    roadmap,
    "- the next bounded implementation receives IMP-082 only when a new implementation issue is opened;",
    "- IMP-082 composes two through four explicitly selected caller-ordered local document, PDF, OCR-image, or CSV attachments into revise, summarize, and translate while reusing the accepted source-specific boundaries, requiring all attachment preparation and all source-operation-ID preflight before the first new source origin is created;\n- IMP-082 is assigned to Issue #247;\n- the IMP-082 multiple-writing-attachment extension passes at the `ci` evidence level and does not broaden accepted primary real-machine evidence;\n- the next bounded implementation receives IMP-083 only when a new implementation issue is opened;",
    "roadmap ledger",
)
section = """

### IMP-082 — Explicit multiple writing attachments

Status: implemented with deterministic synthetic CI evidence.

Extended the accepted local writing workflow so one `revise`, `summarize`, or `translate` turn may consume an explicit caller-ordered set of two through four local attachments. Supported attachment kinds are text/Markdown documents, PDFs, OCR images, and CSVs through the unchanged IMP-074, IMP-076, IMP-077, and IMP-075 preparation boundaries. The existing legacy single-source API remains valid and cannot be mixed with the new multiple-attachment argument. `draft` remains source-free.

The workflow validates attachment cardinality and specification shapes, source-form exclusivity, mode, request, target language, operation identity, conversation target, active binding, and runtime declaration before opening the first attachment. Every attachment must then prepare successfully through its existing source-specific validator. Caller order is preserved. The aggregate prepared writing material must remain within the existing 16,000-character writing-source limit.

No source InstructionOrigin is created until every attachment has prepared successfully and the aggregate character limit has passed. Derived source-operation identifiers for all attachments are also checked for prior use before the first new source origin is created. This prevents a later invalid attachment, aggregate overflow, or pre-existing later origin from leaving a newly created partial source-origin prefix.

Each attachment receives one ordered data-only `external_content` InstructionOrigin with `untrusted_data` authority. OCR material retains acquisition `ocr`; document, PDF, and CSV material retain `extraction`. The current user request remains the only task-authority instruction. Attachment text cannot grant permissions, confirmation, capability authority, binding changes, memory/project/decision mutation, completion authority, or tool authority.

Multi-attachment results use `source_kind = multiple` and expose only ordered content-free source-origin IDs, source kinds, prepared character counts, prepared-content SHA-256 values, and aggregate source character count. Legacy singular source-specific result metadata remains reserved for single-source turns. Native paths, filenames, attachment bodies, prompts, generated responses, credentials, and secrets are not added to the result.

Dedicated acceptance covers mixed document/CSV order, two-through-four cardinality, legacy-source conflicts, draft rejection, invalid attachment members and source-specific option shapes, target-before-read ordering, later-source failure before origin creation, aggregate-limit failure, all-origin-ID preflight before first creation, hostile multiple-source data isolation, runtime failure, path/content privacy, and exact source preservation. Standard CI passes on Ubuntu, macOS, and Windows, including an unchanged project coverage threshold of at least 95 percent. IMP-082 does not broaden the accepted IMP-064 primary Intel Mac real-machine evidence.

IMP-082 does not establish automatic file discovery, directory traversal, globbing, draft reference attachments, attachment persistence, SourceRecord creation, artifact publication, persistent indexing, semantic retrieval, embeddings, ranking, model-selected attachments, XLSX/ODS support, formula execution, PDF OCR/scanned-PDF fallback, new OCR adapters, Web retrieval, process or shell execution, tools, capability execution, network or cloud access, target-specific export, accessibility presentation, Lite performance acceptance, the release-candidate soak, complete Phase 6, Lite v1.0 completion, or stable general anti-lock-in.
"""
roadmap = replace_once(
    roadmap,
    "\nSubsequent daily-use work may expand multiple-attachment writing integration, cross-platform OCR adapters, accessibility presentation, Lite performance measurements, and soak testing.",
    section + "\nSubsequent daily-use work may expand cross-platform OCR adapters, accessibility presentation, Lite performance measurements, and soak testing.",
    "roadmap section insertion",
)
write(roadmap_path, roadmap)

# Public status checker synchronization and new matrix contract.
checker_path = "scripts/check-public-site-status.mjs"
checker = read(checker_path)
checker = replace_once(
    checker,
    'status.phase?.next_implementation === 82,\n  "project-status.json must mark Phase 6 in progress through IMP-081 with IMP-082 next",',
    'status.phase?.next_implementation === 83,\n  "project-status.json must mark Phase 6 in progress through IMP-082 with IMP-083 next",',
    "checker next implementation",
)
checker = replace_once(
    checker,
    'status.model_runtime.message.includes("through IMP-081") &&',
    'status.model_runtime.message.includes("through IMP-082") &&',
    "checker progress message",
)
checker = replace_once(
    checker,
    'status.model_runtime.message.includes("CSV writing attachment integration") &&',
    'status.model_runtime.message.includes("CSV writing attachment integration") &&\n    status.model_runtime.message.includes("multiple-attachment writing integration") &&',
    "checker implemented multiple attachment",
)
checker = replace_once(
    checker,
    '"project-status.json must describe IMP-081 without broadening accepted real-machine evidence",',
    '"project-status.json must describe IMP-082 without broadening accepted real-machine evidence",',
    "checker status label",
)
marker = '''expect(
  localWritingPrimary.test_id === "IMP-064-LOCAL-WRITING-PRIMARY" &&'''
if checker.count(marker) != 1:
    raise SystemExit("checker local-writing marker missing")
multi_check = '''expect(
  dailyUse.multiple_writing_attachment_extension?.implementation === "IMP-082" &&
    dailyUse.multiple_writing_attachment_extension?.status === "ci-pass" &&
    JSON.stringify(dailyUse.multiple_writing_attachment_extension?.passed_evidence_levels) === JSON.stringify(["ci"]) &&
    JSON.stringify(dailyUse.multiple_writing_attachment_extension?.required_evidence_levels) === JSON.stringify(["ci"]) &&
    dailyUse.multiple_writing_attachment_extension?.selection_mode === "explicit-ordered-multiple-files" &&
    dailyUse.multiple_writing_attachment_extension?.minimum_attachments === 2 &&
    dailyUse.multiple_writing_attachment_extension?.maximum_attachments === 4 &&
    JSON.stringify(dailyUse.multiple_writing_attachment_extension?.supported_attachment_kinds) === JSON.stringify(["document", "pdf", "ocr", "csv"]) &&
    JSON.stringify(dailyUse.multiple_writing_attachment_extension?.supported_modes) === JSON.stringify(["revise", "summarize", "translate"]) &&
    dailyUse.multiple_writing_attachment_extension?.draft_attachments_allowed === false &&
    dailyUse.multiple_writing_attachment_extension?.caller_order_preserved === true &&
    dailyUse.multiple_writing_attachment_extension?.legacy_primary_source_mixing_allowed === false &&
    dailyUse.multiple_writing_attachment_extension?.maximum_aggregate_writing_source_characters === 16000 &&
    dailyUse.multiple_writing_attachment_extension?.target_preflight_before_attachment_read === true &&
    dailyUse.multiple_writing_attachment_extension?.all_attachments_prepared_before_origin_creation === true &&
    dailyUse.multiple_writing_attachment_extension?.all_source_operation_ids_preflighted_before_origin_creation === true &&
    dailyUse.multiple_writing_attachment_extension?.one_instruction_origin_per_attachment === true &&
    dailyUse.multiple_writing_attachment_extension?.source_specific_boundaries?.document === "IMP-074" &&
    dailyUse.multiple_writing_attachment_extension?.source_specific_boundaries?.csv === "IMP-075" &&
    dailyUse.multiple_writing_attachment_extension?.source_specific_boundaries?.pdf === "IMP-076" &&
    dailyUse.multiple_writing_attachment_extension?.source_specific_boundaries?.ocr === "IMP-077" &&
    dailyUse.multiple_writing_attachment_extension?.origin_class === "external_content" &&
    dailyUse.multiple_writing_attachment_extension?.actor_type === "extractor" &&
    dailyUse.multiple_writing_attachment_extension?.authority_class === "untrusted_data" &&
    dailyUse.multiple_writing_attachment_extension?.data_only === true &&
    dailyUse.multiple_writing_attachment_extension?.per_source_acquisition_method_preserved === true &&
    dailyUse.multiple_writing_attachment_extension?.automatic_file_discovery === false &&
    dailyUse.multiple_writing_attachment_extension?.directory_traversal === false &&
    dailyUse.multiple_writing_attachment_extension?.globbing === false &&
    dailyUse.multiple_writing_attachment_extension?.attachment_persistence === false &&
    dailyUse.multiple_writing_attachment_extension?.source_record_created === false &&
    dailyUse.multiple_writing_attachment_extension?.artifact_created === false &&
    dailyUse.multiple_writing_attachment_extension?.persistent_index === false &&
    dailyUse.multiple_writing_attachment_extension?.semantic_retrieval === false &&
    dailyUse.multiple_writing_attachment_extension?.model_selected_context === false &&
    dailyUse.multiple_writing_attachment_extension?.network_access === false &&
    dailyUse.multiple_writing_attachment_extension?.cloud_access === false &&
    dailyUse.multiple_writing_attachment_extension?.process_launch === false &&
    dailyUse.multiple_writing_attachment_extension?.shell_execution === false &&
    dailyUse.multiple_writing_attachment_extension?.capability_execution === false &&
    dailyUse.multiple_writing_attachment_extension?.primary_intel_mac_real_machine_evidence === false &&
    dailyUse.multiple_writing_attachment_extension?.phase6_gate_complete === false &&
    dailyUse.multiple_writing_attachment_extension?.lite_v1_complete === false &&
    dailyUse.multiple_writing_attachment_extension?.stable_anti_lock_in_claim === false &&
    dailyUse.multiple_writing_attachment_extension?.implementation_doc === "docs/implementation/imp-082-multiple-writing-attachments.md",
  "IMP-082 multiple writing attachments must remain explicit, ordered, atomic-before-origin, untrusted, local-only, and CI-only",
);

'''
checker = checker.replace(marker, multi_check + marker, 1)
old_roadmap_check = '''    roadmap.includes("### IMP-080 — Explicit OCR image writing attachment") &&
    roadmap.includes("### IMP-081 — Explicit CSV writing attachment") &&
    roadmap.includes("the next bounded implementation receives IMP-082 only when a new implementation issue is opened"),
  "roadmap must record IMP-081 and identify IMP-082 as the next unallocated implementation identifier",'''
new_roadmap_check = '''    roadmap.includes("### IMP-080 — Explicit OCR image writing attachment") &&
    roadmap.includes("### IMP-081 — Explicit CSV writing attachment") &&
    roadmap.includes("### IMP-082 — Explicit multiple writing attachments") &&
    roadmap.includes("the next bounded implementation receives IMP-083 only when a new implementation issue is opened"),
  "roadmap must record IMP-082 and identify IMP-083 as the next unallocated implementation identifier",'''
checker = replace_once(
    checker,
    old_roadmap_check,
    new_roadmap_check,
    "checker roadmap allocation",
)
write(checker_path, checker)
