# IMP-088 — Bounded local semantic recall candidate harness

Status: implementation branch

## Purpose

IMP-088 adds an opt-in experiment harness for measuring one already-installed local embedding model against the deterministic IMP-087 recall benchmark.

It does **not** make semantic recall a supported default, does not add persistent embeddings, and does not decide that doll should ship an embedding model. The accepted roadmap requires usefulness evidence before accepting semantic dependency and rebuild cost. IMP-088 creates the bounded mechanism for obtaining that evidence.

The deterministic IMP-085 lexical RecallState remains the normal fallback and is not modified by this slice.

## First documented candidate

The first documented candidate is `embeddinggemma` through a local Ollama runtime.

Primary references:

- Ollama embed API: <https://docs.ollama.com/api/embed>
- Ollama EmbeddingGemma library entry: <https://ollama.com/library/embeddinggemma>

The current Ollama library describes EmbeddingGemma as a roughly 300M-parameter multilingual embedding model intended for on-device use. The standard Ollama package is roughly 622 MB and advertises a 2K context window. The model entry also states that it requires Ollama 0.11.10 or later. Those properties explain why it is a reasonable **candidate to measure**; they are not a doll support commitment.

IMP-088 never invokes `ollama pull`, `/api/pull`, an installer, a shell, or a remote model URL. The model name is explicit. If it is not already installed, the experiment fails closed.

## Reused transport boundary

`src/doll/semantic_candidate.py` reuses doll's existing Ollama transport instead of adding a second network stack.

The existing transport represents only the fixed IPv4 loopback host `127.0.0.1`, does not expose a remote-host configuration path, and applies bounded local HTTP handling. IMP-088 extends its API allowlist by exactly one POST endpoint:

- `/api/embed`

No cloud endpoint, redirect path, proxy path, credential path, or automatic fallback is added.

The experiment config requires `local_only_confirmed=True` and an explicit model name. Cloud-tagged Ollama model names are rejected.

## Embedding request contract

Version 1 sends:

- one query plus at most 64 eligible memory texts;
- at most 65 total inputs;
- a maximum input length of 6,241 characters per item;
- `truncate: false` so over-context input cannot be silently shortened;
- an explicit model name.

The response must:

- be bounded by the existing Ollama JSON response limit;
- identify exactly the requested model;
- contain exactly one vector per input;
- use one consistent non-zero dimension;
- contain at most 1,024 dimensions per vector;
- contain finite numeric values only;
- contain no boolean or non-number vector members.

Malformed JSON, duplicate JSON keys, `NaN`/Infinity constants, wrong model identity, wrong vector count, inconsistent dimensions, zero vectors, and non-finite values fail closed.

## Retrieval policy

The experiment policy identity is:

`confirmed-memory-subject-content-cosine` version `1`

Only active confirmed memories returned by `ConfirmedMemoryService.list()` are considered. `secret` memories are then explicitly excluded.

Each eligible memory is represented transiently as:

`subject + "\n" + content`

No linked-record expansion, source-reference authority, permission state, procedure state, project state, or imported instruction metadata is added to the semantic text.

The query and memory texts are embedded in memory. Cosine similarity is computed in process. Ordering is:

1. cosine score descending;
2. MemoryRecord ID ascending as the deterministic final tie-breaker.

The result binds each derived score to the authoritative MemoryRecord revision and Doll State revision. Nothing is persisted.

The experiment handles at most 64 memories in one run. This is an explicit bounded experiment surface, not a claim of complete semantic search over arbitrarily large workspaces.

## IMP-087 comparison

`evaluate_semantic_benchmark()` runs the candidate only against the versioned fabricated IMP-087 corpus.

It reports:

- evidence kind (`synthetic` or `real_model`);
- explicit model name;
- semantic policy ID/version;
- lexical recall@1 and recall@3 across the six IMP-087 lexical regression cases;
- semantic-opportunity hit count/rate across the two low-overlap paraphrase cases;
- exclusion-target pass count;
- whether IMP-085 lexical fallback remains independently executable;
- a bounded case-level returned-label/rank view.

The minimum IMP-087 experiment gate passes only when:

1. at least one of the two semantic-opportunity misses is recovered;
2. lexical recall@3 remains `1`;
3. both secret/archive exclusion targets remain absent;
4. the deterministic IMP-085 lexical fallback remains independently available.

Passing this gate does **not** make semantic recall a product default. It only means the candidate deserves further resource/dependency/rebuild evaluation.

## Synthetic CI evidence

Normal CI must remain independent of Ollama installation and model weights.

IMP-088 therefore uses an injectable synthetic transport to prove harness behavior:

- only the expected local API paths are requested;
- `truncate` is false;
- model identity is explicit;
- malformed vectors fail closed;
- secret and archived memories never enter ranking;
- identical vectors produce deterministic MemoryRecord-ID tie ordering;
- ranking is read-only;
- a synthetic semantic candidate can exercise the benchmark gate mathematics;
- IMP-085 output is unchanged before and after the semantic experiment.

Synthetic evidence proves the harness, not semantic usefulness.

## Real-model evidence

`scripts/run_imp_088_semantic_candidate.py --model <installed-model>` creates a temporary synthetic Doll workspace, loads only the fabricated IMP-087 corpus, and evaluates the explicitly named already-installed local Ollama embedding model.

Before running the benchmark it reads local Ollama version and model inventory and records the matching model digest. It does not read the user's normal Doll workspace.

The JSON output explicitly records:

- `evidence_kind: real_model`;
- corpus ID;
- requested model name;
- local model revision/digest;
- local Ollama version;
- semantic benchmark result;
- statements that the corpus is fabricated, automatic download is false, semantic recall remains non-default, and product adoption has not been decided.

A real-model pass still leaves separate questions open: model weight size, installed runtime requirement, rebuild behavior, disk/RAM cost, latency, target-machine behavior, and whether the value is large enough to justify those costs.

## Non-claims

IMP-088 does not establish:

- semantic recall as the default retrieval path;
- an automatically installed or bundled embedding model;
- persistent vector storage or a vector database;
- hybrid lexical-semantic fusion or RRF;
- automatic/model-selected context;
- MemoryUsageSignalRecord or MCON-003;
- consolidation;
- PAM, PLUR, or PROJECTMEM adapters;
- ProjectExperienceRecord;
- ContinuityPreflight;
- MCP;
- cloud recall;
- Phase 6 completion;
- Lite v1.0 completion.

## Follow-up decision

After IMP-088 merges, an actual target-machine run with a preinstalled candidate may be collected separately. The result must remain labeled experimental. A later accepted slice must decide whether semantic dependency, persistent derived embeddings, fusion/ranking, and context-budget selection are justified. No such decision is made here.
