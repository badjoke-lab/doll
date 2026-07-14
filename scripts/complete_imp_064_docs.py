from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROADMAP = ROOT / "docs" / "spec" / "09-development-roadmap.md"
STATUS = ROOT / "website" / "project-status.json"
CHECKER = ROOT / "scripts" / "check-public-site-status.mjs"
IMPLEMENTATION = (
    ROOT
    / "docs"
    / "implementation"
    / "imp-064-primary-intel-mac-local-writing-acceptance.md"
)


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one occurrence, found {count}")
    return text.replace(old, new, 1)


def update_implementation() -> None:
    text = IMPLEMENTATION.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "Implementation in progress.\n\n"
        "Synthetic CI evidence and the exact-commit primary Intel Mac acceptance path "
        "are being added on Issue #206.\n",
        "Acceptance infrastructure implemented with deterministic synthetic CI evidence.\n\n"
        "Primary Intel Mac real-machine evidence remains pending until the merged "
        "implementation commit is executed with networking operator-confirmed disabled "
        "and a privacy-reviewed content-free result is accepted through a separate "
        "completion pull request.\n",
        label="implementation status",
    )
    duplicate = (
        "\nPrimary Intel Mac real-machine evidence remains pending until the merged "
        "implementation commit is executed with networking operator-confirmed disabled "
        "and a privacy-reviewed content-free result is accepted through a separate "
        "completion pull request.\n"
    )
    if text.count(duplicate) == 2:
        text = text.replace(duplicate, "", 1)
    IMPLEMENTATION.write_text(text, encoding="utf-8")


def update_roadmap() -> None:
    text = ROADMAP.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "- IMP-030 through IMP-063;",
        "- IMP-030 through IMP-064;",
        label="completed implementation range",
    )
    text = replace_once(
        text,
        "the bounded local writing workflow through IMP-063.",
        "the bounded local writing workflow through IMP-063, and the exact-commit "
        "primary Intel Mac local-writing acceptance infrastructure through IMP-064.",
        label="completed implementation summary",
    )
    text = replace_once(
        text,
        "- Phase 6 local AI portability and daily-use integration is in progress through IMP-063;",
        "- Phase 6 local AI portability and daily-use integration is in progress through IMP-064;",
        label="current phase point",
    )
    text = replace_once(
        text,
        "- IMP-063 is assigned to Issue #204;\n"
        "- the next bounded implementation receives IMP-064 only when a new implementation issue is opened;",
        "- IMP-063 is assigned to Issue #204;\n"
        "- IMP-064 adds an exact-commit primary Intel Mac acceptance probe and runner for "
        "the IMP-063 `draft`, `revise`, and `summarize` workflow, with injected no-socket "
        "CI mode, fixed-loopback real Ollama mode, strict content-free evidence, and a "
        "private-machine runbook;\n"
        "- IMP-064 is assigned to Issue #206;\n"
        "- the IMP-063/IMP-064 local-writing workflow remains `ci-pass`; separate exact-commit "
        "privacy-reviewed primary Intel Mac evidence remains required before a real-machine "
        "daily-use claim;\n"
        "- the next bounded implementation receives IMP-065 only when a new implementation issue is opened;",
        label="current IMP-064 bullets",
    )
    text = replace_once(
        text,
        "Status: implemented with deterministic synthetic CI evidence; separate exact-commit "
        "primary Intel Mac daily-use evidence is not yet claimed.",
        "Status: implemented with deterministic synthetic CI evidence; IMP-064 provides the "
        "exact-commit primary Intel Mac acceptance path, and accepted real-machine evidence "
        "remains pending.",
        label="IMP-063 status",
    )
    insertion_point = (
        "IMP-063 does not establish translation, automatic or semantic retrieval, embeddings, "
        "vector search, confirmed-memory retrieval, project or Resume Bundle context selection, "
        "attachments, multimodal input, streaming workflow output, arbitrary file publication, "
        "tools, cloud fallback, target-specific export, native application history discovery, "
        "automatic background operation, the complete Phase 6 gate, or stable general anti-lock-in.\n\n"
        "Subsequent daily-use work may expand translation, planning, explicit memory review, "
        "explicit project and decision context selection, work-item proposals, portability review, "
        "accessibility, error clarity, Lite performance, and soak testing."
    )
    imp064_section = (
        "IMP-063 does not establish translation, automatic or semantic retrieval, embeddings, "
        "vector search, confirmed-memory retrieval, project or Resume Bundle context selection, "
        "attachments, multimodal input, streaming workflow output, arbitrary file publication, "
        "tools, cloud fallback, target-specific export, native application history discovery, "
        "automatic background operation, the complete Phase 6 gate, or stable general anti-lock-in.\n\n"
        "### IMP-064 — Primary Intel Mac local-writing acceptance\n\n"
        "Status: acceptance infrastructure implemented with deterministic synthetic CI evidence; "
        "separate exact-commit primary Intel Mac execution and privacy-safe evidence acceptance "
        "remain pending.\n\n"
        "Implemented a bounded acceptance probe and runner for the IMP-063 local-writing path. "
        "The probe creates one deterministic non-private target conversation and executes one "
        "`draft`, one `revise`, and one `summarize` turn through an explicitly bound Ollama adapter.\n\n"
        "The current user request remains the only task-authority instruction. Revision and "
        "summarization source material is represented as immutable `external_content` through "
        "the accepted `extractor` / `extraction` combination, remains `untrusted_data`, and reaches "
        "the runtime only through `untrusted_content`. A hostile embedded instruction remains "
        "data-only and produces an advisory prompt-injection finding.\n\n"
        "CI mode uses an injected deterministic Ollama-compatible transport and performs no socket "
        "operation. Real-machine mode requires the exact checked-out commit, Darwin on Intel, "
        "operator-confirmed networking disabled, explicit local-only confirmation, one caller-selected "
        "already-installed local model, and fixed IPv4 loopback. The socket guard rejects every "
        "undeclared destination, and the runner does not install or start a runtime, download a model, "
        "access a provider account, retrieve credentials, execute tools, or enable cloud fallback.\n\n"
        "The content-free result schema contains only bounded platform facts, booleans, counts, hashes, "
        "event counts, runtime request counts, socket-attempt counts, and explicit non-claim flags. It "
        "excludes model names, requests, source material, prompts, responses, paths, usernames, "
        "hostnames, credentials, and secret values. Dedicated synthetic acceptance covers Ubuntu, "
        "macOS, and Windows. The local-writing workflow remains `ci-pass` until exact-commit primary "
        "Intel Mac evidence is executed and accepted separately.\n\n"
        "IMP-064 does not establish personal writing quality, automatic or semantic retrieval, memory "
        "or project context selection, translation, attachments, multimodal input, streaming workflow "
        "output, tools, cloud portability or fallback, target-specific export, complete Phase 6, or "
        "stable general anti-lock-in.\n\n"
        "Subsequent daily-use work may expand translation, planning, explicit memory review, "
        "explicit project and decision context selection, work-item proposals, portability review, "
        "accessibility, error clarity, Lite performance, and soak testing."
    )
    text = replace_once(
        text,
        insertion_point,
        imp064_section,
        label="IMP-064 roadmap section",
    )
    text = replace_once(
        text,
        "After IMP-063 bounded local writing workflow, the immediate order is:",
        "After IMP-064 local-writing real-machine acceptance infrastructure, the immediate order is:",
        label="immediate work heading",
    )
    text = replace_once(
        text,
        "3. use the IMP-063 task-versus-material separation as the required boundary for later explicit memory, project, decision, and Resume Bundle context selection;\n"
        "4. allocate IMP-064 only when a new bounded implementation issue is opened; translation, automatic retrieval, attachments, target-specific export, cloud credentials, tools, and automatic cloud fallback remain separate work;\n"
        "5. continue Phase 6 daily-use integration and independently required portability work without weakening the Phase 3 safety boundary or Phase 4A/4B canonical state contracts;\n"
        "6. keep the complete Phase 6 gate and stable general anti-lock-in incomplete until their independent remaining requirements pass.",
        "3. retain the IMP-063 task-versus-material separation as the required boundary for later explicit memory, project, decision, and Resume Bundle context selection;\n"
        "4. merge the IMP-064 acceptance infrastructure, execute its network-disabled primary Intel Mac run against the exact merged commit, and accept only a content-free privacy-reviewed result through a separate completion pull request;\n"
        "5. allocate IMP-065 only when a new bounded implementation issue is opened; translation, automatic retrieval, attachments, target-specific export, cloud credentials, tools, and automatic cloud fallback remain separate work;\n"
        "6. continue Phase 6 daily-use integration and independently required portability work without weakening the Phase 3 safety boundary or Phase 4A/4B canonical state contracts;\n"
        "7. keep the complete Phase 6 gate and stable general anti-lock-in incomplete until their independent remaining requirements pass.",
        label="immediate work steps",
    )
    ROADMAP.write_text(text, encoding="utf-8")


def update_status() -> None:
    payload = json.loads(STATUS.read_text(encoding="utf-8"))
    phase = payload.get("phase")
    runtime = payload.get("model_runtime")
    if not isinstance(phase, dict) or not isinstance(runtime, dict):
        raise SystemExit("project status shape is invalid")
    phase["next_implementation"] = 65
    runtime["message"] = (
        "Phase 6 is in progress through IMP-064. Offline Ollama session import, explicit "
        "text-only loopback capture, the accepted bounded local-portability migration drill, "
        "the deterministic shutdown escape bundle, bounded ChatGPT selected-history import, "
        "imported-context replay with accepted primary Intel Mac evidence, and the bounded local "
        "draft/revise/summarize workflow are implemented. IMP-064 adds deterministic cross-platform "
        "acceptance and the exact-commit primary Intel Mac execution path for that writing workflow; "
        "privacy-reviewed real-machine evidence remains pending. Translation, automatic retrieval, "
        "explicit memory/project context selection, attachments, tools, the complete Phase 6 gate, "
        "target-specific application replacement, and stable general anti-lock-in remain incomplete."
    )
    payload["last_reviewed"] = "2026-07-14"
    STATUS.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def update_checker() -> None:
    text = CHECKER.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'const localPortability = JSON.parse(\n  read("docs/testing/phase-6-local-portability-matrix.json"),\n);',
        'const localPortability = JSON.parse(\n  read("docs/testing/phase-6-local-portability-matrix.json"),\n);\n'
        'const dailyUse = JSON.parse(\n  read("docs/testing/phase-6-daily-use-matrix.json"),\n);',
        label="daily-use matrix load",
    )
    text = replace_once(
        text,
        "status.phase?.next_implementation === 64,\n"
        '  "project-status.json must mark Phase 6 in progress through IMP-063 with IMP-064 next",',
        "status.phase?.next_implementation === 65,\n"
        '  "project-status.json must mark Phase 6 in progress through IMP-064 with IMP-065 next",',
        label="project status implementation point",
    )
    status_anchor = (
        'expect(\n  status.model_runtime &&\n    typeof status.model_runtime.connected === "boolean" &&\n'
        '    typeof status.model_runtime.message === "string",\n'
        '  "project-status.json requires model_runtime.connected and model_runtime.message",\n);'
    )
    status_replacement = status_anchor + (
        '\nexpect(\n  status.model_runtime.message.includes("through IMP-064") &&\n'
        '    status.model_runtime.message.includes("real-machine evidence remains pending"),\n'
        '  "project-status.json must describe the bounded IMP-064 pending machine gate",\n);'
    )
    text = replace_once(
        text,
        status_anchor,
        status_replacement,
        label="project status message check",
    )
    matrix_anchor = (
        'expect(\n  importedReplayPrimary.test_id ===\n'
        '    "IMP-062-IMPORTED-CONTEXT-REPLAY-PRIMARY"'
    )
    daily_check = (
        'expect(\n  dailyUse.schema_version === 1 &&\n'
        '    dailyUse.phase === "6" &&\n'
        '    dailyUse.local_writing_workflow?.implementation === "IMP-063" &&\n'
        '    dailyUse.local_writing_workflow?.acceptance_implementation === "IMP-064" &&\n'
        '    dailyUse.local_writing_workflow?.status === "ci-pass" &&\n'
        '    JSON.stringify(dailyUse.local_writing_workflow?.passed_evidence_levels) ===\n'
        '      JSON.stringify(["ci"]) &&\n'
        '    JSON.stringify(dailyUse.local_writing_workflow?.required_evidence_levels) ===\n'
        '      JSON.stringify(["ci", "real-machine"]) &&\n'
        '    dailyUse.local_writing_workflow?.accepted_real_machine_result === null &&\n'
        '    dailyUse.local_writing_workflow?.real_machine_gate?.required === true &&\n'
        '    dailyUse.local_writing_workflow?.real_machine_gate?.status === "pending" &&\n'
        '    dailyUse.local_writing_workflow?.real_machine_gate?.commit_sha === null &&\n'
        '    dailyUse.local_writing_workflow?.real_machine_gate?.completed_at === null &&\n'
        '    dailyUse.local_writing_workflow?.real_machine_gate_status === "pending" &&\n'
        '    dailyUse.local_writing_workflow?.implementation_doc ===\n'
        '      "docs/implementation/imp-064-primary-intel-mac-local-writing-acceptance.md" &&\n'
        '    dailyUse.local_writing_workflow?.runbook ===\n'
        '      "docs/testing/imp-064-primary-intel-mac-runbook.md" &&\n'
        '    dailyUse.local_writing_workflow?.phase6_gate_complete === false &&\n'
        '    dailyUse.local_writing_workflow?.stable_anti_lock_in_claim === false,\n'
        '  "IMP-063/IMP-064 writing workflow must remain ci-pass pending machine evidence",\n'
        ');\n\n'
    )
    text = replace_once(
        text,
        matrix_anchor,
        daily_check + matrix_anchor,
        label="daily-use matrix check",
    )
    text = replace_once(
        text,
        'roadmap.includes("the next bounded implementation receives IMP-064 only when a new implementation issue is opened"),\n'
        '  "roadmap must identify IMP-064 as the next unallocated implementation identifier",',
        'roadmap.includes("the next bounded implementation receives IMP-065 only when a new implementation issue is opened"),\n'
        '  "roadmap must identify IMP-065 as the next unallocated implementation identifier",',
        label="roadmap next identifier check",
    )
    imp063_anchor = (
        'expect(\n  roadmap.includes("### IMP-063 — Bounded local writing workflow"),\n'
        '  "roadmap must record the IMP-063 local writing workflow boundary",\n);'
    )
    text = replace_once(
        text,
        imp063_anchor,
        imp063_anchor
        + '\nexpect(\n  roadmap.includes("### IMP-064 — Primary Intel Mac local-writing acceptance"),\n'
        '  "roadmap must record the IMP-064 local writing acceptance boundary",\n);',
        label="IMP-064 roadmap heading check",
    )
    text = replace_once(
        text,
        '"After IMP-063 bounded local writing workflow, the immediate order is:",',
        '"After IMP-064 local-writing real-machine acceptance infrastructure, the immediate order is:",',
        label="immediate work checker heading",
    )
    text = replace_once(
        text,
        '"roadmap must record IMP-063 and remaining Phase 6 work",',
        '"roadmap must record IMP-064 infrastructure and remaining Phase 6 work",',
        label="immediate work checker message",
    )
    CHECKER.write_text(text, encoding="utf-8")


def main() -> None:
    update_implementation()
    update_roadmap()
    update_status()
    update_checker()
    subprocess.run(
        ["uv", "run", "python", "scripts/build_final_spec.py"],
        cwd=ROOT,
        check=True,
    )
    print("IMP-064 documentation and public status updates applied")


if __name__ == "__main__":
    main()
