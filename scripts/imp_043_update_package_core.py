from __future__ import annotations

from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "src/doll/state_package.py"


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"package anchor mismatch: {old[:80]!r}")
    return text.replace(old, new)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from doll.instruction_origin import (\n",
        "from doll.checkpoint import (\n"
        "    CheckpointCorruptError,\n"
        "    ProjectCheckpointInfo,\n"
        "    _checkpoint_from_record,\n"
        ")\n"
        "from doll.instruction_origin import (\n",
    )
    text = replace_once(
        text,
        '    "procedure": _procedure_from_record,\n}',
        '    "procedure": _procedure_from_record,\n'
        '    "project_checkpoint": _checkpoint_from_record,\n'
        '}',
    )
    text = replace_once(
        text,
        '''        ArtifactCorruptError,
        BackupManifestCorruptError,
''',
        '''        ArtifactCorruptError,
        BackupManifestCorruptError,
        CheckpointCorruptError,
''',
    )
    text = replace_once(
        text,
        '''    _validate_work_item_package_graph(records)
    _validate_procedure_package_graph(records)
''',
        '''    _validate_work_item_package_graph(records)
    _validate_procedure_package_graph(records)
    _validate_checkpoint_package_graph(records)
''',
    )
    PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
