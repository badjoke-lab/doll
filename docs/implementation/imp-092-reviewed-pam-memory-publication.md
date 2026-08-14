# IMP-092 — Reviewed PAM memory candidate publication

## Scope

IMP-092 adds the explicit review boundary between IMP-091 PAM staging and authoritative confirmed Doll memory. Publication operates on one staged PAM memory candidate at a time. A read-only preview records the exact source package hash, source environment, source memory identity, mapping/non-mapping decisions, current Doll State revision, explicit `approve` or `reject` decision, and a deterministic plan hash.

Publishing requires the exact reviewed plan hash and an explicit user-controlled actor. A rejected plan writes nothing. An approved plan creates a normal confirmed `MemoryRecord` with `source_type=approved_import`, imported provenance, personal sensitivity, and a deterministic source reference. No model/runtime/system actor may approve or reject through this path.

## Source identity and idempotency

The source reference binds the PAM source environment, a SHA-256 digest of the source memory identifier, and the exact PAM source-file SHA-256. Repeating the same unchanged staged source and approving the same candidate reuses the existing imported memory without increasing Doll State revision. If the same PAM source identity is later observed from a different source package, approval fails closed rather than silently overwriting or duplicating the earlier approved memory.

## Mapping boundary

The PAM content is the only semantic payload proposed for confirmed memory in this slice. Doll's existing confirmed-memory text validation remains authoritative, so any local normalization is visible in the preview. The local title is deterministic and source-type based rather than imported as instruction-bearing metadata.

PAM lifecycle state and validity, confidence, access grants, relation graph, instruction type, embedding reference, signatures, integrity declarations, owner metadata, and conversation-index data do not become Doll memory lifecycle, confidence, permission, relationship, instruction authority, recall state, or trust. The preview exposes those non-mappings as explicit notes inherited from IMP-091 plus IMP-092 publication-policy notes.

## Fresh-process continuity

Approved results are ordinary `MemoryRecord` state, so they use the existing package, backup, restore, migration, and fresh-process memory path. IMP-092 adds direct reopen/idempotency evidence for the imported result and does not add a new authoritative record type or schema migration.

## Non-claims

IMP-092 does not add automatic approval, batch-wide implicit approval, PAM export, PAM relation-to-Doll-relation conversion, PAM lifecycle conversion, PAM access-to-permission conversion, model-selected context, embeddings, cloud behavior, or network access. PAM export remains required before the complete PAM import/export profile and MCON-005/MCON-007 can be claimed complete.
