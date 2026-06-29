"""Apply the documentation-only Phase 6 status update after IMP-057."""

from __future__ import annotations

import json
from pathlib import Path

ROADMAP = Path("docs/spec/09-development-roadmap.md")
STATUS = Path("website/project-status.json")


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"unexpected replacement count: {old[:100]!r}")
    return text.replace(old, new, 1)


def update_roadmap() -> None:
    text = ROADMAP.read_text(encoding="utf-8")
    text = replace_once(text, "- IMP-030 through IMP-056;", "- IMP-030 through IMP-057;")
    text = replace_once(
        text,
        "- local workspace, SQLite state, migrations, managed artifacts, canonical conversation and project state, State Package v2, backup and restore, the model-independent safety boundary, AI-environment portability, project continuity, runtime-independent adapter contracts, a loopback-only Ollama adapter, authoritative runtime and model manifests, explicit bindings, canonical local conversation and streaming, explicit fallback switching, exact rollback, and accepted primary Intel Mac offline continuity evidence through IMP-054, the offline Ollama API session source adapter through IMP-055, and explicit loopback Ollama chat capture through IMP-056.",
        "- local workspace, SQLite state, migrations, managed artifacts, canonical conversation and project state, State Package v2, backup and restore, the model-independent safety boundary, AI-environment portability, project continuity, runtime-independent adapter contracts, a loopback-only Ollama adapter, authoritative runtime and model manifests, explicit bindings, canonical local conversation and streaming, explicit fallback switching, exact rollback, and accepted primary Intel Mac offline continuity evidence through IMP-054, the offline Ollama API session source adapter through IMP-055, explicit loopback Ollama chat capture through IMP-056, and the deterministic local-portability migration harness through IMP-057.",
    )

    old_current = """- Phase 6 local AI portability and daily-use integration is now in progress;
- IMP-055 adds an offline source adapter for a documented caller-retained Ollama API session bundle, with exact JSON validation, content-free inventory, original-source hashing, deterministic normalization, explicit attachment-metadata loss, and reuse of the accepted generic staging and reviewed-publication boundary;
- IMP-055 performs no live Ollama request, application-database read, shell-history read, model import, credential access, cloud request, tool execution, schema migration, or State Package format change;
- IMP-055 does not complete PORT-013 or a stable local-environment portability claim;
- IMP-056 adds an explicit non-streaming text-only capture path through fixed IPv4 loopback, resolves one opaque already-installed local model through the filtered inventory, and returns an IMP-055-valid session bundle without reading application databases, logs, shell history, or unrelated sessions;
- IMP-056 synthetic CI proves new-session and append capture, unrelated-conversation preservation, strict source and runtime identity checks, bounded failure behavior, and no Doll State, tool, credential, cloud, subprocess, model-download, or automatic authority path;
- IMP-056 does not complete the primary Intel Mac migration drill, PORT-013, tested round trip, application removal, or the Phase 6 gate;
- the next bounded Phase 6 implementation receives IMP-057 when its issue is opened;
- later local migration, cloud, and tool work must continue through the Phase 3 safety boundary and the Phase 4A/4B canonical state contracts.
"""
    new_current = """- Phase 6 local AI portability and daily-use integration is in progress through IMP-057;
- IMP-055 adds an offline source adapter for a documented caller-retained Ollama API session bundle, with exact JSON validation, content-free inventory, original-source hashing, deterministic normalization, explicit attachment-metadata loss, and reuse of the accepted generic staging and reviewed-publication boundary;
- IMP-056 adds an explicit non-streaming text-only capture path through fixed IPv4 loopback, resolves one opaque already-installed local model through the filtered inventory, and returns an IMP-055-valid session bundle without reading application databases, logs, shell history, or unrelated sessions;
- IMP-057 merged at commit `7b63ff512e20d1d6ae65da8938486b093e14b6c6` and composes explicit capture, reviewed canonical import, idempotency and conflict checks, generic export, State Package v2 transfer, backup restore, and alternate fresh-process inspection without the capture component;
- IMP-057 extends State Package v2 conditionally for portability publication records and managed original-source artifacts while preserving the previous package surface when those records are absent;
- deterministic Linux, macOS, and Windows CI accepts PORT-001, PORT-003, and the bounded IMP-057 portion of PORT-013 only at the `ci-pass` evidence level;
- Issue #178 remains open for the exact-commit primary Intel Mac drill with networking disabled, one already-installed local Ollama model selected explicitly, and privacy-safe reviewed evidence;
- until that evidence is accepted, doll does not claim final PORT-001, PORT-003, or PORT-013 satisfaction, removal of the original local application, stable local portability, PORT-015, a stable anti-lock-in property, or the Phase 6 gate;
- this documentation-only status correction allocates no implementation identifier; the next bounded implementation receives IMP-058 only when a new implementation issue is opened;
- later local migration, cloud, and tool work must continue through the Phase 3 safety boundary and the Phase 4A/4B canonical state contracts.
"""
    text = replace_once(text, old_current, new_current)

    insertion = """
### IMP-057 — Local-portability migration harness

Status: implementation harness merged with deterministic synthetic CI evidence; primary Intel Mac evidence remains pending in Issue #178.

Implemented an integrated migration scenario that composes IMP-056 capture, IMP-055 validation and staging, reviewed canonical publication, unchanged-source idempotency, changed-source conflict protection, generic export, State Package v2 transfer, verified backup restore, and alternate fresh-process inspection after the capture component is absent from the execution path.

The implementation also adds conditional State Package v2 support for source environments, import batches, mapping reports, portability losses, source mappings, quarantines, original-source snapshot records, and managed original-source files. Imported content remains data-only, relationships and hashes are revalidated after transfer, and packages without portability records keep the previous v2 category surface.

Deterministic CI passes on Linux, macOS, and Windows and records PORT-001, PORT-003, and the bounded IMP-057 portion of PORT-013 as `ci-pass`. Synthetic CI uses an injected transport and performs no real Ollama socket request, so it is not primary-machine evidence and cannot complete the local portability claim.

The exact merged implementation commit is `7b63ff512e20d1d6ae65da8938486b093e14b6c6`. Completion requires a separate privacy-reviewed evidence pull request from the primary Intel Mac with networking disabled. The result must not include native model names, prompts, responses, personal conversations, paths, usernames, hostnames, credentials, or secrets.

IMP-057 does not complete PORT-015, target-specific export, ChatGPT history migration, native Ollama history discovery, multimodal or tool fidelity, a second runtime migration, the full Phase 6 gate, or a stable anti-lock-in claim.
"""
    marker = "\nDaily-use work may then expand writing, editing, summarization, translation, planning, memory review, project and decision workflows, work-item proposals, portability review, accessibility, error clarity, Lite performance, and soak testing.\n"
    text = replace_once(text, marker, insertion + marker)

    old_immediate = """The required order after IMP-056 is:

1. merge the explicit loopback Ollama chat capture only after all cross-platform, quality, specification, public-status, numbering, and coverage checks pass;
2. open the next bounded Phase 6 issue as IMP-057 for the exact-commit primary Intel Mac capture, import, alternate approved execution, and original-path removal drill;
3. preserve reviewed synthetic or approved private evidence without committing personal conversation content, native model names, prompts, responses, paths, usernames, hostnames, credentials, or secrets;
4. complete applicable PORT-001, PORT-003, PORT-013, and later PORT-015 evidence before making a stable local-portability or anti-lock-in claim;
5. keep ChatGPT history, provider-specific cloud portability, credentials, tools, automatic cloud fallback, multimodal capture, and target-specific export outside the local migration gate.
"""
    new_immediate = """The required order after the IMP-057 harness merge is:

1. keep Issue #178 open until the exact merged implementation commit is run on the primary Intel Mac with networking disabled, Ollama already running locally, and one already-installed model selected explicitly;
2. review the bounded JSON result before storage and commit only privacy-safe evidence in a separate completion pull request;
3. change PORT-001, PORT-003, and the bounded IMP-057 portion of PORT-013 from `ci-pass` to `pass` only after the real-machine evidence is accepted;
4. do not claim stable local portability, application replacement, PORT-015, a stable anti-lock-in property, or the Phase 6 gate while the real-machine gate is pending;
5. keep ChatGPT history, provider-specific cloud portability, credentials, tools, automatic cloud fallback, multimodal capture, and target-specific export outside the pending local migration gate;
6. allocate IMP-058 only when a new bounded implementation issue is actually opened; documentation and maintenance work do not reserve it.
"""
    text = replace_once(text, old_immediate, new_immediate)
    ROADMAP.write_text(text, encoding="utf-8")


def update_public_status() -> None:
    document = json.loads(STATUS.read_text(encoding="utf-8"))
    phase = document["phase"]
    phase["next_implementation"] = 58
    document["model_runtime"]["message"] = (
        "Phase 6 is in progress through IMP-057. Offline session import, explicit text-only "
        "loopback Ollama capture, and the deterministic end-to-end local-portability harness "
        "are implemented. PORT-001, PORT-003, and bounded PORT-013 are ci-pass; the exact-commit "
        "primary Intel Mac evidence remains pending in Issue #178. PORT-015 and the Phase 6 gate "
        "are not complete."
    )
    document["last_reviewed"] = "2026-06-29"
    STATUS.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    update_roadmap()
    update_public_status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
