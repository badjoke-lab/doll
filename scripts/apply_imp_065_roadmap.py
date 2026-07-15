from __future__ import annotations

from pathlib import Path

path = Path("docs/spec/09-development-roadmap.md")
text = path.read_text(encoding="utf-8")

replacements = (
    ("- IMP-030 through IMP-064;", "- IMP-030 through IMP-065;"),
    (
        "and the bounded local writing workflow through IMP-063, and the accepted exact-commit primary Intel Mac local-writing evidence through IMP-064.",
        "and the bounded local writing workflow through IMP-063, the accepted exact-commit primary Intel Mac local-writing evidence through IMP-064, and explicit data-only confirmed-memory and ProjectRecord context selection through IMP-065.",
    ),
    (
        "- Phase 6 local AI portability and daily-use integration is in progress through IMP-064;",
        "- Phase 6 local AI portability and daily-use integration is in progress through IMP-065;",
    ),
    (
        "- the next bounded implementation receives IMP-065 only when a new implementation issue is opened;",
        "- IMP-065 adds explicit ordered confirmed-memory and ProjectRecord selection for local writing, deterministic snapshots, data-only retriever/retrieval origins, secret-record rejection, bounded selection limits, sensitivity preservation, and unchanged authoritative revisions;\n- IMP-065 is assigned to Issue #210;\n- the IMP-065 explicit-context extension passes at the `ci` evidence level and does not broaden the accepted IMP-064 real-machine result;\n- the next bounded implementation receives IMP-066 only when a new implementation issue is opened;",
    ),
    (
        "Subsequent daily-use work may expand translation, planning, explicit memory review, explicit project and decision context selection, work-item proposals, portability review, accessibility, error clarity, Lite performance, and soak testing.",
        "Subsequent daily-use work may expand translation, planning, explicit decision and Resume Bundle context selection, work-item proposals, portability review, accessibility, error clarity, Lite performance, and soak testing.",
    ),
    (
        "After accepted IMP-064 local-writing real-machine evidence, the immediate order is:",
        "After IMP-065 explicit memory and project context selection, the immediate order is:",
    ),
    (
        "3. retain the IMP-063 task-versus-material separation as the required boundary for later explicit memory, project, decision, and Resume Bundle context selection;\n4. retain the accepted IMP-063/IMP-064 local-writing result only within its documented draft/revise/summarize boundary and keep personal writing quality, translation, retrieval, attachments, tools, and cloud claims excluded;\n5. allocate IMP-065 only when a new bounded implementation issue is opened; translation, automatic retrieval, attachments, target-specific export, cloud credentials, tools, and automatic cloud fallback remain separate work;",
        "3. retain the IMP-063 task-versus-material separation and the IMP-065 explicit-selection boundary for all later decision, Resume Bundle, document, and retrieval context;\n4. retain the accepted IMP-063/IMP-064 local-writing result only within its documented real-machine draft/revise/summarize boundary, and treat IMP-065 as a separate CI-only context-selection extension;\n5. allocate IMP-066 only when a new bounded implementation issue is opened; translation, automatic retrieval, decision and Resume Bundle context, attachments, target-specific export, cloud credentials, tools, and automatic cloud fallback remain separate work;",
    ),
)

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"ERROR: expected one roadmap match, found {count}: {old!r}")
    text = text.replace(old, new)

anchor = """IMP-064 does not establish personal writing quality, automatic or semantic retrieval, memory or project context selection, translation, attachments, multimodal input, streaming workflow output, tools, cloud portability or fallback, target-specific export, complete Phase 6, or stable general anti-lock-in.\n\n"""
section = """### IMP-065 — Explicit memory and project context selection\n\nStatus: implemented with deterministic synthetic CI evidence.\n\nImplemented explicit ordered selection of active confirmed-memory and ProjectRecord records for the accepted local `draft`, `revise`, and `summarize` workflow. Selection remains caller-controlled; no search, ranking, embedding, semantic retrieval, model-selected retrieval, background lookup, or automatic expansion is introduced.\n\nAll selected records are resolved and validated before any context origin or runtime request. Missing, wrong-type, archived, duplicate, secret-classified, oversized, or over-limit selections fail closed. Confirmed-memory and project snapshots are deterministic, bounded, revision-pinned representations that exclude automatic linked-record expansion.\n\nEach selected snapshot becomes immutable `external_content` through the `retriever` / `retrieval` origin combination, remains `untrusted_data` and data-only, and reaches the runtime only through `untrusted_content`. The current user request remains the only task authority. Embedded instructions remain non-authoritative and visible to advisory prompt-injection detection.\n\nThe canonical turn sensitivity is never lower than the highest selected record sensitivity. Secret records are rejected rather than inserted into prompts. Runtime failure preserves confirmed-memory and ProjectRecord revisions and uses the unchanged canonical user/context/error graph. Existing no-selection callers remain compatible.\n\nThe content-free result records only selected origin IDs, authoritative record IDs and revisions, counts, aggregate character count, canonical event and manifest IDs, outcome, failure code, and defense counts. It excludes selected record content, generated text, native model names, paths, usernames, hostnames, credentials, and secret values.\n\nDedicated synthetic acceptance covers explicit memory and ProjectRecord v2 selection, deterministic snapshots, data-only placement, authority denial, hostile embedded instructions, invalid-selection rejection before runtime, authoritative revision preservation on runtime failure, and result privacy. Standard CI covers Ubuntu, macOS, and Windows.\n\nIMP-065 does not establish automatic or semantic retrieval, embeddings, vector search, ranking, model-selected context, decision or Resume Bundle context, translation, attachments, multimodal input, streaming workflow output, tools, capability execution, cloud portability or fallback, target-specific export, complete Phase 6, or stable general anti-lock-in.\n\n"""

if text.count(anchor) != 1:
    raise SystemExit("ERROR: IMP-064 roadmap anchor missing")
text = text.replace(anchor, anchor + section)
path.write_text(text, encoding="utf-8")
print("IMP-065 roadmap update applied")
