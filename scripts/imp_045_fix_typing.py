from pathlib import Path

path = Path(__file__).resolve().parents[1] / "src/doll/resume_bundle.py"
text = path.read_text(encoding="utf-8")
replacements = (
    (
        "from dataclasses import asdict, dataclass\n",
        "from collections.abc import Iterable\nfrom dataclasses import asdict, dataclass\n",
    ),
    (
        "from doll.project_status import ProjectStatusInfo, ProjectStatusService\n",
        "from doll.project_status import (\n    ProjectStatusInfo,\n    ProjectStatusService,\n    StatusWorkItem,\n)\n",
    ),
    (
        "        for item in (*active, *ready, *blocked):\n            artifact_ids.update(item.artifact_ids)\n            source_ids.update(item.source_ids)\n        for item in decision_records:\n            artifact_ids.update(item.artifact_ids)\n            source_ids.update(item.memory_ids)\n        for item in procedure_records:\n            source_ids.update(item.source_ids)\n",
        "        for work_item in (*active, *ready, *blocked):\n            artifact_ids.update(work_item.artifact_ids)\n            source_ids.update(work_item.source_ids)\n        for decision in decision_records:\n            artifact_ids.update(decision.artifact_ids)\n            source_ids.update(decision.memory_ids)\n        for procedure in procedure_records:\n            source_ids.update(procedure.source_ids)\n",
    ),
    (
        "def _handoff_work(items: tuple[object, ...]) -> list[str]:\n    if not items:\n        return [\"- none\"]\n    return [\n        f\"- {cast(object, item).__getattribute__('title')}\"\n        for item in items\n    ]\n",
        "def _handoff_work(items: tuple[StatusWorkItem, ...]) -> list[str]:\n    if not items:\n        return [\"- none\"]\n    return [f\"- {item.title}\" for item in items]\n",
    ),
    (
        "def _jsonl_bytes(values: object) -> bytes:\n    return b\"\".join(_json_bytes(value) for value in cast(object, values))\n",
        "def _jsonl_bytes(values: Iterable[object]) -> bytes:\n    return b\"\".join(_json_bytes(value) for value in values)\n",
    ),
)
for old, new in replacements:
    if old not in text:
        raise RuntimeError(f"Resume Bundle typing anchor missing: {old[:80]}")
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
