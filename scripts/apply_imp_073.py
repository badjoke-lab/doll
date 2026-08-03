from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"expected exactly one match in {path}: {old[:100]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


cli = ROOT / "src/doll/cli.py"
replace_once(
    cli,
    "from doll.local_search_cli import search_command\n"
    if "from doll.local_search_cli import search_command\n" in cli.read_text(encoding="utf-8")
    else "from doll.doctor_cli import doctor_command\n",
    "from doll.local_search_cli import search_command\n"
    if "from doll.local_search_cli import search_command\n" in cli.read_text(encoding="utf-8")
    else "from doll.doctor_cli import doctor_command\nfrom doll.local_search_cli import search_command\n",
)
if 'app.command("search")(search_command)\n' not in cli.read_text(encoding="utf-8"):
    replace_once(
        cli,
        'app.command("doctor")(doctor_command)\n',
        'app.command("doctor")(doctor_command)\napp.command("search")(search_command)\n',
    )

cli_tests = ROOT / "tests/test_cli.py"
if '    assert "search" in result.stdout\n' not in cli_tests.read_text(encoding="utf-8"):
    replace_once(
        cli_tests,
        '    assert "doctor" in result.stdout\n',
        '    assert "doctor" in result.stdout\n    assert "search" in result.stdout\n',
    )

roadmap = ROOT / "docs/spec/09-development-roadmap.md"
replace_once(roadmap, "- IMP-030 through IMP-072;", "- IMP-030 through IMP-073;")
replace_once(
    roadmap,
    "and read-only local doctor diagnostics through IMP-072.",
    "read-only local doctor diagnostics through IMP-072, and explicit local full-text state search through IMP-073.",
)
replace_once(
    roadmap,
    "- Phase 6 local AI portability and daily-use integration is in progress through IMP-072;",
    "- Phase 6 local AI portability and daily-use integration is in progress through IMP-073;",
)
replace_once(
    roadmap,
    "- the IMP-072 doctor extension passes at the `ci` evidence level and does not broaden accepted real-machine evidence;\n- the next bounded implementation receives IMP-073 only when a new implementation issue is opened;",
    "- the IMP-072 doctor extension passes at the `ci` evidence level and does not broaden accepted real-machine evidence;\n- IMP-073 adds one explicit deterministic read-only local full-text search over active non-secret authoritative record titles and textual metadata values, with bounded Unicode matching and no model, network, persistent index, or automatic context injection;\n- IMP-073 is assigned to Issue #229;\n- the IMP-073 local-search extension passes at the `ci` evidence level and does not broaden accepted real-machine evidence;\n- the next bounded implementation receives IMP-074 only when a new implementation issue is opened;",
)
imp073_section = """### IMP-073 — Explicit local full-text state search

Status: implemented with deterministic synthetic CI evidence.

Implemented one top-level `doll search` command and one explicit local-search service over active non-secret authoritative records. The caller supplies one bounded query and may add one exact record-type filter. Titles and nested textual metadata values are normalized with Unicode NFKC, matched with case-folded substring semantics, and combined with multi-term AND behavior within one record.

Search uses immutable read-only SQLite access, rejects a non-empty WAL or rollback journal before opening, and performs no state, workspace, artifact, audit, index, cache, backup, model, runtime, process, shell, tool, capability, network, cloud, credential, permission, confirmation, or binding mutation. It does not feed results into model context and does not perform automatic or semantic retrieval.

Results are deterministic, bounded, and available as stable human-readable output or JSON. The initial stable scan covers at most 10,000 active non-secret records and reports truncation. Field paths, snippets, query length, query terms, record-type filters, and result counts are bounded. Invalid workspace input does not initialize a workspace.

Dedicated acceptance covers title and nested metadata matching, Japanese and Unicode behavior, multi-field AND matching, inactive and secret exclusion, exact record-type filtering, deterministic ordering, limits, exact workspace-file preservation, writable-repository rejection, invalid queries, pending-journal rejection, CLI output, and path privacy. Standard CI covers Ubuntu, macOS, and Windows.

IMP-073 does not establish semantic search, embeddings, vector databases, automatic retrieval, model-selected context, persistent search indexes, inactive or secret search, artifact-byte extraction, attachments, PDF/OCR/CSV processing, Web search, performance acceptance, the release-candidate soak, complete Phase 6, Lite v1.0 completion, or stable general anti-lock-in.

"""
replace_once(
    roadmap,
    "Subsequent daily-use work may expand accessibility presentation, Lite performance measurements, and soak testing.\n",
    imp073_section
    + "Subsequent daily-use work may expand approved local document and data adapters, accessibility presentation, Lite performance measurements, and soak testing.\n",
)
replace_once(
    roadmap,
    "5. allocate IMP-068 only when a new bounded implementation issue is opened; translation, automatic retrieval, attachments, target-specific export, cloud credentials, tools, and automatic cloud fallback remain separate work;",
    "5. retain the explicit-only, data-only, and no-automatic-authority boundaries through IMP-068 to IMP-073; semantic retrieval, attachments, target-specific export, cloud credentials, tools, and automatic cloud fallback remain separate work;",
)

matrix_path = ROOT / "docs/testing/phase-6-daily-use-matrix.json"
matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
matrix["local_full_text_search_extension"] = {
    "implementation": "IMP-073",
    "status": "ci-pass",
    "description": "One explicit deterministic read-only local full-text search scans active non-secret authoritative record titles and textual metadata without models, network access, persistent indexes, or automatic context injection.",
    "pytest_files": ["tests/test_imp_073_local_search.py", "tests/test_cli.py"],
    "passed_evidence_levels": ["ci"],
    "required_evidence_levels": ["ci"],
    "report_schema_version": 1,
    "search_mode": "unicode-nfkc-casefold-substring-and",
    "query_mode": "explicit-only",
    "record_status_scope": ["active"],
    "secret_records_allowed": False,
    "maximum_scanned_records": 10000,
    "maximum_results": 100,
    "persistent_index": False,
    "schema_migration": False,
    "state_mutation": False,
    "workspace_mutation": False,
    "artifact_mutation": False,
    "audit_mutation": False,
    "automatic_retrieval": False,
    "semantic_retrieval": False,
    "model_selected_context": False,
    "context_injection": False,
    "model_execution": False,
    "runtime_start": False,
    "process_launch": False,
    "shell_execution": False,
    "tool_execution": False,
    "capability_execution": False,
    "network_access": False,
    "cloud_fallback": False,
    "phase6_gate_complete": False,
    "lite_v1_complete": False,
    "stable_anti_lock_in_claim": False,
    "implementation_doc": "docs/implementation/imp-073-explicit-local-full-text-search.md",
}
matrix_path.write_text(
    json.dumps(matrix, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

status_path = ROOT / "website/project-status.json"
status = json.loads(status_path.read_text(encoding="utf-8"))
status["phase"]["next_implementation"] = 74
status["model_runtime"]["message"] = (
    "Phase 6 is in progress through IMP-073. Offline Ollama session import, explicit text-only loopback capture, "
    "the accepted bounded local-portability migration drill, the deterministic shutdown escape bundle, bounded "
    "ChatGPT selected-history import, imported-context replay with accepted primary Intel Mac evidence, bounded "
    "local draft/revise/summarize/translate workflows, explicit data-only context, bounded local work-item proposals, "
    "explicit local portability review, structured local runtime failure guidance, a deterministic read-only doll "
    "doctor, and explicit local full-text state search are implemented. The IMP-063/IMP-064 writing workflow passes "
    "at both CI and real-machine evidence levels. IMP-073 searches only active non-secret authoritative titles and "
    "textual metadata through bounded Unicode substring matching and immutable read-only SQLite access; it creates no "
    "persistent index, performs no model or network operation, and does not inject results into context automatically. "
    "Accessibility presentation, Lite performance measurements, the release soak gate, semantic or automatic "
    "retrieval, attachments, approved PDF/OCR/CSV adapters, tools, the complete Phase 6 gate, Lite v1.0, "
    "target-specific application replacement, and stable general anti-lock-in remain incomplete."
)
status["last_reviewed"] = "2026-08-03"
status_path.write_text(
    json.dumps(status, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

checker = ROOT / "scripts/check-public-site-status.mjs"
replace_once(
    checker,
    "status.phase?.next_implementation === 73,\n  \"project-status.json must mark Phase 6 in progress through IMP-072 with IMP-073 next\"",
    "status.phase?.next_implementation === 74,\n  \"project-status.json must mark Phase 6 in progress through IMP-073 with IMP-074 next\"",
)
replace_once(
    checker,
    'status.model_runtime.message.includes("through IMP-072") &&\n    status.model_runtime.message.includes("IMP-071 gives every accepted local runtime failure code") &&\n    status.model_runtime.message.includes("IMP-072 validates workspace structure") &&\n    status.model_runtime.message.includes("without repair, mutation, model execution, network access, or native-path disclosure") &&\n    status.model_runtime.message.includes("passes at both CI and real-machine evidence levels"),\n  "project-status.json must describe IMP-072 without broadening accepted real-machine evidence",',
    'status.model_runtime.message.includes("through IMP-073") &&\n    status.model_runtime.message.includes("explicit local full-text state search") &&\n    status.model_runtime.message.includes("searches only active non-secret authoritative titles and textual metadata") &&\n    status.model_runtime.message.includes("creates no persistent index") &&\n    status.model_runtime.message.includes("passes at both CI and real-machine evidence levels"),\n  "project-status.json must describe IMP-073 without broadening accepted real-machine evidence",',
)
search_check = """expect(
  dailyUse.local_full_text_search_extension?.implementation === "IMP-073" &&
    dailyUse.local_full_text_search_extension?.status === "ci-pass" &&
    JSON.stringify(
      dailyUse.local_full_text_search_extension?.passed_evidence_levels,
    ) === JSON.stringify(["ci"]) &&
    JSON.stringify(
      dailyUse.local_full_text_search_extension?.required_evidence_levels,
    ) === JSON.stringify(["ci"]) &&
    dailyUse.local_full_text_search_extension?.report_schema_version === 1 &&
    dailyUse.local_full_text_search_extension?.search_mode ===
      "unicode-nfkc-casefold-substring-and" &&
    dailyUse.local_full_text_search_extension?.query_mode === "explicit-only" &&
    JSON.stringify(
      dailyUse.local_full_text_search_extension?.record_status_scope,
    ) === JSON.stringify(["active"]) &&
    dailyUse.local_full_text_search_extension?.secret_records_allowed === false &&
    dailyUse.local_full_text_search_extension?.maximum_scanned_records === 10000 &&
    dailyUse.local_full_text_search_extension?.maximum_results === 100 &&
    dailyUse.local_full_text_search_extension?.persistent_index === false &&
    dailyUse.local_full_text_search_extension?.schema_migration === false &&
    dailyUse.local_full_text_search_extension?.state_mutation === false &&
    dailyUse.local_full_text_search_extension?.workspace_mutation === false &&
    dailyUse.local_full_text_search_extension?.automatic_retrieval === false &&
    dailyUse.local_full_text_search_extension?.semantic_retrieval === false &&
    dailyUse.local_full_text_search_extension?.model_selected_context === false &&
    dailyUse.local_full_text_search_extension?.context_injection === false &&
    dailyUse.local_full_text_search_extension?.model_execution === false &&
    dailyUse.local_full_text_search_extension?.process_launch === false &&
    dailyUse.local_full_text_search_extension?.shell_execution === false &&
    dailyUse.local_full_text_search_extension?.tool_execution === false &&
    dailyUse.local_full_text_search_extension?.capability_execution === false &&
    dailyUse.local_full_text_search_extension?.network_access === false &&
    dailyUse.local_full_text_search_extension?.cloud_fallback === false &&
    dailyUse.local_full_text_search_extension?.phase6_gate_complete === false &&
    dailyUse.local_full_text_search_extension?.lite_v1_complete === false &&
    dailyUse.local_full_text_search_extension?.stable_anti_lock_in_claim === false &&
    dailyUse.local_full_text_search_extension?.implementation_doc ===
      "docs/implementation/imp-073-explicit-local-full-text-search.md",
  "IMP-073 local full-text search must remain explicit, read-only, local-only, and CI-only",
);

"""
replace_once(
    checker,
    "expect(\n  localWritingPrimary.test_id === \"IMP-064-LOCAL-WRITING-PRIMARY\" &&",
    search_check
    + "expect(\n  localWritingPrimary.test_id === \"IMP-064-LOCAL-WRITING-PRIMARY\" &&",
)
replace_once(
    checker,
    'expect(\n  roadmap.includes("### IMP-072 — Read-only doll doctor diagnostics"),\n  "roadmap must record the IMP-072 doctor boundary",\n);\nexpect(\n  roadmap.includes("the next bounded implementation receives IMP-073 only when a new implementation issue is opened"),\n  "roadmap must identify IMP-073 as the next unallocated implementation identifier",\n);',
    'expect(\n  roadmap.includes("### IMP-072 — Read-only doll doctor diagnostics"),\n  "roadmap must record the IMP-072 doctor boundary",\n);\nexpect(\n  roadmap.includes("### IMP-073 — Explicit local full-text state search"),\n  "roadmap must record the IMP-073 local-search boundary",\n);\nexpect(\n  roadmap.includes("the next bounded implementation receives IMP-074 only when a new implementation issue is opened"),\n  "roadmap must identify IMP-074 as the next unallocated implementation identifier",\n);',
)

print("IMP-073 integration updates applied")
