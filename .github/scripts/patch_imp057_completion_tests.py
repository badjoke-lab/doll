from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "tests/test_ollama_adapter_static.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''    assert matrix["local_portability_gate_complete"] is False
    assert matrix["accepted_real_machine_result"] is None
''',
        '''    assert matrix["local_portability_gate_complete"] is True
    assert matrix["accepted_real_machine_result"] == (
        "docs/testing/results/IMP-057-primary-intel-mac-2026-06-29.json"
    )
''',
        "matrix completion",
    )
    text = replace_once(
        text,
        '''    assert {item["status"] for item in entries} == {"ci-pass"}
    assert {tuple(item["passed_evidence_levels"]) for item in entries} == {("ci",)}
''',
        '''    assert {item["status"] for item in entries} == {"pass"}
    assert {tuple(item["passed_evidence_levels"]) for item in entries} == {
        ("ci", "real-machine")
    }
''',
        "matrix evidence levels",
    )
    text = replace_once(
        text,
        '''    assert matrix["real_machine_gate"]["status"] == "pending"
    assert matrix["real_machine_gate"]["minimum_local_models"] == 1
''',
        '''    assert matrix["real_machine_gate"]["status"] == "pass"
    assert matrix["real_machine_gate"]["minimum_local_models"] == 1
    assert matrix["real_machine_gate"]["commit_sha"] == (
        "7b63ff512e20d1d6ae65da8938486b093e14b6c6"
    )
    assert matrix["real_machine_gate"]["completed_at"] == "2026-06-29T15:48:03.615410Z"
''',
        "matrix machine gate",
    )
    text = replace_once(
        text,
        '''    assert payload["primary_intel_mac_gate"] == "pending"
    assert payload["local_portability_gate_complete"] is False
''',
        '''    assert payload["primary_intel_mac_gate"] == "pass"
    assert payload["local_portability_gate_complete"] is True
''',
        "runner stored evidence",
    )
    PATH.write_text(text, encoding="utf-8", newline="\n")

    for relative in (
        ".github/scripts/patch_imp057_completion_tests.py",
        ".github/workflows/imp057-completion-pr-temporary.yml",
        ".github/workflows/imp057-completion-pr-v2-temporary.yml",
    ):
        candidate = ROOT / relative
        if candidate.exists():
            candidate.unlink()


if __name__ == "__main__":
    main()
