from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8", newline="\n")


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def update_roadmap() -> None:
    path = "docs/spec/09-development-roadmap.md"
    text = read(path)
    text = replace_once(
        text,
        "the offline Ollama API session source adapter through IMP-055, explicit loopback Ollama chat capture through IMP-056, and the deterministic local-portability migration harness through IMP-057.",
        "the offline Ollama API session source adapter through IMP-055, explicit loopback Ollama chat capture through IMP-056, the deterministic local-portability migration harness through IMP-057, and the deterministic shutdown escape bundle through IMP-058.",
        label="roadmap implemented scope",
    )
    old_current = """- Phase 6 local AI portability and daily-use integration is in progress through IMP-057;
- IMP-055 adds an offline source adapter for a documented caller-retained Ollama API session bundle, with exact JSON validation, content-free inventory, original-source hashing, deterministic normalization, explicit attachment-metadata loss, and reuse of the accepted generic staging and reviewed-publication boundary;
- IMP-056 adds an explicit non-streaming text-only capture path through fixed IPv4 loopback, resolves one opaque already-installed local model through the filtered inventory, and returns an IMP-055-valid session bundle without reading application databases, logs, shell history, or unrelated sessions;
- IMP-057 merged at commit `7b63ff512e20d1d6ae65da8938486b093e14b6c6` and composes explicit capture, reviewed canonical import, idempotency and conflict checks, generic export, State Package v2 transfer, backup restore, and alternate fresh-process inspection without the capture component;
- IMP-057 extends State Package v2 conditionally for portability publication records and managed original-source artifacts while preserving the previous package surface when those records are absent;
- accepted primary Intel Mac evidence is bound to exact IMP-057 implementation commit `7b63ff512e20d1d6ae65da8938486b093e14b6c6` and stored at `docs/testing/results/IMP-057-primary-intel-mac-2026-06-29.json`;
- PORT-001, PORT-003, and the bounded IMP-057 portion of PORT-013 pass at both `ci` and `real-machine` evidence levels;
- the bounded IMP-057 local-portability gate is complete, but this does not establish native Ollama history migration, target-specific export, general application replacement, PORT-015, the complete Phase 6 gate, or a stable general anti-lock-in property;
- Issue #178 is completed by the privacy-reviewed evidence pull request;
- this evidence-only completion allocates no implementation identifier; the next bounded implementation receives IMP-058 only when a new implementation issue is opened;"""
    new_current = """- Phase 6 local AI portability and daily-use integration is in progress through IMP-058;
- IMP-055 adds an offline source adapter for a documented caller-retained Ollama API session bundle, with exact JSON validation, content-free inventory, original-source hashing, deterministic normalization, explicit attachment-metadata loss, and reuse of the accepted generic staging and reviewed-publication boundary;
- IMP-056 adds an explicit non-streaming text-only capture path through fixed IPv4 loopback, resolves one opaque already-installed local model through the filtered inventory, and returns an IMP-055-valid session bundle without reading application databases, logs, shell history, or unrelated sessions;
- IMP-057 merged at commit `7b63ff512e20d1d6ae65da8938486b093e14b6c6` and composes explicit capture, reviewed canonical import, idempotency and conflict checks, generic export, State Package v2 transfer, backup restore, and alternate fresh-process inspection without the capture component;
- accepted primary Intel Mac evidence is bound to exact IMP-057 implementation commit `7b63ff512e20d1d6ae65da8938486b093e14b6c6` and stored at `docs/testing/results/IMP-057-primary-intel-mac-2026-06-29.json`;
- PORT-001, PORT-003, and the bounded IMP-057 portion of PORT-013 pass at both `ci` and `real-machine` evidence levels;
- IMP-058 adds a deterministic `doll-shutdown-escape` bundle that composes a verified State Package, generic conversation export, project Resume Bundles, bounded recovery documentation, and a standard-library-only standalone inspector;
- deterministic Linux, macOS, and Windows CI records PORT-015 at `ci-pass`; Issue #183 remains open for privacy-reviewed exact-commit primary Intel Mac evidence with networking disabled and no model or doll service required;
- IMP-058 does not complete PORT-015, the Phase 6 gate, target-specific application round trips, or a stable general anti-lock-in claim before that real-machine evidence is accepted;
- the next bounded implementation receives IMP-059 only when a new implementation issue is opened;"""
    text = replace_once(text, old_current, new_current, label="roadmap current implementation")

    marker = """IMP-057 does not complete PORT-015, target-specific export, ChatGPT history migration, native Ollama history discovery, multimodal or tool fidelity, a second runtime migration, the full Phase 6 gate, or a stable anti-lock-in claim.

Daily-use work may then expand writing, editing, summarization, translation, planning, memory review, project and decision workflows, work-item proposals, portability review, accessibility, error clarity, Lite performance, and soak testing."""
    replacement = """IMP-057 does not complete PORT-015, target-specific export, ChatGPT history migration, native Ollama history discovery, multimodal or tool fidelity, a second runtime migration, the full Phase 6 gate, or a stable anti-lock-in claim.

### IMP-058 — Deterministic Doll shutdown escape bundle

Status: implementation harness complete with deterministic synthetic CI evidence; primary Intel Mac evidence remains pending in Issue #183.

Implemented a versioned `doll-shutdown-escape` ZIP that composes one verified State Package, deterministic generic conversation files when fully non-secret conversations exist, one verified Resume Bundle per non-secret project, bounded recovery documents, a top-level manifest and SHA-256 inventory, and a bundled standard-library-only inspector that imports no doll module.

Export requires a read-only repository, publishes outside the workspace and repository checkout, uses deterministic archive metadata and create-new atomic publication, verifies before publication, preserves existing destinations, cleans failures, and leaves workspace status and audit history unchanged. Secret records and credential material are omitted and counted.

Synthetic CI removes the source workspace before fresh-process `python -I` inspection, verifies all embedded recovery surfaces, proves repeated byte-identical export, and rejects tampering and unsafe archive structure. PORT-015 remains `ci-pass` until a separate privacy-reviewed exact-commit primary Intel Mac result is stored. The real-machine run requires networking disabled and requires no model, runtime execution, cloud credential, preferred UI, or doll service.

IMP-058 does not establish ChatGPT history migration, native Ollama history discovery, target-specific application import, provider-specific round-trip fidelity, secret portability, the complete Phase 6 gate, or a stable general anti-lock-in claim before accepted real-machine evidence.

Daily-use work may then expand writing, editing, summarization, translation, planning, memory review, project and decision workflows, work-item proposals, portability review, accessibility, error clarity, Lite performance, and soak testing."""
    text = replace_once(text, marker, replacement, label="roadmap IMP-058 section")

    old_immediate = """The required order after accepted IMP-057 real-machine evidence is:

1. keep the accepted claim limited to PORT-001, PORT-003, and the bounded IMP-057 portion of PORT-013;
2. do not extend the result to native Ollama history discovery, target-specific export, general application replacement, PORT-015, the complete Phase 6 gate, or a stable general anti-lock-in claim;
3. open the next bounded Phase 6 implementation issue only when its objective, acceptance boundary, and real-machine requirements are defined; the next bounded implementation receives IMP-058 only when a new implementation issue is opened;
4. continue local-first daily-use and migration work through the Phase 3 safety boundary and the Phase 4A/4B canonical state contracts;
5. keep ChatGPT history, provider-specific cloud portability, credentials, tools, automatic cloud fallback, multimodal capture, and target-specific export outside the completed IMP-057 boundary."""
    new_immediate = """The required order after the IMP-058 shutdown escape harness merge is:

1. keep Issue #183 open until the exact merged implementation commit is run on the primary Intel Mac with networking disabled and no model or doll service required;
2. review the bounded JSON result and store only privacy-safe exact-commit evidence in a separate completion pull request;
3. change PORT-015 from `ci-pass` to `pass` only after the real-machine evidence is accepted;
4. do not claim the complete Phase 6 gate, target-specific application replacement, secret portability, or stable general anti-lock-in while the real-machine gate is pending;
5. allocate IMP-059 only when a new bounded implementation issue with explicit acceptance and real-machine requirements is opened;
6. keep ChatGPT history, provider-specific cloud portability, credentials, tools, automatic cloud fallback, multimodal capture, and target-specific export outside the completed IMP-058 implementation boundary."""
    text = replace_once(text, old_immediate, new_immediate, label="roadmap immediate work")
    write(path, text)


def update_status() -> None:
    path = "website/project-status.json"
    status = json.loads(read(path))
    status["phase"]["next_implementation"] = 59
    status["model_runtime"]["message"] = (
        "Phase 6 is in progress through IMP-058. Offline Ollama session import, explicit text-only loopback capture, the accepted bounded local-portability migration drill, and a deterministic shutdown escape bundle are implemented. PORT-001, PORT-003, and bounded PORT-013 pass in CI and on accepted primary Intel Mac evidence. PORT-015 passes CI only and still requires privacy-reviewed exact-commit primary Intel Mac evidence; the complete Phase 6 gate and stable general anti-lock-in are not complete."
    )
    status["last_reviewed"] = "2026-07-02"
    write(path, json.dumps(status, indent=2, ensure_ascii=False) + "\n")


def update_status_check() -> None:
    path = "scripts/check-public-site-status.mjs"
    text = read(path)
    text = replace_once(
        text,
        "status.phase?.next_implementation === 58,",
        "status.phase?.next_implementation === 59,",
        label="status next implementation",
    )
    text = replace_once(
        text,
        '"project-status.json must mark Phase 6 in progress through IMP-057 with IMP-058 next",',
        '"project-status.json must mark Phase 6 in progress through IMP-058 with IMP-059 next",',
        label="status next implementation message",
    )
    old_checks = """expect(
  roadmap.includes("the next bounded implementation receives IMP-058 only when a new implementation issue is opened"),
  "roadmap must identify IMP-058 as the next unallocated implementation identifier",
);
expect(
  roadmap.includes("docs/testing/results/IMP-057-primary-intel-mac-2026-06-29.json"),
  "roadmap must bind the accepted IMP-057 primary Intel Mac evidence",
);
expect(
  roadmap.includes("The required order after accepted IMP-057 real-machine evidence is:"),
  "roadmap must record the accepted real-machine evidence after IMP-057",
);"""
    new_checks = """expect(
  roadmap.includes("### IMP-058 — Deterministic Doll shutdown escape bundle"),
  "roadmap must record the IMP-058 shutdown escape bundle",
);
expect(
  roadmap.includes("the next bounded implementation receives IMP-059 only when a new implementation issue is opened"),
  "roadmap must identify IMP-059 as the next unallocated implementation identifier",
);
expect(
  roadmap.includes("docs/testing/results/IMP-057-primary-intel-mac-2026-06-29.json"),
  "roadmap must bind the accepted IMP-057 primary Intel Mac evidence",
);
expect(
  roadmap.includes("The required order after the IMP-058 shutdown escape harness merge is:"),
  "roadmap must record the pending IMP-058 primary-machine gate",
);"""
    text = replace_once(text, old_checks, new_checks, label="public roadmap checks")
    marker = 'const status = JSON.parse(read("website/project-status.json"));\n'
    addition = marker + 'const shutdownEscape = JSON.parse(\n  read("docs/testing/phase-6-shutdown-escape-matrix.json"),\n);\n'
    text = replace_once(text, marker, addition, label="shutdown matrix read")
    status_marker = """expect(
  /^\\d{4}-\\d{2}-\\d{2}$/.test(status.last_reviewed || ""),
  "project-status.json last_reviewed must be YYYY-MM-DD",
);
"""
    status_addition = status_marker + """expect(
  shutdownEscape.implementation === "IMP-058" &&
    shutdownEscape.shutdown_escape_gate_complete === false &&
    shutdownEscape.portability_tests?.length === 1 &&
    shutdownEscape.portability_tests[0]?.id === "PORT-015" &&
    shutdownEscape.portability_tests[0]?.status === "ci-pass" &&
    shutdownEscape.real_machine_gate?.status === "pending",
  "IMP-058 shutdown escape matrix must remain ci-pass with primary-machine evidence pending",
);
"""
    text = replace_once(text, status_marker, status_addition, label="shutdown matrix check")
    write(path, text)


def main() -> None:
    update_roadmap()
    update_status()
    update_status_check()
    subprocess.run(["python", "scripts/build_final_spec.py"], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
