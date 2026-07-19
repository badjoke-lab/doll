from pathlib import Path

path = Path("src/doll/local_writing.py")
text = path.read_text(encoding="utf-8")

replacements = (
    (
        "from dataclasses import dataclass\nfrom typing import Literal, cast\n",
        "from dataclasses import dataclass\nfrom pathlib import Path\nfrom typing import Literal, cast\n",
    ),
    (
        "from doll.model_manifest import ModelManifestService, ModelManifestValidationError\nfrom doll.state import RecordSensitivity, StateError\n",
        "from doll.model_manifest import ModelManifestService, ModelManifestValidationError\nfrom doll.resume_bundle_context import (\n    ResumeBundleWritingContextResult,\n    ResumeBundleWritingContextService,\n    ResumeBundleWritingContextValidationError,\n)\nfrom doll.state import RecordSensitivity, StateError\n",
    ),
    (
        "from doll.writing_context import (\n    SelectedWritingContextResult,\n",
        "from doll.writing_context import (\n    MAX_SELECTED_CONTEXT_CHARS,\n    MAX_SELECTED_CONTEXT_ITEMS,\n    SelectedWritingContextResult,\n",
    ),
    (
        "    selected_decision_revisions: tuple[int, ...]\n    selected_context_character_count: int\n",
        "    selected_decision_revisions: tuple[int, ...]\n    selected_resume_bundle_project_id: str | None\n    selected_resume_bundle_state_revision: int | None\n    selected_resume_bundle_sha256: str | None\n    selected_resume_bundle_member_group_count: int\n    selected_resume_bundle_character_count: int\n    selected_context_character_count: int\n",
    ),
    (
        "        decision_ids: Sequence[str] = (),\n        parent_event_id: str | None = None,\n",
        "        decision_ids: Sequence[str] = (),\n        resume_bundle_path: Path | None = None,\n        parent_event_id: str | None = None,\n",
    ),
)

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one replacement target, found {count}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("IMP-067 local-writing part 1 applied")
