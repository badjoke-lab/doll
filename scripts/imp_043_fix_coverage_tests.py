from __future__ import annotations

from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "tests/test_checkpoint_coverage.py"


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"coverage fixture anchor mismatch: {old[:100]!r}")
    return text.replace(old, new, 1)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    archive_block = '''        second_record = repository.get_record(second_project)
        repository.update_record(
            second_project,
            expected_revision=second_record.revision,
            status="archived",
        )
        with pytest.raises(CheckpointValidationError):
            _validate_project_link(repository, second_project)

'''
    text = replace_once(text, archive_block, "")
    cross_block = '''        cross = work.transition(
            cross.work_item_id,
            expected_revision=cross.revision,
            to_status="in_progress",
        )
'''
    text = replace_once(text, cross_block, cross_block + archive_block)
    runtime_anchor = '    initialized = _workspace(tmp_path / "runtime")\n'
    if text.count(runtime_anchor) != 2:
        raise RuntimeError("runtime fixture anchors changed")
    text = text.replace(
        runtime_anchor,
        '    monkeypatch.undo()\n    initialized = _workspace(tmp_path / "runtime")\n',
    )
    PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
