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
        "from doll.local_document_cli import document_app\n",
        "from doll.local_csv_cli import csv_app\nfrom doll.local_document_cli import document_app\n",
    )
    replace_once(
        path,
        'app.add_typer(backup_app, name="backup")\n'
        'app.add_typer(document_app, name="document")\n',
        'app.add_typer(backup_app, name="backup")\n'
        'app.add_typer(csv_app, name="csv")\n'
        'app.add_typer(document_app, name="document")\n',
    )
    tests = ROOT / "tests/test_cli.py"
    replace_once(
        tests,
        '    assert "document" in result.stdout\n',
        '    assert "document" in result.stdout\n    assert "csv" in result.stdout\n',
    )


def update_daily_use_matrix() -> None:
    path = ROOT / "docs/testing/phase-6-daily-use-matrix.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["local_csv_extension"] = {
        "implementation": "IMP-075",
        "status": "ci-pass",
        "description": (
            "One caller-selected UTF-8 CSV file can be inspected or transformed by "
            "explicit column selection, reordering, and header renaming without formula "
            "evaluation, persistence, model execution, or network access."
        ),
        "pytest_files": ["tests/test_imp_075_local_csv.py", "tests/test_cli.py"],
        "passed_evidence_levels": ["ci"],
        "required_evidence_levels": ["ci"],
        "report_schema_version": 1,
        "selection_mode": "explicit-single-file",
        "allowed_extensions": [".csv"],
        "delimiter_profiles": ["comma", "tab", "semicolon", "pipe"],
        "strict_utf8": True,
        "utf8_bom_handling": "remove-and-report",
        "maximum_source_bytes": 2097152,
        "maximum_rows": 10000,
        "maximum_columns": 200,
        "maximum_cell_characters": 16384,
        "maximum_aggregate_characters": 4000000,
        "maximum_preview_rows": 100,
        "symlinks_allowed": False,
        "transformation_operations": [
            "column_selection",
            "column_reordering",
            "header_renaming",
        ],
        "type_inference": False,
        "formula_evaluation": False,
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
        "implementation_doc": "docs/implementation/imp-075-explicit-local-csv.md",
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def update_project_status() -> None:
    path = ROOT / "website/project-status.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["phase"]["next_implementation"] = 76
    payload["model_runtime"]["message"] = (
        "Phase 6 is in progress through IMP-075. Offline Ollama session import, "
        "explicit text-only loopback capture, the accepted bounded local-portability "
        "migration drill, the deterministic shutdown escape bundle, bounded ChatGPT "
        "selected-history import, imported-context replay with accepted primary Intel "
        "Mac evidence, bounded local draft/revise/summarize/translate workflows, explicit "
        "data-only context, bounded local work-item proposals, explicit local portability "
        "review, structured local runtime failure guidance, a deterministic read-only "
        "doll doctor, explicit local full-text state search, explicit local UTF-8 text and "
        "Markdown reading, and explicit local CSV inspection and transformation are "
        "implemented. The IMP-063/IMP-064 writing workflow passes at both CI and "
        "real-machine evidence levels. IMP-075 inspects one caller-selected regular "
        "non-symlink UTF-8 .csv file and transforms only explicit column selection, "
        "reordering, and header renaming. Formula-like cells are counted but never "
        "evaluated or rewritten, and no source overwrite, output file, persistence, model "
        "execution, network access, native-path disclosure, or automatic context injection "
        "occurs. Accessibility presentation, Lite performance measurements, the release "
        "soak gate, semantic or automatic retrieval, attachment integration, approved "
        "PDF/OCR adapters, tools, the complete Phase 6 gate, Lite v1.0, target-specific "
        "application replacement, and stable general anti-lock-in remain incomplete."
    )
    payload["last_reviewed"] = "2026-08-05"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def update_roadmap() -> None:
    path = ROOT / "docs/spec/09-development-roadmap.md"
    replace_once(path, "- IMP-030 through IMP-074;", "- IMP-030 through IMP-075;")
    replace_once(
        path,
        "explicit local full-text state search through IMP-073, and explicit local text and "
        "Markdown reading through IMP-074.",
        "explicit local full-text state search through IMP-073, explicit local text and "
        "Markdown reading through IMP-074, and explicit local CSV inspection and simple "
        "transformation through IMP-075.",
    )
    replace_once(
        path,
        "- Phase 6 local AI portability and daily-use integration is in progress through "
        "IMP-074;",
        "- Phase 6 local AI portability and daily-use integration is in progress through "
        "IMP-075;",
    )
    replace_once(
        path,
        "- the IMP-074 local-document extension passes at the `ci` evidence level and does "
        "not broaden accepted real-machine evidence;\n"
        "- the next bounded implementation receives IMP-075 only when a new implementation "
        "issue is opened;",
        "- the IMP-074 local-document extension passes at the `ci` evidence level and does "
        "not broaden accepted real-machine evidence;\n"
        "- IMP-075 adds one explicit local CSV inspection and transformation path with "
        "strict UTF-8 parsing, bounded previews, formula-like-cell visibility, and only "
        "column selection, reordering, and header renaming;\n"
        "- IMP-075 is assigned to Issue #233;\n"
        "- the IMP-075 local-CSV extension passes at the `ci` evidence level and does not "
        "broaden accepted real-machine evidence;\n"
        "- the next bounded implementation receives IMP-076 only when a new implementation "
        "issue is opened;",
    )
    section = """### IMP-075 — Explicit local CSV inspection and transformation

Status: implemented with deterministic synthetic CI evidence.

Implemented `doll csv inspect` and `doll csv transform` over one caller-selected regular non-symlink `.csv` file. Input is bounded, strict UTF-8 with deterministic optional BOM removal, and parsed through the standard-library CSV engine using one explicit comma, tab, semicolon, or pipe delimiter profile. Headers must be non-blank and unique, rows rectangular, and source bytes, rows, columns, cells, aggregate characters, and preview rows remain bounded.

Inspection reports path-free hashes, counts, ordered headers, a bounded preview, blank-cell count, and potential spreadsheet-formula cell count. Formula-like cells remain source text and are counted but never evaluated, rewritten, neutralized, or promoted to authority.

Transformation supports only exact column selection, caller-ordered reordering, and exact header renaming. Cell text remains unchanged. Output is deterministic UTF-8 CSV using the selected delimiter and `\\n` line endings and is returned only through command output; no source overwrite or output file occurs.

All headers and cells remain `external_content`, `extractor`, `extraction`, and `untrusted_data`. The workflow performs no workspace, state, artifact, audit, index, model, runtime, process, shell, tool, capability, network, cloud, credential, permission, confirmation, or binding mutation. Dedicated acceptance covers Unicode and Japanese text, quoted delimiters and line breaks, CRLF and BOM input, all delimiter profiles, hashes and counts, formula visibility, selection and renaming, deterministic output, exact no-write behavior, malformed and unsafe inputs, limits, CLI output, and path privacy. Standard CI covers Ubuntu, macOS, and Windows.

IMP-075 does not establish type inference, sorting, filters, joins, grouping, aggregation, arithmetic, formula execution, arbitrary expressions, spreadsheet formats, persistent output, artifact publication, automatic discovery, semantic retrieval, model-selected context, attachment integration, PDF/OCR/Web processing, tools, cloud services, performance acceptance, the release-candidate soak, complete Phase 6, Lite v1.0 completion, or stable general anti-lock-in.

"""
    replace_once(
        path,
        "Subsequent daily-use work may expand approved local data adapters, attachment "
        "integration, accessibility presentation, Lite performance measurements, and soak "
        "testing.\n",
        section
        + "Subsequent daily-use work may expand approved PDF/OCR adapters, attachment "
        "integration, accessibility presentation, Lite performance measurements, and soak "
        "testing.\n",
    )
    replace_once(
        path,
        "5. retain the explicit-only, data-only, and no-automatic-authority boundaries "
        "through IMP-068 to IMP-074; semantic retrieval, attachment integration, "
        "target-specific export, cloud credentials, tools, and automatic cloud fallback "
        "remain separate work;",
        "5. retain the explicit-only, data-only, and no-automatic-authority boundaries "
        "through IMP-068 to IMP-075; semantic retrieval, attachment integration, "
        "target-specific export, cloud credentials, tools, and automatic cloud fallback "
        "remain separate work;",
    )


def update_public_checker() -> None:
    path = ROOT / "scripts/check-public-site-status.mjs"
    replace_once(
        path,
        "    status.phase?.next_implementation === 75,\n"
        '  "project-status.json must mark Phase 6 in progress through IMP-074 with IMP-075 next",',
        "    status.phase?.next_implementation === 76,\n"
        '  "project-status.json must mark Phase 6 in progress through IMP-075 with IMP-076 next",',
    )
    replace_once(
        path,
        '  status.model_runtime.message.includes("through IMP-074") &&\n'
        '    status.model_runtime.message.includes("explicit local UTF-8 text and Markdown reading") &&\n'
        '    status.model_runtime.message.includes("one caller-selected regular non-symlink") &&\n'
        '    status.model_runtime.message.includes("external_content/untrusted_data") &&\n'
        '    status.model_runtime.message.includes("without copying, persistence, model execution") &&\n'
        '    status.model_runtime.message.includes("passes at both CI and real-machine evidence levels"),\n'
        '  "project-status.json must describe IMP-074 without broadening accepted real-machine evidence",',
        '  status.model_runtime.message.includes("through IMP-075") &&\n'
        '    status.model_runtime.message.includes("explicit local CSV inspection and transformation") &&\n'
        '    status.model_runtime.message.includes("column selection, reordering, and header renaming") &&\n'
        '    status.model_runtime.message.includes("never evaluated or rewritten") &&\n'
        '    status.model_runtime.message.includes("no source overwrite, output file, persistence") &&\n'
        '    status.model_runtime.message.includes("passes at both CI and real-machine evidence levels"),\n'
        '  "project-status.json must describe IMP-075 without broadening accepted real-machine evidence",',
    )
    anchor = """expect(
  localWritingPrimary.test_id === "IMP-064-LOCAL-WRITING-PRIMARY" &&
"""
    assertion = """expect(
  dailyUse.local_csv_extension?.implementation === "IMP-075" &&
    dailyUse.local_csv_extension?.status === "ci-pass" &&
    JSON.stringify(dailyUse.local_csv_extension?.passed_evidence_levels) ===
      JSON.stringify(["ci"]) &&
    JSON.stringify(dailyUse.local_csv_extension?.required_evidence_levels) ===
      JSON.stringify(["ci"]) &&
    dailyUse.local_csv_extension?.report_schema_version === 1 &&
    dailyUse.local_csv_extension?.selection_mode === "explicit-single-file" &&
    JSON.stringify(dailyUse.local_csv_extension?.allowed_extensions) ===
      JSON.stringify([".csv"]) &&
    JSON.stringify(dailyUse.local_csv_extension?.delimiter_profiles) ===
      JSON.stringify(["comma", "tab", "semicolon", "pipe"]) &&
    dailyUse.local_csv_extension?.strict_utf8 === true &&
    dailyUse.local_csv_extension?.utf8_bom_handling === "remove-and-report" &&
    dailyUse.local_csv_extension?.maximum_source_bytes === 2097152 &&
    dailyUse.local_csv_extension?.maximum_rows === 10000 &&
    dailyUse.local_csv_extension?.maximum_columns === 200 &&
    dailyUse.local_csv_extension?.maximum_cell_characters === 16384 &&
    dailyUse.local_csv_extension?.maximum_aggregate_characters === 4000000 &&
    dailyUse.local_csv_extension?.maximum_preview_rows === 100 &&
    dailyUse.local_csv_extension?.symlinks_allowed === false &&
    JSON.stringify(dailyUse.local_csv_extension?.transformation_operations) ===
      JSON.stringify(["column_selection", "column_reordering", "header_renaming"]) &&
    dailyUse.local_csv_extension?.type_inference === false &&
    dailyUse.local_csv_extension?.formula_evaluation === false &&
    dailyUse.local_csv_extension?.source_overwrite === false &&
    dailyUse.local_csv_extension?.source_persisted === false &&
    dailyUse.local_csv_extension?.output_persisted === false &&
    dailyUse.local_csv_extension?.artifact_created === false &&
    dailyUse.local_csv_extension?.index_created === false &&
    dailyUse.local_csv_extension?.workspace_mutation === false &&
    dailyUse.local_csv_extension?.state_mutation === false &&
    dailyUse.local_csv_extension?.audit_mutation === false &&
    dailyUse.local_csv_extension?.context_injection === false &&
    dailyUse.local_csv_extension?.model_execution === false &&
    dailyUse.local_csv_extension?.runtime_start === false &&
    dailyUse.local_csv_extension?.process_launch === false &&
    dailyUse.local_csv_extension?.shell_execution === false &&
    dailyUse.local_csv_extension?.tool_execution === false &&
    dailyUse.local_csv_extension?.capability_execution === false &&
    dailyUse.local_csv_extension?.network_access === false &&
    dailyUse.local_csv_extension?.cloud_fallback === false &&
    dailyUse.local_csv_extension?.origin_class === "external_content" &&
    dailyUse.local_csv_extension?.actor_type === "extractor" &&
    dailyUse.local_csv_extension?.acquisition_method === "extraction" &&
    dailyUse.local_csv_extension?.authority_class === "untrusted_data" &&
    dailyUse.local_csv_extension?.phase6_gate_complete === false &&
    dailyUse.local_csv_extension?.lite_v1_complete === false &&
    dailyUse.local_csv_extension?.stable_anti_lock_in_claim === false &&
    dailyUse.local_csv_extension?.implementation_doc ===
      "docs/implementation/imp-075-explicit-local-csv.md",
  "IMP-075 local CSV must remain explicit, non-persistent, non-evaluating, and CI-only",
);

"""
    replace_once(path, anchor, assertion + anchor)
    replace_once(
        path,
        'expect(\n  roadmap.includes("the next bounded implementation receives IMP-075 only when a new implementation issue is opened"),\n  "roadmap must identify IMP-075 as the next unallocated implementation identifier",\n);',
        'expect(\n  roadmap.includes("### IMP-075 — Explicit local CSV inspection and transformation"),\n  "roadmap must record the IMP-075 local-CSV boundary",\n);\n'
        'expect(\n  roadmap.includes("the next bounded implementation receives IMP-076 only when a new implementation issue is opened"),\n  "roadmap must identify IMP-076 as the next unallocated implementation identifier",\n);',
    )


def main() -> None:
    update_cli()
    update_daily_use_matrix()
    update_project_status()
    update_roadmap()
    update_public_checker()
    print("IMP-075 integration updates applied")


if __name__ == "__main__":
    main()
