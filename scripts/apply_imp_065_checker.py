from __future__ import annotations

from pathlib import Path

context_path = Path("src/doll/writing_context.py")
context_text = context_path.read_text(encoding="utf-8")
old_import = "from typing import Literal, cast\n"
if context_text.count(old_import) != 1:
    raise SystemExit("ERROR: writing_context typing import anchor missing")
context_path.write_text(
    context_text.replace(old_import, "from typing import Literal\n"),
    encoding="utf-8",
)

path = Path("scripts/check-public-site-status.mjs")
text = path.read_text(encoding="utf-8")

replacements = (
    (
        "status.phase?.next_implementation === 65,\n  \"project-status.json must mark Phase 6 in progress through IMP-064 with IMP-065 next\"",
        "status.phase?.next_implementation === 66,\n  \"project-status.json must mark Phase 6 in progress through IMP-065 with IMP-066 next\"",
    ),
    (
        "status.model_runtime.message.includes(\"through IMP-064\") &&\n    status.model_runtime.message.includes(\"passes at both CI and real-machine evidence levels\"),\n  \"project-status.json must describe the accepted bounded IMP-064 machine evidence\"",
        "status.model_runtime.message.includes(\"through IMP-065\") &&\n    status.model_runtime.message.includes(\"IMP-065 adds explicit\") &&\n    status.model_runtime.message.includes(\"passes at both CI and real-machine evidence levels\"),\n  \"project-status.json must describe IMP-065 without broadening IMP-064 evidence\"",
    ),
    (
        "  \"IMP-063/IMP-064 writing workflow must bind accepted real-machine evidence\",\n);",
        "  \"IMP-063/IMP-064 writing workflow must bind accepted real-machine evidence\",\n);\n\nexpect(\n  dailyUse.explicit_context_extension?.implementation === \"IMP-065\" &&\n    dailyUse.explicit_context_extension?.status === \"ci-pass\" &&\n    JSON.stringify(dailyUse.explicit_context_extension?.passed_evidence_levels) ===\n      JSON.stringify([\"ci\"]) &&\n    JSON.stringify(dailyUse.explicit_context_extension?.required_evidence_levels) ===\n      JSON.stringify([\"ci\"]) &&\n    dailyUse.explicit_context_extension?.selection_mode === \"explicit-only\" &&\n    dailyUse.explicit_context_extension?.automatic_retrieval === false &&\n    dailyUse.explicit_context_extension?.semantic_retrieval === false &&\n    dailyUse.explicit_context_extension?.model_selected_context === false &&\n    dailyUse.explicit_context_extension?.secret_records_allowed === false &&\n    dailyUse.explicit_context_extension?.context_origin_class ===\n      \"external_content\" &&\n    dailyUse.explicit_context_extension?.context_actor_type === \"retriever\" &&\n    dailyUse.explicit_context_extension?.context_acquisition_method ===\n      \"retrieval\" &&\n    dailyUse.explicit_context_extension?.context_authority_class ===\n      \"untrusted_data\" &&\n    dailyUse.explicit_context_extension?.phase6_gate_complete === false &&\n    dailyUse.explicit_context_extension?.stable_anti_lock_in_claim === false &&\n    dailyUse.explicit_context_extension?.implementation_doc ===\n      \"docs/implementation/imp-065-explicit-writing-context.md\",\n  \"IMP-065 explicit writing context must remain bounded and CI-only\",\n);",
    ),
    (
        "roadmap.includes(\"### IMP-064 — Primary Intel Mac local-writing acceptance\"),\n  \"roadmap must record the IMP-064 local writing acceptance boundary\",\n);\nexpect(\n  roadmap.includes(\"the next bounded implementation receives IMP-065 only when a new implementation issue is opened\"),\n  \"roadmap must identify IMP-065 as the next unallocated implementation identifier\",",
        "roadmap.includes(\"### IMP-064 — Primary Intel Mac local-writing acceptance\"),\n  \"roadmap must record the IMP-064 local writing acceptance boundary\",\n);\nexpect(\n  roadmap.includes(\"### IMP-065 — Explicit memory and project context selection\"),\n  \"roadmap must record the IMP-065 explicit writing context boundary\",\n);\nexpect(\n  roadmap.includes(\"the next bounded implementation receives IMP-066 only when a new implementation issue is opened\"),\n  \"roadmap must identify IMP-066 as the next unallocated implementation identifier\",",
    ),
    (
        "\"After accepted IMP-064 local-writing real-machine evidence, the immediate order is:\"",
        "\"After IMP-065 explicit memory and project context selection, the immediate order is:\"",
    ),
    (
        "\"roadmap must record accepted IMP-064 evidence and remaining Phase 6 work\"",
        "\"roadmap must record IMP-065 and remaining Phase 6 work\"",
    ),
)

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"ERROR: expected one checker match, found {count}: {old!r}")
    text = text.replace(old, new)

path.write_text(text, encoding="utf-8")
print("IMP-065 checker update applied")
