from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"unexpected source shape in {path}: {old}")
    target.write_text(text.replace(old, new), encoding="utf-8")


def update_source() -> None:
    replace_once(
        "src/doll/local_work_proposal.py",
        'runtime_origin_id = event.extensions.get("instruction_origin_id")',
        'runtime_origin_id = (event.extensions or {}).get("instruction_origin_id")',
    )
    replace_once(
        "src/doll/local_work_proposal.py",
        'f"audit\\0{operation_id}".encode("utf-8")',
        'f"audit\\0{operation_id}".encode()',
    )


def update_tests() -> None:
    path = ROOT / "tests/test_imp_069_local_work_proposal.py"
    text = path.read_text(encoding="utf-8")
    old_import = "from doll.local_work_proposal import LocalWorkProposalService"
    new_import = """from doll.local_work_proposal import (
    LocalWorkProposalService,
    LocalWorkProposalValidationError,
    _parse_proposal,
    _request_text,
)"""
    if text.count(old_import) != 1:
        raise RuntimeError("unexpected local proposal import")
    text = text.replace(old_import, new_import)
    old_project_import = "from doll.project_state import DecisionService, ProjectService"
    new_project_import = (
        "from doll.project_state import DecisionService, ProjectInfo, ProjectService"
    )
    if text.count(old_project_import) != 1:
        raise RuntimeError("unexpected project import")
    text = text.replace(old_project_import, new_project_import)
    old_signature = "def _project(repository: state.StateRepository):"
    new_signature = "def _project(repository: state.StateRepository) -> ProjectInfo:"
    if text.count(old_signature) != 1:
        raise RuntimeError("unexpected project helper signature")
    text = text.replace(old_signature, new_signature)
    if "def test_service_requires_one_shared_repository" in text:
        raise RuntimeError("coverage tests already exist")
    text += '''


def test_service_requires_one_shared_repository(tmp_path: Path) -> None:
    first = workspace.initialize_workspace(tmp_path / "first")
    second = workspace.initialize_workspace(tmp_path / "second")
    with state.initialize_state_repository(first.root):
        pass
    with state.initialize_state_repository(second.root):
        pass
    adapter = FakePlanningAdapter()
    with (
        state.open_state_repository(first.root) as first_repository,
        state.open_state_repository(second.root) as second_repository,
    ):
        local = LocalConversationService(
            first_repository,
            LocalRuntimeBoundary(RuntimeAdapterRegistry((adapter,))),
        )
        with pytest.raises(LocalWorkProposalValidationError, match="same repository"):
            LocalWorkProposalService(second_repository, local)


def test_request_validation_fails_closed() -> None:
    with pytest.raises(LocalWorkProposalValidationError, match="must be text"):
        _request_text(None)
    with pytest.raises(LocalWorkProposalValidationError, match="invalid"):
        _request_text("   ")
    with pytest.raises(LocalWorkProposalValidationError, match="character limit"):
        _request_text("x" * 12_001)


@pytest.mark.parametrize(
    "output_text",
    (
        "[]",
        json.dumps(
            {
                "schema_version": 2,
                "kind": "task",
                "title": "Title",
                "description": "Description",
                "priority": 50,
                "acceptance_criteria": [],
            }
        ),
        json.dumps(
            {
                "schema_version": 1,
                "kind": "task",
                "title": 1,
                "description": "Description",
                "priority": 50,
                "acceptance_criteria": [],
            }
        ),
        json.dumps(
            {
                "schema_version": 1,
                "kind": "task",
                "title": "Title",
                "description": "Description",
                "priority": 50,
                "acceptance_criteria": {},
            }
        ),
        json.dumps(
            {
                "schema_version": 1,
                "kind": "task",
                "title": "Title",
                "description": "Description",
                "priority": 50,
                "acceptance_criteria": [
                    {
                        "criterion_id": "criterion",
                        "description": "Description",
                        "required_evidence_kind": None,
                        "blocking": True,
                        "status": "passed",
                    }
                ],
            }
        ),
        json.dumps(
            {
                "schema_version": 1,
                "kind": "task",
                "title": "Title",
                "description": "Description",
                "priority": 50,
                "acceptance_criteria": [
                    {
                        "criterion_id": "criterion",
                        "description": 1,
                        "required_evidence_kind": None,
                        "blocking": True,
                    }
                ],
            }
        ),
        '{"schema_version":1,"kind":"task","title":"Title",'
        '"description":"Description","priority":NaN,"acceptance_criteria":[]}',
    ),
)
def test_strict_parser_rejects_unsupported_shapes(output_text: str) -> None:
    with pytest.raises(LocalWorkProposalValidationError):
        _parse_proposal(output_text)


def test_missing_project_fails_before_runtime_or_context_creation(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    adapter = FakePlanningAdapter()
    conversation_id = str(uuid4())
    with state.open_state_repository(initialized.root) as repository:
        repository.save_conversation(ConversationRecord(conversation_id=conversation_id))
        _active_binding(repository, adapter)
        with pytest.raises(LocalWorkProposalValidationError, match="context is invalid"):
            _service(repository, adapter).execute(
                conversation_id=conversation_id,
                scope_type="conversation",
                scope_key="planning",
                project_id=str(uuid4()),
                request_text="Propose one work item.",
                operation_id="imp069.missing-project",
            )
        assert adapter.prompts == []
        assert repository.list_conversation_events(conversation_id) == ()
        assert _work_item_count(repository) == 0


def test_secret_bearing_runtime_output_creates_no_work_item(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    adapter = FakePlanningAdapter(
        output_text="Authorization: Bearer abcdefghijklmnopqrstuvwxyz"
    )
    conversation_id = str(uuid4())
    with state.open_state_repository(initialized.root) as repository:
        repository.save_conversation(ConversationRecord(conversation_id=conversation_id))
        _active_binding(repository, adapter)
        project = _project(repository)
        result = _service(repository, adapter).execute(
            conversation_id=conversation_id,
            scope_type="conversation",
            scope_key="planning",
            project_id=project.project_id,
            request_text="Propose one work item.",
            operation_id="imp069.secret-output",
        )
        assert result.outcome == "failed"
        assert result.runtime_failure_code == "invalid_response"
        assert result.proposal_created is False
        assert _work_item_count(repository) == 0
'''
    path.write_text(text, encoding="utf-8")


def main() -> None:
    update_source()
    update_tests()


if __name__ == "__main__":
    main()
