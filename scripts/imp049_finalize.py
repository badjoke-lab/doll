from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace(text: str, old: str, new: str) -> str:
    if old not in text:
        raise RuntimeError(f"missing text: {old[:60]}")
    return text.replace(old, new, 1)


def update_roadmap() -> None:
    path = ROOT / "docs/spec/09-development-roadmap.md"
    text = path.read_text(encoding="utf-8")
    text = replace(text, "- IMP-030 through IMP-048;", "- IMP-030 through IMP-049;")
    text = replace(
        text,
        "and a runtime-independent local adapter contract, verified backup",
        "a runtime-independent local adapter contract, and a loopback-only Ollama adapter, verified backup",
    )
    text = replace(text, "Status: in progress through IMP-048.", "Status: in progress through IMP-049.")
    text = replace(
        text,
        "- IMP-048 connects no real runtime or model and introduces no authoritative state or migration;\n- the first real local runtime adapter receives IMP-049 when opened;",
        "- IMP-049 implements the first concrete Ollama adapter through fixed IPv4 loopback health, inventory, generation, and bounded streaming paths;\n- IMP-049 is fail-closed until local-only operation is confirmed, excludes cloud-marked models, and introduces no authoritative state or migration;\n- IMP-049 has fake-transport CI evidence but no accepted real-runtime evidence;\n- the model-manifest and explicit-binding foundation receives IMP-050 when opened;",
    )

    lines = text.splitlines()
    heading = lines.index("### First local runtime adapter")
    next_heading = lines.index("### Model manifests and bindings")
    lines[heading:next_heading] = [
        "### IMP-049 — First local Ollama runtime adapter",
        "",
        "Status: complete in code; real-machine evidence is deferred to the integrated drill.",
        "",
        "Implemented loopback-only health, inventory, generation, bounded NDJSON streaming, timeout, cancellation, opaque model identifiers, explicit local-only confirmation, cloud-model exclusion, and closed failure mapping. Tests use an injected fake transport. No runtime or model is persistently bound and no authoritative state is added.",
        "",
    ]

    immediate = lines.index("The required order after IMP-048 is:")
    change_control = lines.index("## 19. Roadmap change control")
    lines[immediate:change_control] = [
        "The required order after IMP-049 is:",
        "",
        "1. schedule the model-manifest and explicit-binding foundation as IMP-050;",
        "2. add model and runtime manifests, provenance, exact revisions, checksums, compatibility, quarantine, candidate, active, previous, fallback, and rollback state;",
        "3. implement canonical local conversation through the IMP-048 contract and Phase 3 safety boundary;",
        "4. implement explicit model switching and local fallback, then prove rollback without unrelated state rewrite;",
        "5. run the network-disabled real-runtime drill before making a local-inference release claim;",
        "6. prove a real local AI migration path before provider-specific cloud portability becomes a primary claim.",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_checker() -> None:
    path = ROOT / "scripts/check-public-site-status.mjs"
    text = path.read_text(encoding="utf-8")
    text = replace(text, "status.phase?.next_implementation === 49", "status.phase?.next_implementation === 50")
    text = replace(
        text,
        '"project-status.json must mark Phase 5 in progress from IMP-048 with IMP-049 next"',
        '"project-status.json must mark Phase 5 in progress from IMP-048 with IMP-050 next"',
    )
    text = replace(
        text,
        '''expect(
  roadmap.includes("the first real local runtime adapter receives IMP-049 when opened"),
  "roadmap must identify IMP-049 as the next implementation identifier",
);''',
        '''expect(
  roadmap.includes("IMP-049 implements the first concrete Ollama adapter"),
  "roadmap must record the IMP-049 Ollama adapter",
);
expect(
  roadmap.includes("the model-manifest and explicit-binding foundation receives IMP-050 when opened"),
  "roadmap must identify IMP-050 as the next implementation identifier",
);''',
    )
    path.write_text(text, encoding="utf-8")


update_roadmap()
update_checker()
