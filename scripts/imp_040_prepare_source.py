from __future__ import annotations

from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "src/doll/project_state.py"
DATACLASS_MARKER = "    # IMP-040 temporary DecisionInfo dataclass marker\n"
RETURN_MARKER = "        # IMP-040 temporary DecisionInfo return marker\n"


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one match, found {count}: {old[:100]!r}")
    return text.replace(old, new)


def prepare() -> None:
    text = PATH.read_text(encoding="utf-8")
    decision_start = text.index("class DecisionInfo:")
    service_start = text.index("\n\n@dataclass(slots=True)\nclass ProjectService:")
    before = text[:decision_start]
    decision_block = text[decision_start:service_start]
    after = text[service_start:]
    decision_block = replace_once(
        decision_block,
        "    artifact_ids: tuple[str, ...]\n    revision: int\n",
        "    artifact_ids: tuple[str, ...]\n" + DATACLASS_MARKER + "    revision: int\n",
    )
    decision_return_start = after.index("    return DecisionInfo(")
    decision_return_end = after.index("\n\n\ndef _validate_envelope", decision_return_start)
    prefix = after[:decision_return_start]
    decision_return = after[decision_return_start:decision_return_end]
    suffix = after[decision_return_end:]
    decision_return = replace_once(
        decision_return,
        "        artifact_ids=artifact_ids,\n        revision=record.revision,\n",
        "        artifact_ids=artifact_ids,\n"
        + RETURN_MARKER
        + "        revision=record.revision,\n",
    )
    PATH.write_text(
        before + decision_block + prefix + decision_return + suffix,
        encoding="utf-8",
    )


def cleanup() -> None:
    text = PATH.read_text(encoding="utf-8")
    if text.count(DATACLASS_MARKER) != 1 or text.count(RETURN_MARKER) != 1:
        raise RuntimeError("IMP-040 source markers are missing")
    PATH.write_text(
        text.replace(DATACLASS_MARKER, "").replace(RETURN_MARKER, ""),
        encoding="utf-8",
    )


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["prepare"]:
        prepare()
    elif sys.argv[1:] == ["cleanup"]:
        cleanup()
    else:
        raise SystemExit("usage: imp_040_prepare_source.py prepare|cleanup")
