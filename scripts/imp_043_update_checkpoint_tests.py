from __future__ import annotations

from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "tests/test_checkpoint.py"


def rep(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"checkpoint test anchor mismatch: {old[:80]!r}")
    return text.replace(old, new)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    text = rep(
        text,
        "from pathlib import Path\n",
        "from dataclasses import replace\nfrom pathlib import Path\n",
    )
    text = rep(
        text,
        '''    CheckpointCorruptError,
    CheckpointValidationError,
    ProjectCheckpointService,
''',
        '''    CheckpointCorruptError,
    CheckpointValidationError,
    ProjectCheckpointInfo,
    ProjectCheckpointService,
''',
    )
    text = rep(
        text,
        '''    basis_record_ids: tuple[str, ...] = (),
):
''',
        '''    basis_record_ids: tuple[str, ...] = (),
) -> ProjectCheckpointInfo:
''',
    )
    text = rep(
        text,
        "        corrupt = replace_record_metadata(record, metadata)\n",
        "        corrupt = replace(record, metadata=metadata)\n",
    )
    helper = '''

def replace_record_metadata(record: state.RecordEnvelope, metadata: dict[str, object]):
    return state.RecordEnvelope(
        id=record.id,
        record_type=record.record_type,
        schema_version=record.schema_version,
        created_at=record.created_at,
        updated_at=record.updated_at,
        revision=record.revision,
        status=record.status,
        provenance=record.provenance,
        sensitivity=record.sensitivity,
        title=record.title,
        metadata=metadata,
    )
'''
    text = rep(text, helper, "")
    function_start = text.index(
        "def test_tampered_fingerprint_fails_before_target_mutation"
    )
    function_end = text.find("\n\ndef ", function_start + 1)
    if function_end == -1:
        function_end = len(text)
    function = text[function_start:function_end]
    if "        confirmed = service.confirm(\n" not in function:
        raise RuntimeError("tampered fingerprint confirmation anchor changed")
    function = function.replace(
        "        confirmed = service.confirm(\n",
        "        service.confirm(\n",
        1,
    )
    text = text[:function_start] + function + text[function_end:]
    PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
