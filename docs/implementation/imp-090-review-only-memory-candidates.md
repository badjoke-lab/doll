# IMP-090 — Review-only memory consolidation candidates

Status: implementation branch

IMP-090 adds a deterministic read-only MCON-004 candidate detector over active confirmed memories. The output is advisory, derived, and non-persistent.

Detector `deterministic-memory-review` version `1` uses Unicode NFKC, case-folding, whitespace collapse, and deterministic character-trigram overlap. It inspects at most 100 memories, excludes secret records before pair comparison, evaluates at most 4,950 pairs, and returns at most 500 candidates.

Version 1 reports four candidate kinds: normalized exact duplicates, lexical near-duplicates at the declared 7,800-basis-point threshold, same-subject compatible content extensions, and existing explicit contradiction links. It does not infer semantic contradiction from a model. Unrelated memories produce no candidate.

Each candidate exposes both MemoryRecord IDs and revisions plus bounded comparison evidence. The report exposes detector/normalization versions, Doll State revision, bounds, scan counts, pair counts, and truncation state.

The detector requires a read-only repository, persists no candidate record, creates no instruction or usage record, performs no authoritative memory change, uses no model/embedding/Ollama/network/cloud dependency, and fails closed if Doll State revision changes during detection.

Synthetic MCON-004 tests cover exact duplicate, near duplicate, compatible extension, explicit contradiction, unrelated, secret, and archived fixtures and compare authoritative memory state before and after detection. This slice establishes candidate detection only; any future accepted consolidation action remains a separate user-controlled path.

Quality, type checking, and Ubuntu/macOS/Windows CI are blocking before merge.
