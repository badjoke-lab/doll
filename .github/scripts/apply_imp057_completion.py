from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_PATH = "docs/testing/results/IMP-057-primary-intel-mac-2026-06-29.json"
IMPLEMENTATION_COMMIT = "7b63ff512e20d1d6ae65da8938486b093e14b6c6"
COMPLETED_AT = "2026-06-29T15:48:03.615410Z"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8", newline="\n")


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def update_matrix() -> None:
    path = "docs/testing/phase-6-local-portability-matrix.json"
    matrix = json.loads(read(path))
    matrix["local_portability_gate_complete"] = True
    matrix["accepted_real_machine_result"] = EVIDENCE_PATH
    for item in matrix["portability_tests"]:
        if item["id"] not in {"PORT-001", "PORT-003", "PORT-013"}:
            raise RuntimeError(f"unexpected portability ID: {item['id']}")
        item["status"] = "pass"
        item["passed_evidence_levels"] = ["ci", "real-machine"]
    gate = matrix["real_machine_gate"]
    gate["status"] = "pass"
    gate["commit_sha"] = IMPLEMENTATION_COMMIT
    gate["completed_at"] = COMPLETED_AT
    matrix["limitations"] = [
        "Synthetic CI uses an injected transport and is not real Ollama evidence.",
        "Primary Intel Mac evidence is accepted for the exact merged IMP-057 implementation commit and stored as a privacy-reviewed result.",
        "The bounded drill completes PORT-001, PORT-003, and the IMP-057 portion of PORT-013 for explicit non-streaming text capture and parent relationships.",
        "Native Ollama history discovery, attachments, multimodal content, tools, streaming capture, and target-specific export remain outside this evidence.",
        "The alternate component is a fresh-process canonical-state reader and generic exporter; no second model or runtime adapter is claimed.",
        "ChatGPT migration, PORT-015, the complete Phase 6 gate, general application replacement, and a stable general anti-lock-in claim remain outside this implementation.",
    ]
    write(path, json.dumps(matrix, indent=2, ensure_ascii=False) + "\n")


def update_implementation_doc() -> None:
    path = "docs/implementation/imp-057-local-portability-migration-drill.md"
    text = read(path)
    text = replace_once(
        text,
        "Implementation harness complete. Deterministic synthetic CI is accepted for the implementation boundary. Primary Intel Mac evidence remains pending and must be stored by a separate completion pull request bound to the exact merged implementation commit.",
        "Implementation and evidence complete for the bounded IMP-057 migration drill. Deterministic synthetic CI and privacy-reviewed primary Intel Mac evidence are accepted and bound to the exact merged implementation commit.",
        label="implementation status",
    )
    text = replace_once(
        text,
        "CI proves orchestration and failure-preserving contracts. It is not evidence that a real local Ollama installation or model works on the project owner's machine. Matrix entries therefore remain `ci-pass`, with only `ci` listed under passed evidence levels, until accepted real-machine evidence is stored.",
        "CI proves orchestration and failure-preserving contracts. It is not by itself evidence that a real local Ollama installation or model works on the project owner's machine. After the accepted real-machine result was stored, the bounded PORT-001, PORT-003, and PORT-013 entries moved from `ci-pass` to `pass` with both `ci` and `real-machine` listed as passed evidence levels.",
        label="implementation CI evidence",
    )
    text = replace_once(
        text,
        "The runner installs, downloads, deletes, activates, or selects no model automatically.",
        "The runner installs, downloads, deletes, activates, or selects no model automatically.\n\nThe accepted run used Darwin `x86_64`, networking disabled, fixed IPv4 loopback Ollama, one explicitly selected already-installed local model, and exact implementation commit `7b63ff512e20d1d6ae65da8938486b093e14b6c6`. The privacy-reviewed result is stored at `docs/testing/results/IMP-057-primary-intel-mac-2026-06-29.json`.",
        label="implementation accepted evidence",
    )
    text = replace_once(
        text,
        "Issue #178 remains open after that merge. A separate completion pull request must:\n\n1. run the exact merged implementation commit on the primary Intel Mac with networking disabled;\n2. review the bounded result for private-data leakage;\n3. store only the accepted result and matrix binding;\n4. change the bounded PORT-001, PORT-003, and PORT-013 entries from `ci-pass` to `pass` only after accepted real-machine evidence exists;\n5. leave PORT-015 and the complete Phase 6 gate pending unless their full separate criteria are met.",
        "Issue #178 is completed by the separate evidence pull request. That completion:\n\n1. ran the exact merged implementation commit on the primary Intel Mac with networking disabled;\n2. reviewed the bounded result for private-data leakage;\n3. stored only the accepted privacy-safe result and matrix binding;\n4. changed the bounded PORT-001, PORT-003, and PORT-013 entries from `ci-pass` to `pass`;\n5. left PORT-015 and the complete Phase 6 gate pending because their separate criteria are not met.",
        label="implementation completion",
    )
    text = replace_once(
        text,
        "- a stable local-environment portability or anti-lock-in claim before accepted real-machine evidence is stored.",
        "- a stable general local-environment portability or anti-lock-in claim beyond the bounded IMP-057 component and evidence surface.",
        label="implementation non-claim",
    )
    write(path, text)


def update_roadmap() -> None:
    path = "docs/spec/09-development-roadmap.md"
    text = read(path)
    old_current = """- deterministic Linux, macOS, and Windows CI accepts PORT-001, PORT-003, and the bounded IMP-057 portion of PORT-013 only at the `ci-pass` evidence level;
- Issue #178 remains open for the exact-commit primary Intel Mac drill with networking disabled, one already-installed local Ollama model selected explicitly, and privacy-safe reviewed evidence;
- until that evidence is accepted, doll does not claim final PORT-001, PORT-003, or PORT-013 satisfaction, removal of the original local application, stable local portability, PORT-015, a stable anti-lock-in property, or the Phase 6 gate;
- this documentation-only status correction allocates no implementation identifier; the next bounded implementation receives IMP-058 only when a new implementation issue is opened;"""
    new_current = """- accepted primary Intel Mac evidence is bound to exact IMP-057 implementation commit `7b63ff512e20d1d6ae65da8938486b093e14b6c6` and stored at `docs/testing/results/IMP-057-primary-intel-mac-2026-06-29.json`;
- PORT-001, PORT-003, and the bounded IMP-057 portion of PORT-013 pass at both `ci` and `real-machine` evidence levels;
- the bounded IMP-057 local-portability gate is complete, but this does not establish native Ollama history migration, target-specific export, general application replacement, PORT-015, the complete Phase 6 gate, or a stable general anti-lock-in property;
- Issue #178 is completed by the privacy-reviewed evidence pull request;
- this evidence-only completion allocates no implementation identifier; the next bounded implementation receives IMP-058 only when a new implementation issue is opened;"""
    text = replace_once(text, old_current, new_current, label="roadmap current state")
    text = replace_once(
        text,
        "Status: implementation harness merged with deterministic synthetic CI evidence; primary Intel Mac evidence remains pending in Issue #178.",
        "Status: implementation and bounded evidence complete with deterministic synthetic CI and accepted primary Intel Mac real-machine evidence.",
        label="roadmap IMP-057 status",
    )
    old_evidence = """Deterministic CI passes on Linux, macOS, and Windows and records PORT-001, PORT-003, and the bounded IMP-057 portion of PORT-013 as `ci-pass`. Synthetic CI uses an injected transport and performs no real Ollama socket request, so it is not primary-machine evidence and cannot complete the local portability claim.

The exact merged implementation commit is `7b63ff512e20d1d6ae65da8938486b093e14b6c6`. Completion requires a separate privacy-reviewed evidence pull request from the primary Intel Mac with networking disabled. The result must not include native model names, prompts, responses, personal conversations, paths, usernames, hostnames, credentials, or secrets."""
    new_evidence = """Deterministic CI passes on Linux, macOS, and Windows. The accepted primary Intel Mac run used Darwin `x86_64`, networking disabled, fixed IPv4 loopback Ollama, and one explicitly selected already-installed local model. PORT-001, PORT-003, and the bounded IMP-057 portion of PORT-013 now pass at both `ci` and `real-machine` evidence levels.

The accepted result is bound to exact merged implementation commit `7b63ff512e20d1d6ae65da8938486b093e14b6c6` and stored at `docs/testing/results/IMP-057-primary-intel-mac-2026-06-29.json`. Privacy review confirmed that the result contains no native model names, prompts, responses, personal conversations, paths, usernames, hostnames, credentials, or secrets."""
    text = replace_once(text, old_evidence, new_evidence, label="roadmap IMP-057 evidence")
    old_immediate = """The required order after the IMP-057 harness merge is:

1. keep Issue #178 open until the exact merged implementation commit is run on the primary Intel Mac with networking disabled, Ollama already running locally, and one already-installed model selected explicitly;
2. review the bounded JSON result before storage and commit only privacy-safe evidence in a separate completion pull request;
3. change PORT-001, PORT-003, and the bounded IMP-057 portion of PORT-013 from `ci-pass` to `pass` only after the real-machine evidence is accepted;
4. do not claim stable local portability, application replacement, PORT-015, a stable anti-lock-in property, or the Phase 6 gate while the real-machine gate is pending;
5. keep ChatGPT history, provider-specific cloud portability, credentials, tools, automatic cloud fallback, multimodal capture, and target-specific export outside the pending local migration gate;
6. allocate IMP-058 only when a new bounded implementation issue is actually opened; documentation and maintenance work do not reserve it."""
    new_immediate = """The required order after accepted IMP-057 real-machine evidence is:

1. keep the accepted claim limited to PORT-001, PORT-003, and the bounded IMP-057 portion of PORT-013;
2. do not extend the result to native Ollama history discovery, target-specific export, general application replacement, PORT-015, the complete Phase 6 gate, or a stable general anti-lock-in claim;
3. open the next bounded Phase 6 implementation issue only when its objective, acceptance boundary, and real-machine requirements are defined; the next bounded implementation receives IMP-058 only when a new implementation issue is opened;
4. continue local-first daily-use and migration work through the Phase 3 safety boundary and the Phase 4A/4B canonical state contracts;
5. keep ChatGPT history, provider-specific cloud portability, credentials, tools, automatic cloud fallback, multimodal capture, and target-specific export outside the completed IMP-057 boundary."""
    text = replace_once(text, old_immediate, new_immediate, label="roadmap immediate work")
    write(path, text)


def update_public_status() -> None:
    path = "website/project-status.json"
    status = json.loads(read(path))
    status["model_runtime"]["message"] = (
        "Phase 6 is in progress through IMP-057. Offline session import, explicit text-only loopback Ollama capture, and the deterministic end-to-end local-portability harness are implemented. PORT-001, PORT-003, and bounded PORT-013 pass in CI and on accepted exact-commit primary Intel Mac evidence; the bounded IMP-057 local-portability gate is complete. PORT-015, native history migration, general application replacement, stable general anti-lock-in, and the Phase 6 gate are not complete."
    )
    status["last_reviewed"] = "2026-06-29"
    write(path, json.dumps(status, indent=2, ensure_ascii=False) + "\n")


def update_public_status_check() -> None:
    path = "scripts/check-public-site-status.mjs"
    text = read(path)
    text = replace_once(
        text,
        'roadmap.includes("The required order after the IMP-057 harness merge is:")',
        'roadmap.includes("The required order after accepted IMP-057 real-machine evidence is:")',
        label="public status immediate-work check",
    )
    text = replace_once(
        text,
        '"roadmap must record the real-machine gate after IMP-057",',
        '"roadmap must record the accepted real-machine evidence after IMP-057",',
        label="public status immediate-work message",
    )
    marker = """expect(
  roadmap.includes("the next bounded implementation receives IMP-058 only when a new implementation issue is opened"),
  "roadmap must identify IMP-058 as the next unallocated implementation identifier",
);
"""
    addition = marker + """expect(
  roadmap.includes("docs/testing/results/IMP-057-primary-intel-mac-2026-06-29.json"),
  "roadmap must bind the accepted IMP-057 primary Intel Mac evidence",
);
"""
    text = replace_once(text, marker, addition, label="public status evidence check")
    write(path, text)


def validate_evidence() -> None:
    evidence = json.loads(read(EVIDENCE_PATH))
    if evidence.get("result") != "pass":
        raise RuntimeError("real-machine result is not pass")
    if evidence.get("commit_sha") != IMPLEMENTATION_COMMIT:
        raise RuntimeError("real-machine result commit mismatch")
    if evidence.get("evidence_level") != "real-machine":
        raise RuntimeError("wrong evidence level")
    if evidence.get("operating_system") != "Darwin" or evidence.get("architecture") != "x86_64":
        raise RuntimeError("wrong primary-machine platform")
    if evidence.get("completed_at") != COMPLETED_AT:
        raise RuntimeError("completion timestamp mismatch")
    if evidence.get("primary_intel_mac_gate") != "pass":
        raise RuntimeError("primary machine gate did not pass")
    if evidence.get("local_portability_gate_complete") is not True:
        raise RuntimeError("bounded local-portability gate incomplete")
    if evidence.get("phase6_gate_complete") is not False:
        raise RuntimeError("Phase 6 must remain incomplete")
    if not evidence.get("checks") or not all(evidence["checks"].values()):
        raise RuntimeError("not all real-machine checks passed")
    if not evidence.get("privacy") or any(evidence["privacy"].values()):
        raise RuntimeError("privacy flags are not clean")


def main() -> None:
    validate_evidence()
    update_matrix()
    update_implementation_doc()
    update_roadmap()
    update_public_status()
    update_public_status_check()
    subprocess.run(["python", "scripts/build_final_spec.py"], cwd=ROOT, check=True)
    (ROOT / ".github/scripts/apply_imp057_completion.py").unlink()
    (ROOT / ".github/workflows/imp057-completion-temporary.yml").unlink()


if __name__ == "__main__":
    main()
