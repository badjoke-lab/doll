# IMP-091 — PAM v1.0 staged memory import

## Scope

IMP-091 adds the first bounded Portable AI Memory (PAM) v1.0 adapter. It accepts caller-provided `memory-store.json` bytes, validates the supported root and memory contract offline, verifies each PAM `content_hash`, preserves the exact source SHA-256, and projects each memory into the existing generic staged-import boundary as `external_data`.

The adapter version is explicit (`pam-v1-memory-store/1.0.0`) and the supported source version is exactly PAM `1.0`.

## Authority boundary

This slice creates no confirmed `MemoryRecord`, permission, policy, procedure approval, work completion, instruction authority, model binding, or automatic context. PAM lifecycle, access, confidence, instruction type, relation, embedding reference, integrity, signature, owner, and conversation-index data remain source metadata or explicit mapping notes.

PAM `content_hash` is checked for PAM compatibility only. It is not a Doll record identifier or semantic-equivalence proof. Two distinct source memories may legitimately have the same PAM content hash and still remain distinct candidates.

## Generic staging boundary

The adapter creates a deterministic in-memory `doll-generic-import` projection and runs it through `GenericImportStager` with network behavior `none`. The generic projection is separately hashed. The exact caller-provided PAM bytes retain their own SHA-256 so later reviewed publication can bind to the original interchange document rather than the derived projection.

## Non-claims

IMP-091 does not implement reviewed publication into confirmed Doll memory, PAM export, companion conversation import, embeddings import, RFC 8785 integrity verification, signature verification, incremental-base merging, or any network fetch. It is foundation toward MCON-005 and MCON-007, not a claim that those complete acceptance gates or the PAM import/export profile are finished.

## Evidence

Synthetic tests cover deterministic restaging, exact source hashing, PAM v1 content-hash normalization, Unicode normalization collisions without identity collapse, external-data authority, access/instruction non-authority, relation preservation, invalid hashes, unsupported versions, invalid relation references, source-environment validation, and the absence of confirmed-memory or state-write dependencies.

Additional fail-closed coverage exercises malformed bytes and JSON, parser depth and size bounds, source-environment and adapter limits, invalid root, memory, relation, integrity and signature fields, timestamp requirements, incremental and extension metadata handling, and result-contract consistency without weakening the validation rules.
