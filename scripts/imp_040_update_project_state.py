from __future__ import annotations

from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "src/doll/project_state.py"


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one match, found {count}: {old[:120]!r}")
    return text.replace(old, new)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from doll.memory import ConfirmedMemoryError, ConfirmedMemoryService\n",
        "from doll.memory import ConfirmedMemoryError, ConfirmedMemoryService\n"
        "from doll.settings import SettingsCorruptError, _policy_from_record\n",
    )
    text = replace_once(
        text,
        'ProjectStatus = Literal["planned", "active", "on_hold", "completed", "cancelled"]\n',
        'ProjectStatus = Literal["planned", "active", "on_hold", "completed", "cancelled"]\n'
        "PROJECT_SCHEMA_VERSION_V1 = 1\n"
        "PROJECT_SCHEMA_VERSION_V2 = 2\n"
        "SUPPORTED_PROJECT_SCHEMA_VERSIONS = frozenset(\n"
        "    {PROJECT_SCHEMA_VERSION_V1, PROJECT_SCHEMA_VERSION_V2}\n"
        ")\n",
    )
    text = replace_once(
        text,
        '''class ProjectInfo:
    project_id: str
    name: str
    description: str
    project_status: ProjectStatus
''',
        '''class ProjectInfo:
    project_id: str
    schema_version: int
    name: str
    description: str
    objective: str | None
    in_scope: tuple[str, ...]
    out_of_scope: tuple[str, ...]
    success_criteria: tuple[str, ...]
    project_status: ProjectStatus
''',
    )
    text = replace_once(
        text,
        '''    artifact_ids: tuple[str, ...]
    revision: int
''',
        '''    artifact_ids: tuple[str, ...]
    governing_policy_ids: tuple[str, ...]
    revision: int
''',
    )

    create_v2 = '''
    def create_v2(
        self,
        *,
        name: str,
        description: str,
        objective: str,
        in_scope: Sequence[str],
        out_of_scope: Sequence[str],
        success_criteria: Sequence[str],
        project_status: ProjectStatus,
        started_at: str,
        ended_at: str | None = None,
        decision_ids: Sequence[str] = (),
        memory_ids: Sequence[str] = (),
        artifact_ids: Sequence[str] = (),
        governing_policy_ids: Sequence[str] = (),
        sensitivity: RecordSensitivity = "personal",
        operation_id: str | None = None,
        actor_type: AuthorityActor = "user",
    ) -> ProjectInfo:
        """Create one explicit ProjectRecord v2 charter through the user path."""

        _require_user_actor(actor_type)
        metadata = _validated_project_v2_values(
            self.repository,
            name=name,
            description=description,
            objective=objective,
            in_scope=in_scope,
            out_of_scope=out_of_scope,
            success_criteria=success_criteria,
            project_status=project_status,
            started_at=started_at,
            ended_at=ended_at,
            decision_ids=decision_ids,
            memory_ids=memory_ids,
            artifact_ids=artifact_ids,
            governing_policy_ids=governing_policy_ids,
        )
        project_id = _create_record(
            self.repository,
            record_type="project",
            title=cast(str, metadata["name"]),
            metadata=metadata,
            provenance="user-created",
            sensitivity=sensitivity,
            operation_id=operation_id,
            action="project.create_v2",
            schema_version=PROJECT_SCHEMA_VERSION_V2,
        )
        return self.get(project_id)

'''
    text = replace_once(
        text,
        "        return self.get(project_id)\n\n    def update(\n",
        "        return self.get(project_id)\n\n" + create_v2 + "    def update(\n",
    )
    text = replace_once(
        text,
        '''        current = _project_from_record(current_record, self.repository)
        _require_active(current.lifecycle_status)
        metadata = _validated_project_values(
''',
        '''        current = _project_from_record(current_record, self.repository)
        _require_active(current.lifecycle_status)
        if current.schema_version != PROJECT_SCHEMA_VERSION_V1:
            raise ProjectDecisionValidationError(
                "ProjectRecord v2 requires the explicit update_v2 path"
            )
        metadata = _validated_project_values(
''',
    )
    update_v2 = '''
    def update_v2(
        self,
        project_id: str,
        *,
        expected_revision: int,
        name: str,
        description: str,
        objective: str,
        in_scope: Sequence[str],
        out_of_scope: Sequence[str],
        success_criteria: Sequence[str],
        project_status: ProjectStatus,
        started_at: str,
        ended_at: str | None = None,
        decision_ids: Sequence[str] = (),
        memory_ids: Sequence[str] = (),
        artifact_ids: Sequence[str] = (),
        governing_policy_ids: Sequence[str] = (),
        operation_id: str | None = None,
        actor_type: AuthorityActor = "user",
    ) -> ProjectInfo:
        """Write a ProjectRecord v2 charter, explicitly upgrading v1 when needed."""

        _require_user_actor(actor_type)
        current_record = _require_record(self.repository, project_id, "project")
        current = _project_from_record(current_record, self.repository)
        _require_active(current.lifecycle_status)
        metadata = _validated_project_v2_values(
            self.repository,
            name=name,
            description=description,
            objective=objective,
            in_scope=in_scope,
            out_of_scope=out_of_scope,
            success_criteria=success_criteria,
            project_status=project_status,
            started_at=started_at,
            ended_at=ended_at,
            decision_ids=decision_ids,
            memory_ids=memory_ids,
            artifact_ids=artifact_ids,
            governing_policy_ids=governing_policy_ids,
        )
        _update_record(
            self.repository,
            current_record=current_record,
            expected_revision=expected_revision,
            title=cast(str, metadata["name"]),
            metadata=metadata,
            lifecycle_status="active",
            provenance="user-created",
            operation_id=operation_id,
            action="project.update_v2",
            schema_version=PROJECT_SCHEMA_VERSION_V2,
        )
        return self.get(project_id)

'''
    text = replace_once(
        text,
        "        return self.get(project_id)\n\n    def archive(\n",
        "        return self.get(project_id)\n\n" + update_v2 + "    def archive(\n",
    )

    old_export = '''    def export_json(self, project_id: str) -> str:
        project = self.get(project_id)
        _require_exportable(project.sensitivity)
        return _deterministic_json(
            {
                "export_schema": "doll.project.v1",
                "record": {
                    "id": project.project_id,
                    "record_type": "project",
                    "schema_version": 1,
                    "created_at": project.created_at,
                    "updated_at": project.updated_at,
                    "revision": project.revision,
                    "status": project.lifecycle_status,
                    "provenance": project.provenance,
                    "sensitivity": project.sensitivity,
                    "title": project.name,
                    "project": {
                        "name": project.name,
                        "description": project.description,
                        "status": project.project_status,
                        "started_at": project.started_at,
                        "ended_at": project.ended_at,
                        "decision_ids": list(project.decision_ids),
                        "memory_ids": list(project.memory_ids),
                        "artifact_ids": list(project.artifact_ids),
                    },
                },
            }
        )
'''
    new_export = '''    def export_json(self, project_id: str) -> str:
        project = self.get(project_id)
        _require_exportable(project.sensitivity)
        project_payload: dict[str, object] = {
            "name": project.name,
            "description": project.description,
            "status": project.project_status,
            "started_at": project.started_at,
            "ended_at": project.ended_at,
            "decision_ids": list(project.decision_ids),
            "memory_ids": list(project.memory_ids),
            "artifact_ids": list(project.artifact_ids),
        }
        if project.schema_version == PROJECT_SCHEMA_VERSION_V2:
            project_payload.update(
                {
                    "objective": project.objective,
                    "in_scope": list(project.in_scope),
                    "out_of_scope": list(project.out_of_scope),
                    "success_criteria": list(project.success_criteria),
                    "governing_policy_ids": list(project.governing_policy_ids),
                }
            )
        return _deterministic_json(
            {
                "export_schema": f"doll.project.v{project.schema_version}",
                "record": {
                    "id": project.project_id,
                    "record_type": "project",
                    "schema_version": project.schema_version,
                    "created_at": project.created_at,
                    "updated_at": project.updated_at,
                    "revision": project.revision,
                    "status": project.lifecycle_status,
                    "provenance": project.provenance,
                    "sensitivity": project.sensitivity,
                    "title": project.name,
                    "project": project_payload,
                },
            }
        )
'''
    text = replace_once(text, old_export, new_export)

    insert_v2_validator = '''

def _validated_project_v2_values(
    repository: StateRepository,
    *,
    name: str,
    description: str,
    objective: str,
    in_scope: Sequence[str],
    out_of_scope: Sequence[str],
    success_criteria: Sequence[str],
    project_status: ProjectStatus,
    started_at: str,
    ended_at: str | None,
    decision_ids: Sequence[str],
    memory_ids: Sequence[str],
    artifact_ids: Sequence[str],
    governing_policy_ids: Sequence[str],
) -> dict[str, object]:
    metadata = _validated_project_values(
        repository,
        name=name,
        description=description,
        project_status=project_status,
        started_at=started_at,
        ended_at=ended_at,
        decision_ids=decision_ids,
        memory_ids=memory_ids,
        artifact_ids=artifact_ids,
    )
    safe_objective = _validate_text(
        "project objective",
        objective,
        MAX_DESCRIPTION_LENGTH,
    )
    safe_in_scope = _validate_text_items("project in-scope work", in_scope)
    safe_out_of_scope = _validate_text_items("project out-of-scope work", out_of_scope)
    safe_success_criteria = _validate_text_items(
        "project success criteria",
        success_criteria,
    )
    safe_policies = _validate_reference_ids(
        "project governing policy IDs",
        governing_policy_ids,
    )
    _validate_typed_links(repository, policy_ids=safe_policies)
    metadata.update(
        {
            "objective": safe_objective,
            "in_scope": list(safe_in_scope),
            "out_of_scope": list(safe_out_of_scope),
            "success_criteria": list(safe_success_criteria),
            "governing_policy_ids": list(safe_policies),
        }
    )
    return metadata
'''
    text = replace_once(
        text,
        "\n\ndef _validated_decision_values(\n",
        insert_v2_validator + "\n\ndef _validated_decision_values(\n",
    )

    text = replace_once(
        text,
        '''    action: str,
) -> str:
''',
        '''    action: str,
    schema_version: int = 1,
) -> str:
''',
    )
    text = replace_once(
        text,
        '''        record_type=record_type,
        schema_version=1,
''',
        '''        record_type=record_type,
        schema_version=schema_version,
''',
    )
    text = replace_once(
        text,
        '''            ) VALUES (?, ?, 1, ?, ?, 1, 'active', ?, ?, ?, ?)
            """,
            (
                record_id,
                record_type,
                now,
''',
        '''            ) VALUES (?, ?, ?, ?, ?, 1, 'active', ?, ?, ?, ?)
            """,
            (
                record_id,
                record_type,
                schema_version,
                now,
''',
    )
    text = replace_once(
        text,
        '''    action: str,
) -> None:
''',
        '''    action: str,
    schema_version: int | None = None,
) -> None:
''',
    )
    text = replace_once(
        text,
        '''    safe_operation_id = _validate_operation_id(operation_id)
    connection = repository.connection
    now = _utc_now()
''',
        '''    safe_operation_id = _validate_operation_id(operation_id)
    target_schema_version = schema_version or current_record.schema_version
    connection = repository.connection
    now = _utc_now()
''',
    )
    text = replace_once(
        text,
        '''            SET updated_at = ?, revision = revision + 1, status = ?,
                provenance = ?, title = ?, metadata_json = ?
''',
        '''            SET schema_version = ?, updated_at = ?, revision = revision + 1,
                status = ?, provenance = ?, title = ?, metadata_json = ?
''',
    )
    text = replace_once(
        text,
        '''            (
                now,
                lifecycle_status,
''',
        '''            (
                target_schema_version,
                now,
                lifecycle_status,
''',
    )

    project_parse_old = '''        decision_ids = _metadata_reference_ids(record.metadata, "decision_ids")
        memory_ids = _metadata_reference_ids(record.metadata, "memory_ids")
        artifact_ids = _metadata_reference_ids(record.metadata, "artifact_ids")
        if repository is not None:
            _validate_typed_links(
                repository,
                decision_ids=decision_ids,
                memory_ids=memory_ids,
                artifact_ids=artifact_ids,
            )
'''
    project_parse_new = '''        decision_ids = _metadata_reference_ids(record.metadata, "decision_ids")
        memory_ids = _metadata_reference_ids(record.metadata, "memory_ids")
        artifact_ids = _metadata_reference_ids(record.metadata, "artifact_ids")
        if record.schema_version == PROJECT_SCHEMA_VERSION_V1:
            objective = None
            in_scope: tuple[str, ...] = ()
            out_of_scope: tuple[str, ...] = ()
            success_criteria: tuple[str, ...] = ()
            governing_policy_ids: tuple[str, ...] = ()
        else:
            objective = _validate_text(
                "project objective",
                _required_string(record.metadata, "objective"),
                MAX_DESCRIPTION_LENGTH,
            )
            in_scope = _metadata_text_items(record.metadata, "in_scope")
            out_of_scope = _metadata_text_items(record.metadata, "out_of_scope")
            success_criteria = _metadata_text_items(
                record.metadata,
                "success_criteria",
            )
            governing_policy_ids = _metadata_reference_ids(
                record.metadata,
                "governing_policy_ids",
            )
        if repository is not None:
            _validate_typed_links(
                repository,
                decision_ids=decision_ids,
                memory_ids=memory_ids,
                artifact_ids=artifact_ids,
                policy_ids=governing_policy_ids,
            )
'''
    text = replace_once(text, project_parse_old, project_parse_new)
    text = replace_once(
        text,
        '''    return ProjectInfo(
        project_id=record.id,
        name=name,
        description=description,
        project_status=project_status,
''',
        '''    return ProjectInfo(
        project_id=record.id,
        schema_version=record.schema_version,
        name=name,
        description=description,
        objective=objective,
        in_scope=in_scope,
        out_of_scope=out_of_scope,
        success_criteria=success_criteria,
        project_status=project_status,
''',
    )
    text = replace_once(
        text,
        '''        artifact_ids=artifact_ids,
        revision=record.revision,
''',
        '''        artifact_ids=artifact_ids,
        governing_policy_ids=governing_policy_ids,
        revision=record.revision,
''',
    )

    text = replace_once(
        text,
        '''    if record.schema_version != 1:
        raise ProjectDecisionValidationError("record schema version is unsupported")
''',
        '''    supported_versions = (
        SUPPORTED_PROJECT_SCHEMA_VERSIONS
        if record_type == "project"
        else frozenset({1})
    )
    if record.schema_version not in supported_versions:
        raise ProjectDecisionValidationError("record schema version is unsupported")
''',
    )
    text = replace_once(
        text,
        '''    decision_ids: Sequence[str] = (),
    memory_ids: Sequence[str] = (),
    artifact_ids: Sequence[str] = (),
) -> None:
''',
        '''    decision_ids: Sequence[str] = (),
    memory_ids: Sequence[str] = (),
    artifact_ids: Sequence[str] = (),
    policy_ids: Sequence[str] = (),
) -> None:
''',
    )
    policy_validation = '''
    for policy_id in policy_ids:
        try:
            policy_record = repository.get_record(policy_id)
            if policy_record.record_type != "policy":
                raise ProjectDecisionValidationError(
                    "governing policy link target has the wrong record type"
                )
            policy = _policy_from_record(policy_record)
            if policy.status != "active":
                raise ProjectDecisionValidationError(
                    "governing policy link target is not active"
                )
        except (
            KeyError,
            SettingsCorruptError,
            ProjectDecisionValidationError,
        ) as exc:
            raise ProjectDecisionValidationError(
                "governing policy link does not reference a valid active policy"
            ) from exc
'''
    text = replace_once(
        text,
        "\n\ndef _validate_artifact_link_envelope(record: RecordEnvelope) -> None:\n",
        policy_validation + "\n\ndef _validate_artifact_link_envelope(record: RecordEnvelope) -> None:\n",
    )

    PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
