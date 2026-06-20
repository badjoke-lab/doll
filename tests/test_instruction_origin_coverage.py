from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

import doll.instruction_origin as module
from doll import state, workspace
from doll.instruction_origin import (
    InstructionOriginCorruptError,
    InstructionOriginService,
    InstructionOriginValidationError,
    InstructionSource,
)
from doll.settings import PolicyService, PreferenceService
from doll.state import RecordProvenance


def initialized_repository(
    tmp_path: Path,
) -> tuple[workspace.InitializedWorkspace, state.StateRepository]:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized, state.open_state_repository(initialized.root)


def user_source(**changes: object) -> InstructionSource:
    values: dict[str, object] = {
        "origin_class": "current_user_instruction",
        "actor_type": "user",
        "acquisition_method": "user_entry",
        "session_id": "session",
    }
    values.update(changes)
    return InstructionSource(**values)  # type: ignore[arg-type]


def external_source(**changes: object) -> InstructionSource:
    values: dict[str, object] = {
        "origin_class": "external_content",
        "actor_type": "retriever",
        "acquisition_method": "retrieval",
        "source_identifier": "source",
        "parent_operation_id": "operation",
    }
    values.update(changes)
    return InstructionSource(**values)  # type: ignore[arg-type]


def system_source(**changes: object) -> InstructionSource:
    values: dict[str, object] = {
        "origin_class": "system_policy",
        "actor_type": "system",
        "acquisition_method": "system_defined",
        "authority_reference_id": "system-policy",
        "authority_reference_revision": 1,
    }
    values.update(changes)
    return InstructionSource(**values)  # type: ignore[arg-type]


def test_list_includes_archived_and_empty_result(tmp_path: Path) -> None:
    _, repository = initialized_repository(tmp_path)
    with repository:
        service = InstructionOriginService(repository)
        assert service.list() == ()
        first = service.create(title="One", content="One.", source=user_source())
        second = service.create(
            title="Two", content="Two.", source=user_source(session_id="session-2")
        )
        service.archive(first.record_id, expected_revision=1)
        assert [item.record_id for item in service.list()] == [second.record_id]
        assert [item.record_id for item in service.list(include_archived=True)] == [
            first.record_id,
            second.record_id,
        ]
        with pytest.raises(InstructionOriginValidationError):
            service.list(limit=cast(int, True))
        with pytest.raises(InstructionOriginValidationError):
            service.list(limit=201)


def test_graph_validation_rejects_self_missing_wrong_type_elevation_and_cycle(
    tmp_path: Path,
) -> None:
    _, repository = initialized_repository(tmp_path)
    with repository:
        service = InstructionOriginService(repository)
        parent = service.create(title="Parent", content="Parent.", source=external_source())
        child = service.create(
            title="Child",
            content="Child.",
            source=external_source(derived_from_instruction_id=parent.record_id),
        )
        system = service.create(title="System", content="System.", source=system_source())
        preference = PreferenceService(repository).create(key="x", value="y")
        parent_record = repository.get_record(parent.record_id)
        child_record = repository.get_record(child.record_id)
        system_record = repository.get_record(system.record_id)
        preference_record = repository.get_record(preference.record_id)

        module._validate_instruction_origin_graph(
            {parent.record_id: parent_record, child.record_id: child_record}
        )

        self_link = replace(
            child_record,
            metadata={
                **child_record.metadata,
                "derived_from_instruction_id": child.record_id,
            },
        )
        with pytest.raises(InstructionOriginCorruptError, match="itself"):
            module._validate_instruction_origin_graph({child.record_id: self_link})

        missing_link = replace(
            child_record,
            metadata={
                **child_record.metadata,
                "derived_from_instruction_id": str(uuid4()),
            },
        )
        with pytest.raises(InstructionOriginCorruptError, match="missing"):
            module._validate_instruction_origin_graph({child.record_id: missing_link})

        wrong_type = replace(
            child_record,
            metadata={
                **child_record.metadata,
                "derived_from_instruction_id": preference.record_id,
            },
        )
        with pytest.raises(InstructionOriginCorruptError, match="wrong type"):
            module._validate_instruction_origin_graph(
                {
                    child.record_id: wrong_type,
                    preference.record_id: preference_record,
                }
            )

        elevated = replace(
            system_record,
            metadata={
                **system_record.metadata,
                "derived_from_instruction_id": parent.record_id,
            },
        )
        with pytest.raises(InstructionOriginCorruptError, match="raises authority"):
            module._validate_instruction_origin_graph(
                {system.record_id: elevated, parent.record_id: parent_record}
            )

        first_cycle = replace(
            parent_record,
            metadata={
                **parent_record.metadata,
                "derived_from_instruction_id": child.record_id,
            },
        )
        second_cycle = replace(
            child_record,
            metadata={
                **child_record.metadata,
                "derived_from_instruction_id": parent.record_id,
            },
        )
        with pytest.raises(InstructionOriginCorruptError, match="cycle"):
            module._validate_instruction_origin_graph(
                {parent.record_id: first_cycle, child.record_id: second_cycle}
            )


def test_graph_validation_requires_durable_policy_reference(tmp_path: Path) -> None:
    _, repository = initialized_repository(tmp_path)
    with repository:
        policy = PolicyService(repository).create(key="rule", rule="Rule.", enabled=True)
        service = InstructionOriginService(repository)
        durable = service.create(
            title="Policy",
            content=policy.rule,
            source=InstructionSource(
                origin_class="durable_user_policy",
                actor_type="user",
                acquisition_method="policy_reference",
                authority_reference_id=policy.record_id,
                authority_reference_revision=policy.revision,
            ),
        )
        durable_record = repository.get_record(durable.record_id)
        with pytest.raises(InstructionOriginCorruptError, match="missing or wrong-type"):
            module._validate_instruction_origin_graph({durable.record_id: durable_record})

        preference = PreferenceService(repository).create(key="wrong", value=True)
        wrong_reference = replace(
            durable_record,
            metadata={
                **durable_record.metadata,
                "authority_reference_id": preference.record_id,
            },
        )
        with pytest.raises(InstructionOriginCorruptError, match="missing or wrong-type"):
            module._validate_instruction_origin_graph(
                {
                    durable.record_id: wrong_reference,
                    preference.record_id: repository.get_record(preference.record_id),
                }
            )


def test_policy_reference_validation_covers_malformed_and_inactive(tmp_path: Path) -> None:
    _, repository = initialized_repository(tmp_path)
    with repository:
        malformed = repository.create_record(
            record_type="policy",
            title="bad",
            metadata={"policy_key": "bad", "rule": 1, "enabled": True},
        )
        service = InstructionOriginService(repository)
        with pytest.raises(InstructionOriginValidationError, match="malformed"):
            service.create(
                title="Malformed",
                content="Rule.",
                source=InstructionSource(
                    origin_class="durable_user_policy",
                    actor_type="user",
                    acquisition_method="policy_reference",
                    authority_reference_id=malformed.id,
                    authority_reference_revision=1,
                ),
            )

        disabled = PolicyService(repository).create(
            key="disabled", rule="Disabled rule.", enabled=False
        )
        with pytest.raises(InstructionOriginValidationError, match="not active"):
            service.create(
                title="Disabled",
                content=disabled.rule,
                source=InstructionSource(
                    origin_class="durable_user_policy",
                    actor_type="user",
                    acquisition_method="policy_reference",
                    authority_reference_id=disabled.record_id,
                    authority_reference_revision=disabled.revision,
                ),
            )

        archived = PolicyService(repository).create(
            key="archived", rule="Archived rule.", enabled=True
        )
        PolicyService(repository).archive(archived.record_id, expected_revision=1)
        with pytest.raises(InstructionOriginValidationError, match="not active"):
            service.create(
                title="Archived",
                content=archived.rule,
                source=InstructionSource(
                    origin_class="durable_user_policy",
                    actor_type="user",
                    acquisition_method="policy_reference",
                    authority_reference_id=archived.record_id,
                    authority_reference_revision=2,
                ),
            )


def test_missing_derived_parent_is_rejected(tmp_path: Path) -> None:
    _, repository = initialized_repository(tmp_path)
    with repository:
        with pytest.raises(InstructionOriginValidationError, match="does not exist"):
            InstructionOriginService(repository).create(
                title="Missing parent",
                content="Derived.",
                source=external_source(derived_from_instruction_id=str(uuid4())),
            )


def test_durable_reference_status_helper_covers_all_failure_reasons(tmp_path: Path) -> None:
    _, repository = initialized_repository(tmp_path)
    with repository:
        policy = PolicyService(repository).create(key="policy", rule="Rule.", enabled=True)
        service = InstructionOriginService(repository)
        info = service.create(
            title="Policy",
            content=policy.rule,
            source=InstructionSource(
                origin_class="durable_user_policy",
                actor_type="user",
                acquisition_method="policy_reference",
                authority_reference_id=policy.record_id,
                authority_reference_revision=policy.revision,
            ),
        )
        missing_source = cast(
            InstructionSource,
            SimpleNamespace(authority_reference_id=None, authority_reference_revision=None),
        )
        missing_info = replace(info, source=missing_source)
        assert module._durable_policy_reference_is_current(repository, missing_info)[0] is False

        absent_source = cast(
            InstructionSource,
            SimpleNamespace(authority_reference_id=str(uuid4()), authority_reference_revision=1),
        )
        absent_info = replace(info, source=absent_source)
        assert "no longer exists" in cast(
            str, module._durable_policy_reference_is_current(repository, absent_info)[1]
        )

        preference = PreferenceService(repository).create(key="wrong", value=True)
        wrong_source = cast(
            InstructionSource,
            SimpleNamespace(
                authority_reference_id=preference.record_id,
                authority_reference_revision=preference.revision,
            ),
        )
        wrong_info = replace(info, source=wrong_source)
        assert "wrong record type" in cast(
            str, module._durable_policy_reference_is_current(repository, wrong_info)[1]
        )

        malformed = repository.create_record(
            record_type="policy",
            title="bad",
            metadata={"policy_key": "bad", "rule": 1, "enabled": True},
        )
        malformed_source = cast(
            InstructionSource,
            SimpleNamespace(authority_reference_id=malformed.id, authority_reference_revision=1),
        )
        malformed_info = replace(info, source=malformed_source)
        assert "malformed" in cast(
            str, module._durable_policy_reference_is_current(repository, malformed_info)[1]
        )

        disabled = PolicyService(repository).create(key="disabled", rule="Disabled.", enabled=False)
        disabled_source = cast(
            InstructionSource,
            SimpleNamespace(
                authority_reference_id=disabled.record_id,
                authority_reference_revision=disabled.revision,
            ),
        )
        disabled_info = replace(info, source=disabled_source, content=disabled.rule)
        assert "inactive" in cast(
            str, module._durable_policy_reference_is_current(repository, disabled_info)[1]
        )

        mismatched_content = replace(info, content="Other.")
        assert "no longer matches" in cast(
            str,
            module._durable_policy_reference_is_current(repository, mismatched_content)[1],
        )


def test_create_and_archive_database_errors_are_normalized(tmp_path: Path) -> None:
    _, repository = initialized_repository(tmp_path)
    with repository:
        repository.connection.execute("DROP TABLE audit_events")
        with pytest.raises(state.StateCorruptError, match="could not be created"):
            InstructionOriginService(repository).create(
                title="Fail", content="Fail.", source=user_source()
            )
        count = repository.connection.execute(
            "SELECT COUNT(*) FROM records WHERE record_type = 'instruction_origin'"
        ).fetchone()
        assert count is not None and count[0] == 0
        assert repository.connection.in_transaction is False

    initialized2 = workspace.initialize_workspace(tmp_path / "archive-workspace")
    with state.initialize_state_repository(initialized2.root):
        pass
    with state.open_state_repository(initialized2.root) as repository2:
        service = InstructionOriginService(repository2)
        record = service.create(title="Archive", content="Archive.", source=user_source())
        repository2.connection.execute("DROP TABLE audit_events")
        with pytest.raises(state.StateCorruptError, match="could not be archived"):
            service.archive(record.record_id, expected_revision=1)
        assert service.get(record.record_id).status == "active"
        assert repository2.connection.in_transaction is False


def test_archive_defensive_revision_and_change_checks(tmp_path: Path) -> None:
    _, repository = initialized_repository(tmp_path)
    with repository:
        service = InstructionOriginService(repository)
        record = service.create(title="Archive", content="Archive.", source=user_source())
        with pytest.raises(InstructionOriginValidationError, match="integer"):
            service.archive(record.record_id, expected_revision=cast(int, True))

        repository.connection.execute(
            f"""
            CREATE TRIGGER ignore_instruction_archive
            BEFORE UPDATE ON records
            WHEN OLD.id = '{record.record_id}'
            BEGIN
                SELECT RAISE(IGNORE);
            END
            """
        )
        with pytest.raises(state.StaleRevisionError, match="changed"):
            service.archive(record.record_id, expected_revision=1)
        repository.connection.execute("DROP TRIGGER ignore_instruction_archive")

        stale_copy = repository.get_record(record.record_id)
        service.archive(record.record_id, expected_revision=1)
        with pytest.raises(InstructionOriginValidationError, match="already archived"):
            module._archive_instruction_record(
                repository,
                current=stale_copy,
                expected_revision=2,
                operation_id=None,
            )


def test_private_validators_cover_types_lengths_and_control_characters() -> None:
    with pytest.raises(InstructionOriginValidationError, match="validated"):
        module._require_source(object())
    with pytest.raises(InstructionOriginValidationError, match="exceeds"):
        module._validate_record_ids(tuple(str(uuid4()) for _ in range(201)))
    with pytest.raises(InstructionOriginValidationError, match="sequence"):
        module._validate_transformations("bad")
    with pytest.raises(InstructionOriginValidationError, match="exceed"):
        module._validate_transformations(["normalization"] * 13)
    with pytest.raises(InstructionOriginValidationError, match="origin"):
        module._validate_origin(1)
    with pytest.raises(InstructionOriginValidationError, match="authority"):
        module._validate_authority("bad")
    with pytest.raises(InstructionOriginValidationError, match="actor"):
        module._validate_actor("bad")
    with pytest.raises(InstructionOriginValidationError, match="acquisition"):
        module._validate_acquisition("bad")
    with pytest.raises(InstructionOriginValidationError, match="string"):
        module._validate_content(1)
    with pytest.raises(InstructionOriginValidationError, match="exceeds"):
        module._validate_content("x" * (module.MAX_CONTENT_LENGTH + 1))
    with pytest.raises(InstructionOriginValidationError, match="string"):
        module._validate_text("text", 1, 10)
    with pytest.raises(InstructionOriginValidationError, match="exceeds"):
        module._validate_text("text", "x" * 11, 10)
    with pytest.raises(InstructionOriginValidationError, match="control"):
        module._validate_text("text", "a\x00b", 10)
    with pytest.raises(InstructionOriginValidationError, match="unsafe"):
        module._validate_text("text", "password = unsafe-secret-value", 100)
    with pytest.raises(InstructionOriginValidationError, match="string"):
        module._validate_identifier("id", 1)
    with pytest.raises(InstructionOriginValidationError, match="blank"):
        module._validate_identifier("id", " ")
    with pytest.raises(InstructionOriginValidationError, match="exceeds"):
        module._validate_identifier("id", "x" * 301)
    with pytest.raises(InstructionOriginValidationError, match="control"):
        module._validate_identifier("id", "a\x00b")
    with pytest.raises(InstructionOriginValidationError, match="unsafe"):
        module._validate_identifier("id", "/home/alice/file")
    with pytest.raises(InstructionOriginValidationError, match="string"):
        module._validate_optional_hash(1)
    with pytest.raises(InstructionOriginValidationError, match="string or null"):
        module._validate_optional_utc("time", 1)
    with pytest.raises(InstructionOriginValidationError, match="ISO"):
        module._validate_optional_utc("time", "not-a-time")
    with pytest.raises(InstructionOriginValidationError, match="UUID"):
        module._validate_uuid("id", 1)
    noncanonical = "{" + str(uuid4()) + "}"
    with pytest.raises(InstructionOriginValidationError, match="canonical"):
        module._validate_uuid("id", noncanonical)
    with pytest.raises(InstructionOriginValidationError, match="missing"):
        module._required_string({}, "missing")
    with pytest.raises(InstructionOriginValidationError, match="invalid"):
        module._optional_string({"value": 1}, "value")
    with pytest.raises(InstructionOriginValidationError, match="not a list"):
        module._metadata_list({"value": "bad"}, "value")


def test_invalid_actor_acquisition_and_content_parser_branches(tmp_path: Path) -> None:
    with pytest.raises(InstructionOriginValidationError, match="actor"):
        InstructionSource(
            origin_class="unknown",
            actor_type=cast(module.InstructionActorType, "bad"),
            acquisition_method="unknown",
        )
    with pytest.raises(InstructionOriginValidationError, match="acquisition"):
        InstructionSource(
            origin_class="unknown",
            actor_type="unknown",
            acquisition_method=cast(module.InstructionAcquisitionMethod, "bad"),
        )

    _, repository = initialized_repository(tmp_path)
    with repository:
        record = InstructionOriginService(repository).create(
            title="Valid", content="Valid.", source=user_source()
        )
        base = repository.get_record(record.record_id)
        bad_provenance = replace(base, provenance=cast(RecordProvenance, "invalid-provenance"))
        with pytest.raises(InstructionOriginCorruptError):
            module._instruction_origin_from_record(bad_provenance)
        bad_content = replace(base, metadata={**base.metadata, "content": 1})
        with pytest.raises(InstructionOriginCorruptError):
            module._instruction_origin_from_record(bad_content)
        bad_optional = replace(base, metadata={**base.metadata, "source_identifier": 1})
        with pytest.raises(InstructionOriginCorruptError):
            module._instruction_origin_from_record(bad_optional)
