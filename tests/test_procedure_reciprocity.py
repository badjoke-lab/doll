from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import cast

import pytest

import doll.state_package as package
from doll import state, workspace
from doll.procedure import ProcedureInfo, ProcedureService, ProcedureValidationError
from doll.project_state import ProjectService
from doll.state_repository import StateRepository


def _project(repository: StateRepository) -> str:
    return (
        ProjectService(repository)
        .create_v2(
            name="Procedure reciprocity project",
            description="Procedure supersession reciprocity test.",
            objective="Keep predecessor and replacement relations reciprocal.",
            in_scope=("Procedure supersession",),
            out_of_scope=("Procedure execution",),
            success_criteria=("Conflicting replacements fail closed",),
            project_status="active",
            started_at="2026-06-25T00:00:00Z",
        )
        .project_id
    )


def _approved(
    service: ProcedureService,
    project_id: str,
    *,
    title: str,
    version: int,
    supersedes_id: str | None = None,
) -> ProcedureInfo:
    return service.create_approved(
        project_id=project_id,
        title=title,
        purpose="Synthetic supersession reciprocity procedure.",
        version=version,
        ordered_steps=("Apply one bounded step.",),
        validation_steps=("Validate the bounded result.",),
        rollback_steps=("Restore the previous accepted state.",),
        supersedes_id=supersedes_id,
        approved_at="2026-06-25T01:00:00Z",
    )


def _read_members(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path, "r") as archive:
        return {info.filename: archive.read(info) for info in archive.infolist()}


def _write_members(path: Path, members: dict[str, bytes]) -> None:
    updated = dict(members)
    checksum_name = f"{package.PACKAGE_ROOT}/checksums.json"
    updated.pop(checksum_name, None)
    updated[checksum_name] = package._json_bytes(
        {
            "algorithm": package.CHECKSUM_ALGORITHM,
            "entries": [
                {
                    "path": name,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size_bytes": len(content),
                }
                for name, content in sorted(updated.items())
            ],
        }
    )
    package._write_deterministic_zip(path, updated)


def test_superseded_predecessor_rejects_second_replacement(tmp_path: Path) -> None:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass

    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        service = ProcedureService(repository)
        original = _approved(
            service,
            project_id,
            title="Original",
            version=1,
        )
        replacement = _approved(
            service,
            project_id,
            title="Replacement",
            version=2,
            supersedes_id=original.procedure_id,
        )
        service.supersede(
            original.procedure_id,
            replacement_id=replacement.procedure_id,
            expected_revision=original.revision,
        )

        with pytest.raises(ProcedureValidationError):
            _approved(
                service,
                project_id,
                title="Conflicting replacement",
                version=3,
                supersedes_id=original.procedure_id,
            )


def test_package_rejects_nonreciprocal_replacement_before_mutation(
    tmp_path: Path,
) -> None:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass

    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        service = ProcedureService(repository)
        original = _approved(service, project_id, title="Original", version=1)
        other = _approved(service, project_id, title="Other", version=1)
        replacement = _approved(
            service,
            project_id,
            title="Replacement",
            version=2,
            supersedes_id=original.procedure_id,
        )
        service.supersede(
            original.procedure_id,
            replacement_id=replacement.procedure_id,
            expected_revision=original.revision,
        )

    source = tmp_path / "source.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        package.export_state_package(
            repository,
            source,
            exported_at="2026-06-25T05:00:00Z",
        )

    members = _read_members(source)
    member_name = f"{package.PACKAGE_ROOT}/records/procedures.jsonl"
    payloads = [
        cast(dict[str, object], json.loads(line))
        for line in members[member_name].decode("utf-8").splitlines()
    ]
    for payload in payloads:
        if payload["id"] == replacement.procedure_id:
            metadata = cast(dict[str, object], payload["metadata"])
            metadata["supersedes_id"] = other.procedure_id
    members[member_name] = b"".join(package._json_bytes(payload) for payload in payloads)
    hostile = tmp_path / "hostile.zip"
    _write_members(hostile, members)

    target = tmp_path / "target"
    target.mkdir()
    marker = target / "marker.txt"
    marker.write_text("unchanged", encoding="utf-8")
    with pytest.raises(package.StatePackageValidationError):
        package.import_state_package(hostile, target)
    assert marker.read_text(encoding="utf-8") == "unchanged"
