from __future__ import annotations

from pathlib import Path

from doll import state, workspace
from doll.memory import ConfirmedMemoryService
from doll.recall_benchmark import (
    RecallBenchmarkCaseResult,
    RecallBenchmarkReport,
    load_recall_benchmark_corpus,
    populate_synthetic_recall_benchmark,
    run_recall_benchmark,
)
from doll.recall_index import build_memory_lexical_index, memory_lexical_index_path

_CORPUS_PATH = (
    Path(__file__).parents[1] / "docs" / "testing" / "imp-087-memory-recall-benchmark-corpus.json"
)


def _initialized_workspace(root: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(root)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _populate(root: Path) -> tuple[workspace.InitializedWorkspace, object, object]:
    corpus = load_recall_benchmark_corpus(_CORPUS_PATH)
    initialized = _initialized_workspace(root)
    with state.open_state_repository(initialized.root) as repository:
        bindings = populate_synthetic_recall_benchmark(repository, corpus)
    return initialized, corpus, bindings


def _case(report: RecallBenchmarkReport, case_id: str) -> RecallBenchmarkCaseResult:
    return next(case for case in report.cases if case.case_id == case_id)


def test_imp_087_baseline_measures_lexical_strength_and_semantic_opportunity(
    tmp_path: Path,
) -> None:
    initialized, corpus, bindings = _populate(tmp_path / "workspace")

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        state_revision_before = repository.status().state_revision
        build_memory_lexical_index(repository)
        report = run_recall_benchmark(repository, corpus, bindings)

        assert report.corpus_id == "imp-087-memory-recall-baseline-v1"
        assert report.recall_algorithm_id == "weighted-memory-fields"
        assert report.recall_algorithm_version == "1"
        assert report.lexical_case_count == 6
        assert report.lexical_recall_at_1 == "1"
        assert report.lexical_recall_at_3 == "1"
        assert report.lexical_mrr == "1"
        assert report.semantic_opportunity_case_count == 2
        assert report.semantic_opportunity_miss_count == 2
        assert report.semantic_opportunity_miss_rate == "1"
        assert report.exclusion_case_count == 2
        assert report.exclusion_pass_count == 2
        assert report.index_status == "available"
        assert report.index_error_type is None
        assert report.index_compatible_lexical_case_count == 5
        assert report.index_coverage == "1"
        assert _case(report, "lexical-substring-fallback").expected_rank == 1
        assert _case(report, "lexical-substring-fallback").index_returned_labels == ()
        assert _case(report, "semantic-vehicle-paraphrase").expected_rank is None
        assert _case(report, "semantic-grocery-paraphrase").expected_rank is None
        assert _case(report, "exclude-secret").returned_labels == ()
        assert _case(report, "exclude-archived").returned_labels == ()
        assert repository.status().state_revision == state_revision_before


def test_imp_087_logical_report_is_reproducible_across_fresh_synthetic_workspaces(
    tmp_path: Path,
) -> None:
    reports: list[dict[str, object]] = []
    generated_ids: list[set[str]] = []
    for name in ("first", "second"):
        initialized, corpus, bindings = _populate(tmp_path / name)
        generated_ids.append(set(bindings.label_to_memory_id.values()))
        with state.open_state_repository(
            initialized.root,
            read_only=True,
            immutable=True,
        ) as repository:
            build_memory_lexical_index(repository)
            report = run_recall_benchmark(repository, corpus, bindings)
            reports.append(report.logical_dict())

    assert generated_ids[0].isdisjoint(generated_ids[1])
    assert reports[0] == reports[1]


def test_imp_087_missing_or_corrupt_index_never_blocks_scan_baseline(tmp_path: Path) -> None:
    initialized, corpus, bindings = _populate(tmp_path / "workspace")

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        missing = run_recall_benchmark(repository, corpus, bindings)
        assert missing.index_status == "unavailable"
        assert missing.index_error_type == "RecallIndexUnavailableError"
        assert missing.index_coverage is None
        assert missing.lexical_recall_at_1 == "1"
        assert missing.semantic_opportunity_miss_count == 2
        build_memory_lexical_index(repository)
        scan_baseline = run_recall_benchmark(repository, corpus, bindings).logical_dict()
        index_path = memory_lexical_index_path(repository)

    index_path.write_bytes(b"synthetic-corrupt-index")

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        corrupt = run_recall_benchmark(repository, corpus, bindings)
        assert corrupt.index_status == "unavailable"
        assert corrupt.index_error_type == "RecallIndexCorruptError"
        assert corrupt.index_coverage is None
        assert corrupt.lexical_recall_at_1 == "1"
        assert corrupt.lexical_recall_at_3 == "1"
        assert corrupt.semantic_opportunity_miss_count == 2
        corrupt_logical = corrupt.logical_dict()
        for key in ("index_status", "index_error_type", "index_coverage"):
            corrupt_logical[key] = scan_baseline[key]
        for case in corrupt_logical["cases"]:
            assert isinstance(case, dict)
            case["index_returned_labels"] = next(
                baseline_case["index_returned_labels"]
                for baseline_case in scan_baseline["cases"]
                if isinstance(baseline_case, dict) and baseline_case["case_id"] == case["case_id"]
            )
        assert corrupt_logical == scan_baseline


def test_imp_087_benchmark_does_not_mutate_authoritative_memory(tmp_path: Path) -> None:
    initialized, corpus, bindings = _populate(tmp_path / "workspace")
    with state.open_state_repository(initialized.root) as repository:
        service = ConfirmedMemoryService(repository)
        authoritative_before = {
            label: service.get(memory_id)
            for label, memory_id in bindings.label_to_memory_id.items()
        }
        state_revision_before = repository.status().state_revision
        record_count_before = repository.status().record_count

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        report = run_recall_benchmark(repository, corpus, bindings)
        assert report.lexical_recall_at_1 == "1"
        assert repository.status().state_revision == state_revision_before
        assert repository.status().record_count == record_count_before
        service = ConfirmedMemoryService(repository)
        for label, memory_id in bindings.label_to_memory_id.items():
            assert service.get(memory_id) == authoritative_before[label]
