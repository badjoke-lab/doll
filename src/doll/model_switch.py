"""Explicit local model switching with bounded smoke tests and rollback."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Literal

from doll.audit import AuditService
from doll.model_manifest import (
    ModelBindingInfo,
    ModelManifestInfo,
    ModelManifestService,
    ModelManifestValidationError,
    RuntimeManifestInfo,
    _runtime_fingerprint,
)
from doll.runtime_adapter import (
    LocalRuntimeBoundary,
    RuntimeCancellationToken,
    RuntimeFailureCode,
    RuntimeGenerationRequest,
)
from doll.state import ReadOnlyStateError, StateError
from doll.state_repository import StateRepository

ModelSwitchOutcome = Literal["switched", "preflight_failed", "rolled_back"]

_OPERATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$")
_MODEL_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
MODEL_SWITCH_PROBE_INPUT = (
    "purpose=local_model_switch_smoke_test\n"
    "Generate a brief plain-text acknowledgement that this local model can produce output. "
    "The response is discarded and grants no authority."
)
MODEL_SWITCH_PROBE_MAX_OUTPUT_CHARS = 2_048
MODEL_SWITCH_PROBE_TIMEOUT_SECONDS = 60.0
_MAX_BINDINGS = 500
_TARGET_STATES = frozenset({"candidate", "previous", "fallback", "disabled"})


class ModelSwitchError(StateError):
    """Base class for explicit model-switch failures."""


class ModelSwitchValidationError(ModelSwitchError):
    """Raised before activation when switch state is invalid."""


class DuplicateModelSwitchOperationError(ModelSwitchValidationError):
    """Raised when a switch operation ID has already started."""


class ModelSwitchRollbackError(ModelSwitchError):
    """Raised when a failed activated target cannot restore the previous binding."""


@dataclass(frozen=True, slots=True)
class ModelSwitchCandidate:
    """Bounded, non-secret view of one explicit switch target."""

    binding_id: str
    binding_revision: int
    binding_state: str
    runtime_manifest_id: str
    runtime_manifest_revision: int
    model_manifest_id: str
    model_manifest_revision: int
    smoke_test_status: str
    fallback_priority: int | None
    fallback_eligible: bool


@dataclass(frozen=True, slots=True)
class ModelSwitchResult:
    """Bounded identifiers and normalized outcome for one switch attempt."""

    operation_id: str
    scope_type: str
    scope_key_hash: str
    target_binding_id: str
    previous_binding_id: str
    active_binding_id: str
    target_runtime_manifest_id: str
    target_runtime_manifest_revision: int
    target_model_manifest_id: str
    target_model_manifest_revision: int
    outcome: ModelSwitchOutcome
    failure_code: RuntimeFailureCode | None
    fallback_selected: bool


def validate_model_switch_probe_output(value: object) -> bool:
    """Accept any non-empty bounded local generation result without semantic coupling."""

    return (
        isinstance(value, str)
        and bool(value.strip())
        and len(value) <= MODEL_SWITCH_PROBE_MAX_OUTPUT_CHARS
        and "\x00" not in value
    )


@dataclass(slots=True)
class ModelSwitchService:
    """Switch one explicit scope without automatic discovery or failover."""

    repository: StateRepository
    runtime_boundary: LocalRuntimeBoundary

    def __post_init__(self) -> None:
        if not isinstance(self.runtime_boundary, LocalRuntimeBoundary):
            raise ModelSwitchValidationError("runtime boundary is invalid")

    def list_switch_targets(
        self,
        *,
        scope_type: str,
        scope_key: str,
    ) -> tuple[ModelSwitchCandidate, ...]:
        manifests = ModelManifestService(self.repository)
        active, _, _ = self._resolve_active(manifests, scope_type, scope_key)
        candidates: list[ModelSwitchCandidate] = []
        for binding in manifests.list_bindings(limit=_MAX_BINDINGS):
            if (
                binding.binding_id == active.binding_id
                or binding.scope_type != active.scope_type
                or binding.scope_key != active.scope_key
                or binding.binding_state not in _TARGET_STATES
            ):
                continue
            try:
                _, runtime, model = manifests.resolve_binding(binding.binding_id)
                self._validate_adapter_declaration(runtime)
                _runtime_model_id(model.runtime_private_locator)
            except (ModelManifestValidationError, ModelSwitchValidationError):
                continue
            candidates.append(_candidate(binding))
        return tuple(sorted(candidates, key=lambda item: item.binding_id))

    def list_fallback_candidates(
        self,
        *,
        scope_type: str,
        scope_key: str,
    ) -> tuple[ModelSwitchCandidate, ...]:
        candidates = tuple(
            candidate
            for candidate in self.list_switch_targets(
                scope_type=scope_type,
                scope_key=scope_key,
            )
            if candidate.binding_state == "fallback"
            and candidate.fallback_eligible
            and candidate.fallback_priority is not None
            and candidate.smoke_test_status == "passed"
        )
        return tuple(
            sorted(
                candidates,
                key=lambda item: (item.fallback_priority or 0, item.binding_id),
            )
        )

    def switch_binding(
        self,
        *,
        scope_type: str,
        scope_key: str,
        target_binding_id: str,
        operation_id: str,
    ) -> ModelSwitchResult:
        return self._switch(
            scope_type=scope_type,
            scope_key=scope_key,
            target_binding_id=target_binding_id,
            operation_id=operation_id,
            require_fallback=False,
        )

    def switch_to_fallback(
        self,
        *,
        scope_type: str,
        scope_key: str,
        target_binding_id: str,
        operation_id: str,
    ) -> ModelSwitchResult:
        return self._switch(
            scope_type=scope_type,
            scope_key=scope_key,
            target_binding_id=target_binding_id,
            operation_id=operation_id,
            require_fallback=True,
        )

    def _switch(
        self,
        *,
        scope_type: str,
        scope_key: str,
        target_binding_id: str,
        operation_id: str,
        require_fallback: bool,
    ) -> ModelSwitchResult:
        if self.repository.read_only:
            raise ReadOnlyStateError("state repository is open in read-only mode")
        safe_operation_id = _operation_id(operation_id)
        manifests = ModelManifestService(self.repository)
        active, _, _ = self._resolve_active(manifests, scope_type, scope_key)
        target, runtime, model = self._resolve_target(
            manifests,
            active=active,
            target_binding_id=target_binding_id,
            require_fallback=require_fallback,
        )
        self._require_unused_operation(safe_operation_id)
        self._reserve_operation(
            operation_id=safe_operation_id,
            active=active,
            target=target,
            fallback_selected=require_fallback,
        )

        preflight_failure = self._probe(
            runtime,
            model,
            operation_id=f"{safe_operation_id}.preflight",
        )
        if preflight_failure is not None:
            target = manifests.set_smoke_test(
                target.binding_id,
                expected_revision=target.revision,
                status="failed",
                operation_id=f"{safe_operation_id}.smoke-failed",
            )
            self._complete_audit(
                operation_id=safe_operation_id,
                active_binding_id=active.binding_id,
                target_binding_id=target.binding_id,
                outcome="preflight_failed",
                failure_code=preflight_failure,
                fallback_selected=require_fallback,
            )
            return _result(
                operation_id=safe_operation_id,
                active=active,
                previous=active,
                target=target,
                runtime=runtime,
                model=model,
                outcome="preflight_failed",
                failure_code=preflight_failure,
                fallback_selected=require_fallback,
            )

        target = manifests.set_smoke_test(
            target.binding_id,
            expected_revision=target.revision,
            status="passed",
            operation_id=f"{safe_operation_id}.smoke-passed",
        )
        activated = manifests.activate_binding(
            target.binding_id,
            expected_revision=target.revision,
            operation_id=f"{safe_operation_id}.activate",
        )
        resolved = activated
        active_runtime = runtime
        active_model = model
        try:
            resolved, active_runtime, active_model = self._resolve_active(
                manifests,
                active.scope_type,
                active.scope_key,
            )
            if resolved.binding_id != activated.binding_id:
                raise ModelSwitchValidationError("activated binding did not become scope active")
            post_failure = self._probe(
                active_runtime,
                active_model,
                operation_id=f"{safe_operation_id}.post-activate",
            )
        except (KeyError, ModelManifestValidationError, ModelSwitchValidationError):
            post_failure = "invalid_response"
        if post_failure is None:
            self._complete_audit(
                operation_id=safe_operation_id,
                active_binding_id=resolved.binding_id,
                target_binding_id=target.binding_id,
                outcome="switched",
                failure_code=None,
                fallback_selected=require_fallback,
            )
            return _result(
                operation_id=safe_operation_id,
                active=resolved,
                previous=active,
                target=resolved,
                runtime=active_runtime,
                model=active_model,
                outcome="switched",
                failure_code=None,
                fallback_selected=require_fallback,
            )

        try:
            rolled_back = manifests.rollback_binding(
                activated.binding_id,
                expected_revision=activated.revision,
                reason="post-activation smoke test failed",
                operation_id=f"{safe_operation_id}.rollback",
            )
            rolled_back = manifests.set_smoke_test(
                rolled_back.binding_id,
                expected_revision=rolled_back.revision,
                status="failed",
                operation_id=f"{safe_operation_id}.post-failed",
            )
            try:
                restored, _, _ = manifests.resolve_active_binding(
                    scope_type=active.scope_type,
                    scope_key=active.scope_key,
                )
            except (KeyError, ModelManifestValidationError) as exc:
                raise ModelSwitchRollbackError("restored binding could not be revalidated") from exc
            if restored.binding_id != active.binding_id:
                raise ModelSwitchRollbackError("previous binding was not restored")
        except ModelSwitchRollbackError:
            raise
        except BaseException as exc:
            raise ModelSwitchRollbackError("model switch rollback did not complete") from exc

        self._complete_audit(
            operation_id=safe_operation_id,
            active_binding_id=restored.binding_id,
            target_binding_id=rolled_back.binding_id,
            outcome="rolled_back",
            failure_code=post_failure,
            fallback_selected=require_fallback,
        )
        return _result(
            operation_id=safe_operation_id,
            active=restored,
            previous=active,
            target=rolled_back,
            runtime=active_runtime,
            model=active_model,
            outcome="rolled_back",
            failure_code=post_failure,
            fallback_selected=require_fallback,
        )

    def _resolve_active(
        self,
        manifests: ModelManifestService,
        scope_type: str,
        scope_key: str,
    ) -> tuple[ModelBindingInfo, RuntimeManifestInfo, ModelManifestInfo]:
        try:
            active, runtime, model = manifests.resolve_active_binding(
                scope_type=scope_type,
                scope_key=scope_key,
            )
            self._validate_adapter_declaration(runtime)
            _runtime_model_id(model.runtime_private_locator)
            return active, runtime, model
        except (KeyError, ModelManifestValidationError) as exc:
            raise ModelSwitchValidationError("active local model binding is unavailable") from exc

    def _resolve_target(
        self,
        manifests: ModelManifestService,
        *,
        active: ModelBindingInfo,
        target_binding_id: str,
        require_fallback: bool,
    ) -> tuple[ModelBindingInfo, RuntimeManifestInfo, ModelManifestInfo]:
        try:
            target, runtime, model = manifests.resolve_binding(target_binding_id)
        except (KeyError, ModelManifestValidationError) as exc:
            raise ModelSwitchValidationError("target local model binding is unavailable") from exc
        if target.binding_id == active.binding_id:
            raise ModelSwitchValidationError("target binding is already active")
        if target.scope_type != active.scope_type or target.scope_key != active.scope_key:
            raise ModelSwitchValidationError("target binding belongs to another scope")
        if target.binding_state not in _TARGET_STATES:
            raise ModelSwitchValidationError("target binding cannot be switched from its state")
        if require_fallback and (
            target.binding_state != "fallback"
            or not target.fallback_eligible
            or target.fallback_priority is None
            or target.smoke_test_status != "passed"
        ):
            raise ModelSwitchValidationError("target binding is not an eligible fallback")
        self._validate_adapter_declaration(runtime)
        _runtime_model_id(model.runtime_private_locator)
        return target, runtime, model

    def _validate_adapter_declaration(self, runtime: RuntimeManifestInfo) -> None:
        declaration = self.runtime_boundary.declaration(runtime.adapter_id)
        if declaration is None:
            raise ModelSwitchValidationError("bound local runtime adapter is unavailable")
        operations = tuple(sorted({*declaration.supported_operations, "health", "cancel"}))
        fingerprint = _runtime_fingerprint(
            declaration.adapter_id,
            declaration.adapter_version,
            declaration.runtime_class,
            declaration.connection_kind,
            operations,
            declaration.offline_capable,
            declaration.cloud_fallback,
            declaration.automatic_download,
        )
        if (
            declaration.adapter_id != runtime.adapter_id
            or declaration.adapter_version != runtime.adapter_version
            or declaration.runtime_class != runtime.runtime_class
            or declaration.connection_kind != runtime.connection_kind
            or operations != runtime.operations
            or declaration.offline_capable != runtime.offline_capable
            or declaration.cloud_fallback != runtime.cloud_fallback
            or declaration.automatic_download != runtime.automatic_download
            or fingerprint != runtime.declaration_fingerprint
            or "generate" not in runtime.operations
        ):
            raise ModelSwitchValidationError(
                "bound runtime declaration does not match the manifest"
            )

    def _probe(
        self,
        runtime: RuntimeManifestInfo,
        model: ModelManifestInfo,
        *,
        operation_id: str,
    ) -> RuntimeFailureCode | None:
        result = self.runtime_boundary.generate(
            runtime.adapter_id,
            RuntimeGenerationRequest(
                operation_id=operation_id,
                model_id=_runtime_model_id(model.runtime_private_locator),
                input_text=MODEL_SWITCH_PROBE_INPUT,
                max_output_chars=MODEL_SWITCH_PROBE_MAX_OUTPUT_CHARS,
                timeout_seconds=MODEL_SWITCH_PROBE_TIMEOUT_SECONDS,
                cancellation=RuntimeCancellationToken(),
            ),
        )
        if result.outcome != "completed":
            return result.failure_code or "adapter_failure"
        if not validate_model_switch_probe_output(result.output_text):
            return "invalid_response"
        return None

    def _require_unused_operation(self, operation_id: str) -> None:
        row = self.repository.connection.execute(
            "SELECT 1 FROM audit_events WHERE operation_id = ? OR operation_id LIKE ? LIMIT 1",
            (operation_id, f"{operation_id}.%"),
        ).fetchone()
        if row is not None:
            raise DuplicateModelSwitchOperationError("model switch operation ID already exists")

    def _reserve_operation(
        self,
        *,
        operation_id: str,
        active: ModelBindingInfo,
        target: ModelBindingInfo,
        fallback_selected: bool,
    ) -> None:
        AuditService(self.repository).append(
            action="model_switch.begin",
            result="partial",
            actor_type="user",
            operation_id=operation_id,
            target_type="model_binding",
            target_id=target.binding_id,
            metadata={
                "scope_type": active.scope_type,
                "scope_key_hash": _scope_hash(active.scope_key),
                "active_binding_id": active.binding_id,
                "fallback_selected": fallback_selected,
            },
        )

    def _complete_audit(
        self,
        *,
        operation_id: str,
        active_binding_id: str,
        target_binding_id: str,
        outcome: ModelSwitchOutcome,
        failure_code: RuntimeFailureCode | None,
        fallback_selected: bool,
    ) -> None:
        metadata: dict[str, object] = {
            "active_binding_id": active_binding_id,
            "target_binding_id": target_binding_id,
            "outcome": outcome,
            "fallback_selected": fallback_selected,
        }
        if failure_code is not None:
            metadata["failure_code"] = failure_code
        AuditService(self.repository).append(
            action="model_switch.complete",
            result="success" if outcome == "switched" else "failed",
            actor_type="system",
            operation_id=operation_id,
            target_type="model_binding",
            target_id=target_binding_id,
            metadata=metadata,
        )


def _candidate(binding: ModelBindingInfo) -> ModelSwitchCandidate:
    return ModelSwitchCandidate(
        binding_id=binding.binding_id,
        binding_revision=binding.revision,
        binding_state=binding.binding_state,
        runtime_manifest_id=binding.runtime_manifest_id,
        runtime_manifest_revision=binding.runtime_manifest_revision,
        model_manifest_id=binding.model_manifest_id,
        model_manifest_revision=binding.model_manifest_revision,
        smoke_test_status=binding.smoke_test_status,
        fallback_priority=binding.fallback_priority,
        fallback_eligible=binding.fallback_eligible,
    )


def _result(
    *,
    operation_id: str,
    active: ModelBindingInfo,
    previous: ModelBindingInfo,
    target: ModelBindingInfo,
    runtime: RuntimeManifestInfo,
    model: ModelManifestInfo,
    outcome: ModelSwitchOutcome,
    failure_code: RuntimeFailureCode | None,
    fallback_selected: bool,
) -> ModelSwitchResult:
    return ModelSwitchResult(
        operation_id=operation_id,
        scope_type=active.scope_type,
        scope_key_hash=_scope_hash(active.scope_key),
        target_binding_id=target.binding_id,
        previous_binding_id=previous.binding_id,
        active_binding_id=active.binding_id,
        target_runtime_manifest_id=runtime.runtime_manifest_id,
        target_runtime_manifest_revision=runtime.revision,
        target_model_manifest_id=model.model_manifest_id,
        target_model_manifest_revision=model.revision,
        outcome=outcome,
        failure_code=failure_code,
        fallback_selected=fallback_selected,
    )


def _operation_id(value: object) -> str:
    if not isinstance(value, str) or not _OPERATION_ID.fullmatch(value):
        raise ModelSwitchValidationError("operation ID is invalid")
    return value


def _runtime_model_id(value: object) -> str:
    if not isinstance(value, str) or not _MODEL_ID.fullmatch(value):
        raise ModelSwitchValidationError(
            "bound model locator is not an adapter-facing model identifier"
        )
    return value


def _scope_hash(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"
