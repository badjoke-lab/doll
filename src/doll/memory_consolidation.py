"""Deterministic read-only memory consolidation candidate detection."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from doll.memory import ConfirmedMemoryInfo, ConfirmedMemoryService
from doll.state import StateError
from doll.state_repository import StateRepository

MemoryConsolidationCandidateKind = Literal[
    "exact_duplicate",
    "near_duplicate",
    "compatible_extension",
    "explicit_contradiction",
]
MemoryContentRelation = Literal[
    "equal",
    "left_contains_right",
    "right_contains_left",
    "none",
]

MEMORY_CONSOLIDATION_REPORT_SCHEMA_VERSION = 1
MEMORY_CONSOLIDATION_DETECTOR_ID = "deterministic-memory-review"
MEMORY_CONSOLIDATION_DETECTOR_VERSION = "1"
MEMORY_CONSOLIDATION_NORMALIZATION_ID = "unicode-nfkc-casefold-whitespace"
MEMORY_CONSOLIDATION_NORMALIZATION_VERSION = "1"
MAX_MEMORY_CONSOLIDATION_MEMORIES = 100
MAX_MEMORY_CONSOLIDATION_PAIRS = (
    MAX_MEMORY_CONSOLIDATION_MEMORIES * (MAX_MEMORY_CONSOLIDATION_MEMORIES - 1) // 2
)
MAX_MEMORY_CONSOLIDATION_CANDIDATES = 500
NEAR_DUPLICATE_NGRAM_SIZE = 3
NEAR_DUPLICATE_MIN_NORMALIZED_CHARS = 24
NEAR_DUPLICATE_THRESHOLD_BASIS_POINTS = 7800
COMPATIBLE_EXTENSION_MIN_CONTENT_CHARS = 12

_WHITESPACE_PATTERN = re.compile(r"\s+")
_KIND_ORDER: dict[MemoryConsolidationCandidateKind, int] = {
    "exact_duplicate": 0,
    "near_duplicate": 1,
    "compatible_extension": 2,
    "explicit_contradiction": 3,
}


class MemoryConsolidationError(StateError):
    """Base class for review-only memory consolidation detector failures."""


class MemoryConsolidationValidationError(MemoryConsolidationError):
    """Raised when a detector request cannot remain within the accepted boundary."""


@dataclass(frozen=True, slots=True)
class MemoryConsolidationCandidate:
    """One advisory pair candidate; it has no mutation authority."""

    kind: MemoryConsolidationCandidateKind
    left_memory_id: str
    left_memory_revision: int
    right_memory_id: str
    right_memory_revision: int
    subject_equal: bool
    content_relation: MemoryContentRelation
    lexical_overlap_basis_points: int | None
    explicit_contradiction_link: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "left_memory_id": self.left_memory_id,
            "left_memory_revision": self.left_memory_revision,
            "right_memory_id": self.right_memory_id,
            "right_memory_revision": self.right_memory_revision,
            "subject_equal": self.subject_equal,
            "content_relation": self.content_relation,
            "lexical_overlap_basis_points": self.lexical_overlap_basis_points,
            "explicit_contradiction_link": self.explicit_contradiction_link,
            "review_required": True,
            "authoritative_mutation": False,
        }


@dataclass(frozen=True, slots=True)
class MemoryConsolidationReport:
    """Bounded deterministic candidate report bound to one Doll State revision."""

    source_state_revision: int
    detector_id: str
    detector_version: str
    normalization_id: str
    normalization_version: str
    scanned_memories: int
    eligible_memories: int
    excluded_secret_memories: int
    evaluated_pairs: int
    scan_truncated: bool
    candidate_truncated: bool
    candidates: tuple[MemoryConsolidationCandidate, ...]

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": MEMORY_CONSOLIDATION_REPORT_SCHEMA_VERSION,
            "source_state_revision": self.source_state_revision,
            "detector_id": self.detector_id,
            "detector_version": self.detector_version,
            "normalization_id": self.normalization_id,
            "normalization_version": self.normalization_version,
            "maximum_memories": MAX_MEMORY_CONSOLIDATION_MEMORIES,
            "maximum_pairs": MAX_MEMORY_CONSOLIDATION_PAIRS,
            "maximum_candidates": MAX_MEMORY_CONSOLIDATION_CANDIDATES,
            "near_duplicate_ngram_size": NEAR_DUPLICATE_NGRAM_SIZE,
            "near_duplicate_threshold_basis_points": NEAR_DUPLICATE_THRESHOLD_BASIS_POINTS,
            "scanned_memories": self.scanned_memories,
            "eligible_memories": self.eligible_memories,
            "excluded_secret_memories": self.excluded_secret_memories,
            "evaluated_pairs": self.evaluated_pairs,
            "scan_truncated": self.scan_truncated,
            "candidate_truncated": self.candidate_truncated,
            "candidate_count": self.candidate_count,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "review_required": True,
            "automatic_memory_mutation": False,
        }


def detect_memory_consolidation_candidates(
    repository: StateRepository,
) -> MemoryConsolidationReport:
    """Return deterministic advisory candidates without changing authoritative memory."""

    if not repository.read_only:
        raise MemoryConsolidationValidationError(
            "memory consolidation detection requires a read-only repository"
        )
    source_state_revision = repository.status().state_revision
    memories = ConfirmedMemoryService(repository).list(
        limit=MAX_MEMORY_CONSOLIDATION_MEMORIES + 1,
    )
    scan_truncated = len(memories) > MAX_MEMORY_CONSOLIDATION_MEMORIES
    scanned = memories[:MAX_MEMORY_CONSOLIDATION_MEMORIES]
    eligible = tuple(memory for memory in scanned if memory.sensitivity != "secret")
    excluded_secret = len(scanned) - len(eligible)
    ordered = tuple(sorted(eligible, key=lambda memory: memory.record_id))

    candidates: list[MemoryConsolidationCandidate] = []
    evaluated_pairs = 0
    candidate_truncated = False
    stop = False
    for left_index, left in enumerate(ordered):
        if stop:
            break
        for right in ordered[left_index + 1 :]:
            evaluated_pairs += 1
            for candidate in _pair_candidates(left, right):
                if len(candidates) >= MAX_MEMORY_CONSOLIDATION_CANDIDATES:
                    candidate_truncated = True
                    stop = True
                    break
                candidates.append(candidate)
            if stop:
                break

    candidates.sort(
        key=lambda candidate: (
            candidate.left_memory_id,
            candidate.right_memory_id,
            _KIND_ORDER[candidate.kind],
        )
    )
    if repository.status().state_revision != source_state_revision:
        raise MemoryConsolidationValidationError(
            "Doll State changed during memory consolidation detection"
        )
    return MemoryConsolidationReport(
        source_state_revision=source_state_revision,
        detector_id=MEMORY_CONSOLIDATION_DETECTOR_ID,
        detector_version=MEMORY_CONSOLIDATION_DETECTOR_VERSION,
        normalization_id=MEMORY_CONSOLIDATION_NORMALIZATION_ID,
        normalization_version=MEMORY_CONSOLIDATION_NORMALIZATION_VERSION,
        scanned_memories=len(scanned),
        eligible_memories=len(eligible),
        excluded_secret_memories=excluded_secret,
        evaluated_pairs=evaluated_pairs,
        scan_truncated=scan_truncated,
        candidate_truncated=candidate_truncated,
        candidates=tuple(candidates),
    )


def _pair_candidates(
    left: ConfirmedMemoryInfo,
    right: ConfirmedMemoryInfo,
) -> tuple[MemoryConsolidationCandidate, ...]:
    left_subject = _normalize(left.subject)
    right_subject = _normalize(right.subject)
    left_content = _normalize(left.content)
    right_content = _normalize(right.content)
    subject_equal = left_subject == right_subject
    content_relation = _content_relation(left_content, right_content)
    explicit_contradiction = (
        right.record_id in left.contradicts_memory_ids
        or left.record_id in right.contradicts_memory_ids
    )
    pair_text_left = _pair_text(left_subject, left_content)
    pair_text_right = _pair_text(right_subject, right_content)
    overlap = _ngram_overlap_basis_points(pair_text_left, pair_text_right)

    kinds: list[MemoryConsolidationCandidateKind] = []
    if subject_equal and content_relation == "equal":
        kinds.append("exact_duplicate")
    elif _is_compatible_extension(subject_equal, left_content, right_content, content_relation):
        kinds.append("compatible_extension")
    elif _is_near_duplicate(pair_text_left, pair_text_right, overlap):
        kinds.append("near_duplicate")
    if explicit_contradiction:
        kinds.append("explicit_contradiction")

    return tuple(
        MemoryConsolidationCandidate(
            kind=kind,
            left_memory_id=left.record_id,
            left_memory_revision=left.revision,
            right_memory_id=right.record_id,
            right_memory_revision=right.revision,
            subject_equal=subject_equal,
            content_relation=content_relation,
            lexical_overlap_basis_points=overlap,
            explicit_contradiction_link=explicit_contradiction,
        )
        for kind in kinds
    )


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return _WHITESPACE_PATTERN.sub(" ", normalized).strip()


def _pair_text(subject: str, content: str) -> str:
    return f"{subject}\n{content}"


def _content_relation(left: str, right: str) -> MemoryContentRelation:
    if left == right:
        return "equal"
    if right in left:
        return "left_contains_right"
    if left in right:
        return "right_contains_left"
    return "none"


def _is_compatible_extension(
    subject_equal: bool,
    left_content: str,
    right_content: str,
    content_relation: MemoryContentRelation,
) -> bool:
    if not subject_equal or content_relation not in {
        "left_contains_right",
        "right_contains_left",
    }:
        return False
    shorter = min(len(left_content), len(right_content))
    return shorter >= COMPATIBLE_EXTENSION_MIN_CONTENT_CHARS


def _is_near_duplicate(left: str, right: str, overlap_basis_points: int) -> bool:
    if min(len(left), len(right)) < NEAR_DUPLICATE_MIN_NORMALIZED_CHARS:
        return False
    return overlap_basis_points >= NEAR_DUPLICATE_THRESHOLD_BASIS_POINTS


def _ngram_overlap_basis_points(left: str, right: str) -> int:
    left_ngrams = _ngrams(left)
    right_ngrams = _ngrams(right)
    union = left_ngrams | right_ngrams
    if not union:
        return 0
    intersection = left_ngrams & right_ngrams
    return len(intersection) * 10_000 // len(union)


def _ngrams(value: str) -> frozenset[str]:
    compact = value.replace(" ", "")
    if len(compact) < NEAR_DUPLICATE_NGRAM_SIZE:
        return frozenset({compact}) if compact else frozenset()
    return frozenset(
        compact[index : index + NEAR_DUPLICATE_NGRAM_SIZE]
        for index in range(len(compact) - NEAR_DUPLICATE_NGRAM_SIZE + 1)
    )
