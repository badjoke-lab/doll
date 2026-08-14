# IMP-093 — Bounded PAM v1.0 confirmed-memory export

## Scope

IMP-093 adds the outbound half of the bounded PAM v1.0 memory-interchange profile. The exporter is offline and read-only. It accepts an explicit caller-provided PAM owner identifier and an explicit sequence of confirmed Doll `MemoryRecord` identifiers. It does not enumerate or export the whole workspace implicitly.

The output is a deterministic PAM v1.0 `memory-store.json` byte sequence. The root contains the PAM schema identifier/version, caller-supplied owner identifier, and the explicitly selected memories. Every exported memory uses the PAM `custom` type with `custom_type=doll_confirmed_memory`, preserves the Doll record identifier as the PAM memory identifier, carries the confirmed memory content, maps Doll creation time to PAM `temporal.created_at`, declares `provenance.platform=doll`, and computes `content_hash` through the same PAM v1.0 normalization used by IMP-091.

## Authority and identity boundary

PAM export is memory interchange, not a Doll State Package and not complete AI-environment continuity export. The exporter does not derive PAM identity from normalized content. Two Doll memories whose content collapses to the same PAM `content_hash` retain separate Doll/PAM memory identifiers. PAM content hashes therefore remain target-format integrity metadata rather than Doll semantic identity.

The PAM owner id is caller-supplied. IMP-093 does not infer a person identity from `workspace_id`, account data, or other durable Doll identifiers.

## Mapping and loss reporting

The first export profile intentionally maps only the semantics required for a safe, deterministic memory interchange baseline: Doll record identity, content, and creation time. It uses a neutral PAM custom type instead of guessing whether arbitrary confirmed Doll content is a PAM fact, preference, goal, instruction, identity, or another built-in category.

The result returns explicit per-memory out-of-band mapping/loss evidence for Doll semantics not represented in the PAM file, including subject, source type, confirmation state, confidence, revision, sensitivity, Doll provenance, lifecycle/status, update time, and any present validity, relationship, source-reference, model/runtime/session, or operation metadata. Those omissions are not silently converted into PAM permission, lifecycle, trust, or instruction semantics.

Optional PAM embeddings, access blocks, relation objects, integrity blocks, and signatures are not emitted in this slice. Their absence does not affect the required PAM memory content, and no custom cryptography or canonicalization is introduced.

## Exportability and fail-close behavior

The exporter supports active non-secret confirmed memories only. Secret memories and archived memories fail closed. Empty selections, duplicate identifiers, unsupported target versions, invalid owner identifiers, and unavailable selected memories also fail closed.

The exporter snapshots the current Doll State revision and verifies that the revision is unchanged before and after serialization. Export itself performs no authoritative write and is valid against a fresh read-only/immutable repository open.

## Contract evidence

Synthetic tests parse the produced JSON and then feed the exact emitted bytes back through the existing IMP-091 offline PAM v1.0 stager. This provides a deterministic local supported-contract check for the required PAM fields and content hashes without network access.

Tests also cover deterministic output independent of caller selection order, explicit mapping/loss evidence, the PAM-content-hash-versus-Doll-identity boundary, secret/archived refusal, invalid selection/version inputs, state-revision non-mutation, and fresh read-only export. These tests provide the bounded IMP-093 evidence for MCON-006 while preserving MCON-007.

## Non-claims

IMP-093 does not add whole-workspace automatic export, PAM embeddings, PAM signatures or integrity blocks, relation conversion, lifecycle conversion, access/permission conversion, semantic type inference, model behavior, cloud behavior, network access, a new authoritative record type, schema migration, State Package signing, or complete Doll continuity export.
