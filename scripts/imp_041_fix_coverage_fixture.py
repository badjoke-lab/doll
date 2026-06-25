from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COVERAGE = ROOT / "tests/test_work_item_coverage.py"
VALIDATION = ROOT / "tests/test_work_item_validation_coverage.py"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"coverage fixture anchor changed: {old[:80]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    replace_once(
        COVERAGE,
        '''        secret_source = repository.create_record(
            record_type="other_source",
            sensitivity="secret",
            metadata={},
        )
''',
        '''        inactive_source = repository.create_record(
            record_type="other_source",
            metadata={},
        )
        repository.update_record(
            inactive_source.id,
            expected_revision=inactive_source.revision,
            status="archived",
        )
''',
    )
    replace_once(
        COVERAGE,
        "        for invalid_source in (str(uuid4()), secret_source.id):\n",
        "        for invalid_source in (str(uuid4()), inactive_source.id):\n",
    )
    replace_once(
        COVERAGE,
        "        for actor in (\"model\", \"runtime\", \"capability\", \"system\"):\n",
        "        actors: tuple[WorkItemActor, ...] = (\n"
        "            \"model\",\n"
        "            \"runtime\",\n"
        "            \"capability\",\n"
        "            \"system\",\n"
        "        )\n"
        "        for actor in actors:\n",
    )
    replace_once(
        COVERAGE,
        "                    actor_type=cast(WorkItemActor, actor),\n",
        "                    actor_type=actor,\n",
    )
    replace_once(
        COVERAGE,
        '            replace(record, status=cast(RecordStatus, "deleted")),\n',
        '            replace(record, status="deleted"),\n',
    )
    replace_once(
        COVERAGE,
        '            replace(record, provenance=cast(RecordProvenance, "model-proposed")),\n',
        '            replace(record, provenance="model-proposed"),\n',
    )
    replace_once(
        COVERAGE,
        "from doll.state import RecordProvenance, RecordStatus\n",
        "",
    )
    replace_once(
        COVERAGE,
        "            metadata = dict(record.metadata)\n            metadata[key] = value\n",
        "            metadata: dict[str, object] = dict(record.metadata)\n"
        "            metadata[key] = value\n",
    )

    replace_once(
        VALIDATION,
        "from pathlib import Path\n",
        "from collections.abc import Callable\nfrom pathlib import Path\n",
    )
    replace_once(
        VALIDATION,
        "    invalid_calls = (\n",
        "    invalid_calls: tuple[Callable[[], None], ...] = (\n",
    )


if __name__ == "__main__":
    main()
