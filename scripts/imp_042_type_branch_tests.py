from __future__ import annotations

from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "tests/test_procedure_branch_coverage.py"


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"branch-test anchor mismatch: {old[:80]!r}")
    return text.replace(old, new)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from pathlib import Path\nfrom uuid import uuid4\n",
        "from collections.abc import Callable\n"
        "from pathlib import Path\n"
        "from typing import TypedDict\n"
        "from uuid import uuid4\n",
    )
    text = replace_once(
        text,
        "    ProcedureService,\n",
        "    ProcedureService,\n    ProcedureStatus,\n",
    )
    text = replace_once(
        text,
        "\n\ndef _project(repository: StateRepository, name: str = \"Project\") -> str:\n",
        "\n\nclass LinkCase(TypedDict):\n"
        "    version: int\n"
        "    supersedes_id: str | None\n"
        "    superseded_by_id: str | None\n"
        "\n\ndef _project(repository: StateRepository, name: str = \"Project\") -> str:\n",
    )
    text = replace_once(
        text,
        '    procedure_status: str = "draft",\n',
        '    procedure_status: ProcedureStatus = "draft",\n',
    )
    text = replace_once(
        text,
        "        invalid_calls = (\n",
        "        invalid_calls: tuple[Callable[[], object], ...] = (\n",
    )
    text = replace_once(
        text,
        "        cases = (\n",
        "        cases: tuple[LinkCase, ...] = (\n",
    )
    PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
