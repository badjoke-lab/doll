from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

from doll import state, workspace
from doll.audit import AuditService
from doll.memory import ConfirmedMemoryService
from doll.state_package import export_state_package, import_state_package
from doll.trust import (
    ClaimEvidenceTrustService,
    EvidenceInfo,
    EvidenceType,
    ForbiddenTruthMutationError,
    InferenceInfo,
    TrustAssessmentInfo,
    TrustAssessorType,
    TrustLevel,
    TrustSubjectType,
    TruthCorruptError,
    TruthRecordKind,
    TruthSource,
    TruthValidationError,
)


def initialized_workspace(
    tmp_path: Path, name: str = "workspace"
) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / name)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def user_source(**changes: object) -> TruthSource:
    values: dict[str, object] = {
        "origin_type": "user_statement",
        "creator_actor_type": "user",
        "source_identifier": None,
        "observed_at": "2026-06-20T00:00:00Z",
        "source_content_hash": None,
        "transformation_method": None,
        "model_manifest_id": None,
        "runtime_adapter_id": None,
        "session_id": None,
        "origin_operation_id": None,
    }
    values.update(changes)
    return TruthSource(**values)  # type: ignore[arg-type]


def model_source(**changes: object) -> TruthSource:
    values: dict[str, object] = {
        "origin_type": "model_proposal",
        "creator_actor_type": "model",
        "source_identifier": "synthetic-model-output",
        "observed_at": "2026-06-20T01:00:00+09:00",
        "source_content_hash": "sha256:" + "a" * 64,
        "transformation_method": "synthetic structured proposal",
        "model_manifest_id": "model-1",
        "runtime_adapter_id": "runtime-1",
        "session_id": "session-1",
        "origin_operation_id": "operation-1",
    }
    values.update(changes)
    return TruthSource(**values)  # type: ignore[arg-type]


def imported_source(**changes: object) -> TruthSource:
    values: dict[str, object] = {
        "origin_type": "imported_content",
        "creator_actor_type": "importer",
        "source_identifier": "import-batch-1",
        "observed_at": None,
        "source_content_hash": None,
        "transformation_method": "synthetic import",
        "model_manifest_id": None,
        "runtime_adapter_id": None,
        "session_id": None,
        "origin_operation_id": "import-operation-1",
    }
    values.update(changes)
    return TruthSource(**values)  # type: ignore[arg-type]


def create_graph(service: ClaimEvidenceTrustService) -> tuple[str, str, str, str]:
    claim = service.create_claim(
        title="Service status",
        statement="The synthetic service is available.",
        source=model_source(),
        confidence=1.0,
        uncertainty="The proposal has not been reviewed.",
        operation_id="truth-claim",
    )
    evidence = service.create_evidence(
        title="Synthetic observation",
        summary="A synthetic status response reported availability.",
        evidence_type="observation",
        source=TruthSource(
            origin_type="tool_result",
            creator_actor_type="tool",
            source_identifier="synthetic.status",
            observed_at="2026-06-20T02:00:00Z",
            origin_operation_id="tool-operation-1",
        ),
        supports_claim_ids=(claim.record_id,),
        confidence=0.7,
        uncertainty="The source is synthetic.",
        operation_id="truth-evidence",
    )
    inference = service.create_inference(
        title="Availability inference",
        conclusion="The service may be available at the observed time.",
        method="Combine the proposal and the synthetic observation.",
        source=TruthSource(
            origin_type="system_observation",
            creator_actor_type="system",
            observed_at="2026-06-20T02:01:00Z",
            transformation_method="deterministic synthetic derivation",
            origin_operation_id="inference-operation-1",
        ),
        claim_ids=(claim.record_id,),
        evidence_ids=(evidence.record_id,),
        confidence=0.9,
        uncertainty="No real provider was contacted.",
        operation_id="truth-inference",
    )
    trust = service.assess_trust(
        subject_type="evidence",
        subject_id=evidence.record_id,
        level="limited",
        reason="Synthetic evidence is suitable only for contract testing.",
        evidence_ids=(evidence.record_id,),
        operation_id="truth-trust",
    )
    return claim.record_id, evidence.record_id, inference.record_id, trust.record_id


def test_model_and_import_claims_remain_unreviewed_non_authoritative(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ClaimEvidenceTrustService(repository)
        model_claim = service.create_claim(
            title="Model proposal",
            statement="This statement is not a confirmed fact.",
            source=model_source(),
            confidence=1.0,
            operation_id="model-claim",
        )
        imported_claim = service.create_claim(
            title="Imported assertion",
            statement="Imported content remains a claim.",
            source=imported_source(),
            operation_id="imported-claim",
        )

        assert model_claim.review_state == "unreviewed"
        assert model_claim.record_provenance == "model-proposed"
        assert model_claim.confidence == 1.0
        assert imported_claim.review_state == "unreviewed"
        assert imported_claim.record_provenance == "imported"
        assert imported_claim.source.observed_at is None
        assert imported_claim.source.source_content_hash is None
        assert repository.status().record_count == 2
        memory_count = repository.connection.execute(
            "SELECT COUNT(*) FROM records WHERE record_type = 'memory'"
        ).fetchone()
        assert memory_count is not None and memory_count[0] == 0
        actions = {event.action for event in AuditService(repository).list(limit=20)}
        assert actions == {"truth.claim.create"}


def test_user_review_is_explicit_and_non_user_review_is_denied(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ClaimEvidenceTrustService(repository)
        claim = service.create_claim(
            title="Review target",
            statement="A user may review this claim.",
            source=model_source(),
        )
        with pytest.raises(ForbiddenTruthMutationError):
            service.review(
                claim.record_id,
                expected_revision=1,
                review_state="reviewed",
                actor_type="model",
            )
        reviewed = service.review(
            claim.record_id,
            expected_revision=1,
            review_state="disputed",
            review_note="Evidence is incomplete.",
            operation_id="claim-review",
        )
        assert reviewed.review_state == "disputed"
        assert reviewed.reviewer_actor_type == "user"
        assert reviewed.reviewed_at is not None
        assert reviewed.revision == 2
        assert reviewed.record_provenance == "model-proposed"

        with pytest.raises(state.StaleRevisionError):
            service.review(
                claim.record_id,
                expected_revision=1,
                review_state="reviewed",
            )
        with pytest.raises(TruthValidationError):
            service.review(
                claim.record_id,
                expected_revision=2,
                review_state="unreviewed",
                review_note="not allowed",
            )


def test_user_can_create_reviewed_claim_but_confidence_is_not_trust(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ClaimEvidenceTrustService(repository)
        claim = service.create_claim(
            title="Reviewed claim",
            statement="Reviewed is still not the same record type as confirmed fact.",
            source=user_source(),
            confidence=1.0,
            review_state="reviewed",
            review_note="Reviewed through the trusted user path.",
        )
        assert claim.review_state == "reviewed"
        assert claim.record_provenance == "user-created"
        assert repository.get_record(claim.record_id).record_type == "claim"
        assert service.list("trust_assessment") == ()

        fact = ConfirmedMemoryService(repository).create(
            subject="Confirmed fact",
            content="This is explicitly confirmed by the user.",
        )
        assessment = service.assess_trust(
            subject_type="confirmed_fact",
            subject_id=fact.record_id,
            level="trusted",
            reason="The user explicitly confirmed this fact.",
        )
        assert assessment.subject_type == "confirmed_fact"
        assert assessment.level == "trusted"
        assert assessment.record_provenance == "user-created"


def test_evidence_relations_are_typed_existing_and_disjoint(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ClaimEvidenceTrustService(repository)
        first = service.create_claim(title="First", statement="First claim.", source=user_source())
        second = service.create_claim(
            title="Second", statement="Second claim.", source=user_source()
        )
        evidence = service.create_evidence(
            title="Typed evidence",
            summary="The evidence has three explicit relation classes.",
            evidence_type="record",
            source=user_source(),
            supports_claim_ids=(first.record_id,),
            contextualizes_claim_ids=(second.record_id,),
        )
        assert evidence.supports_claim_ids == (first.record_id,)
        assert evidence.contextualizes_claim_ids == (second.record_id,)
        assert evidence.contradicts_claim_ids == ()

        before = repository.status().state_revision
        with pytest.raises(TruthValidationError, match="multiple"):
            service.create_evidence(
                title="Overlap",
                summary="Invalid overlap.",
                evidence_type="source",
                source=user_source(),
                supports_claim_ids=(first.record_id,),
                contradicts_claim_ids=(first.record_id,),
            )
        with pytest.raises(TruthValidationError, match="at least one"):
            service.create_evidence(
                title="Unlinked",
                summary="Evidence must be linked.",
                evidence_type="artifact",
                source=user_source(),
            )
        with pytest.raises(TruthValidationError, match="does not exist"):
            service.create_evidence(
                title="Missing",
                summary="Missing claim.",
                evidence_type="observation",
                source=user_source(),
                supports_claim_ids=(str(uuid4()),),
            )
        with pytest.raises(TruthValidationError, match="not claim"):
            service.create_evidence(
                title="Wrong type",
                summary="Wrong linked type.",
                evidence_type="record",
                source=user_source(),
                supports_claim_ids=(evidence.record_id,),
            )
        assert repository.status().state_revision == before


def test_inference_requires_typed_sources_and_never_becomes_fact(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ClaimEvidenceTrustService(repository)
        claim_id, evidence_id, _, _ = create_graph(service)
        inference = service.create_inference(
            title="High confidence inference",
            conclusion="High confidence remains an inference.",
            method="Synthetic deterministic method.",
            source=user_source(),
            claim_ids=(claim_id,),
            evidence_ids=(evidence_id,),
            confidence=1.0,
            review_state="reviewed",
        )
        assert inference.confidence == 1.0
        assert inference.review_state == "reviewed"
        assert repository.get_record(inference.record_id).record_type == "inference"

        with pytest.raises(TruthValidationError, match="at least one"):
            service.create_inference(
                title="No links",
                conclusion="Invalid.",
                method="None.",
                source=user_source(),
            )
        with pytest.raises(TruthValidationError, match="not evidence"):
            service.create_inference(
                title="Wrong evidence",
                conclusion="Invalid.",
                method="Wrong type.",
                source=user_source(),
                evidence_ids=(claim_id,),
            )


def test_trust_assessment_is_explicit_policy_bound_and_actor_restricted(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ClaimEvidenceTrustService(repository)
        claim = service.create_claim(
            title="Trust target", statement="Target claim.", source=user_source()
        )
        user = service.assess_trust(
            subject_type="claim",
            subject_id=claim.record_id,
            level="limited",
            reason="The claim has not been corroborated.",
        )
        assert user.assessor_type == "user"
        assert user.policy_reference is None

        with pytest.raises(TruthValidationError, match="policy"):
            service.assess_trust(
                subject_type="claim",
                subject_id=claim.record_id,
                level="unknown",
                reason="A system decision requires explicit policy.",
                assessor_type="system",
            )
        system = service.assess_trust(
            subject_type="source",
            subject_id="source-registry:synthetic",
            level="distrusted",
            reason="The synthetic policy marks this source as untrusted.",
            assessor_type="system",
            policy_reference="policy.synthetic.v1",
        )
        assert system.assessor_type == "system"
        assert system.record_provenance == "system-generated"

        with pytest.raises(ForbiddenTruthMutationError):
            service.assess_trust(
                subject_type="claim",
                subject_id=claim.record_id,
                level="trusted",
                reason="A model cannot assess trust.",
                assessor_type=cast(TrustAssessorType, "model"),
            )
        with pytest.raises(TruthValidationError, match="does not exist"):
            service.assess_trust(
                subject_type="claim",
                subject_id=str(uuid4()),
                level="unknown",
                reason="Missing subject.",
            )


def test_source_provenance_validation_keeps_missing_values_visible() -> None:
    unknown = TruthSource(origin_type="unknown", creator_actor_type="system")
    assert unknown.source_identifier is None
    assert unknown.observed_at is None
    assert unknown.source_content_hash is None

    matrix: tuple[dict[str, object], ...] = (
        {"origin_type": "user_statement", "creator_actor_type": "model"},
        {"origin_type": "imported_content", "creator_actor_type": "importer"},
        {
            "origin_type": "imported_content",
            "creator_actor_type": "user",
            "source_identifier": "x",
            "origin_operation_id": "op",
        },
        {"origin_type": "external_source", "creator_actor_type": "system"},
        {"origin_type": "tool_result", "creator_actor_type": "tool"},
        {
            "origin_type": "tool_result",
            "creator_actor_type": "runtime",
            "source_identifier": "x",
            "origin_operation_id": "op",
        },
        {"origin_type": "runtime_output", "creator_actor_type": "runtime"},
        {"origin_type": "model_proposal", "creator_actor_type": "model"},
        {"origin_type": "system_observation", "creator_actor_type": "model"},
        {"origin_type": "migrated", "creator_actor_type": "system"},
        {"origin_type": "restored", "creator_actor_type": "migration"},
        {"origin_type": "invented", "creator_actor_type": "system"},
        {"origin_type": "unknown", "creator_actor_type": "invented"},
        {"origin_type": "unknown", "creator_actor_type": "model"},
        {"origin_type": "external_source", "creator_actor_type": "tool", "source_identifier": "x"},
    )
    for values in matrix:
        with pytest.raises(TruthValidationError):
            TruthSource(**values)  # type: ignore[arg-type]

    with pytest.raises(TruthValidationError, match="sha256"):
        user_source(source_content_hash="sha256:bad")
    with pytest.raises(TruthValidationError, match="timezone"):
        user_source(observed_at="2026-06-20T00:00:00")
    with pytest.raises(TruthValidationError, match="ISO"):
        user_source(observed_at="invalid")
    with pytest.raises(TruthValidationError, match="unsafe"):
        user_source(transformation_method="password=synthetic-secret")


def test_non_user_records_must_begin_unreviewed(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ClaimEvidenceTrustService(repository)
        with pytest.raises(ForbiddenTruthMutationError):
            service.create_claim(
                title="Forbidden review",
                statement="A model cannot self-review.",
                source=model_source(),
                review_state="reviewed",
            )
        with pytest.raises(TruthValidationError, match="review note"):
            service.create_claim(
                title="Invalid note",
                statement="Unreviewed cannot carry a note.",
                source=user_source(),
                review_note="not reviewed",
            )
        assert repository.status().state_revision == 0


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"confidence": -0.1}, "confidence"),
        ({"confidence": 1.1}, "confidence"),
        ({"confidence": float("nan")}, "confidence"),
        ({"confidence": True}, "confidence"),
        ({"statement": ""}, "blank"),
        ({"statement": "/private/path"}, "unsafe"),
        ({"statement": "password=synthetic-secret"}, "unsafe"),
        ({"review_state": "invented"}, "review state"),
    ],
)
def test_claim_validation_rejects_hostile_values(
    tmp_path: Path,
    changes: dict[str, object],
    message: str,
) -> None:
    initialized = initialized_workspace(tmp_path)
    values: dict[str, object] = {
        "title": "Validation",
        "statement": "Valid claim.",
        "source": user_source(),
    }
    values.update(changes)
    with state.open_state_repository(initialized.root) as repository:
        with pytest.raises(TruthValidationError, match=message):
            ClaimEvidenceTrustService(repository).create_claim(**values)  # type: ignore[arg-type]
        assert repository.status().state_revision == 0


def test_archive_list_read_only_and_wrong_types(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ClaimEvidenceTrustService(repository)
        ids = create_graph(service)
        claim = service.get_claim(ids[0])
        archived = service.archive(claim.record_id, expected_revision=claim.revision)
        assert archived.status == "archived"
        assert service.list("claim") == ()
        assert service.list("claim", include_archived=True) == (archived,)
        with pytest.raises(ForbiddenTruthMutationError):
            service.archive(ids[1], expected_revision=1, actor_type="model")
        with pytest.raises(TruthValidationError):
            service.archive(claim.record_id, expected_revision=2)
        with pytest.raises(TruthValidationError, match="kind"):
            service.list(cast(TruthRecordKind, "bad"))
        with pytest.raises(TruthValidationError, match="limit"):
            service.list("claim", limit=0)
        with pytest.raises(TruthValidationError, match="limit"):
            service.list("claim", limit=True)
        with pytest.raises(TruthValidationError, match="not evidence"):
            service.get_evidence(ids[0])

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        service = ClaimEvidenceTrustService(repository)
        assert service.get_evidence(ids[1]).record_id == ids[1]
        with pytest.raises(state.ReadOnlyStateError):
            service.create_claim(title="Blocked", statement="Blocked.", source=user_source())
        with pytest.raises(state.ReadOnlyStateError):
            service.review(ids[1], expected_revision=1, review_state="reviewed")


def test_corrupt_records_are_normalized(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        malformed = repository.create_record(
            record_type="claim",
            title="Bad",
            provenance="model-proposed",
            metadata={
                "truth_kind": "claim",
                "title": "Bad",
                "statement": "Bad claim.",
                "confidence": 0.5,
                "uncertainty": None,
                "review_state": "reviewed",
                "reviewed_at": None,
                "reviewer_actor_type": None,
                "review_note": None,
                "origin_type": "model_proposal",
                "creator_actor_type": "model",
                "source_identifier": None,
                "observed_at": None,
                "source_content_hash": None,
                "transformation_method": None,
                "model_manifest_id": None,
                "runtime_adapter_id": None,
                "session_id": None,
                "origin_operation_id": None,
            },
        )
        with pytest.raises(TruthCorruptError):
            ClaimEvidenceTrustService(repository).get_claim(malformed.id)

        wrong = repository.create_record(record_type="other", metadata={})
        with pytest.raises(TruthValidationError, match="not claim"):
            ClaimEvidenceTrustService(repository).get_claim(wrong.id)


def test_database_failure_rolls_back_record_audit_and_revision(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        repository.connection.execute("DROP TABLE audit_events")
        with pytest.raises(state.StateCorruptError):
            ClaimEvidenceTrustService(repository).create_claim(
                title="Rollback",
                statement="This record must roll back.",
                source=user_source(),
            )
        row = repository.connection.execute(
            "SELECT COUNT(*) FROM records WHERE record_type = 'claim'"
        ).fetchone()
        assert row is not None and row[0] == 0
        assert repository.status().state_revision == 0
        assert repository.connection.in_transaction is False


def test_state_package_round_trip_preserves_truth_graph(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ClaimEvidenceTrustService(repository)
        ids = create_graph(service)
    package = tmp_path / "truth-state.doll.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        inspection = export_state_package(
            repository,
            package,
            exported_at="2026-06-20T03:00:00Z",
        )
    assert inspection.record_counts["claim"] == 1
    assert inspection.record_counts["evidence"] == 1
    assert inspection.record_counts["inference"] == 1
    assert inspection.record_counts["trust_assessment"] == 1
    assert inspection.omitted_secret_counts["claim"] == 0

    target = tmp_path / "imported"
    import_state_package(package, target)
    with state.open_state_repository(target, read_only=True) as repository:
        service = ClaimEvidenceTrustService(repository)
        assert service.get_claim(ids[0]).record_id == ids[0]
        assert service.get_evidence(ids[1]).supports_claim_ids == (ids[0],)
        inference = service.get_inference(ids[2])
        assert inference.claim_ids == (ids[0],)
        assert inference.evidence_ids == (ids[1],)
        trust = service.get_trust_assessment(ids[3])
        assert trust.subject_id == ids[1]


def test_typed_getters_and_review_return_types(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ClaimEvidenceTrustService(repository)
        claim_id, evidence_id, inference_id, trust_id = create_graph(service)
        evidence = service.get_evidence(evidence_id)
        inference = service.get_inference(inference_id)
        trust = service.get_trust_assessment(trust_id)
        assert isinstance(evidence, EvidenceInfo)
        assert isinstance(inference, InferenceInfo)
        assert isinstance(trust, TrustAssessmentInfo)

        reviewed_evidence = service.review(
            evidence_id,
            expected_revision=1,
            review_state="reviewed",
        )
        reviewed_inference = service.review(
            inference_id,
            expected_revision=1,
            review_state="rejected",
            review_note="The derivation is not accepted.",
        )
        assert isinstance(reviewed_evidence, EvidenceInfo)
        assert isinstance(reviewed_inference, InferenceInfo)

        with pytest.raises(KeyError):
            service.review(trust_id, expected_revision=1, review_state="reviewed")
        with pytest.raises(KeyError):
            service.archive(
                repository.create_record(record_type="other", metadata={}).id,
                expected_revision=1,
            )
        assert service.get_claim(claim_id).record_id == claim_id


def test_all_supported_origins_map_to_explicit_record_provenance(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    sources: tuple[tuple[TruthSource, str], ...] = (
        (user_source(), "user-created"),
        (imported_source(), "imported"),
        (model_source(), "model-proposed"),
        (
            TruthSource(
                origin_type="runtime_output",
                creator_actor_type="runtime",
                runtime_adapter_id="runtime-1",
                origin_operation_id="runtime-op",
            ),
            "system-generated",
        ),
        (
            TruthSource(
                origin_type="migrated",
                creator_actor_type="migration",
                source_identifier="migration-1",
            ),
            "migrated",
        ),
        (
            TruthSource(
                origin_type="restored",
                creator_actor_type="system",
                source_identifier="restore-1",
            ),
            "restored",
        ),
    )
    with state.open_state_repository(initialized.root) as repository:
        service = ClaimEvidenceTrustService(repository)
        for index, (source, expected) in enumerate(sources):
            claim = service.create_claim(
                title=f"Origin {index}",
                statement=f"Origin mapping {index}.",
                source=source,
            )
            assert claim.record_provenance == expected


def test_uuid_list_and_enum_validation(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ClaimEvidenceTrustService(repository)
        claim = service.create_claim(title="Claim", statement="Claim.", source=user_source())
        invalid_calls = (
            lambda: service.create_evidence(
                title="Bad enum",
                summary="Bad.",
                evidence_type=cast(EvidenceType, "bad"),
                source=user_source(),
                supports_claim_ids=(claim.record_id,),
            ),
            lambda: service.create_evidence(
                title="Duplicate",
                summary="Duplicate.",
                evidence_type="source",
                source=user_source(),
                supports_claim_ids=(claim.record_id, claim.record_id),
            ),
            lambda: service.create_evidence(
                title="String sequence",
                summary="Invalid sequence.",
                evidence_type="source",
                source=user_source(),
                supports_claim_ids=cast(Sequence[str], claim.record_id),
            ),
            lambda: service.assess_trust(
                subject_type=cast(TrustSubjectType, "bad"),
                subject_id=claim.record_id,
                level="unknown",
                reason="Bad subject.",
            ),
            lambda: service.assess_trust(
                subject_type="claim",
                subject_id=claim.record_id,
                level=cast(TrustLevel, "bad"),
                reason="Bad level.",
            ),
        )
        for call in invalid_calls:
            with pytest.raises(TruthValidationError):
                call()


def test_source_round_trip_normalizes_time_and_hash() -> None:
    source = model_source(
        observed_at="2026-06-20T10:00:00+09:00",
        source_content_hash="SHA256:" + "B" * 64,
    )
    assert source.observed_at == "2026-06-20T01:00:00Z"
    assert source.source_content_hash == "sha256:" + "b" * 64
    assert replace(source) == source
