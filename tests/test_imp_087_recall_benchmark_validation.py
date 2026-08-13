from __future__ import annotations

from pathlib import Path

import pytest

from doll import state, workspace
from doll.memory import ConfirmedMemoryService
from doll.recall_benchmark import (
    RecallBenchmarkBindings,
    RecallBenchmarkValidationError,
    load_recall_benchmark_corpus,
    populate_synthetic_recall_benchmark,
    run_recall_benchmark,
)

_CORPUS_PATH = (
    Path(__file__).parents[1] / "docs" / "testing" / "imp-087-memory-recall-benchmark-corpus.json"
)

_INVALID_CORPORA = (
    "{",
    '{"schema_version":2,"corpus_id":"x","memories":[],"cases":[]}',
    '{"schema_version":1,"corpus_id":"x","memories":[],"cases":[]}',
    '{"schema_version":true,"corpus_id":"x","memories":[],"cases":[]}',
    "[]",
    '{"schema_version":1,"corpus_id":"x","memories":{},"cases":[]}',
    '{"schema_version":1,"corpus_id":"","memories":[],"cases":[]}',
    (
        '{"schema_version":1,"corpus_id":"x","memories":['
        '{"label":"m","subject":"s","content":"c","sensitivity":"invalid"}],'
        '"cases":[]}'
    ),
    (
        '{"schema_version":1,"corpus_id":"x","memories":['
        '{"label":"m","subject":"s","content":"c","archived":"yes"}],'
        '"cases":[]}'
    ),
    (
        '{"schema_version":1,"corpus_id":"x","memories":['
        '{"label":"m","subject":"s","content":"c","source_reference":42}],'
        '"cases":[]}'
    ),
    (
        '{"schema_version":1,"corpus_id":"x","memories":['
        '{"label":"m","subject":"s","content":"c"},'
        '{"label":"m","subject":"s2","content":"c2"}],'
        '"cases":[{"case_id":"c","classification":"lexical","query":"s",'
        '"expected_label":"m","index_compatible":true}]}'
    ),
    (
        '{"schema_version":1,"corpus_id":"x","memories":['
        '{"label":"m","subject":"s","content":"c"}],'
        '"cases":[{"case_id":"c","classification":"invalid","query":"s",'
        '"expected_label":"m","index_compatible":true}]}'
    ),
    (
        '{"schema_version":1,"corpus_id":"x","memories":['
        '{"label":"m","subject":"s","content":"c"}],'
        '"cases":[{"case_id":"c","classification":"lexical","query":"s",'
        '"expected_label":"m","index_compatible":"yes"}]}'
    ),
    (
        '{"schema_version":1,"corpus_id":"x","memories":['
        '{"label":"m","subject":"s","content":"c"}],'
        '"cases":[{"case_id":"c","classification":"lexical","query":"s",'
        '"expected_label":42,"index_compatible":true}]}'
    ),
    (
        '{"schema_version":1,"corpus_id":"x","memories":['
        '{"label":"m","subject":"s","content":"c"}],'
        '"cases":[{"case_id":"c","classification":"lexical","query":"s",'
        '"expected_label":"missing","index_compatible":true}]}'
    ),
    (
        '{"schema_version":1,"corpus_id":"x","memories":['
        '{"label":"m","subject":"s","content":"c"}],'
        '"cases":[{"case_id":"c","classification":"exclusion","query":"s",'
        '"expected_label":"m","index_compatible":true}]}'
    ),
    (
        '{"schema_version":1,"corpus_id":"x","memories":['
        '{"label":"m","subject":"s","content":"c"}],'
        '"cases":['
        '{"case_id":"c","classification":"lexical","query":"s",'
        '"expected_label":"m","index_compatible":true},'
        '{"case_id":"c","classification":"lexical","query":"s",'
        '"expected_label":"m","index_compatible":true}]}'
    ),
)


@pytest.mark.parametrize("payload", _INVALID_CORPORA)
def test_imp_087_corpus_validation_fails_closed(tmp_path: Path, payload: str) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(RecallBenchmarkValidationError):
        load_recall_benchmark_corpus(path)


def test_imp_087_missing_corpus_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(RecallBenchmarkValidationError):
        load_recall_benchmark_corpus(tmp_path / "missing.json")


def test_imp_087_population_and_runner_enforce_workspace_boundaries(tmp_path: Path) -> None:
    corpus = load_recall_benchmark_corpus(_CORPUS_PATH)
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        with pytest.raises(RecallBenchmarkValidationError):
            populate_synthetic_recall_benchmark(repository, corpus)

    with state.open_state_repository(initialized.root) as repository:
        service = ConfirmedMemoryService(repository)
        service.create(subject="preexisting", content="synthetic")
        with pytest.raises(RecallBenchmarkValidationError):
            populate_synthetic_recall_benchmark(repository, corpus)

    second = workspace.initialize_workspace(tmp_path / "second")
    with state.initialize_state_repository(second.root):
        pass
    with state.open_state_repository(second.root) as repository:
        bindings = populate_synthetic_recall_benchmark(repository, corpus)
        with pytest.raises(RecallBenchmarkValidationError):
            run_recall_benchmark(repository, corpus, bindings)

    with state.open_state_repository(
        second.root,
        read_only=True,
        immutable=True,
    ) as repository:
        with pytest.raises(RecallBenchmarkValidationError):
            run_recall_benchmark(
                repository,
                corpus,
                RecallBenchmarkBindings(label_to_memory_id={}),
            )
