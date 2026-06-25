from __future__ import annotations

from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "tests/test_work_item_coverage.py"


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    old = '''        secret_source = repository.create_record(
            record_type="other_source",
            sensitivity="secret",
            metadata={},
        )
'''
    new = '''        inactive_source = repository.create_record(
            record_type="other_source",
            metadata={},
        )
        repository.update_record(
            inactive_source.id,
            expected_revision=inactive_source.revision,
            status="archived",
        )
'''
    if text.count(old) != 1:
        raise RuntimeError("secret source fixture anchor changed")
    text = text.replace(old, new)
    old_relation = "        for invalid_source in (str(uuid4()), secret_source.id):\n"
    new_relation = "        for invalid_source in (str(uuid4()), inactive_source.id):\n"
    if text.count(old_relation) != 1:
        raise RuntimeError("invalid source fixture anchor changed")
    PATH.write_text(text.replace(old_relation, new_relation), encoding="utf-8")


if __name__ == "__main__":
    main()
