from __future__ import annotations

import json
from pathlib import Path


def once(text: str, old: str, new: str) -> str:
    if old not in text:
        raise SystemExit(f"marker missing: {old[:120]!r}")
    return text.replace(old, new, 1)


# Roadmap
roadmap_path = Path("docs/spec/09-development-roadmap.md")
roadmap = roadmap_path.read_text(encoding="utf-8")
roadmap = once(roadmap, "- IMP-030 through IMP-078;", "- IMP-030 through IMP-079;")
roadmap = once(
    roadmap,
    ", optional local image OCR through IMP-077, and explicit text/Markdown writing attachments through IMP-078.",
    ", optional local image OCR through IMP-077, explicit text/Markdown writing attachments through IMP-078, and explicit PDF writing attachments through IMP-079.",
)
roadmap = once(
    roadmap,
    "- Phase 6 local AI portability and daily-use integration is in progress through IMP-078;",
    "- Phase 6 local AI portability and daily-use integration is in progress through IMP-079;",
)
roadmap = once(
    roadmap,
    "- the IMP-078 text/Markdown writing-attachment extension passes at the `ci` evidence level and does not broaden accepted primary real-machine evidence;\n- the next bounded implementation receives IMP-079 only when a new implementation issue is opened;",
    "- the IMP-078 text/Markdown writing-attachment extension passes at the `ci` evidence level and does not broaden accepted primary real-machine evidence;\n- IMP-079 composes one explicitly selected local PDF into revise, summarize, and translate as the primary data-only writing source by reusing the bounded IMP-076 extraction boundary and the IMP-078 exactly-one-primary-source contract;\n- IMP-079 is assigned to Issue #241;\n- the IMP-079 PDF writing-attachment extension passes at the `ci` evidence level and does not broaden accepted primary real-machine evidence;\n- the next bounded implementation receives IMP-080 only when a new implementation issue is opened;",
)
section = """
### IMP-079 — Explicit PDF writing attachment

Status: implemented with deterministic synthetic CI evidence.

Extended the accepted local writing workflow with one optional caller-selected PDF primary source. `revise`, `summarize`, and `translate` now require exactly one of inline source text, one explicit text/Markdown document, or one explicit PDF. `draft` remains source-free. Existing inline and text/Markdown source behavior is preserved.

The workflow validates source-form selection, optional PDF page-selection types, operation identity, conversation target, capacity, active binding, and runtime declaration before opening the selected PDF. The PDF then passes only through the unchanged IMP-076 bounded extraction boundary: regular non-symlink file validation, the eight-megabyte source limit, path/open-handle identity checks, strict PDF parsing, encrypted-document rejection, a 200-page document limit, at most 100 unique one-based selected pages, caller-order preservation, and bounded page and aggregate extraction. The optional in-process `pypdf` adapter remains invocation-only. No OCR or scanned-PDF fallback is introduced.

After successful extraction, selected page strings are joined deterministically in caller order with two newline characters between page strings. The resulting writing material must also satisfy the existing 16,000-character writing-source limit before a writing-source InstructionOrigin is created. Blank selected material fails closed.

Extracted PDF text remains data-only `external_content` through `extractor` / `extraction` with `untrusted_data` authority. The current user request remains the only task-authority instruction. Instructions embedded in the PDF cannot change writing mode, target language, permissions, confirmation, capability authority, binding state, memory, project state, decisions, completion authority, or other authoritative state.

The content-free writing result identifies `pdf` source kind and exposes only adapter ID/version, source byte count and SHA-256, document page count, selected page numbers in caller order, empty-text selected page numbers, aggregate raw extracted-character count, and the existing writing-source character count after deterministic joining. Native path, filename, source text, prompt text, generated response text, credentials, and secrets are not added to the result.

Dedicated acceptance exercises real `pypdf` extraction through the writing workflow, selected-page order, source-form conflicts, page metadata validation, target-before-read ordering, optional-adapter failure, blank and over-limit material, hostile PDF instructions, runtime failure, path privacy, and exact source-file preservation. Standard CI passes on Ubuntu, macOS, and Windows. IMP-079 does not broaden the accepted IMP-064 primary Intel Mac real-machine evidence.

IMP-079 does not establish OCR or scanned-PDF fallback, image extraction, layout reconstruction, tables, forms, annotations, embedded attachments, password entry, PDF repair, multiple attachments, mixed primary sources, draft reference attachments, attachment persistence, SourceRecord creation, artifact publication, persistent indexing, automatic file discovery, semantic retrieval, embeddings, ranking, model-selected context, Web retrieval, process or shell execution, tools, capability execution, network or cloud access, target-specific export, accessibility presentation, Lite performance acceptance, the release-candidate soak, complete Phase 6, Lite v1.0 completion, or stable general anti-lock-in.

"""
roadmap = once(
    roadmap,
    "Subsequent daily-use work may expand PDF/OCR/CSV and multiple-attachment integration, cross-platform OCR adapters, accessibility presentation, Lite performance measurements, and soak testing.",
    section
    + "Subsequent daily-use work may expand OCR/CSV and multiple-attachment writing integration, cross-platform OCR adapters, accessibility presentation, Lite performance measurements, and soak testing.",
)
roadmap_path.write_text(roadmap, encoding="utf-8")


# Daily-use matrix
matrix_path = Path("docs/testing/phase-6-daily-use-matrix.json")
matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
matrix["pdf_writing_attachment_extension"] = {
    "implementation": "IMP-079",
    "status": "ci-pass",
    "description": "One explicit local PDF can replace inline or text/Markdown primary source material for revise, summarize, or translate after bounded IMP-076 extraction while remaining data-only untrusted writing material.",
    "pytest_files": [
        "tests/test_imp_079_pdf_writing_attachment.py",
        "tests/test_local_writing_workflow.py",
        "tests/test_imp_076_local_pdf.py",
    ],
    "passed_evidence_levels": ["ci"],
    "required_evidence_levels": ["ci"],
    "selection_mode": "explicit-single-file",
    "allowed_extensions": [".pdf"],
    "supported_modes": ["revise", "summarize", "translate"],
    "draft_primary_source_allowed": False,
    "exactly_one_primary_source": True,
    "primary_source_forms": ["inline", "document", "pdf"],
    "reader_implementation": "IMP-076",
    "adapter_optional": True,
    "adapter_id": "pypdf",
    "adapter_loading": "invocation-only",
    "page_numbering": "one-based",
    "caller_order_preserved": True,
    "page_join_separator": "\\n\\n",
    "maximum_pdf_source_bytes": 8388608,
    "maximum_document_pages": 200,
    "maximum_selected_pages": 100,
    "maximum_pdf_page_characters": 100000,
    "maximum_pdf_aggregate_characters": 1000000,
    "maximum_writing_source_characters": 16000,
    "encrypted_pdf_allowed": False,
    "ocr_used": False,
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
    "implementation_doc": "docs/implementation/imp-079-pdf-writing-attachment.md",
}
matrix_path.write_text(json.dumps(matrix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# Public project status
status_path = Path("website/project-status.json")
status = json.loads(status_path.read_text(encoding="utf-8"))
status["phase"]["next_implementation"] = 80
status["model_runtime"]["message"] = (
    "Phase 6 is in progress through IMP-079. Offline Ollama session import, explicit text-only loopback capture, the accepted bounded local-portability migration drill, the deterministic shutdown escape bundle, bounded ChatGPT selected-history import, imported-context replay with accepted primary Intel Mac evidence, bounded local draft/revise/summarize/translate workflows, explicit data-only state context, bounded local work-item proposals, explicit local portability review, structured local runtime failure guidance, a deterministic read-only doll doctor, explicit local full-text state search, explicit local UTF-8 text and Markdown reading, explicit local CSV inspection and transformation, optional local PDF text extraction, optional local image OCR, text/Markdown writing attachment integration, and PDF writing attachment integration are implemented. The IMP-063/IMP-064 writing workflow passes at both CI and real-machine evidence levels. IMP-076 uses an invocation-only in-process pypdf adapter; encrypted documents fail closed, pages without extractable text are reported without OCR, and no source overwrite, output file, persistence, model execution, process launch, network access, native-path disclosure, or automatic context injection occurs. IMP-077 uses the optional macOS Vision OCR path with no broadened primary real-machine claim. IMP-079 reuses IMP-076 so one explicit PDF, with optional caller-selected pages in caller order, can replace inline or text/Markdown primary source material for revise, summarize, or translate; extracted PDF text remains data-only untrusted content and must also satisfy the existing 16,000-character writing-source limit before source-origin creation. OCR/scanned-PDF fallback, OCR/CSV and multiple-attachment writing integration, accessibility presentation, Lite performance measurements, the release soak gate, semantic or automatic retrieval, cross-platform real OCR adapters, tools, the complete Phase 6 gate, Lite v1.0, target-specific application replacement, and stable general anti-lock-in remain incomplete."
)
status["last_reviewed"] = "2026-08-10"
status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# Public status checker
checker_path = Path("scripts/check-public-site-status.mjs")
checker = checker_path.read_text(encoding="utf-8")
checker = once(
    checker,
    'status.phase?.next_implementation === 79,\n  "project-status.json must mark Phase 6 in progress through IMP-078 with IMP-079 next"',
    'status.phase?.next_implementation === 80,\n  "project-status.json must mark Phase 6 in progress through IMP-079 with IMP-080 next"',
)
checker = once(
    checker,
    'status.model_runtime.message.includes("through IMP-078") &&',
    'status.model_runtime.message.includes("through IMP-079") &&',
)
checker = once(
    checker,
    'status.model_runtime.message.includes("text/Markdown writing attachment integration") &&',
    'status.model_runtime.message.includes("text/Markdown writing attachment integration") &&\n    status.model_runtime.message.includes("PDF writing attachment integration") &&',
)
checker = once(
    checker,
    '"project-status.json must describe IMP-078 without broadening accepted real-machine evidence"',
    '"project-status.json must describe IMP-079 without broadening accepted real-machine evidence"',
)
checker = once(
    checker,
    'roadmap.includes("### IMP-077 — Optional local image OCR adapter") &&\n    roadmap.includes("### IMP-078 — Explicit text and Markdown writing attachments") &&\n    roadmap.includes("the next bounded implementation receives IMP-079 only when a new implementation issue is opened"),\n  "roadmap must record IMP-078 and identify IMP-079 as the next unallocated implementation identifier"',
    'roadmap.includes("### IMP-077 — Optional local image OCR adapter") &&\n    roadmap.includes("### IMP-078 — Explicit text and Markdown writing attachments") &&\n    roadmap.includes("### IMP-079 — Explicit PDF writing attachment") &&\n    roadmap.includes("the next bounded implementation receives IMP-080 only when a new implementation issue is opened"),\n  "roadmap must record IMP-079 and identify IMP-080 as the next unallocated implementation identifier"',
)
marker = '''  "IMP-078 text/Markdown writing attachments must remain explicit, untrusted, local-only, and CI-only",\n);\n'''
attachment_check = '''\n\nexpect(\n  dailyUse.pdf_writing_attachment_extension?.implementation === "IMP-079" &&\n    dailyUse.pdf_writing_attachment_extension?.status === "ci-pass" &&\n    JSON.stringify(dailyUse.pdf_writing_attachment_extension?.passed_evidence_levels) === JSON.stringify(["ci"]) &&\n    JSON.stringify(dailyUse.pdf_writing_attachment_extension?.required_evidence_levels) === JSON.stringify(["ci"]) &&\n    dailyUse.pdf_writing_attachment_extension?.selection_mode === "explicit-single-file" &&\n    JSON.stringify(dailyUse.pdf_writing_attachment_extension?.allowed_extensions) === JSON.stringify([".pdf"]) &&\n    JSON.stringify(dailyUse.pdf_writing_attachment_extension?.supported_modes) === JSON.stringify(["revise", "summarize", "translate"]) &&\n    dailyUse.pdf_writing_attachment_extension?.draft_primary_source_allowed === false &&\n    dailyUse.pdf_writing_attachment_extension?.exactly_one_primary_source === true &&\n    JSON.stringify(dailyUse.pdf_writing_attachment_extension?.primary_source_forms) === JSON.stringify(["inline", "document", "pdf"]) &&\n    dailyUse.pdf_writing_attachment_extension?.reader_implementation === "IMP-076" &&\n    dailyUse.pdf_writing_attachment_extension?.adapter_optional === true &&\n    dailyUse.pdf_writing_attachment_extension?.adapter_id === "pypdf" &&\n    dailyUse.pdf_writing_attachment_extension?.adapter_loading === "invocation-only" &&\n    dailyUse.pdf_writing_attachment_extension?.page_numbering === "one-based" &&\n    dailyUse.pdf_writing_attachment_extension?.caller_order_preserved === true &&\n    dailyUse.pdf_writing_attachment_extension?.page_join_separator === "\\\\n\\\\n" &&\n    dailyUse.pdf_writing_attachment_extension?.maximum_pdf_source_bytes === 8388608 &&\n    dailyUse.pdf_writing_attachment_extension?.maximum_document_pages === 200 &&\n    dailyUse.pdf_writing_attachment_extension?.maximum_selected_pages === 100 &&\n    dailyUse.pdf_writing_attachment_extension?.maximum_pdf_page_characters === 100000 &&\n    dailyUse.pdf_writing_attachment_extension?.maximum_pdf_aggregate_characters === 1000000 &&\n    dailyUse.pdf_writing_attachment_extension?.maximum_writing_source_characters === 16000 &&\n    dailyUse.pdf_writing_attachment_extension?.encrypted_pdf_allowed === false &&\n    dailyUse.pdf_writing_attachment_extension?.ocr_used === false &&\n    dailyUse.pdf_writing_attachment_extension?.symlinks_allowed === false &&\n    dailyUse.pdf_writing_attachment_extension?.automatic_file_discovery === false &&\n    dailyUse.pdf_writing_attachment_extension?.persistent_document_record === false &&\n    dailyUse.pdf_writing_attachment_extension?.source_record_created === false &&\n    dailyUse.pdf_writing_attachment_extension?.artifact_created === false &&\n    dailyUse.pdf_writing_attachment_extension?.persistent_index === false &&\n    dailyUse.pdf_writing_attachment_extension?.semantic_retrieval === false &&\n    dailyUse.pdf_writing_attachment_extension?.model_selected_context === false &&\n    dailyUse.pdf_writing_attachment_extension?.network_access === false &&\n    dailyUse.pdf_writing_attachment_extension?.cloud_access === false &&\n    dailyUse.pdf_writing_attachment_extension?.process_launch === false &&\n    dailyUse.pdf_writing_attachment_extension?.shell_execution === false &&\n    dailyUse.pdf_writing_attachment_extension?.capability_execution === false &&\n    dailyUse.pdf_writing_attachment_extension?.origin_class === "external_content" &&\n    dailyUse.pdf_writing_attachment_extension?.actor_type === "extractor" &&\n    dailyUse.pdf_writing_attachment_extension?.acquisition_method === "extraction" &&\n    dailyUse.pdf_writing_attachment_extension?.authority_class === "untrusted_data" &&\n    dailyUse.pdf_writing_attachment_extension?.phase6_gate_complete === false &&\n    dailyUse.pdf_writing_attachment_extension?.lite_v1_complete === false &&\n    dailyUse.pdf_writing_attachment_extension?.stable_anti_lock_in_claim === false &&\n    dailyUse.pdf_writing_attachment_extension?.implementation_doc === "docs/implementation/imp-079-pdf-writing-attachment.md",\n  "IMP-079 PDF writing attachment must remain explicit, bounded, untrusted, local-only, and CI-only",\n);\n'''
checker = once(checker, marker, marker + attachment_check)
checker_path.write_text(checker, encoding="utf-8")


# Implementation status line
impl_path = Path("docs/implementation/imp-079-pdf-writing-attachment.md")
impl = impl_path.read_text(encoding="utf-8")
impl = once(
    impl,
    "Status: implementation and CI acceptance in progress.",
    "Status: implemented with deterministic CI evidence on Ubuntu, macOS, and Windows.",
)
impl_path.write_text(impl, encoding="utf-8")
