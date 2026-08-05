from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one match in {path}: found {count}: {old[:80]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def update_cli() -> None:
    path = ROOT / "src/doll/cli.py"
    replace_once(
        path,
        "from doll.local_search_cli import search_command\n",
        "from doll.local_document_cli import document_app\n"
        "from doll.local_search_cli import search_command\n",
    )
    replace_once(
        path,
        "app.add_typer(backup_app, name=\"backup\")\n"
        "app.command(\"doctor\")(doctor_command)\n",
        "app.add_typer(backup_app, name=\"backup\")\n"
        "app.add_typer(document_app, name=\"document\")\n"
        "app.command(\"doctor\")(doctor_command)\n",
    )

    tests = ROOT / "tests/test_cli.py"
    replace_once(
        tests,
        '    assert "search" in result.stdout\n',
        '    assert "search" in result.stdout\n    assert "document" in result.stdout\n',
    )


def update_daily_use_matrix() -> None:
    path = ROOT / "docs/testing/phase-6-daily-use-matrix.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "local_text_markdown_extension" in payload:
        raise RuntimeError("IMP-074 daily-use entry already exists")
    payload["local_text_markdown_extension"] = {
        "implementation": "IMP-074",
        "status": "ci-pass",
        "description": (
            "One caller-selected local UTF-8 text or Markdown file can be read "
            "exactly through a bounded path-free external-content boundary without "
            "copying, persistence, model execution, or network access."
        ),
        "pytest_files": [
            "tests/test_imp_074_local_document.py",
            "tests/test_cli.py",
        ],
        "passed_evidence_levels": ["ci"],
        "required_evidence_levels": ["ci"],
        "report_schema_version": 1,
        "selection_mode": "explicit-single-file",
        "allowed_extensions": [".txt", ".md", ".markdown"],
        "strict_utf8": True,
        "utf8_bom_handling": "remove-and-report",
        "maximum_source_bytes": 1048576,
        "maximum_text_characters": 1000000,
        "symlinks_allowed": False,
        "source_persisted": False,
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
            "docs/implementation/imp-074-explicit-local-text-markdown-read.md"
        ),
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def update_project_status() -> None:
    path = ROOT / "website/project-status.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["phase"]["next_implementation"] = 75
    payload["model_runtime"]["message"] = (
        "Phase 6 is in progress through IMP-074. Offline Ollama session import, "
        "explicit text-only loopback capture, the accepted bounded local-portability "
        "migration drill, the deterministic shutdown escape bundle, bounded ChatGPT "
        "selected-history import, imported-context replay with accepted primary Intel "
        "Mac evidence, bounded local draft/revise/summarize/translate workflows, "
        "explicit data-only context, bounded local work-item proposals, explicit local "
        "portability review, structured local runtime failure guidance, a deterministic "
        "read-only doll doctor, explicit local full-text state search, and explicit local "
        "UTF-8 text and Markdown reading are implemented. The IMP-063/IMP-064 writing "
        "workflow passes at both CI and real-machine evidence levels. IMP-074 reads only "
        "one caller-selected regular non-symlink .txt, .md, or .markdown file, preserves "
        "bounded UTF-8 content after deterministic BOM handling, and classifies it as "
        "external_content/untrusted_data without copying, persistence, model execution, "
        "network access, native-path disclosure, or automatic context injection. "
        "Accessibility presentation, Lite performance measurements, the release soak "
        "gate, semantic or automatic retrieval, attachment integration, approved "
        "PDF/OCR/CSV adapters, tools, the complete Phase 6 gate, Lite v1.0, "
        "target-specific application replacement, and stable general anti-lock-in "
        "remain incomplete."
    )
    payload["last_reviewed"] = "2026-08-05"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def update_roadmap() -> None:
    path = ROOT / "docs/spec/09-development-roadmap.md"
    replace_once(path, "- IMP-030 through IMP-073;", "- IMP-030 through IMP-074;")
    replace_once(
        path,
        "read-only local doctor diagnostics through IMP-072, and explicit local full-text "
        "state search through IMP-073.",
        "read-only local doctor diagnostics through IMP-072, explicit local full-text "
        "state search through IMP-073, and explicit local text and Markdown reading "
        "through IMP-074.",
    )
    replace_once(
        path,
        "- Phase 6 local AI portability and daily-use integration is in progress through "
        "IMP-073;",
        "- Phase 6 local AI portability and daily-use integration is in progress through "
        "IMP-074;",
    )
    replace_once(
        path,
        "- the IMP-073 local-search extension passes at the `ci` evidence level and does "
        "not broaden accepted real-machine evidence;\n"
        "- the next bounded implementation receives IMP-074 only when a new implementation "
        "issue is opened;",
        "- the IMP-073 local-search extension passes at the `ci` evidence level and does "
        "not broaden accepted real-machine evidence;\n"
        "- IMP-074 adds one explicit bounded read of a caller-selected regular non-symlink "
        "UTF-8 text or Markdown file, with deterministic BOM handling, exact hashes, fixed "
        "external-content origin, and no persistence, model execution, or network access;\n"
        "- IMP-074 is assigned to Issue #231;\n"
        "- the IMP-074 local-document extension passes at the `ci` evidence level and does "
        "not broaden accepted real-machine evidence;\n"
        "- the next bounded implementation receives IMP-075 only when a new implementation "
        "issue is opened;",
    )
    section = """### IMP-074 — Explicit local text and Markdown reading

Status: implemented with deterministic synthetic CI evidence.

Implemented one `doll document read` command and one explicit local-document reader for a caller-selected `.txt`, `.md`, or `.markdown` file. The selected source must be a regular non-symlink file, remain within the one-megabyte byte limit, stay unchanged across path and open-handle verification, and decode as strict UTF-8 after deterministic optional BOM removal.

Returned text preserves Unicode, Japanese content, and existing line endings after BOM handling. Content-free metadata records only document kind, media type, normalized extension, bounded byte, character, and line counts, exact source and returned-content SHA-256 values, BOM handling, and fixed instruction-origin classification. Native paths, filenames, usernames, hostnames, credentials, and secret values are omitted from metadata and failures.

Every selected document remains `external_content`, `extractor`, `extraction`, and `untrusted_data`. Reading cannot grant task authority, approval, permission, confirmation, capability authority, credential scope, memory, fact, project, work-completion, procedure, checkpoint, or binding authority. IMP-074 does not inject content into a model context.

The path performs no workspace, state, artifact, audit, index, memory, project, permission, confirmation, capability, model, runtime, process, shell, network, cloud, credential, or binding mutation. Dedicated acceptance covers exact text and Markdown reads, Unicode and CRLF preservation, BOM behavior, hashes, path-free output, workspace and state preservation, unsupported and binary-like input, missing files, directories, symlinks, size and character limits, changed files, CLI output, and help without initialization. Standard CI covers Ubuntu, macOS, and Windows.

IMP-074 does not establish file copying, artifact publication, automatic discovery, directory traversal, globbing, file-content indexing, semantic retrieval, model-selected context, writing-workflow attachment integration, PDF/OCR/CSV processing, office or Web formats, encoding detection beyond UTF-8, Markdown rendering, model execution, tools, cloud services, performance acceptance, the release-candidate soak, complete Phase 6, Lite v1.0 completion, or stable general anti-lock-in.

"""
    replace_once(
        path,
        "Subsequent daily-use work may expand approved local document and data adapters, "
        "accessibility presentation, Lite performance measurements, and soak testing.\n",
        section
        + "Subsequent daily-use work may expand approved local data adapters, attachment "
        "integration, accessibility presentation, Lite performance measurements, and soak "
        "testing.\n",
    )
    replace_once(
        path,
        "5. retain the explicit-only, data-only, and no-automatic-authority boundaries "
        "through IMP-068 to IMP-073; semantic retrieval, attachments, target-specific "
        "export, cloud credentials, tools, and automatic cloud fallback remain separate "
        "work;",
        "5. retain the explicit-only, data-only, and no-automatic-authority boundaries "
        "through IMP-068 to IMP-074; semantic retrieval, attachment integration, "
        "target-specific export, cloud credentials, tools, and automatic cloud fallback "
        "remain separate work;",
    )


def update_public_checker() -> None:
    path = ROOT / "scripts/check-public-site-status.mjs"
    replace_once(
        path,
        "    status.phase?.next_implementation === 74,\n"
        '  "project-status.json must mark Phase 6 in progress through IMP-073 with IMP-074 next",',
        "    status.phase?.next_implementation === 75,\n"
        '  "project-status.json must mark Phase 6 in progress through IMP-074 with IMP-075 next",',
    )
    replace_once(
        path,
        '  status.model_runtime.message.includes("through IMP-073") &&\n'
        '    status.model_runtime.message.includes("explicit local full-text state search") &&\n'
        '    status.model_runtime.message.includes("searches only active non-secret authoritative titles and textual metadata") &&\n'
        '    status.model_runtime.message.includes("creates no persistent index") &&\n'
        '    status.model_runtime.message.includes("passes at both CI and real-machine evidence levels"),\n'
        '  "project-status.json must describe IMP-073 without broadening accepted real-machine evidence",',
        '  status.model_runtime.message.includes("through IMP-074") &&\n'
        '    status.model_runtime.message.includes("explicit local UTF-8 text and Markdown reading") &&\n'
        '    status.model_runtime.message.includes("one caller-selected regular non-symlink") &&\n'
        '    status.model_runtime.message.includes("external_content/untrusted_data") &&\n'
        '    status.model_runtime.message.includes("without copying, persistence, model execution") &&\n'
        '    status.model_runtime.message.includes("passes at both CI and real-machine evidence levels"),\n'
        '  "project-status.json must describe IMP-074 without broadening accepted real-machine evidence",',
    )
    anchor = """expect(
  localWritingPrimary.test_id === "IMP-064-LOCAL-WRITING-PRIMARY" &&
"""
    assertion = """expect(
  dailyUse.local_text_markdown_extension?.implementation === "IMP-074" &&
    dailyUse.local_text_markdown_extension?.status === "ci-pass" &&
    JSON.stringify(
      dailyUse.local_text_markdown_extension?.passed_evidence_levels,
    ) === JSON.stringify(["ci"]) &&
    JSON.stringify(
      dailyUse.local_text_markdown_extension?.required_evidence_levels,
    ) === JSON.stringify(["ci"]) &&
    dailyUse.local_text_markdown_extension?.report_schema_version === 1 &&
    dailyUse.local_text_markdown_extension?.selection_mode ===
      "explicit-single-file" &&
    JSON.stringify(dailyUse.local_text_markdown_extension?.allowed_extensions) ===
      JSON.stringify([".txt", ".md", ".markdown"]) &&
    dailyUse.local_text_markdown_extension?.strict_utf8 === true &&
    dailyUse.local_text_markdown_extension?.utf8_bom_handling ===
      "remove-and-report" &&
    dailyUse.local_text_markdown_extension?.maximum_source_bytes === 1048576 &&
    dailyUse.local_text_markdown_extension?.maximum_text_characters === 1000000 &&
    dailyUse.local_text_markdown_extension?.symlinks_allowed === false &&
    dailyUse.local_text_markdown_extension?.source_persisted === false &&
    dailyUse.local_text_markdown_extension?.artifact_created === false &&
    dailyUse.local_text_markdown_extension?.index_created === false &&
    dailyUse.local_text_markdown_extension?.workspace_mutation === false &&
    dailyUse.local_text_markdown_extension?.state_mutation === false &&
    dailyUse.local_text_markdown_extension?.audit_mutation === false &&
    dailyUse.local_text_markdown_extension?.context_injection === false &&
    dailyUse.local_text_markdown_extension?.model_execution === false &&
    dailyUse.local_text_markdown_extension?.runtime_start === false &&
    dailyUse.local_text_markdown_extension?.process_launch === false &&
    dailyUse.local_text_markdown_extension?.shell_execution === false &&
    dailyUse.local_text_markdown_extension?.tool_execution === false &&
    dailyUse.local_text_markdown_extension?.capability_execution === false &&
    dailyUse.local_text_markdown_extension?.network_access === false &&
    dailyUse.local_text_markdown_extension?.cloud_fallback === false &&
    dailyUse.local_text_markdown_extension?.origin_class === "external_content" &&
    dailyUse.local_text_markdown_extension?.actor_type === "extractor" &&
    dailyUse.local_text_markdown_extension?.acquisition_method === "extraction" &&
    dailyUse.local_text_markdown_extension?.authority_class === "untrusted_data" &&
    dailyUse.local_text_markdown_extension?.phase6_gate_complete === false &&
    dailyUse.local_text_markdown_extension?.lite_v1_complete === false &&
    dailyUse.local_text_markdown_extension?.stable_anti_lock_in_claim === false &&
    dailyUse.local_text_markdown_extension?.implementation_doc ===
      "docs/implementation/imp-074-explicit-local-text-markdown-read.md",
  "IMP-074 local text and Markdown reading must remain explicit, untrusted, local-only, and CI-only",
);

"""
    replace_once(path, anchor, assertion + anchor)
    replace_once(
        path,
        'expect(\n  roadmap.includes("the next bounded implementation receives IMP-074 only when a new implementation issue is opened"),\n  "roadmap must identify IMP-074 as the next unallocated implementation identifier",\n);',
        'expect(\n  roadmap.includes("### IMP-074 — Explicit local text and Markdown reading"),\n  "roadmap must record the IMP-074 local-document boundary",\n);\n'
        'expect(\n  roadmap.includes("the next bounded implementation receives IMP-075 only when a new implementation issue is opened"),\n  "roadmap must identify IMP-075 as the next unallocated implementation identifier",\n);',
    )


def main() -> None:
    update_cli()
    update_daily_use_matrix()
    update_project_status()
    update_roadmap()
    update_public_checker()
    print("IMP-074 integration updates applied")


if __name__ == "__main__":
    main()
