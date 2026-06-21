"""Model-independent prompt-injection detection and context packaging."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, cast

from doll.instruction_origin import (
    InstructionAuthorityClass,
    InstructionAuthorityDecision,
    InstructionAuthorityPurpose,
    InstructionContextBundle,
    InstructionContextItem,
    InstructionOriginClass,
    InstructionOriginService,
    InstructionTransformation,
)
from doll.secret_detection import RedactionResult, redact_text

PromptInjectionFindingKind = Literal[
    "authority_override",
    "hidden_context_disclosure",
    "secret_exfiltration",
    "fake_approval",
    "policy_change",
    "risk_change",
    "scope_expansion",
    "unrelated_capability",
    "encoded_instruction",
    "instruction_metadata",
]
PromptInjectionConfidence = Literal["high", "medium"]
PromptContextField = Literal["title", "content", "source_identifier"]
PromptContextChannel = Literal[
    "system_policy",
    "current_user_instruction",
    "durable_user_policy",
    "user_management_action",
    "untrusted_content",
    "model_proposals",
    "unknown_origin",
]

DEFAULT_MAX_SCAN_CHARS = 65_536
DEFAULT_MAX_FINDINGS = 64
DEFAULT_MAX_CONTEXT_ITEMS = 64
DEFAULT_MAX_ITEM_CHARS = 16_000
DEFAULT_MAX_CONTEXT_CHARS = 65_536
MAX_CONFIGURED_SCAN_CHARS = 1_048_576
MAX_CONFIGURED_FINDINGS = 1_024
MAX_CONFIGURED_CONTEXT_ITEMS = 200
MAX_CONFIGURED_ITEM_CHARS = 65_536
MAX_CONFIGURED_CONTEXT_CHARS = 2_097_152
DETECTOR_VERSION = "prompt-injection-v1"


class PromptInjectionError(ValueError):
    """Base class for prompt-injection defense failures."""


class PromptInjectionValidationError(PromptInjectionError):
    """Raised when caller input or configured limits are invalid."""


class PromptContextLimitError(PromptInjectionError):
    """Raised when a complete safe context package cannot be produced."""


class PromptAuthorizationError(PromptInjectionError):
    """Raised when instruction origin does not authorize a requested purpose."""


@dataclass(frozen=True, slots=True)
class PromptInjectionFinding:
    """One advisory indicator without matched text or reconstruction material."""

    kind: PromptInjectionFindingKind
    confidence: PromptInjectionConfidence
    detector_id: str
    field: PromptContextField


@dataclass(frozen=True, slots=True)
class PromptInjectionScanResult:
    """Bounded advisory scan result."""

    findings: tuple[PromptInjectionFinding, ...]
    input_characters: int
    scanned_characters: int
    input_truncated: bool
    finding_limit_reached: bool

    @property
    def detected(self) -> bool:
        return bool(self.findings)


@dataclass(frozen=True, slots=True)
class PromptContextItem:
    """Secret-safe context item that preserves IMP-019 origin metadata."""

    record_id: str
    channel: PromptContextChannel
    title: str
    content: str
    origin_class: InstructionOriginClass
    declared_authority_class: InstructionAuthorityClass
    effective_authority_class: InstructionAuthorityClass
    data_only: bool
    authority_active: bool
    authority_failure: str | None
    source_identifier: str | None
    transformations: tuple[InstructionTransformation, ...]
    prompt_injection_findings: tuple[PromptInjectionFinding, ...]
    secret_redaction_count: int


@dataclass(frozen=True, slots=True)
class PromptContextPackage:
    """Complete structured context package; never a flattened trusted prompt."""

    system_policy: tuple[PromptContextItem, ...]
    current_user_instruction: tuple[PromptContextItem, ...]
    durable_user_policy: tuple[PromptContextItem, ...]
    user_management_action: tuple[PromptContextItem, ...]
    untrusted_content: tuple[PromptContextItem, ...]
    model_proposals: tuple[PromptContextItem, ...]
    unknown_origin: tuple[PromptContextItem, ...]
    total_items: int
    total_characters: int
    prompt_injection_finding_count: int
    secret_redaction_count: int
    detector_version: str = DETECTOR_VERSION


@dataclass(frozen=True, slots=True)
class _Detector:
    detector_id: str
    kind: PromptInjectionFindingKind
    confidence: PromptInjectionConfidence
    pattern: re.Pattern[str]
    metadata_only: bool = False


_DETECTORS = (
    _Detector(
        detector_id="authority-override-v1",
        kind="authority_override",
        confidence="high",
        pattern=re.compile(
            r"\b(?:ignore|disregard|override|bypass|forget)\b.{0,80}"
            r"\b(?:previous|prior|system|developer|user|security)\b.{0,40}"
            r"\b(?:instruction|policy|rule|message)s?\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    _Detector(
        detector_id="hidden-context-disclosure-v1",
        kind="hidden_context_disclosure",
        confidence="high",
        pattern=re.compile(
            r"\b(?:reveal|show|print|expose|repeat|dump|return)\b.{0,80}"
            r"\b(?:system prompt|hidden prompt|developer message|private context|memory|"
            r"internal instruction)s?\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    _Detector(
        detector_id="secret-exfiltration-v1",
        kind="secret_exfiltration",
        confidence="high",
        pattern=re.compile(
            r"\b(?:send|upload|post|transmit|reveal|expose|copy|forward)\b.{0,100}"
            r"\b(?:secret|credential|api[ _-]?key|access[ _-]?token|password|private key|"
            r"cookie|recovery phrase|local file)s?\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    _Detector(
        detector_id="fake-approval-v1",
        kind="fake_approval",
        confidence="high",
        pattern=re.compile(
            r"\b(?:user|administrator|admin|owner|security team)\b.{0,60}"
            r"\b(?:approved|authorized|confirmed|granted permission|already consented)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    _Detector(
        detector_id="policy-change-v1",
        kind="policy_change",
        confidence="high",
        pattern=re.compile(
            r"\b(?:change|disable|remove|replace|weaken|ignore|bypass)\b.{0,80}"
            r"\b(?:security policy|policy|permission|confirmation|safety rule)s?\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    _Detector(
        detector_id="risk-change-v1",
        kind="risk_change",
        confidence="high",
        pattern=re.compile(
            r"\b(?:lower|downgrade|reduce|change|override)\b.{0,50}"
            r"\b(?:risk tier|risk level|tier[ _-]?[0-9])\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    _Detector(
        detector_id="scope-expansion-v1",
        kind="scope_expansion",
        confidence="medium",
        pattern=re.compile(
            r"\b(?:widen|expand|broaden|unrestricted|all files|entire filesystem|"
            r"any host|any domain|full access)\b",
            re.IGNORECASE,
        ),
    ),
    _Detector(
        detector_id="unrelated-capability-v1",
        kind="unrelated_capability",
        confidence="medium",
        pattern=re.compile(
            r"\b(?:run|execute|call|invoke|launch|use)\b.{0,50}"
            r"\b(?:shell|terminal|command|tool|browser|network|email|upload|delete|"
            r"filesystem write|subprocess)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    _Detector(
        detector_id="encoded-instruction-v1",
        kind="encoded_instruction",
        confidence="medium",
        pattern=re.compile(
            r"\b(?:base64|rot13|hex|unicode|decode|deobfuscate)\b.{0,80}"
            r"\b(?:instruction|command|prompt|payload|message)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    _Detector(
        detector_id="instruction-metadata-v1",
        kind="instruction_metadata",
        confidence="medium",
        pattern=re.compile(
            r"(?:^|\b)(?:system|developer|assistant|administrator|instruction|policy)\s*[:=]",
            re.IGNORECASE,
        ),
        metadata_only=True,
    ),
)

_CHANNELS: tuple[PromptContextChannel, ...] = (
    "system_policy",
    "current_user_instruction",
    "durable_user_policy",
    "user_management_action",
    "untrusted_content",
    "model_proposals",
    "unknown_origin",
)


def scan_prompt_injection(
    text: str,
    *,
    field: PromptContextField = "content",
    max_scan_chars: int = DEFAULT_MAX_SCAN_CHARS,
    max_findings: int = DEFAULT_MAX_FINDINGS,
) -> PromptInjectionScanResult:
    """Scan only supplied text within bounds; findings remain advisory."""

    if not isinstance(text, str):
        raise PromptInjectionValidationError("prompt-injection input must be a string")
    safe_field = _validate_field(field)
    _validate_scan_limits(max_scan_chars=max_scan_chars, max_findings=max_findings)
    scanned = text[:max_scan_chars]
    findings: list[PromptInjectionFinding] = []
    limit_reached = False
    for detector in _DETECTORS:
        if detector.metadata_only and safe_field == "content":
            continue
        if detector.pattern.search(scanned) is None:
            continue
        findings.append(
            PromptInjectionFinding(
                kind=detector.kind,
                confidence=detector.confidence,
                detector_id=detector.detector_id,
                field=safe_field,
            )
        )
        if len(findings) >= max_findings:
            limit_reached = True
            break
    return PromptInjectionScanResult(
        findings=tuple(findings),
        input_characters=len(text),
        scanned_characters=len(scanned),
        input_truncated=len(text) > len(scanned),
        finding_limit_reached=limit_reached,
    )


@dataclass(slots=True)
class PromptDefenseService:
    """Build safe context packages and enforce authority outside any model."""

    instruction_origins: InstructionOriginService

    def package_context(
        self,
        record_ids: Sequence[str],
        *,
        max_items: int = DEFAULT_MAX_CONTEXT_ITEMS,
        max_item_chars: int = DEFAULT_MAX_ITEM_CHARS,
        max_total_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
        max_scan_chars: int = DEFAULT_MAX_SCAN_CHARS,
        max_findings: int = DEFAULT_MAX_FINDINGS,
    ) -> PromptContextPackage:
        _validate_package_limits(
            max_items=max_items,
            max_item_chars=max_item_chars,
            max_total_chars=max_total_chars,
        )
        _validate_scan_limits(max_scan_chars=max_scan_chars, max_findings=max_findings)
        if isinstance(record_ids, str | bytes):
            raise PromptInjectionValidationError("record IDs must be a sequence")
        ids = tuple(record_ids)
        if len(ids) > max_items:
            raise PromptContextLimitError(f"context item count exceeds {max_items}")
        bundle = self.instruction_origins.assemble_context(ids)
        packaged = _package_bundle(
            bundle,
            max_item_chars=max_item_chars,
            max_scan_chars=max_scan_chars,
            max_findings=max_findings,
        )
        all_items = tuple(item for channel in _CHANNELS for item in packaged[channel])
        if len(all_items) != len(ids):
            raise PromptInjectionValidationError("context package item count is inconsistent")
        total_characters = sum(_item_character_count(item) for item in all_items)
        if total_characters > max_total_chars:
            raise PromptContextLimitError(
                f"context character count exceeds {max_total_chars}; no package was returned"
            )
        return PromptContextPackage(
            system_policy=packaged["system_policy"],
            current_user_instruction=packaged["current_user_instruction"],
            durable_user_policy=packaged["durable_user_policy"],
            user_management_action=packaged["user_management_action"],
            untrusted_content=packaged["untrusted_content"],
            model_proposals=packaged["model_proposals"],
            unknown_origin=packaged["unknown_origin"],
            total_items=len(all_items),
            total_characters=total_characters,
            prompt_injection_finding_count=sum(
                len(item.prompt_injection_findings) for item in all_items
            ),
            secret_redaction_count=sum(item.secret_redaction_count for item in all_items),
        )

    def authority_decision(
        self,
        record_id: str,
        *,
        purpose: InstructionAuthorityPurpose,
    ) -> InstructionAuthorityDecision:
        """Return the IMP-019 decision without consulting detector or model output."""

        return self.instruction_origins.authority_decision(record_id, purpose=purpose)

    def require_authority(
        self,
        record_id: str,
        *,
        purpose: InstructionAuthorityPurpose,
    ) -> InstructionAuthorityDecision:
        decision = self.authority_decision(record_id, purpose=purpose)
        if not decision.allowed:
            raise PromptAuthorizationError(decision.reason)
        return decision


def package_instruction_context(
    bundle: InstructionContextBundle,
    *,
    max_item_chars: int = DEFAULT_MAX_ITEM_CHARS,
    max_total_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
    max_scan_chars: int = DEFAULT_MAX_SCAN_CHARS,
    max_findings: int = DEFAULT_MAX_FINDINGS,
) -> PromptContextPackage:
    """Package a validated IMP-019 bundle without persistence or model execution."""

    _validate_package_limits(
        max_items=MAX_CONFIGURED_CONTEXT_ITEMS,
        max_item_chars=max_item_chars,
        max_total_chars=max_total_chars,
    )
    _validate_scan_limits(max_scan_chars=max_scan_chars, max_findings=max_findings)
    if not isinstance(bundle, InstructionContextBundle):
        raise PromptInjectionValidationError("bundle must be an InstructionContextBundle")
    packaged = _package_bundle(
        bundle,
        max_item_chars=max_item_chars,
        max_scan_chars=max_scan_chars,
        max_findings=max_findings,
    )
    all_items = tuple(item for channel in _CHANNELS for item in packaged[channel])
    total_characters = sum(_item_character_count(item) for item in all_items)
    if total_characters > max_total_chars:
        raise PromptContextLimitError(
            f"context character count exceeds {max_total_chars}; no package was returned"
        )
    return PromptContextPackage(
        system_policy=packaged["system_policy"],
        current_user_instruction=packaged["current_user_instruction"],
        durable_user_policy=packaged["durable_user_policy"],
        user_management_action=packaged["user_management_action"],
        untrusted_content=packaged["untrusted_content"],
        model_proposals=packaged["model_proposals"],
        unknown_origin=packaged["unknown_origin"],
        total_items=len(all_items),
        total_characters=total_characters,
        prompt_injection_finding_count=sum(
            len(item.prompt_injection_findings) for item in all_items
        ),
        secret_redaction_count=sum(item.secret_redaction_count for item in all_items),
    )


def _package_bundle(
    bundle: InstructionContextBundle,
    *,
    max_item_chars: int,
    max_scan_chars: int,
    max_findings: int,
) -> dict[PromptContextChannel, tuple[PromptContextItem, ...]]:
    source_channels: dict[PromptContextChannel, tuple[InstructionContextItem, ...]] = {
        "system_policy": bundle.system_policy,
        "current_user_instruction": bundle.current_user_instruction,
        "durable_user_policy": bundle.durable_user_policy,
        "user_management_action": bundle.user_management_action,
        "untrusted_content": bundle.untrusted_content,
        "model_proposals": bundle.model_proposals,
        "unknown_origin": bundle.unknown_origin,
    }
    return {
        channel: tuple(
            _package_item(
                item,
                channel=channel,
                max_item_chars=max_item_chars,
                max_scan_chars=max_scan_chars,
                max_findings=max_findings,
            )
            for item in source_channels[channel]
        )
        for channel in _CHANNELS
    }


def _package_item(
    item: InstructionContextItem,
    *,
    channel: PromptContextChannel,
    max_item_chars: int,
    max_scan_chars: int,
    max_findings: int,
) -> PromptContextItem:
    if len(item.title) > max_item_chars or len(item.content) > max_item_chars:
        raise PromptContextLimitError(
            f"instruction-origin record {item.record_id} exceeds the per-item character limit"
        )
    title = _safe_field(
        item.title,
        field="title",
        max_scan_chars=max_scan_chars,
        max_findings=max_findings,
    )
    content = _safe_field(
        item.content,
        field="content",
        max_scan_chars=max_scan_chars,
        max_findings=max_findings,
    )
    source = None
    source_findings: tuple[PromptInjectionFinding, ...] = ()
    source_secret_count = 0
    if item.source_identifier is not None:
        source_value = _safe_field(
            item.source_identifier,
            field="source_identifier",
            max_scan_chars=max_scan_chars,
            max_findings=max_findings,
        )
        source = source_value.text
        source_findings = source_value.findings
        source_secret_count = source_value.secret_redaction_count
    findings = title.findings + content.findings + source_findings
    if len(findings) > max_findings:
        raise PromptContextLimitError(
            f"instruction-origin record {item.record_id} exceeds the finding limit"
        )
    return PromptContextItem(
        record_id=item.record_id,
        channel=channel,
        title=title.text,
        content=content.text,
        origin_class=item.origin_class,
        declared_authority_class=item.declared_authority_class,
        effective_authority_class=item.effective_authority_class,
        data_only=item.data_only,
        authority_active=item.authority_active,
        authority_failure=item.authority_failure,
        source_identifier=source,
        transformations=item.transformations,
        prompt_injection_findings=findings,
        secret_redaction_count=(
            title.secret_redaction_count + content.secret_redaction_count + source_secret_count
        ),
    )


@dataclass(frozen=True, slots=True)
class _SafeField:
    text: str
    findings: tuple[PromptInjectionFinding, ...]
    secret_redaction_count: int


def _safe_field(
    text: str,
    *,
    field: PromptContextField,
    max_scan_chars: int,
    max_findings: int,
) -> _SafeField:
    redaction = redact_text(
        text,
        max_scan_chars=max_scan_chars,
        max_findings=max_findings,
    )
    _require_complete_redaction(redaction, field=field)
    scan = scan_prompt_injection(
        redaction.redacted_text,
        field=field,
        max_scan_chars=max_scan_chars,
        max_findings=max_findings,
    )
    if scan.input_truncated or scan.finding_limit_reached:
        raise PromptContextLimitError(
            f"{field} could not be completely scanned; no context package was returned"
        )
    return _SafeField(
        text=redaction.redacted_text,
        findings=scan.findings,
        secret_redaction_count=len(redaction.findings),
    )


def _require_complete_redaction(result: RedactionResult, *, field: PromptContextField) -> None:
    if result.input_truncated or result.finding_limit_reached:
        raise PromptContextLimitError(
            f"{field} could not be completely secret-scanned; no context package was returned"
        )


def _item_character_count(item: PromptContextItem) -> int:
    return len(item.title) + len(item.content) + len(item.source_identifier or "")


def _validate_field(value: object) -> PromptContextField:
    if value not in {"title", "content", "source_identifier"}:
        raise PromptInjectionValidationError("invalid prompt context field")
    return cast(PromptContextField, value)


def _validate_scan_limits(*, max_scan_chars: int, max_findings: int) -> None:
    if (
        isinstance(max_scan_chars, bool)
        or not isinstance(max_scan_chars, int)
        or not 1 <= max_scan_chars <= MAX_CONFIGURED_SCAN_CHARS
    ):
        raise PromptInjectionValidationError(
            f"max_scan_chars must be between 1 and {MAX_CONFIGURED_SCAN_CHARS}"
        )
    if (
        isinstance(max_findings, bool)
        or not isinstance(max_findings, int)
        or not 1 <= max_findings <= MAX_CONFIGURED_FINDINGS
    ):
        raise PromptInjectionValidationError(
            f"max_findings must be between 1 and {MAX_CONFIGURED_FINDINGS}"
        )


def _validate_package_limits(
    *,
    max_items: int,
    max_item_chars: int,
    max_total_chars: int,
) -> None:
    if (
        isinstance(max_items, bool)
        or not isinstance(max_items, int)
        or not 1 <= max_items <= MAX_CONFIGURED_CONTEXT_ITEMS
    ):
        raise PromptInjectionValidationError(
            f"max_items must be between 1 and {MAX_CONFIGURED_CONTEXT_ITEMS}"
        )
    if (
        isinstance(max_item_chars, bool)
        or not isinstance(max_item_chars, int)
        or not 1 <= max_item_chars <= MAX_CONFIGURED_ITEM_CHARS
    ):
        raise PromptInjectionValidationError(
            f"max_item_chars must be between 1 and {MAX_CONFIGURED_ITEM_CHARS}"
        )
    if (
        isinstance(max_total_chars, bool)
        or not isinstance(max_total_chars, int)
        or not 1 <= max_total_chars <= MAX_CONFIGURED_CONTEXT_CHARS
    ):
        raise PromptInjectionValidationError(
            f"max_total_chars must be between 1 and {MAX_CONFIGURED_CONTEXT_CHARS}"
        )


__all__ = [
    "DEFAULT_MAX_CONTEXT_CHARS",
    "DEFAULT_MAX_CONTEXT_ITEMS",
    "DEFAULT_MAX_FINDINGS",
    "DEFAULT_MAX_ITEM_CHARS",
    "DEFAULT_MAX_SCAN_CHARS",
    "DETECTOR_VERSION",
    "PromptAuthorizationError",
    "PromptContextChannel",
    "PromptContextField",
    "PromptContextItem",
    "PromptContextLimitError",
    "PromptContextPackage",
    "PromptDefenseService",
    "PromptInjectionConfidence",
    "PromptInjectionError",
    "PromptInjectionFinding",
    "PromptInjectionFindingKind",
    "PromptInjectionScanResult",
    "PromptInjectionValidationError",
    "package_instruction_context",
    "scan_prompt_injection",
]
