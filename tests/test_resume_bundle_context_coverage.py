from __future__ import annotations

import hashlib
from pathlib import Path
from typing import cast

import pytest

from doll import resume_bundle_context as context
from doll import state, workspace
from doll.instruction_origin import InstructionOriginService, InstructionSource
from doll.resume_bundle import ResumeBundleInspection
from doll.writing_context import MAX_SELECTED_CONTEXT_CHARS


def _workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _identity(digest: str = "a") -> context._FileIdentity:
    return context._FileIdentity(
        size_bytes=1,
        modified_ns=1,
        device=1,
        inode=1,
        sha256=f"sha256:{digest * 64}",
    )


def _inspection() -> ResumeBundleInspection:
    return ResumeBundleInspection(
        bundle_format_version=1,
        project_id="project-coverage",
        workspace_id="workspace-coverage",
        state_revision=1,
        checkpoint_id=None,
        checkpoint_freshness=None,
        included_record_counts={},
        omitted_record_counts={},
        member_count=14,
        checksum_algorithm="sha256",
    )


def _stable_identity(path: Path) -> context._FileIdentity:
    return _identity()


def _valid_inspection(path: Path) -> ResumeBundleInspection:
    return _inspection()


def _small_snapshot(path: Path, inspection: ResumeBundleInspection) -> str:
    return "{}"


def _oversized_snapshot(path: Path, inspection: ResumeBundleInspection) -> str:
    return "x" * (MAX_SELECTED_CONTEXT_CHARS + 1)


def test_plan_rejects_invalid_path_type_and_oversized_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = _workspace(tmp_path)
    bundle = tmp_path / "oversized.resume.zip"
    bundle.write_bytes(b"x")

    with state.open_state_repository(initialized.root) as repository:
        service = context.ResumeBundleWritingContextService(repository)
        with pytest.raises(context.ResumeBundleWritingContextValidationError):
            service.plan(cast(Path, "not-a-path"))

        monkeypatch.setattr(context, "_MAX_BUNDLE_FILE_BYTES", 0)
        with pytest.raises(context.ResumeBundleWritingContextValidationError):
            service.plan(bundle)


def test_plan_rejects_unreadable_changed_and_oversized_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = _workspace(tmp_path)
    bundle = tmp_path / "synthetic.resume.zip"
    bundle.write_bytes(b"x")

    with state.open_state_repository(initialized.root) as repository:
        service = context.ResumeBundleWritingContextService(repository)

        monkeypatch.setattr(context, "_file_identity", _stable_identity)

        def unreadable(path: Path) -> ResumeBundleInspection:
            raise RuntimeError("synthetic unreadable bundle")

        monkeypatch.setattr(context, "verify_resume_bundle", unreadable)
        with pytest.raises(context.ResumeBundleWritingContextValidationError):
            service.plan(bundle)

        identities = iter((_identity("a"), _identity("b")))

        def changed_identity(path: Path) -> context._FileIdentity:
            return next(identities)

        monkeypatch.setattr(context, "_file_identity", changed_identity)
        monkeypatch.setattr(context, "verify_resume_bundle", _valid_inspection)
        monkeypatch.setattr(context, "_snapshot_content", _small_snapshot)
        with pytest.raises(context.ResumeBundleWritingContextValidationError):
            service.plan(bundle)

        monkeypatch.setattr(context, "_file_identity", _stable_identity)
        monkeypatch.setattr(context, "_snapshot_content", _oversized_snapshot)
        with pytest.raises(context.ResumeBundleWritingContextValidationError):
            service.plan(bundle)


def test_materialization_rejects_incomplete_and_duplicate_preparation(
    tmp_path: Path,
) -> None:
    initialized = _workspace(tmp_path)
    incomplete = context.ResumeBundleWritingContextPlan(
        content="{}",
        project_id=None,
        state_revision=1,
        bundle_sha256="sha256:" + ("a" * 64),
        member_group_count=9,
        character_count=2,
        required_sensitivity="sensitive",
    )
    complete = context.ResumeBundleWritingContextPlan(
        content="{}",
        project_id="project-coverage",
        state_revision=1,
        bundle_sha256="sha256:" + ("a" * 64),
        member_group_count=9,
        character_count=2,
        required_sensitivity="sensitive",
    )

    with state.open_state_repository(initialized.root) as repository:
        service = context.ResumeBundleWritingContextService(repository)
        with pytest.raises(context.ResumeBundleWritingContextValidationError):
            service.materialize(
                conversation_id="coverage-conversation",
                operation_id="imp067.coverage.incomplete",
                plan=incomplete,
            )
        with pytest.raises(context.ResumeBundleWritingContextValidationError):
            context._context_operation_id("imp067.coverage.incomplete", incomplete)

        operation_id = "imp067.coverage.duplicate"
        parent_operation_id = context._context_operation_id(operation_id, complete)
        content = "{}"
        InstructionOriginService(repository).create(
            title="Existing Resume Bundle context",
            content=content,
            source=InstructionSource(
                origin_class="external_content",
                actor_type="extractor",
                acquisition_method="extraction",
                source_identifier="resume_bundle:coverage",
                parent_operation_id=parent_operation_id,
                session_id="coverage-conversation",
                content_hash=f"sha256:{hashlib.sha256(content.encode()).hexdigest()}",
            ),
            operation_id=parent_operation_id,
            sensitivity="sensitive",
        )
        with pytest.raises(context.ResumeBundleWritingContextValidationError):
            service.require_unused(operation_id=operation_id, plan=complete)


def test_strict_snapshot_helpers_reject_malformed_content() -> None:
    with pytest.raises(context.ResumeBundleWritingContextValidationError):
        context._json_value(b'{"duplicate":1,"duplicate":2}', "duplicate object")
    with pytest.raises(context.ResumeBundleWritingContextValidationError):
        context._json_value(b"NaN", "unsupported constant")
    with pytest.raises(context.ResumeBundleWritingContextValidationError):
        context._json_object(b"[]", "object")

    assert context._optional_json_object(b"null", "optional object") is None
    with pytest.raises(context.ResumeBundleWritingContextValidationError):
        context._optional_json_object(b"[]", "optional object")

    with pytest.raises(context.ResumeBundleWritingContextValidationError):
        context._jsonl_objects(b"\xff", "invalid UTF-8 JSONL")
    with pytest.raises(context.ResumeBundleWritingContextValidationError):
        context._jsonl_objects(b"{}\n\n{}\n", "empty JSONL row")
    with pytest.raises(context.ResumeBundleWritingContextValidationError):
        context._jsonl_objects(b"[]\n", "non-object JSONL row")

    with pytest.raises(context.ResumeBundleWritingContextValidationError):
        context._json_array_of_objects(b"{}", "object array")
    with pytest.raises(context.ResumeBundleWritingContextValidationError):
        context._json_array_of_objects(b"[1]", "object array")
    with pytest.raises(context.ResumeBundleWritingContextValidationError):
        context._canonical_json({"unsupported": {1, 2}})
