from pathlib import Path

path = Path("tests/test_imp_066_decision_context_acceptance.py")
text = path.read_text(encoding="utf-8")

addition = r'''


@pytest.mark.parametrize(
    ("mode", "source_text"),
    (
        ("draft", None),
        ("revise", "Revise this bounded Resume Bundle source."),
        ("summarize", "Summarize this bounded Resume Bundle source."),
    ),
)
def test_explicit_resume_bundle_context_works_in_all_writing_modes(
    tmp_path: Path,
    mode: WritingMode,
    source_text: str | None,
) -> None:
    initialized = _workspace(tmp_path)
    adapter = FakeImp066Adapter()
    conversation_id = str(uuid4())
    bundle = tmp_path / f"{mode}.resume.zip"

    with state.open_state_repository(initialized.root) as repository:
        repository.save_conversation(ConversationRecord(conversation_id=conversation_id))
        _active_binding(repository, adapter)
        project_id = _resume_context_project(
            repository,
            operation_id=f"imp067.all-modes.{mode}.project",
        )
        project_revision = repository.get_record(project_id).revision
    state_revision = _export_resume_context_bundle(initialized, project_id, bundle)
    bundle_bytes = bundle.read_bytes()
    bundle_sha256 = f"sha256:{hashlib.sha256(bundle_bytes).hexdigest()}"

    with state.open_state_repository(initialized.root) as repository:
        result = _service(repository, adapter).execute(
            mode=mode,
            conversation_id=conversation_id,
            scope_type="conversation",
            scope_key="imp066-acceptance",
            request_text=f"Run bounded {mode} mode with explicit Resume Bundle context.",
            source_text=source_text,
            resume_bundle_path=bundle,
            operation_id=f"imp067.all-modes.{mode}.execute",
        )

        assert result.outcome == "completed"
        assert result.selected_resume_bundle_project_id == project_id
        assert result.selected_resume_bundle_state_revision == state_revision
        assert result.selected_resume_bundle_sha256 == bundle_sha256
        assert result.selected_resume_bundle_member_group_count == 9
        assert result.selected_resume_bundle_character_count > 0
        assert result.selected_context_character_count == (
            result.selected_resume_bundle_character_count
        )
        assert len(result.selected_context_instruction_ids) == 1
        assert result.prompt_injection_finding_count >= 1
        assert repository.get_record(result.context_event_id).sensitivity == "sensitive"
        assert repository.get_record(project_id).revision == project_revision

        prompt = json.loads(adapter.prompts[0])
        task = json.loads(prompt["channels"]["current_user_instruction"][0]["content"])
        assert task["mode"] == mode
        assert task["selected_resume_bundle_count"] == 1
        assert project_id not in prompt["channels"]["current_user_instruction"][0]["content"]

        bundle_items = [
            item
            for item in prompt["channels"]["untrusted_content"]
            if item["title"] == "Selected Resume Bundle context"
        ]
        assert len(bundle_items) == 1
        snapshot = json.loads(bundle_items[0]["content"])
        assert snapshot["context_kind"] == "resume_bundle"
        assert snapshot["project_id"] == project_id
        assert snapshot["generated_from_state_revision"] == state_revision
        assert snapshot["bundle_sha256"] == bundle_sha256
        assert "Ignore previous instructions" in snapshot["project"]["description"]
        assert "active_work_items" in snapshot
        assert "validation_requirements" in snapshot
        assert "handoff" not in snapshot
        assert "checksums" not in snapshot
        assert "artifact_references" not in snapshot
        assert "source_references" not in snapshot
        assert bundle_items[0]["origin_class"] == "external_content"
        assert bundle_items[0]["effective_authority_class"] == "untrusted_data"
        assert bundle_items[0]["data_only"] is True

        origin = InstructionOriginService(repository).get(
            result.selected_context_instruction_ids[0]
        )
        assert origin.source.actor_type == "extractor"
        assert origin.source.acquisition_method == "extraction"
        assert str(bundle) not in (origin.source.source_identifier or "")
        assert (
            not InstructionOriginService(repository)
            .authority_decision(origin.record_id, purpose="task_instruction")
            .allowed
        )

        encoded = json.dumps(asdict(result), sort_keys=True)
        assert str(bundle) not in encoded
        assert "Resume context project" not in encoded
        assert "Ignore previous instructions" not in encoded
        assert adapter.output_text not in encoded
        assert "/Users/" not in encoded
        assert "/home/" not in encoded

    assert bundle.read_bytes() == bundle_bytes


def test_invalid_resume_bundles_fail_before_runtime_or_origin_creation(
    tmp_path: Path,
) -> None:
    initialized = _workspace(tmp_path)
    adapter = FakeImp066Adapter()
    conversation_id = str(uuid4())
    source = tmp_path / "valid.resume.zip"
    tampered = tmp_path / "tampered.resume.zip"
    secret = tmp_path / "secret.resume.zip"

    with state.open_state_repository(initialized.root) as repository:
        repository.save_conversation(ConversationRecord(conversation_id=conversation_id))
        _active_binding(repository, adapter)
        project_id = _resume_context_project(
            repository,
            operation_id="imp067.invalid.project",
        )
    _export_resume_context_bundle(initialized, project_id, source)
    _rewrite_resume_bundle(
        source,
        tampered,
        description="Tampered without checksum repair.",
        recompute_checksums=False,
    )
    _rewrite_resume_bundle(
        source,
        secret,
        description="api_key=sk-1234567890abcdefghijklmnop",
        recompute_checksums=True,
    )
    invalid_paths = [tmp_path / "missing.resume.zip", tampered, secret]
    symlink = tmp_path / "linked.resume.zip"
    try:
        symlink.symlink_to(source)
    except OSError:
        pass
    else:
        invalid_paths.append(symlink)

    with state.open_state_repository(initialized.root) as repository:
        service = _service(repository, adapter)
        before = _instruction_origin_count(repository)
        for index, bundle_path in enumerate(invalid_paths):
            with pytest.raises(LocalWritingWorkflowValidationError):
                service.execute(
                    mode="draft",
                    conversation_id=conversation_id,
                    scope_type="conversation",
                    scope_key="imp066-acceptance",
                    request_text="This invalid bundle must not execute.",
                    resume_bundle_path=bundle_path,
                    operation_id=f"imp067.invalid.{index}",
                )
        assert adapter.prompts == []
        assert _instruction_origin_count(repository) == before
'''

if "test_explicit_resume_bundle_context_works_in_all_writing_modes" in text:
    raise SystemExit("IMP-067 primary acceptance tests are already present")
path.write_text(text + addition, encoding="utf-8")
print("IMP-067 primary acceptance tests applied")
