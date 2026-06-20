from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

import doll.trust as trust_module
from doll import state, workspace
from doll.state import (
    RecordEnvelope,
    RecordSensitivity,
)
from doll.trust import (
    ClaimEvidenceTrustService,
    ClaimInfo,
    EvidenceInfo,
    InferenceInfo,
    TrustAssessmentInfo,
    TruthCorruptError,
    TruthSource,
    TruthValidationError,
)


def initialized_repository(
    tmp_path: Path,
) -> tuple[workspace.InitializedWorkspace, state.StateRepository]:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized, state.open_state_repository(initialized.root)


def source() -> TruthSource:
    return TruthSource(origin_type="user_statement", creator_actor_type="user")


def create_records(
    service: ClaimEvidenceTrustService,
) -> tuple[ClaimInfo, EvidenceInfo, InferenceInfo, TrustAssessmentInfo]:
    claim = service.create_claim(title="Claim", statement="A valid claim.", source=source())
    evidence = service.create_evidence(
        title="Evidence",
        summary="A valid evidence record.",
        evidence_type="source",
        source=source(),
        supports_claim_ids=(claim.record_id,),
    )
    inference = service.create_inference(
        title="Inference",
        conclusion="A valid inference.",
        method="A deterministic synthetic method.",
        source=source(),
        claim_ids=(claim.record_id,),
        evidence_ids=(evidence.record_id,),
    )
    trust = service.assess_trust(
        subject_type="claim",
        subject_id=claim.record_id,
        level="limited",
        reason="Synthetic assessment.",
        evidence_ids=(evidence.record_id,),
    )
    return claim, evidence, inference, trust


def test_private_typed_parsers_reject_other_record_kinds(tmp_path: Path) -> None:
    _, repository = initialized_repository(tmp_path)
    with repository:
        service = ClaimEvidenceTrustService(repository)
        claim, evidence, inference, trust = create_records(service)
        claim_record = repository.get_record(claim.record_id)
        evidence_record = repository.get_record(evidence.record_id)
        inference_record = repository.get_record(inference.record_id)
        trust_record = repository.get_record(trust.record_id)
        with pytest.raises(TruthCorruptError, match="not a claim"):
            trust_module._claim_from_record(evidence_record)
        with pytest.raises(TruthCorruptError, match="not evidence"):
            trust_module._evidence_from_record(claim_record)
        with pytest.raises(TruthCorruptError, match="not an inference"):
            trust_module._inference_from_record(trust_record)
        with pytest.raises(TruthCorruptError, match="not a trust"):
            trust_module._trust_assessment_from_record(inference_record)


def test_corrupt_envelopes_and_common_fields_are_normalized(tmp_path: Path) -> None:
    _, repository = initialized_repository(tmp_path)
    with repository:
        service = ClaimEvidenceTrustService(repository)
        claim, _, _, _ = create_records(service)
        base = repository.get_record(claim.record_id)
        corruptions: tuple[RecordEnvelope, ...] = (
            replace(base, record_type="other"),
            replace(base, schema_version=2),
            replace(base, revision=0),
            replace(base, status="deleted"),
            replace(base, provenance="user-confirmed"),
            replace(base, sensitivity=cast(RecordSensitivity, "other")),
            replace(base, title="wrong"),
            replace(base, provenance="system-generated"),
            replace(base, metadata={**base.metadata, "truth_kind": "evidence"}),
            replace(base, metadata={**base.metadata, "truth_kind": "unknown"}),
            replace(base, metadata={**base.metadata, "statement": 1}),
            replace(base, metadata={**base.metadata, "uncertainty": 1}),
            replace(base, metadata={**base.metadata, "review_state": "reviewed"}),
        )
        for record in corruptions:
            with pytest.raises(TruthCorruptError):
                trust_module._parse_truth_record(record)


def test_corrupt_evidence_inference_and_trust_are_normalized(tmp_path: Path) -> None:
    _, repository = initialized_repository(tmp_path)
    with repository:
        service = ClaimEvidenceTrustService(repository)
        _, evidence, inference, trust = create_records(service)
        evidence_record = repository.get_record(evidence.record_id)
        inference_record = repository.get_record(inference.record_id)
        trust_record = repository.get_record(trust.record_id)
        records = (
            replace(
                evidence_record,
                metadata={**evidence_record.metadata, "evidence_type": "bad"},
            ),
            replace(
                evidence_record,
                metadata={
                    **evidence_record.metadata,
                    "supports_claim_ids": [],
                    "contradicts_claim_ids": [],
                    "contextualizes_claim_ids": [],
                },
            ),
            replace(
                evidence_record,
                metadata={**evidence_record.metadata, "supports_claim_ids": [1]},
            ),
            replace(
                evidence_record,
                metadata={**evidence_record.metadata, "supports_claim_ids": "bad"},
            ),
            replace(
                inference_record,
                metadata={**inference_record.metadata, "claim_ids": [], "evidence_ids": []},
            ),
            replace(trust_record, title="wrong"),
            replace(
                trust_record,
                metadata={
                    **trust_record.metadata,
                    "assessor_type": "system",
                    "policy_reference": None,
                },
                provenance="system-generated",
            ),
            replace(trust_record, provenance="system-generated"),
        )
        for record in records:
            with pytest.raises(TruthCorruptError):
                trust_module._parse_truth_record(record)


def test_malformed_confirmed_fact_subject_is_denied(tmp_path: Path) -> None:
    _, repository = initialized_repository(tmp_path)
    with repository:
        malformed = repository.create_record(
            record_type="memory",
            title="bad",
            provenance="user-confirmed",
            metadata={"memory_class": "confirmed"},
        )
        with pytest.raises(TruthValidationError, match="malformed"):
            ClaimEvidenceTrustService(repository).assess_trust(
                subject_type="confirmed_fact",
                subject_id=malformed.id,
                level="unknown",
                reason="Malformed memory cannot be trusted.",
            )


def test_validation_helpers_cover_type_length_control_and_uuid_failures() -> None:
    with pytest.raises(TruthValidationError, match="validated source"):
        trust_module._require_source(cast(TruthSource, object()))
    with pytest.raises(TruthValidationError, match="100 entries"):
        trust_module._validate_reference_ids("references", tuple(str(uuid4()) for _ in range(101)))
    with pytest.raises(TruthValidationError, match="non-string"):
        trust_module._metadata_reference_ids({"ids": [1]}, "ids")
    with pytest.raises(TruthValidationError, match="not a list"):
        trust_module._metadata_list({"ids": "bad"}, "ids")
    with pytest.raises(TruthValidationError, match="string"):
        trust_module._validate_optional_hash(1)
    with pytest.raises(TruthValidationError, match="string or null"):
        trust_module._validate_optional_utc("time", 1)
    with pytest.raises(TruthValidationError, match="must be a string"):
        trust_module._validate_text("text", 1, 20)
    with pytest.raises(TruthValidationError, match="exceeds"):
        trust_module._validate_text("text", "x" * 21, 20)
    with pytest.raises(TruthValidationError, match="control"):
        trust_module._validate_text("text", "a\x00b", 20)
    with pytest.raises(TruthValidationError, match="must be a string"):
        trust_module._validate_identifier("identifier", 1)
    with pytest.raises(TruthValidationError, match="blank"):
        trust_module._validate_identifier("identifier", "  ")
    with pytest.raises(TruthValidationError, match="exceeds"):
        trust_module._validate_identifier("identifier", "x" * 301)
    with pytest.raises(TruthValidationError, match="control"):
        trust_module._validate_identifier("identifier", "a\x00b")
    with pytest.raises(TruthValidationError, match="unsafe"):
        trust_module._validate_identifier("identifier", "/private/path")
    with pytest.raises(TruthValidationError, match="UUID string"):
        trust_module._validate_uuid("identifier", 1)
    with pytest.raises(TruthValidationError, match="UUID string"):
        trust_module._validate_uuid("identifier", "bad")
    noncanonical_uuid = "{" + str(uuid4()) + "}"
    with pytest.raises(TruthValidationError, match="canonical"):
        trust_module._validate_uuid("identifier", noncanonical_uuid)
    with pytest.raises(TruthValidationError, match="missing"):
        trust_module._required_string({}, "missing")
    with pytest.raises(TruthValidationError, match="invalid"):
        trust_module._optional_string({"value": 1}, "value")


def test_additional_source_origin_actor_mismatches() -> None:
    with pytest.raises(TruthValidationError, match="runtime creator"):
        TruthSource(
            origin_type="runtime_output",
            creator_actor_type="system",
            runtime_adapter_id="runtime",
            origin_operation_id="operation",
        )
    with pytest.raises(TruthValidationError, match="model creator"):
        TruthSource(
            origin_type="model_proposal",
            creator_actor_type="system",
            model_manifest_id="model",
            runtime_adapter_id="runtime",
            session_id="session",
            origin_operation_id="operation",
        )
    external = TruthSource(
        origin_type="external_source",
        creator_actor_type="system",
        source_identifier="source",
    )
    assert external.source_identifier == "source"


def test_update_validation_and_non_database_exception_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, repository = initialized_repository(tmp_path)
    with repository:
        service = ClaimEvidenceTrustService(repository)
        claim = service.create_claim(title="Claim", statement="Claim.", source=source())
        with pytest.raises(TruthValidationError, match="integer"):
            service.review(
                claim.record_id,
                expected_revision=cast(int, True),
                review_state="reviewed",
            )

        original = trust_module._insert_truth_audit

        def fail_audit(*args: object, **kwargs: object) -> None:
            del args, kwargs
            raise RuntimeError("synthetic failure")

        monkeypatch.setattr(trust_module, "_insert_truth_audit", fail_audit)
        before = repository.status().state_revision
        with pytest.raises(RuntimeError, match="synthetic"):
            service.create_claim(title="Rollback", statement="Rollback.", source=source())
        assert repository.status().state_revision == before
        assert repository.connection.in_transaction is False

        with pytest.raises(RuntimeError, match="synthetic"):
            service.review(claim.record_id, expected_revision=1, review_state="reviewed")
        assert service.get_claim(claim.record_id).revision == 1
        assert repository.connection.in_transaction is False
        monkeypatch.setattr(trust_module, "_insert_truth_audit", original)


def test_list_database_failure_is_normalized(tmp_path: Path) -> None:
    _, repository = initialized_repository(tmp_path)
    with repository:
        repository.connection.execute("DROP TABLE records")
        with pytest.raises(state.StateCorruptError, match="unreadable"):
            ClaimEvidenceTrustService(repository).list("claim")
