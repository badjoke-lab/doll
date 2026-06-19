"""Bounded best-effort secret detection and deterministic redaction."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

SecretFindingKind = Literal[
    "authorization_header",
    "credential_assignment",
    "known_token",
    "private_key",
    "recovery_phrase",
    "session_cookie",
    "personal_email",
    "personal_phone",
    "private_path",
]
SecretFindingConfidence = Literal["high", "medium"]

DEFAULT_MAX_SCAN_CHARS = 65_536
DEFAULT_MAX_FINDINGS = 64
MAX_CONFIGURED_SCAN_CHARS = 1_048_576
MAX_CONFIGURED_FINDINGS = 1_024
_SCAN_LIMIT_MARKER = "[REDACTION_SCAN_LIMIT_REACHED]"
_FINDING_LIMIT_MARKER = "[REDACTION_FINDING_LIMIT_REACHED]"


@dataclass(frozen=True, slots=True)
class SecretFinding:
    """One non-secret finding descriptor.

    The matched value is deliberately absent. Offsets apply only to the bounded
    input prefix inspected by :func:`scan_secrets`.
    """

    kind: SecretFindingKind
    confidence: SecretFindingConfidence
    detector_id: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class SecretScanResult:
    """Structured result for one bounded in-memory scan."""

    findings: tuple[SecretFinding, ...]
    input_characters: int
    scanned_characters: int
    input_truncated: bool
    finding_limit_reached: bool

    @property
    def detected(self) -> bool:
        return bool(self.findings)


@dataclass(frozen=True, slots=True)
class RedactionResult:
    """Secret-safe redacted text and non-secret scan metadata."""

    redacted_text: str
    findings: tuple[SecretFinding, ...]
    input_characters: int
    scanned_characters: int
    input_truncated: bool
    finding_limit_reached: bool

    @property
    def changed(self) -> bool:
        return bool(self.findings) or self.input_truncated


@dataclass(frozen=True, slots=True)
class _Detector:
    detector_id: str
    kind: SecretFindingKind
    confidence: SecretFindingConfidence
    pattern: re.Pattern[str]
    value_group: str | None = None


_CREDENTIAL_NAMES = (
    r"password|passwd|passphrase|api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"client[_-]?secret|secret[_-]?key|session[_-]?(?:id|token|cookie)|private[_-]?key"
)

_DETECTORS = (
    _Detector(
        detector_id="private-key-block-v1",
        kind="private_key",
        confidence="high",
        pattern=re.compile(
            r"-----BEGIN (?P<label>(?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY)-----"
            r"[\s\S]{0,16384}?"
            r"-----END (?P=label)-----",
            re.IGNORECASE,
        ),
    ),
    _Detector(
        detector_id="authorization-header-v1",
        kind="authorization_header",
        confidence="high",
        pattern=re.compile(
            r"\bauthorization\s*:\s*(?:bearer|basic)\s+"
            r"(?P<secret>[A-Za-z0-9._~+/=-]{8,2048})",
            re.IGNORECASE | re.MULTILINE,
        ),
        value_group="secret",
    ),
    _Detector(
        detector_id="cookie-header-v1",
        kind="session_cookie",
        confidence="high",
        pattern=re.compile(
            r"\b(?:set-cookie|cookie)\s*:\s*(?P<secret>[^\r\n]{4,2048})",
            re.IGNORECASE | re.MULTILINE,
        ),
        value_group="secret",
    ),
    _Detector(
        detector_id="recovery-phrase-v1",
        kind="recovery_phrase",
        confidence="high",
        pattern=re.compile(
            r"\b(?:seed|recovery|mnemonic)(?:\s+phrase)?\s*[:=]\s*"
            r"(?P<secret>(?:[a-z]{2,16}[ \t]+){11,23}[a-z]{2,16})",
            re.IGNORECASE | re.MULTILINE,
        ),
        value_group="secret",
    ),
    _Detector(
        detector_id="credential-assignment-quoted-v1",
        kind="credential_assignment",
        confidence="high",
        pattern=re.compile(
            rf"\b(?:{_CREDENTIAL_NAMES})\b\s*[:=]\s*[\"']"
            r"(?P<secret>[^\"'\r\n]{4,2048})[\"']",
            re.IGNORECASE,
        ),
        value_group="secret",
    ),
    _Detector(
        detector_id="credential-assignment-bare-v1",
        kind="credential_assignment",
        confidence="high",
        pattern=re.compile(
            rf"\b(?:{_CREDENTIAL_NAMES})\b\s*[:=]\s*"
            r"(?P<secret>[^\s,;}\]\r\n]{4,2048})",
            re.IGNORECASE,
        ),
        value_group="secret",
    ),
    _Detector(
        detector_id="known-token-v1",
        kind="known_token",
        confidence="high",
        pattern=re.compile(
            r"\b(?:sk-[A-Za-z0-9_-]{16,255}|"
            r"gh[pousr]_[A-Za-z0-9]{20,255}|"
            r"github_pat_[A-Za-z0-9_]{20,255})\b"
        ),
    ),
    _Detector(
        detector_id="jwt-v1",
        kind="known_token",
        confidence="medium",
        pattern=re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    ),
    _Detector(
        detector_id="email-address-v1",
        kind="personal_email",
        confidence="medium",
        pattern=re.compile(
            r"\b[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}"
            r"@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,63}\b"
        ),
    ),
    _Detector(
        detector_id="labeled-phone-v1",
        kind="personal_phone",
        confidence="medium",
        pattern=re.compile(
            r"\b(?:phone|mobile|tel(?:ephone)?)\s*[:=]\s*"
            r"(?P<secret>\+?[0-9][0-9(). \-]{6,24}[0-9])",
            re.IGNORECASE,
        ),
        value_group="secret",
    ),
    _Detector(
        detector_id="unix-home-path-v1",
        kind="private_path",
        confidence="medium",
        pattern=re.compile(r"/(?:Users|home)/[^/\s:]+(?:/[^\s:;,]*)?"),
    ),
    _Detector(
        detector_id="windows-home-path-v1",
        kind="private_path",
        confidence="medium",
        pattern=re.compile(
            r"[A-Za-z]:\\Users\\[^\\\s:]+(?:\\[^\s:;,]*)?",
            re.IGNORECASE,
        ),
    ),
)


def scan_secrets(
    text: str,
    *,
    max_scan_chars: int = DEFAULT_MAX_SCAN_CHARS,
    max_findings: int = DEFAULT_MAX_FINDINGS,
) -> SecretScanResult:
    """Inspect only the supplied text prefix within explicit resource bounds."""

    _validate_limits(max_scan_chars=max_scan_chars, max_findings=max_findings)
    input_characters = len(text)
    scanned_text = text[:max_scan_chars]
    raw_findings: list[SecretFinding] = []
    raw_limit = max_findings * 4
    raw_limit_reached = False

    for detector in _DETECTORS:
        for match in detector.pattern.finditer(scanned_text):
            start, end = match.span(detector.value_group or 0)
            if start == end:
                continue
            raw_findings.append(
                SecretFinding(
                    kind=detector.kind,
                    confidence=detector.confidence,
                    detector_id=detector.detector_id,
                    start=start,
                    end=end,
                )
            )
            if len(raw_findings) >= raw_limit:
                raw_limit_reached = True
                break
        if raw_limit_reached:
            break

    findings = _normalize_findings(raw_findings)
    finding_limit_reached = raw_limit_reached or len(findings) > max_findings
    return SecretScanResult(
        findings=tuple(findings[:max_findings]),
        input_characters=input_characters,
        scanned_characters=len(scanned_text),
        input_truncated=input_characters > len(scanned_text),
        finding_limit_reached=finding_limit_reached,
    )


def redact_text(
    text: str,
    *,
    max_scan_chars: int = DEFAULT_MAX_SCAN_CHARS,
    max_findings: int = DEFAULT_MAX_FINDINGS,
) -> RedactionResult:
    """Redact detected spans and return no original text when limits are reached."""

    scan = scan_secrets(
        text,
        max_scan_chars=max_scan_chars,
        max_findings=max_findings,
    )
    if scan.finding_limit_reached:
        return RedactionResult(
            redacted_text=_FINDING_LIMIT_MARKER,
            findings=scan.findings,
            input_characters=scan.input_characters,
            scanned_characters=scan.scanned_characters,
            input_truncated=scan.input_truncated,
            finding_limit_reached=True,
        )
    if scan.input_truncated:
        return RedactionResult(
            redacted_text=_SCAN_LIMIT_MARKER,
            findings=scan.findings,
            input_characters=scan.input_characters,
            scanned_characters=scan.scanned_characters,
            input_truncated=True,
            finding_limit_reached=False,
        )
    parts: list[str] = []
    cursor = 0
    for finding in scan.findings:
        parts.append(text[cursor : finding.start])
        parts.append(f"[REDACTED:{finding.kind}]")
        cursor = finding.end
    parts.append(text[cursor:])
    return RedactionResult(
        redacted_text="".join(parts),
        findings=scan.findings,
        input_characters=scan.input_characters,
        scanned_characters=scan.scanned_characters,
        input_truncated=False,
        finding_limit_reached=False,
    )


def _normalize_findings(findings: list[SecretFinding]) -> list[SecretFinding]:
    ordered = sorted(
        findings,
        key=lambda item: (
            item.start,
            -item.end,
            _confidence_rank(item.confidence),
            item.detector_id,
        ),
    )
    normalized: list[SecretFinding] = []
    for finding in ordered:
        if not normalized or finding.start >= normalized[-1].end:
            normalized.append(finding)
            continue
        previous = normalized[-1]
        preferred = _preferred_finding(previous, finding)
        normalized[-1] = SecretFinding(
            kind=preferred.kind,
            confidence=preferred.confidence,
            detector_id=preferred.detector_id,
            start=min(previous.start, finding.start),
            end=max(previous.end, finding.end),
        )
    return normalized


def _preferred_finding(first: SecretFinding, second: SecretFinding) -> SecretFinding:
    first_key = (
        _confidence_rank(first.confidence),
        -(first.end - first.start),
        first.detector_id,
    )
    second_key = (
        _confidence_rank(second.confidence),
        -(second.end - second.start),
        second.detector_id,
    )
    return first if first_key <= second_key else second


def _confidence_rank(confidence: SecretFindingConfidence) -> int:
    return 0 if confidence == "high" else 1


def _validate_limits(*, max_scan_chars: int, max_findings: int) -> None:
    if not 1 <= max_scan_chars <= MAX_CONFIGURED_SCAN_CHARS:
        raise ValueError(f"max_scan_chars must be between 1 and {MAX_CONFIGURED_SCAN_CHARS}")
    if not 1 <= max_findings <= MAX_CONFIGURED_FINDINGS:
        raise ValueError(f"max_findings must be between 1 and {MAX_CONFIGURED_FINDINGS}")


__all__ = [
    "DEFAULT_MAX_FINDINGS",
    "DEFAULT_MAX_SCAN_CHARS",
    "MAX_CONFIGURED_FINDINGS",
    "MAX_CONFIGURED_SCAN_CHARS",
    "RedactionResult",
    "SecretFinding",
    "SecretFindingConfidence",
    "SecretFindingKind",
    "SecretScanResult",
    "redact_text",
    "scan_secrets",
]
