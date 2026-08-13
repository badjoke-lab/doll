from __future__ import annotations

from doll import memory_consolidation as review


def test_imp_090_detector_edge_helpers_are_deterministic() -> None:
    assert review._content_relation("abc", "prefix abc suffix") == "right_contains_left"
    assert review._content_relation("prefix abc suffix", "abc") == "left_contains_right"
    assert review._is_compatible_extension(False, "long enough text", "long enough text plus", "right_contains_left") is False
    assert review._is_near_duplicate("short", "short", 10_000) is False
    assert review._ngram_overlap_basis_points("", "") == 0
    assert review._ngrams("") == frozenset()
    assert review._ngrams("ab") == frozenset({"ab"})
