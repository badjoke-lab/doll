#!/usr/bin/env python3
"""Run IMP-088 only against the fabricated IMP-087 corpus and an installed local model."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from doll import state, workspace
from doll.recall_benchmark import load_recall_benchmark_corpus, populate_synthetic_recall_benchmark
from doll.semantic_candidate import (
    OllamaSemanticEmbeddingClient,
    SemanticCandidateConfig,
    evaluate_semantic_benchmark,
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_CORPUS_PATH = _REPOSITORY_ROOT / "docs" / "testing" / "imp-087-memory-recall-benchmark-corpus.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate an already-installed local Ollama embedding model against the fabricated "
            "IMP-087 corpus. This command never pulls or installs a model."
        )
    )
    parser.add_argument(
        "--model",
        required=True,
        help=(
            "Explicit already-installed local Ollama embedding model name, "
            "for example embeddinggemma"
        ),
    )
    args = parser.parse_args()

    corpus = load_recall_benchmark_corpus(_CORPUS_PATH)
    client = OllamaSemanticEmbeddingClient(
        SemanticCandidateConfig(
            model_name=args.model,
            local_only_confirmed=True,
        )
    )
    identity = client.inspect_identity()

    with tempfile.TemporaryDirectory(prefix="doll-imp-088-") as temporary_directory:
        initialized = workspace.initialize_workspace(Path(temporary_directory) / "workspace")
        with state.initialize_state_repository(initialized.root):
            pass
        with state.open_state_repository(initialized.root) as repository:
            bindings = populate_synthetic_recall_benchmark(repository, corpus)
        with state.open_state_repository(
            initialized.root,
            read_only=True,
            immutable=True,
        ) as repository:
            report = evaluate_semantic_benchmark(
                repository,
                corpus,
                bindings,
                client,
                evidence_kind="real_model",
            )

    payload = {
        "evidence_schema_version": 1,
        "evidence_kind": "real_model",
        "corpus_id": corpus.corpus_id,
        "model_identity": identity.to_dict(),
        "semantic_candidate": report.to_dict(),
        "claims": {
            "fabricated_corpus_only": True,
            "model_was_preinstalled": True,
            "automatic_download": False,
            "semantic_recall_default": False,
            "product_adoption_decided": False,
        },
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
