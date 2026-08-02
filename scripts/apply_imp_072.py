# ruff: noqa: E501
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"expected exactly one match in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


cli = ROOT / "src/doll/cli.py"
replace_once(
    cli,
    "from doll.diagnostics import redact_exception_text\n",
    "from doll.diagnostics import redact_exception_text\nfrom doll.doctor_cli import doctor_command\n",
)
replace_once(
    cli,
    'app.add_typer(backup_app, name="backup")\n',
    'app.add_typer(backup_app, name="backup")\napp.command("doctor")(doctor_command)\n',
)

cli_tests = ROOT / "tests/test_cli.py"
replace_once(
    cli_tests,
    '    assert "version" in result.stdout\n',
    '    assert "version" in result.stdout\n    assert "doctor" in result.stdout\n',
)

roadmap = ROOT / "docs/spec/09-development-roadmap.md"
replace_once(roadmap, "- IMP-030 through IMP-071;", "- IMP-030 through IMP-072;")
replace_once(
    roadmap,
    "structured local runtime failure guidance through IMP-071.",
    "structured local runtime failure guidance through IMP-071, and read-only local doctor diagnostics through IMP-072.",
)
replace_once(
    roadmap,
    "- Phase 6 local AI portability and daily-use integration is in progress through IMP-071;",
    "- Phase 6 local AI portability and daily-use integration is in progress through IMP-072;",
)
replace_once(
    roadmap,
    "- the IMP-071 failure-guidance extension passes at the `ci` evidence level and does not broaden accepted real-machine evidence;\n- the next bounded implementation receives IMP-072 only when a new implementation issue is opened;",
    "- the IMP-071 failure-guidance extension passes at the `ci` evidence level and does not broaden accepted real-machine evidence;\n- IMP-072 adds one deterministic `doll doctor` command that validates workspace structure and authoritative SQLite state through the read-only recovery path without migration, repair, model execution, or native-path disclosure;\n- IMP-072 is assigned to Issue #227;\n- the IMP-072 doctor extension passes at the `ci` evidence level and does not broaden accepted real-machine evidence;\n- the next bounded implementation receives IMP-073 only when a new implementation issue is opened;",
)
doctor_section = """### IMP-072 — Read-only doll doctor diagnostics

Status: implemented with deterministic synthetic CI evidence.

Implemented one deterministic top-level `doll doctor` command over one explicitly selected local workspace. The service validates workspace identity, every required workspace directory, authoritative state identity and current schema, workspace/database revision agreement, read-only opening, and SQLite `PRAGMA quick_check`.

Every check returns a stable `pass`, `warn`, or `fail` result with a bounded summary and fixed local-only guidance. Human-readable and deterministic JSON outputs exclude native paths, workspace identifiers, database paths, usernames, hostnames, record content, model output, credentials, and secret values. Invalid workspace input does not initialize a workspace.

The doctor path performs no migration, repair, deletion, state write, audit write, backup creation, restore, model execution, runtime start, process launch, shell command, tool, capability, network request, cloud fallback, login, credential access, model download, installation, or binding change. Dedicated acceptance covers healthy state, no-write preservation, invalid workspace handling, required-directory absence and symlink rejection, corrupt SQLite state, revision mismatch, injected quick-check failure, deterministic JSON, stable exit codes, and path privacy. Standard CI covers Ubuntu, macOS, and Windows.

IMP-072 does not establish automatic repair, runtime or model health calls, provider-specific troubleshooting, performance benchmarking, installer diagnostics, accessibility presentation, the release-candidate soak, complete Phase 6, Lite v1.0 completion, or stable general anti-lock-in.

"""
replace_once(
    roadmap,
    "Subsequent daily-use work may expand accessibility, Lite performance measurements, and soak testing.\n",
    doctor_section
    + "Subsequent daily-use work may expand accessibility presentation, Lite performance measurements, and soak testing.\n",
)

matrix_path = ROOT / "docs/testing/phase-6-daily-use-matrix.json"
matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
matrix["doctor_extension"] = {
    "implementation": "IMP-072",
    "status": "ci-pass",
    "description": "One deterministic read-only doll doctor command validates workspace structure and authoritative SQLite state without repair, mutation, model execution, network access, or native-path disclosure.",
    "pytest_files": ["tests/test_imp_072_doctor.py", "tests/test_cli.py"],
    "passed_evidence_levels": ["ci"],
    "required_evidence_levels": ["ci"],
    "report_schema_version": 1,
    "read_only": True,
    "workspace_mutation": False,
    "state_mutation": False,
    "schema_migration": False,
    "automatic_repair": False,
    "model_execution": False,
    "runtime_start": False,
    "process_launch": False,
    "shell_execution": False,
    "tool_execution": False,
    "capability_execution": False,
    "network_access": False,
    "cloud_fallback": False,
    "native_path_disclosure": False,
    "phase6_gate_complete": False,
    "lite_v1_complete": False,
    "stable_anti_lock_in_claim": False,
    "implementation_doc": "docs/implementation/imp-072-read-only-doll-doctor.md",
}
matrix_path.write_text(json.dumps(matrix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

status_path = ROOT / "website/project-status.json"
status = json.loads(status_path.read_text(encoding="utf-8"))
status["phase"]["next_implementation"] = 73
status["model_runtime"]["message"] = (
    "Phase 6 is in progress through IMP-072. Offline Ollama session import, explicit text-only loopback capture, "
    "the accepted bounded local-portability migration drill, the deterministic shutdown escape bundle, bounded "
    "ChatGPT selected-history import, imported-context replay with accepted primary Intel Mac evidence, bounded "
    "local draft/revise/summarize/translate workflows, explicit data-only context, bounded local work-item proposals, "
    "explicit local portability review, structured local runtime failure guidance, and a deterministic read-only "
    "doll doctor are implemented. The IMP-063/IMP-064 writing workflow passes at both CI and real-machine evidence "
    "levels. IMP-071 gives every accepted local runtime failure code deterministic provider-neutral local-only options "
    "while recording no automatic action and no cloud fallback; IMP-072 validates workspace structure, authoritative "
    "state identity, schema, revision agreement, read-only opening, and SQLite quick-check without repair, mutation, "
    "model execution, network access, or native-path disclosure. Accessibility presentation, Lite performance "
    "measurements, the release soak gate, automatic or semantic retrieval, attachments, tools, the complete Phase 6 "
    "gate, Lite v1.0, target-specific application replacement, and stable general anti-lock-in remain incomplete."
)
status["last_reviewed"] = "2026-08-03"
status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

checker = ROOT / "scripts/check-public-site-status.mjs"
replace_once(
    checker,
    "status.phase?.next_implementation === 72,\n  \"project-status.json must mark Phase 6 in progress through IMP-071 with IMP-072 next\"",
    "status.phase?.next_implementation === 73,\n  \"project-status.json must mark Phase 6 in progress through IMP-072 with IMP-073 next\"",
)
replace_once(
    checker,
    'status.model_runtime.message.includes("through IMP-071") &&\n    status.model_runtime.message.includes("IMP-069 keeps work-item acceptance and execution user-controlled") &&\n    status.model_runtime.message.includes("IMP-070 reviews one explicitly selected import batch") &&\n    status.model_runtime.message.includes("IMP-071 gives every accepted local runtime failure code") &&\n    status.model_runtime.message.includes("no automatic action and no cloud fallback") &&\n    status.model_runtime.message.includes("passes at both CI and real-machine evidence levels"),\n  "project-status.json must describe IMP-071 without broadening accepted real-machine evidence",',
    'status.model_runtime.message.includes("through IMP-072") &&\n    status.model_runtime.message.includes("IMP-071 gives every accepted local runtime failure code") &&\n    status.model_runtime.message.includes("IMP-072 validates workspace structure") &&\n    status.model_runtime.message.includes("without repair, mutation, model execution, network access, or native-path disclosure") &&\n    status.model_runtime.message.includes("passes at both CI and real-machine evidence levels"),\n  "project-status.json must describe IMP-072 without broadening accepted real-machine evidence",',
)
doctor_check = """expect(
  dailyUse.doctor_extension?.implementation === "IMP-072" &&
    dailyUse.doctor_extension?.status === "ci-pass" &&
    JSON.stringify(dailyUse.doctor_extension?.passed_evidence_levels) ===
      JSON.stringify(["ci"]) &&
    JSON.stringify(dailyUse.doctor_extension?.required_evidence_levels) ===
      JSON.stringify(["ci"]) &&
    dailyUse.doctor_extension?.report_schema_version === 1 &&
    dailyUse.doctor_extension?.read_only === true &&
    dailyUse.doctor_extension?.workspace_mutation === false &&
    dailyUse.doctor_extension?.state_mutation === false &&
    dailyUse.doctor_extension?.schema_migration === false &&
    dailyUse.doctor_extension?.automatic_repair === false &&
    dailyUse.doctor_extension?.model_execution === false &&
    dailyUse.doctor_extension?.runtime_start === false &&
    dailyUse.doctor_extension?.process_launch === false &&
    dailyUse.doctor_extension?.shell_execution === false &&
    dailyUse.doctor_extension?.tool_execution === false &&
    dailyUse.doctor_extension?.capability_execution === false &&
    dailyUse.doctor_extension?.network_access === false &&
    dailyUse.doctor_extension?.cloud_fallback === false &&
    dailyUse.doctor_extension?.native_path_disclosure === false &&
    dailyUse.doctor_extension?.phase6_gate_complete === false &&
    dailyUse.doctor_extension?.lite_v1_complete === false &&
    dailyUse.doctor_extension?.stable_anti_lock_in_claim === false &&
    dailyUse.doctor_extension?.implementation_doc ===
      "docs/implementation/imp-072-read-only-doll-doctor.md",
  "IMP-072 doctor must remain deterministic, read-only, local-only, and CI-only",
);

"""
replace_once(
    checker,
    "expect(\n  localWritingPrimary.test_id === \"IMP-064-LOCAL-WRITING-PRIMARY\" &&",
    doctor_check + "expect(\n  localWritingPrimary.test_id === \"IMP-064-LOCAL-WRITING-PRIMARY\" &&",
)
replace_once(
    checker,
    'expect(\n  roadmap.includes("the next bounded implementation receives IMP-072 only when a new implementation issue is opened"),\n  "roadmap must identify IMP-072 as the next unallocated implementation identifier",\n);',
    'expect(\n  roadmap.includes("### IMP-072 — Read-only doll doctor diagnostics"),\n  "roadmap must record the IMP-072 doctor boundary",\n);\nexpect(\n  roadmap.includes("the next bounded implementation receives IMP-073 only when a new implementation issue is opened"),\n  "roadmap must identify IMP-073 as the next unallocated implementation identifier",\n);',
)

print("IMP-072 integration updates applied")
