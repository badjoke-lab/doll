from __future__ import annotations

import hashlib
import stat
import zipfile
from pathlib import Path

import pytest

from doll import state, workspace
from doll.artifact import WorkspaceFileService
from doll.audit import AuditService
from doll.memory import ConfirmedMemoryService
from doll.project_state import DecisionService, ProjectService
from doll.settings import PermissionService, PolicyService, PreferenceService
from doll.state_package import (
    PACKAGE_ROOT,
    StatePackageConflictError,
    StatePackageExportError,
    StatePackageIntegrityError,
    StatePackageUnsafePathError,
    StatePackageValidationError,
    export_state_package,
    import_state_package,
    inspect_state_package,
    plan_state_package_import,
    verify_state_package,
)


def initialized_workspace(
    tmp_path: Path, name: str = "workspace"
) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / name)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def populated_workspace(tmp_path: Path) -> tuple[workspace.InitializedWorkspace, dict[str, str]]:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        preference = PreferenceService(repository).create(
            key="output.language",
            value={"language": "日本語"},
            description="表示言語",
            operation_id="package-preference",
        )
        PolicyService(repository).create(
            key="network.local-only",
            rule="クラウドへ接続しない",
            enabled=True,
            operation_id="package-policy",
        )
        PermissionService(repository).create(
            capability_id="artifact.create",
            scope={"kind": "project", "project_id": "synthetic"},
            mode="ask",
            operation_id="package-permission",
        )
        memory = ConfirmedMemoryService(repository).create(
            subject="継続方針",
            content="ローカル優先で状態を保持する。",
            operation_id="package-memory",
        )
        secret = PreferenceService(repository).create(
            key="private.synthetic",
            value="omitted",
            sensitivity="secret",
            operation_id="package-secret",
        )
        artifact = WorkspaceFileService(repository).create_text(
            managed_path="package/報告.txt",
            text="portable artifact\n",
            title="移送用報告",
            operation_id="package-artifact",
        )
        project = ProjectService(repository).create(
            name="移送プロジェクト",
            description="Doll State Packageを検証する。",
            project_status="active",
            started_at="2026-06-15T00:00:00Z",
            memory_ids=(memory.record_id,),
            artifact_ids=(artifact.artifact_id,),
            operation_id="package-project",
        )
        decision = DecisionService(repository).create(
            decision="versioned packageを使う",
            reason="検証可能な状態移送が必要だから。",
            decision_status="accepted",
            decided_at="2026-06-15T01:00:00Z",
            project_id=project.project_id,
            memory_ids=(memory.record_id,),
            artifact_ids=(artifact.artifact_id,),
            operation_id="package-decision",
        )
        project = ProjectService(repository).update(
            project.project_id,
            expected_revision=1,
            name=project.name,
            description=project.description,
            project_status=project.project_status,
            started_at=project.started_at,
            decision_ids=(decision.decision_id,),
            memory_ids=project.memory_ids,
            artifact_ids=project.artifact_ids,
            operation_id="package-project-link",
        )
    return initialized, {
        "preference": preference.record_id,
        "secret": secret.record_id,
        "memory": memory.record_id,
        "artifact": artifact.artifact_id,
        "project": project.project_id,
        "decision": decision.decision_id,
    }


def test_export_verify_inspect_and_import_round_trip(tmp_path: Path) -> None:
    initialized, ids = populated_workspace(tmp_path)
    package = tmp_path / "state.doll.zip"

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        revision_before = repository.status().state_revision
        audit_before = len(AuditService(repository).list(limit=200))
        inspection = export_state_package(
            repository,
            package,
            exported_at="2026-06-15T02:00:00Z",
        )
        assert repository.status().state_revision == revision_before
        assert len(AuditService(repository).list(limit=200)) == audit_before

    assert inspection.workspace_id == str(initialized.record.workspace_id)
    assert inspection.record_counts["preference"] == 1
    assert inspection.omitted_secret_counts["preference"] == 1
    assert inspection.authoritative_file_count == 1
    assert verify_state_package(package) == inspection
    assert inspect_state_package(package) == inspection

    target = tmp_path / "imported"
    result = import_state_package(package, target)
    assert result.workspace_id == inspection.workspace_id
    assert result.imported_state_revision == inspection.state_revision + 1

    imported_workspace = workspace.load_workspace(target)
    assert imported_workspace.record.workspace_id == initialized.record.workspace_id
    with state.open_state_repository(target, read_only=True) as repository:
        assert PreferenceService(repository).get(ids["preference"]).value == {"language": "日本語"}
        assert ConfirmedMemoryService(repository).get(ids["memory"]).subject == "継続方針"
        assert ProjectService(repository).get(ids["project"]).decision_ids == (ids["decision"],)
        assert DecisionService(repository).get(ids["decision"]).project_id == ids["project"]
        verification = WorkspaceFileService(repository).verify(ids["artifact"])
        assert verification.actual_hash == (
            "sha256:" + hashlib.sha256(b"portable artifact\n").hexdigest()
        )
        assert repository.status().state_revision == inspection.state_revision + 1
        assert len(AuditService(repository).list(limit=200)) == audit_before + 1
        with pytest.raises(KeyError):
            PreferenceService(repository).get(ids["secret"])

    archive_bytes = package.read_bytes()
    assert str(initialized.root).encode() not in archive_bytes
    assert str(target).encode() not in archive_bytes


def _rewrite_zip(
    source: Path,
    target: Path,
    *,
    remove: str | None = None,
    add: tuple[str, bytes] | None = None,
    mutate: str | None = None,
) -> None:
    with (
        zipfile.ZipFile(source, "r") as current,
        zipfile.ZipFile(
            target,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as rewritten,
    ):
        for info in current.infolist():
            if info.filename == remove:
                continue
            content = current.read(info)
            if info.filename == mutate:
                content = content + b"x"
            rewritten.writestr(info, content)
        if add is not None:
            rewritten.writestr(add[0], add[1])


@pytest.mark.parametrize("mode", ["mutate", "remove", "extra"])
def test_verify_rejects_inventory_and_content_tampering(
    tmp_path: Path,
    mode: str,
) -> None:
    initialized, _ = populated_workspace(tmp_path)
    package = tmp_path / "source.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        export_state_package(
            repository,
            package,
            exported_at="2026-06-15T02:00:00Z",
        )
    target = tmp_path / f"{mode}.zip"
    member = f"{PACKAGE_ROOT}/records/memories.jsonl"
    if mode == "mutate":
        _rewrite_zip(package, target, mutate=member)
    elif mode == "remove":
        _rewrite_zip(package, target, remove=member)
    else:
        _rewrite_zip(
            package,
            target,
            add=(f"{PACKAGE_ROOT}/records/extra.jsonl", b"{}\n"),
        )
    with pytest.raises(StatePackageIntegrityError):
        verify_state_package(target)


@pytest.mark.parametrize(
    "unsafe_name",
    [
        "../escape",
        "/absolute",
        "C:/drive",
        r"\\server\share",
        f"{PACKAGE_ROOT}/../escape",
    ],
)
def test_verify_rejects_unsafe_member_names(
    tmp_path: Path,
    unsafe_name: str,
) -> None:
    package = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr(unsafe_name, b"x")
    with pytest.raises(StatePackageUnsafePathError):
        verify_state_package(package)


def test_verify_rejects_symlink_entry(tmp_path: Path) -> None:
    package = tmp_path / "symlink.zip"
    info = zipfile.ZipInfo(f"{PACKAGE_ROOT}/manifest.json")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr(info, b"x")
    with pytest.raises(StatePackageUnsafePathError):
        verify_state_package(package)


def test_import_conflicts_leave_target_unchanged(tmp_path: Path) -> None:
    initialized, _ = populated_workspace(tmp_path)
    package = tmp_path / "source.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        export_state_package(
            repository,
            package,
            exported_at="2026-06-15T02:00:00Z",
        )

    target = initialized_workspace(tmp_path, "target")
    marker = target.root / "marker.txt"
    marker.write_text("unchanged", encoding="utf-8")
    plan = plan_state_package_import(package, target.root)
    assert plan.conflicts
    with pytest.raises(StatePackageConflictError):
        import_state_package(package, target.root)
    assert marker.read_text(encoding="utf-8") == "unchanged"


def test_export_rejects_unsupported_record_and_existing_output(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    output = tmp_path / "state.zip"
    with state.open_state_repository(initialized.root) as repository:
        repository.create_record(record_type="unsupported")
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(StatePackageValidationError):
            export_state_package(repository, output)

    output.write_bytes(b"existing")
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(StatePackageExportError):
            export_state_package(repository, output)
    assert output.read_bytes() == b"existing"


def test_import_supports_preexisting_empty_target(tmp_path: Path) -> None:
    initialized, _ = populated_workspace(tmp_path)
    package = tmp_path / "source.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        export_state_package(
            repository,
            package,
            exported_at="2026-06-15T02:00:00Z",
        )
    target = tmp_path / "empty"
    target.mkdir()
    result = import_state_package(package, target)
    assert result.workspace_id == str(initialized.record.workspace_id)
    assert workspace.load_workspace(target).record.workspace_id == initialized.record.workspace_id
