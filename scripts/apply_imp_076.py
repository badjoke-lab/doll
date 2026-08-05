from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8", newline="\n")


def replace_once(content: str, old: str, new: str, *, label: str) -> str:
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return content.replace(old, new, 1)


def update_pdf_core() -> None:
    path = "src/doll/local_pdf.py"
    content = read(path)
    old = """    try:\n        encrypted = bool(reader.is_encrypted)\n        document_page_count = len(reader.pages)\n    except Exception as exc:\n        raise LocalPdfValidationError(\"local PDF page inventory is unavailable\") from exc\n    if encrypted:\n        raise LocalPdfValidationError(\"encrypted local PDFs are not supported\")\n"""
    new = """    try:\n        encrypted = bool(reader.is_encrypted)\n    except Exception as exc:\n        raise LocalPdfValidationError(\"local PDF encryption state is unavailable\") from exc\n    if encrypted:\n        raise LocalPdfValidationError(\"encrypted local PDFs are not supported\")\n    try:\n        document_page_count = len(reader.pages)\n    except Exception as exc:\n        raise LocalPdfValidationError(\"local PDF page inventory is unavailable\") from exc\n"""
    write(path, replace_once(content, old, new, label="PDF encryption order"))


def update_pyproject() -> None:
    path = "pyproject.toml"
    content = read(path)
    content = replace_once(
        content,
        "]\n\n[project.scripts]\n",
        "]\n\n[project.optional-dependencies]\npdf = [\"pypdf>=6.14.2,<7\"]\n\n[project.scripts]\n",
        label="optional PDF dependency",
    )
    content = replace_once(
        content,
        '  "mypy>=1.15,<2",\n',
        '  "mypy>=1.15,<2",\n  "pypdf>=6.14.2,<7",\n',
        label="PDF development dependency",
    )
    write(path, content)


def update_cli() -> None:
    path = "src/doll/cli.py"
    content = read(path)
    content = replace_once(
        content,
        "from doll.local_document_cli import document_app\n",
        "from doll.local_document_cli import document_app\nfrom doll.local_pdf_cli import pdf_app\n",
        label="PDF CLI import",
    )
    content = replace_once(
        content,
        'app.add_typer(document_app, name="document")\n',
        'app.add_typer(document_app, name="document")\napp.add_typer(pdf_app, name="pdf")\n',
        label="PDF CLI registration",
    )
    write(path, content)

    test_path = "tests/test_cli.py"
    tests = read(test_path)
    tests = replace_once(
        tests,
        '    assert "csv" in result.stdout\n',
        '    assert "csv" in result.stdout\n    assert "pdf" in result.stdout\n',
        label="PDF root help test",
    )
    write(test_path, tests)


def update_daily_matrix() -> None:
    path = "docs/testing/phase-6-daily-use-matrix.json"
    payload = json.loads(read(path))
    if "local_pdf_extension" in payload:
        raise RuntimeError("local PDF matrix extension already exists")
    payload["local_pdf_extension"] = {
        "implementation": "IMP-076",
        "status": "ci-pass",
        "description": (
            "One caller-selected PDF can be text-extracted through an optional "
            "in-process pypdf adapter with explicit page selection and no OCR, "
            "persistence, model execution, process launch, or network access."
        ),
        "pytest_files": ["tests/test_imp_076_local_pdf.py", "tests/test_cli.py"],
        "passed_evidence_levels": ["ci"],
        "required_evidence_levels": ["ci"],
        "report_schema_version": 1,
        "selection_mode": "explicit-single-file",
        "allowed_extensions": [".pdf"],
        "adapter_optional": True,
        "adapter_id": "pypdf",
        "adapter_version_range": ">=6.14.2,<7",
        "adapter_loading": "invocation-only",
        "strict_parsing": True,
        "maximum_source_bytes": 8388608,
        "maximum_document_pages": 200,
        "maximum_selected_pages": 100,
        "maximum_page_characters": 100000,
        "maximum_aggregate_characters": 1000000,
        "page_numbering": "one-based",
        "caller_order_preserved": True,
        "symlinks_allowed": False,
        "encrypted_pdf_allowed": False,
        "password_entry": False,
        "ocr_used": False,
        "image_extraction_used": False,
        "source_overwrite": False,
        "source_persisted": False,
        "output_persisted": False,
        "artifact_created": False,
        "index_created": False,
        "workspace_mutation": False,
        "state_mutation": False,
        "audit_mutation": False,
        "context_injection": False,
        "model_execution": False,
        "runtime_start": False,
        "process_launch": False,
        "shell_execution": False,
        "tool_execution": False,
        "capability_execution": False,
        "network_access": False,
        "cloud_fallback": False,
        "origin_class": "external_content",
        "actor_type": "extractor",
        "acquisition_method": "extraction",
        "authority_class": "untrusted_data",
        "phase6_gate_complete": False,
        "lite_v1_complete": False,
        "stable_anti_lock_in_claim": False,
        "implementation_doc": (
            "docs/implementation/imp-076-optional-local-pdf-text-extraction.md"
        ),
    }
    write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def update_status() -> None:
    path = "website/project-status.json"
    payload = json.loads(read(path))
    payload["phase"]["next_implementation"] = 77
    payload["model_runtime"]["message"] = (
        "Phase 6 is in progress through IMP-076. Offline Ollama session import, "
        "explicit text-only loopback capture, the accepted bounded local-portability "
        "migration drill, the deterministic shutdown escape bundle, bounded ChatGPT "
        "selected-history import, imported-context replay with accepted primary Intel "
        "Mac evidence, bounded local draft/revise/summarize/translate workflows, "
        "explicit data-only context, bounded local work-item proposals, explicit local "
        "portability review, structured local runtime failure guidance, a deterministic "
        "read-only doll doctor, explicit local full-text state search, explicit local "
        "UTF-8 text and Markdown reading, explicit local CSV inspection and "
        "transformation, and optional local PDF text extraction are implemented. The "
        "IMP-063/IMP-064 writing workflow passes at both CI and real-machine evidence "
        "levels. IMP-076 extracts bounded page text from one caller-selected regular "
        "non-symlink PDF through an invocation-only in-process pypdf adapter. Encrypted "
        "documents fail closed, pages without extractable text are reported without "
        "OCR, and no source overwrite, output file, persistence, model execution, "
        "process launch, network access, native-path disclosure, or automatic context "
        "injection occurs. Accessibility presentation, Lite performance measurements, "
        "the release soak gate, semantic or automatic retrieval, attachment "
        "integration, approved OCR adapters, tools, the complete Phase 6 gate, Lite "
        "v1.0, target-specific application replacement, and stable general anti-lock-in "
        "remain incomplete."
    )
    payload["last_reviewed"] = "2026-08-05"
    write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def update_roadmap() -> None:
    path = "docs/spec/09-development-roadmap.md"
    content = read(path)
    replacements = [
        ("- IMP-030 through IMP-075;", "- IMP-030 through IMP-076;", "completed range"),
        (
            "explicit local text and Markdown reading through IMP-074, and explicit "
            "local CSV inspection and simple transformation through IMP-075.",
            "explicit local text and Markdown reading through IMP-074, explicit local "
            "CSV inspection and simple transformation through IMP-075, and optional "
            "local PDF text extraction through IMP-076.",
            "completed summary",
        ),
        (
            "- Phase 6 local AI portability and daily-use integration is in progress "
            "through IMP-075;",
            "- Phase 6 local AI portability and daily-use integration is in progress "
            "through IMP-076;",
            "phase progress",
        ),
        (
            "- the IMP-075 local-CSV extension passes at the `ci` evidence level and "
            "does not broaden accepted real-machine evidence;\n"
            "- the next bounded implementation receives IMP-076 only when a new "
            "implementation issue is opened;",
            "- the IMP-075 local-CSV extension passes at the `ci` evidence level and "
            "does not broaden accepted real-machine evidence;\n"
            "- IMP-076 adds one optional invocation-only in-process pypdf adapter for "
            "bounded text extraction from one explicitly selected local PDF, with "
            "exact page selection, empty-text page reporting, and no OCR, persistence, "
            "process launch, model execution, or network access;\n"
            "- IMP-076 is assigned to Issue #235;\n"
            "- the IMP-076 local-PDF extension passes at the `ci` evidence level and "
            "does not broaden accepted real-machine evidence;\n"
            "- the next bounded implementation receives IMP-077 only when a new "
            "implementation issue is opened;",
            "current implementation bullets",
        ),
        (
            "through IMP-068 to IMP-075; semantic retrieval",
            "through IMP-068 to IMP-076; semantic retrieval",
            "immediate work boundary",
        ),
    ]
    for old, new, label in replacements:
        content = replace_once(content, old, new, label=label)

    marker = (
        "Subsequent daily-use work may expand approved PDF/OCR adapters, attachment "
        "integration, accessibility presentation, Lite performance measurements, and "
        "soak testing."
    )
    section = """### IMP-076 — Optional local PDF text extraction adapter

Status: implemented with deterministic synthetic and in-process `pypdf` CI evidence.

Implemented `doll pdf extract` over one caller-selected regular non-symlink `.pdf` file through a replaceable optional adapter contract. The default `pypdf` adapter is imported only when extraction is invoked; core startup, help, and non-PDF commands remain available without the optional dependency.

Source bytes are bounded to eight megabytes and protected by path/open-handle identity, size, and modification-time verification. Parsing is in-process through `PdfReader(..., strict=True)`. Encrypted documents fail before page inventory. Documents are bounded to 200 pages, and callers may extract all pages or up to 100 unique one-based pages in exact caller order.

Per-page extracted text is bounded to 100,000 characters and aggregate selected text to 1,000,000 characters. Pages with no extractable text are reported explicitly without OCR or image fallback. Results contain path-free adapter identity, source hash and byte count, page counts and order, aggregate counts, empty-text pages, and optional page text.

All extracted text remains `external_content`, `extractor`, `extraction`, and `untrusted_data`. The workflow performs no source overwrite, output-file creation, workspace, state, artifact, audit, or index mutation, context injection, OCR, image extraction, model or runtime execution, process or shell launch, tool or capability execution, network or cloud access, credential access, permission or binding change. Dedicated acceptance covers adapter absence, real extraction, Unicode and Japanese synthetic text, page selection, empty pages, hashes, limits, encryption, malformed and unsafe inputs, source and state preservation, CLI output, and path privacy. Standard CI covers Ubuntu, macOS, and Windows.

IMP-076 does not establish OCR, image extraction, layout reconstruction, table extraction, forms, annotations, attachments, password entry, PDF repair, JavaScript execution, external processes, arbitrary plugins, automatic discovery, semantic retrieval, model-selected context, writing-workflow attachment integration, artifact publication, persistent extraction results, Web retrieval, performance acceptance, the release-candidate soak, complete Phase 6, Lite v1.0 completion, or stable general anti-lock-in.

Subsequent daily-use work may expand approved OCR adapters, attachment integration, accessibility presentation, Lite performance measurements, and soak testing."""
    content = replace_once(content, marker, section, label="IMP-076 roadmap section")
    write(path, content)


def update_checker() -> None:
    path = "scripts/check-public-site-status.mjs"
    content = read(path)
    content = replace_once(
        content,
        '    status.phase?.next_implementation === 76,\n  "project-status.json must mark Phase 6 in progress through IMP-075 with IMP-076 next",',
        '    status.phase?.next_implementation === 77,\n  "project-status.json must mark Phase 6 in progress through IMP-076 with IMP-077 next",',
        label="public status phase",
    )
    old_status = """  status.model_runtime.message.includes("through IMP-075") &&
    status.model_runtime.message.includes("explicit local CSV inspection and transformation") &&
    status.model_runtime.message.includes("column selection, reordering, and header renaming") &&
    status.model_runtime.message.includes("never evaluated or rewritten") &&
    status.model_runtime.message.includes("no source overwrite, output file, persistence") &&
    status.model_runtime.message.includes("passes at both CI and real-machine evidence levels"),
  "project-status.json must describe IMP-075 without broadening accepted real-machine evidence",
"""
    new_status = """  status.model_runtime.message.includes("through IMP-076") &&
    status.model_runtime.message.includes("optional local PDF text extraction") &&
    status.model_runtime.message.includes("invocation-only in-process pypdf adapter") &&
    status.model_runtime.message.includes("reported without OCR") &&
    status.model_runtime.message.includes("no source overwrite, output file, persistence") &&
    status.model_runtime.message.includes("passes at both CI and real-machine evidence levels"),
  "project-status.json must describe IMP-076 without broadening accepted real-machine evidence",
"""
    content = replace_once(content, old_status, new_status, label="public status message")

    marker = """expect(
  localWritingPrimary.test_id === "IMP-064-LOCAL-WRITING-PRIMARY" &&
"""
    pdf_check = """expect(
  dailyUse.local_pdf_extension?.implementation === "IMP-076" &&
    dailyUse.local_pdf_extension?.status === "ci-pass" &&
    JSON.stringify(dailyUse.local_pdf_extension?.passed_evidence_levels) ===
      JSON.stringify(["ci"]) &&
    JSON.stringify(dailyUse.local_pdf_extension?.required_evidence_levels) ===
      JSON.stringify(["ci"]) &&
    dailyUse.local_pdf_extension?.report_schema_version === 1 &&
    dailyUse.local_pdf_extension?.selection_mode === "explicit-single-file" &&
    JSON.stringify(dailyUse.local_pdf_extension?.allowed_extensions) ===
      JSON.stringify([".pdf"]) &&
    dailyUse.local_pdf_extension?.adapter_optional === true &&
    dailyUse.local_pdf_extension?.adapter_id === "pypdf" &&
    dailyUse.local_pdf_extension?.adapter_version_range === ">=6.14.2,<7" &&
    dailyUse.local_pdf_extension?.adapter_loading === "invocation-only" &&
    dailyUse.local_pdf_extension?.strict_parsing === true &&
    dailyUse.local_pdf_extension?.maximum_source_bytes === 8388608 &&
    dailyUse.local_pdf_extension?.maximum_document_pages === 200 &&
    dailyUse.local_pdf_extension?.maximum_selected_pages === 100 &&
    dailyUse.local_pdf_extension?.maximum_page_characters === 100000 &&
    dailyUse.local_pdf_extension?.maximum_aggregate_characters === 1000000 &&
    dailyUse.local_pdf_extension?.page_numbering === "one-based" &&
    dailyUse.local_pdf_extension?.caller_order_preserved === true &&
    dailyUse.local_pdf_extension?.symlinks_allowed === false &&
    dailyUse.local_pdf_extension?.encrypted_pdf_allowed === false &&
    dailyUse.local_pdf_extension?.password_entry === false &&
    dailyUse.local_pdf_extension?.ocr_used === false &&
    dailyUse.local_pdf_extension?.image_extraction_used === false &&
    dailyUse.local_pdf_extension?.source_overwrite === false &&
    dailyUse.local_pdf_extension?.source_persisted === false &&
    dailyUse.local_pdf_extension?.output_persisted === false &&
    dailyUse.local_pdf_extension?.artifact_created === false &&
    dailyUse.local_pdf_extension?.index_created === false &&
    dailyUse.local_pdf_extension?.workspace_mutation === false &&
    dailyUse.local_pdf_extension?.state_mutation === false &&
    dailyUse.local_pdf_extension?.audit_mutation === false &&
    dailyUse.local_pdf_extension?.context_injection === false &&
    dailyUse.local_pdf_extension?.model_execution === false &&
    dailyUse.local_pdf_extension?.runtime_start === false &&
    dailyUse.local_pdf_extension?.process_launch === false &&
    dailyUse.local_pdf_extension?.shell_execution === false &&
    dailyUse.local_pdf_extension?.tool_execution === false &&
    dailyUse.local_pdf_extension?.capability_execution === false &&
    dailyUse.local_pdf_extension?.network_access === false &&
    dailyUse.local_pdf_extension?.cloud_fallback === false &&
    dailyUse.local_pdf_extension?.origin_class === "external_content" &&
    dailyUse.local_pdf_extension?.actor_type === "extractor" &&
    dailyUse.local_pdf_extension?.acquisition_method === "extraction" &&
    dailyUse.local_pdf_extension?.authority_class === "untrusted_data" &&
    dailyUse.local_pdf_extension?.phase6_gate_complete === false &&
    dailyUse.local_pdf_extension?.lite_v1_complete === false &&
    dailyUse.local_pdf_extension?.stable_anti_lock_in_claim === false &&
    dailyUse.local_pdf_extension?.implementation_doc ===
      "docs/implementation/imp-076-optional-local-pdf-text-extraction.md",
  "IMP-076 local PDF extraction must remain optional, untrusted, local-only, and CI-only",
);

"""
    content = replace_once(content, marker, pdf_check + marker, label="PDF status check")
    write(path, content)


def main() -> None:
    update_pdf_core()
    update_pyproject()
    update_cli()
    update_daily_matrix()
    update_status()
    update_roadmap()
    update_checker()
    print("IMP-076 integration updates applied")


if __name__ == "__main__":
    main()
