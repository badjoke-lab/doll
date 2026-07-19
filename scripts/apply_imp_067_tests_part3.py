from pathlib import Path

path = Path("tests/test_imp_066_decision_context_acceptance.py")
text = path.read_text(encoding="utf-8")

addition = r'''


def test_resume_bundle_context_obeys_aggregate_item_and_character_limits(
    tmp_path: Path,
) -> None:
    initialized = _workspace(tmp_path)
    adapter = FakeImp066Adapter()
    conversation_id = str(uuid4())
    item_bundle = tmp_path / "item-limit.resume.zip"
    char_bundle = tmp_path / "character-limit.resume.zip"

    with state.open_state_repository(initialized.root) as repository:
        repository.save_conversation(ConversationRecord(conversation_id=conversation_id))
        _active_binding(repository, adapter)
        item_project_id = _resume_context_project(
            repository,
            operation_id="imp067.limit.item.bundle-project",
        )
        second_project_id = _resume_context_project(
            repository,
            operation_id="imp067.limit.item.second-project",
            description="Second selected project.",
        )
        decision_ids = tuple(
            _decision(
                repository,
                operation_id=f"imp067.limit.item.decision.{index}",
            ).decision_id
            for index in range(8)
        )
        char_project_id = _resume_context_project(
            repository,
            operation_id="imp067.limit.character.bundle-project",
            description="x" * 3_500,
        )
        large_decision_ids = tuple(
            _decision(
                repository,
                operation_id=f"imp067.limit.character.decision.{index}",
                reason="y" * 4_500,
            ).decision_id
            for index in range(4)
        )
    _export_resume_context_bundle(initialized, item_project_id, item_bundle)
    _export_resume_context_bundle(initialized, char_project_id, char_bundle)

    with state.open_state_repository(initialized.root) as repository:
        service = _service(repository, adapter)
        before = _instruction_origin_count(repository)
        with pytest.raises(LocalWritingWorkflowValidationError):
            service.execute(
                mode="draft",
                conversation_id=conversation_id,
                scope_type="conversation",
                scope_key="imp066-acceptance",
                request_text="Reject eleven selected context items.",
                project_ids=(item_project_id, second_project_id),
                decision_ids=decision_ids,
                resume_bundle_path=item_bundle,
                operation_id="imp067.limit.item.execute",
            )
        with pytest.raises(LocalWritingWorkflowValidationError):
            service.execute(
                mode="draft",
                conversation_id=conversation_id,
                scope_type="conversation",
                scope_key="imp066-acceptance",
                request_text="Reject aggregate selected context characters.",
                decision_ids=large_decision_ids,
                resume_bundle_path=char_bundle,
                operation_id="imp067.limit.character.execute",
            )
        assert adapter.prompts == []
        assert _instruction_origin_count(repository) == before


def test_runtime_failure_preserves_resume_bundle_and_project_revision(
    tmp_path: Path,
) -> None:
    initialized = _workspace(tmp_path)
    adapter = FakeImp066Adapter(output_text="")
    conversation_id = str(uuid4())
    bundle = tmp_path / "failure.resume.zip"

    with state.open_state_repository(initialized.root) as repository:
        repository.save_conversation(ConversationRecord(conversation_id=conversation_id))
        _active_binding(repository, adapter)
        project_id = _resume_context_project(
            repository,
            operation_id="imp067.failure.project",
        )
        project_revision = repository.get_record(project_id).revision
    _export_resume_context_bundle(initialized, project_id, bundle)
    bundle_bytes = bundle.read_bytes()

    with state.open_state_repository(initialized.root) as repository:
        result = _service(repository, adapter).execute(
            mode="draft",
            conversation_id=conversation_id,
            scope_type="conversation",
            scope_key="imp066-acceptance",
            request_text="Run a failing local runtime with bundle context.",
            resume_bundle_path=bundle,
            operation_id="imp067.failure.execute",
        )
        assert result.outcome == "failed"
        assert result.failure_code == "invalid_response"
        assert result.assistant_event_id is None
        assert result.error_event_id is not None
        assert repository.get_record(project_id).revision == project_revision
        assert [
            event.event_kind for event in repository.list_conversation_events(conversation_id)
        ] == ["user_message", "system_context_snapshot", "error"]

    assert bundle.read_bytes() == bundle_bytes
'''

if "test_resume_bundle_context_obeys_aggregate_item_and_character_limits" in text:
    raise SystemExit("IMP-067 limit acceptance tests are already present")
path.write_text(text + addition, encoding="utf-8")
print("IMP-067 limit and failure tests applied")
