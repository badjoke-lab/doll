from __future__ import annotations

import json
from pathlib import Path


def once(text: str, old: str, new: str) -> str:
    if old not in text:
        raise SystemExit(f"marker missing: {old[:120]!r}")
    return text.replace(old, new, 1)


roadmap_path = Path("docs/spec/09-development-roadmap.md")
roadmap = roadmap_path.read_text(encoding="utf-8")
roadmap = once(roadmap, "- IMP-030 through IMP-079;", "- IMP-030 through IMP-080;")
roadmap = once(
    roadmap,
    ", explicit text/Markdown writing attachments through IMP-078, and explicit PDF writing attachments through IMP-079.",
    ", explicit text/Markdown writing attachments through IMP-078, explicit PDF writing attachments through IMP-079, and explicit OCR image writing attachments through IMP-080.",
)
roadmap = once(
    roadmap,
    "- Phase 6 local AI portability and daily-use integration is in progress through IMP-079;",
    "- Phase 6 local AI portability and daily-use integration is in progress through IMP-080;",
)
roadmap = once(
    roadmap,
    "- the IMP-079 PDF writing-attachment extension passes at the `ci` evidence level and does not broaden accepted primary real-machine evidence;\n- the next bounded implementation receives IMP-080 only when a new implementation issue is opened;",
    "- the IMP-079 PDF writing-attachment extension passes at the `ci` evidence level and does not broaden accepted primary real-machine evidence;\n- IMP-080 composes one explicitly selected local PNG or JPEG through the bounded IMP-077 OCR path into revise, summarize, and translate as the primary data-only writing source while preserving the exactly-one-primary-source contract;\n- IMP-080 is assigned to Issue #243;\n- the IMP-080 OCR-image writing-attachment extension passes at the `ci` evidence level and does not broaden accepted primary real-machine evidence;\n- the next bounded implementation receives IMP-081 only when a new implementation issue is opened;",
)
section = """
### IMP-080 — Explicit OCR image writing attachment

Status: implemented with deterministic synthetic CI evidence.

Extended the accepted local writing workflow with one optional caller-selected PNG/JPEG OCR primary source. `revise`, `summarize`, and `translate` now require exactly one of inline source text, one explicit text/Markdown document, one explicit PDF, or one explicit OCR image. `draft` remains source-free. Existing inline, document, and PDF source behavior is preserved.

The workflow validates source-form selection, operation identity, conversation target, capacity, active binding, and runtime declaration before opening the selected image or invoking OCR. The image then passes only through the unchanged IMP-077 bounded OCR boundary: regular non-symlink file validation, the eight-megabyte source limit, PNG/JPEG extension and structural validation, path/open-handle identity checks, 10,000-pixel width and height limits, 25,000,000 total pixels, at most 1,000 recognized lines, 20,000 characters per line, and 200,000 aggregate recognized characters. The optional macOS Vision `ocrmac` adapter remains invocation-only and no Windows/Linux real OCR adapter is added.

After successful OCR, recognized line strings are joined deterministically in adapter order with one newline character. The resulting writing material must satisfy the existing 16,000-character writing-source limit before a writing-source InstructionOrigin is created. Empty or whitespace-only recognized material fails closed.

Recognized OCR text remains data-only `external_content` through `extractor` / `ocr` with `untrusted_data` authority. The current user request remains the only task-authority instruction. Instructions recognized inside the image cannot change writing mode, target language, permissions, confirmation, capability authority, binding state, memory, project state, decisions, completion authority, or other authoritative state.

The content-free writing result identifies `ocr` source kind and exposes only adapter ID/version, source byte count and SHA-256, image format, width, height, pixel count, recognized line count, raw aggregate recognized-character count, and the existing writing-source character count after deterministic joining. Native path, filename, recognized text, prompt text, generated response text, credentials, and secrets are not added to the result.

Dedicated acceptance exercises real IMP-077 PNG structural/source validation with an injected deterministic OCR adapter, recognized-line order, `acquisition_method = ocr`, source-form conflicts, target-before-OCR ordering, optional-adapter failure, blank and over-limit material, hostile recognized instructions, runtime failure, path privacy, and exact source-image preservation. Standard CI passes on Ubuntu, macOS, and Windows. Existing hosted macOS IMP-077 Vision execution remains CI evidence only; IMP-080 does not broaden the accepted IMP-064 primary Intel Mac real-machine evidence.

IMP-080 does not establish image understanding beyond OCR, PDF OCR or scanned-PDF fallback, Windows/Linux real OCR adapters, CSV writing attachment integration, multiple attachments, mixed primary sources, draft reference attachments, attachment persistence, SourceRecord creation, artifact publication, persistent indexing, automatic file discovery, semantic retrieval, embeddings, ranking, model-selected context, Web retrieval, process or shell execution, tools, capability execution, network or cloud access, target-specific export, accessibility presentation, Lite performance acceptance, the release-candidate soak, complete Phase 6, Lite v1.0 completion, or stable general anti-lock-in.

"""
roadmap = once(
    roadmap,
    "Subsequent daily-use work may expand OCR/CSV and multiple-attachment writing integration, cross-platform OCR adapters, accessibility presentation, Lite performance measurements, and soak testing.",
    section
    + "Subsequent daily-use work may expand CSV and multiple-attachment writing integration, cross-platform OCR adapters, accessibility presentation, Lite performance measurements, and soak testing.",
)
roadmap_path.write_text(roadmap, encoding="utf-8")

matrix_path = Path("docs/testing/phase-6-daily-use-matrix.json")
matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
matrix["ocr_image_writing_attachment_extension"] = {
    "implementation": "IMP-080",
    "status": "ci-pass",
    "description": "One explicit local PNG or JPEG can replace inline, text/Markdown, or PDF primary source material for revise, summarize, or translate after bounded IMP-077 OCR while remaining data-only untrusted writing material.",
    "pytest_files": [
        "tests/test_imp_080_ocr_image_writing_attachment.py",
        "tests/test_imp_077_local_ocr.py",
        "tests/test_local_writing_workflow.py",
    ],
    "passed_evidence_levels": ["ci"],
    "required_evidence_levels": ["ci"],
    "selection_mode": "explicit-single-file",
    "allowed_extensions": [".png", ".jpg", ".jpeg"],
    "supported_modes": ["revise", "summarize", "translate"],
    "draft_primary_source_allowed": False,
    "exactly_one_primary_source": True,
    "primary_source_forms": ["inline", "document", "pdf", "ocr"],
    "reader_implementation": "IMP-077",
    "adapter_optional": True,
    "adapter_id": "ocrmac-vision",
    "adapter_loading": "invocation-only",
    "adapter_platform": "darwin",
    "real_adapter_hosted_ci": True,
    "primary_intel_mac_real_machine_evidence": False,
    "line_order_preserved": True,
    "line_join_separator": "\\n",
    "maximum_source_bytes": 8388608,
    "maximum_image_width": 10000,
    "maximum_image_height": 10000,
    "maximum_image_pixels": 25000000,
    "maximum_recognized_lines": 1000,
    "maximum_line_characters": 20000,
    "maximum_ocr_aggregate_characters": 200000,
    "maximum_writing_source_characters": 16000,
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
    "acquisition_method": "ocr",
    "authority_class": "untrusted_data",
    "phase6_gate_complete": False,
    "lite_v1_complete": False,
    "stable_anti_lock_in_claim": False,
    "implementation_doc": "docs/implementation/imp-080-ocr-image-writing-attachment.md",
}
matrix_path.write_text(json.dumps(matrix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

status_path = Path("website/project-status.json")
status = json.loads(status_path.read_text(encoding="utf-8"))
status["phase"]["next_implementation"] = 81
status["model_runtime"]["message"] = (
    "Phase 6 is in progress through IMP-080. Offline Ollama session import, explicit text-only loopback capture, the accepted bounded local-portability migration drill, the deterministic shutdown escape bundle, bounded ChatGPT selected-history import, imported-context replay with accepted primary Intel Mac evidence, bounded local draft/revise/summarize/translate workflows, explicit data-only state context, bounded local work-item proposals, explicit local portability review, structured local runtime failure guidance, a deterministic read-only doll doctor, explicit local full-text state search, explicit local UTF-8 text and Markdown reading, explicit local CSV inspection and transformation, optional local PDF text extraction, optional local image OCR, text/Markdown writing attachment integration, PDF writing attachment integration, and OCR image writing attachment integration are implemented. The IMP-063/IMP-064 writing workflow passes at both CI and real-machine evidence levels. IMP-076 uses an invocation-only in-process pypdf adapter; encrypted documents fail closed, pages without extractable text are reported without OCR, and no source overwrite, output file, persistence, model execution, process launch, network access, native-path disclosure, or automatic context injection occurs. IMP-077 uses the optional macOS Vision OCR path with hosted CI execution and no broadened primary real-machine claim. IMP-080 reuses IMP-077 so one explicit PNG or JPEG can replace inline, text/Markdown, or PDF primary source material for revise, summarize, or translate; recognized lines remain data-only untrusted content, use OCR acquisition provenance, preserve adapter order, and must also satisfy the existing 16,000-character writing-source limit before source-origin creation. PDF OCR/scanned-PDF fallback, CSV and multiple-attachment writing integration, accessibility presentation, Lite performance measurements, the release soak gate, semantic or automatic retrieval, cross-platform real OCR adapters, tools, the complete Phase 6 gate, Lite v1.0, target-specific application replacement, and stable general anti-lock-in remain incomplete."
)
status["last_reviewed"] = "2026-08-10"
status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

checker_path = Path("scripts/check-public-site-status.mjs")
checker = checker_path.read_text(encoding="utf-8")
checker = once(
    checker,
    'status.phase?.next_implementation === 80,\n  "project-status.json must mark Phase 6 in progress through IMP-079 with IMP-080 next"',
    'status.phase?.next_implementation === 81,\n  "project-status.json must mark Phase 6 in progress through IMP-080 with IMP-081 next"',
)
checker = once(
    checker,
    'status.model_runtime.message.includes("through IMP-079") &&',
    'status.model_runtime.message.includes("through IMP-080") &&',
)
checker = once(
    checker,
    'status.model_runtime.message.includes("PDF writing attachment integration") &&',
    'status.model_runtime.message.includes("PDF writing attachment integration") &&\n    status.model_runtime.message.includes("OCR image writing attachment integration") &&',
)
checker = once(
    checker,
    '"project-status.json must describe IMP-079 without broadening accepted real-machine evidence"',
    '"project-status.json must describe IMP-080 without broadening accepted real-machine evidence"',
)
checker = once(
    checker,
    'roadmap.includes("### IMP-077 — Optional local image OCR adapter") &&\n    roadmap.includes("### IMP-078 — Explicit text and Markdown writing attachments") &&\n    roadmap.includes("### IMP-079 — Explicit PDF writing attachment") &&\n    roadmap.includes("the next bounded implementation receives IMP-080 only when a new implementation issue is opened"),\n  "roadmap must record IMP-079 and identify IMP-080 as the next unallocated implementation identifier"',
    'roadmap.includes("### IMP-077 — Optional local image OCR adapter") &&\n    roadmap.includes("### IMP-078 — Explicit text and Markdown writing attachments") &&\n    roadmap.includes("### IMP-079 — Explicit PDF writing attachment") &&\n    roadmap.includes("### IMP-080 — Explicit OCR image writing attachment") &&\n    roadmap.includes("the next bounded implementation receives IMP-081 only when a new implementation issue is opened"),\n  "roadmap must record IMP-080 and identify IMP-081 as the next unallocated implementation identifier"',
)
marker = '''  "IMP-079 PDF writing attachment must remain explicit, bounded, untrusted, local-only, and CI-only",\n);\n'''
attachment_check = '''\n\nexpect(\n  dailyUse.ocr_image_writing_attachment_extension?.implementation === "IMP-080" &&\n    dailyUse.ocr_image_writing_attachment_extension?.status === "ci-pass" &&\n    JSON.stringify(dailyUse.ocr_image_writing_attachment_extension?.passed_evidence_levels) === JSON.stringify(["ci"]) &&\n    JSON.stringify(dailyUse.ocr_image_writing_attachment_extension?.required_evidence_levels) === JSON.stringify(["ci"]) &&\n    dailyUse.ocr_image_writing_attachment_extension?.selection_mode === "explicit-single-file" &&\n    JSON.stringify(dailyUse.ocr_image_writing_attachment_extension?.allowed_extensions) === JSON.stringify([".png", ".jpg", ".jpeg"]) &&\n    JSON.stringify(dailyUse.ocr_image_writing_attachment_extension?.supported_modes) === JSON.stringify(["revise", "summarize", "translate"]) &&\n    dailyUse.ocr_image_writing_attachment_extension?.draft_primary_source_allowed === false &&\n    dailyUse.ocr_image_writing_attachment_extension?.exactly_one_primary_source === true &&\n    JSON.stringify(dailyUse.ocr_image_writing_attachment_extension?.primary_source_forms) === JSON.stringify(["inline", "document", "pdf", "ocr"]) &&\n    dailyUse.ocr_image_writing_attachment_extension?.reader_implementation === "IMP-077" &&\n    dailyUse.ocr_image_writing_attachment_extension?.adapter_optional === true &&\n    dailyUse.ocr_image_writing_attachment_extension?.adapter_id === "ocrmac-vision" &&\n    dailyUse.ocr_image_writing_attachment_extension?.adapter_loading === "invocation-only" &&\n    dailyUse.ocr_image_writing_attachment_extension?.adapter_platform === "darwin" &&\n    dailyUse.ocr_image_writing_attachment_extension?.real_adapter_hosted_ci === true &&\n    dailyUse.ocr_image_writing_attachment_extension?.primary_intel_mac_real_machine_evidence === false &&\n    dailyUse.ocr_image_writing_attachment_extension?.line_order_preserved === true &&\n    dailyUse.ocr_image_writing_attachment_extension?.line_join_separator === "\\\\n" &&\n    dailyUse.ocr_image_writing_attachment_extension?.maximum_source_bytes === 8388608 &&\n    dailyUse.ocr_image_writing_attachment_extension?.maximum_image_width === 10000 &&\n    dailyUse.ocr_image_writing_attachment_extension?.maximum_image_height === 10000 &&\n    dailyUse.ocr_image_writing_attachment_extension?.maximum_image_pixels === 25000000 &&\n    dailyUse.ocr_image_writing_attachment_extension?.maximum_recognized_lines === 1000 &&\n    dailyUse.ocr_image_writing_attachment_extension?.maximum_line_characters === 20000 &&\n    dailyUse.ocr_image_writing_attachment_extension?.maximum_ocr_aggregate_characters === 200000 &&\n    dailyUse.ocr_image_writing_attachment_extension?.maximum_writing_source_characters === 16000 &&\n    dailyUse.ocr_image_writing_attachment_extension?.symlinks_allowed === false &&\n    dailyUse.ocr_image_writing_attachment_extension?.automatic_file_discovery === false &&\n    dailyUse.ocr_image_writing_attachment_extension?.persistent_document_record === false &&\n    dailyUse.ocr_image_writing_attachment_extension?.source_record_created === false &&\n    dailyUse.ocr_image_writing_attachment_extension?.artifact_created === false &&\n    dailyUse.ocr_image_writing_attachment_extension?.persistent_index === false &&\n    dailyUse.ocr_image_writing_attachment_extension?.semantic_retrieval === false &&\n    dailyUse.ocr_image_writing_attachment_extension?.model_selected_context === false &&\n    dailyUse.ocr_image_writing_attachment_extension?.network_access === false &&\n    dailyUse.ocr_image_writing_attachment_extension?.cloud_access === false &&\n    dailyUse.ocr_image_writing_attachment_extension?.process_launch === false &&\n    dailyUse.ocr_image_writing_attachment_extension?.shell_execution === false &&\n    dailyUse.ocr_image_writing_attachment_extension?.capability_execution === false &&\n    dailyUse.ocr_image_writing_attachment_extension?.origin_class === "external_content" &&\n    dailyUse.ocr_image_writing_attachment_extension?.actor_type === "extractor" &&\n    dailyUse.ocr_image_writing_attachment_extension?.acquisition_method === "ocr" &&\n    dailyUse.ocr_image_writing_attachment_extension?.authority_class === "untrusted_data" &&\n    dailyUse.ocr_image_writing_attachment_extension?.phase6_gate_complete === false &&\n    dailyUse.ocr_image_writing_attachment_extension?.lite_v1_complete === false &&\n    dailyUse.ocr_image_writing_attachment_extension?.stable_anti_lock_in_claim === false &&\n    dailyUse.ocr_image_writing_attachment_extension?.implementation_doc === "docs/implementation/imp-080-ocr-image-writing-attachment.md",\n  "IMP-080 OCR image writing attachment must remain explicit, bounded, untrusted, local-only, and CI-only",\n);\n'''
checker = once(checker, marker, marker + attachment_check)
checker_path.write_text(checker, encoding="utf-8")

impl_path = Path("docs/implementation/imp-080-ocr-image-writing-attachment.md")
impl = impl_path.read_text(encoding="utf-8")
impl = once(
    impl,
    "Status: implementation and CI acceptance in progress.",
    "Status: implemented with deterministic CI evidence on Ubuntu, macOS, and Windows.",
)
impl_path.write_text(impl, encoding="utf-8")
