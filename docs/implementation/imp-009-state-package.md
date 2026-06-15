# IMP-009 Doll State package export and import

IMP-009 adds the first portable representation of implemented Doll State.

## Package

The package is a versioned ZIP archive containing:

- a self-describing manifest;
- workspace identity;
- JSONL files for preferences, policies, permissions, confirmed memories,
  projects, decisions, artifacts, audit events, and migration history;
- verified managed artifact bytes;
- a sorted SHA-256 inventory;
- a plain-text safety notice.

Package content is data only and is never executed.

## Export

Export requires a read-only state repository. It:

- validates every supported typed record;
- rejects unsupported authoritative record types;
- excludes secret records from an unencrypted package and records omission counts;
- verifies managed artifacts before and during reading;
- writes through a sibling temporary file;
- reopens and fully verifies the package;
- publishes only after verification;
- does not change source records, state revision, audit history, or workspace identity.

Existing output is not overwritten.

## Verification and inspection

Verification checks:

- normalized safe member paths;
- duplicate and case-fold collisions;
- regular-file entry types only;
- member, total-size, and compression-ratio limits;
- exact member inventory;
- SHA-256 and byte sizes;
- manifest/workspace identity and revisions;
- strict JSON and JSONL;
- common envelopes and existing typed-record validators;
- cross-record typed links;
- artifact records, paths, hashes, sizes, and bytes;
- audit and migration history structure.

Inspection performs the same verification and returns only portable counts and
identity metadata.

## Import

The first import slice supports an absent or empty target.

Import:

1. verifies and parses the complete package without extraction;
2. reports conflicts for populated targets;
3. creates a private sibling staging workspace;
4. publishes verified managed files into staging;
5. inserts records, audit events, and migration history in one SQLite transaction;
6. preserves workspace identity and record IDs/revisions/timestamps;
7. appends one sanitized import audit event;
8. validates the complete staged workspace;
9. atomically publishes the target where the platform permits.

A failed import removes staging and leaves the target absent or unchanged. This slice
does not merge into populated workspaces or overwrite conflicting state.

## CLI

```text
doll state-package export OUTPUT --workspace WORKSPACE
doll state-package inspect PACKAGE
doll state-package verify PACKAGE
doll state-package import PACKAGE --target EMPTY_TARGET
```

Normal CLI output does not print workspace, package, staging, or home-directory paths.

## Exclusions

This is not yet backup lifecycle management. It does not add incremental export,
encryption, secret export, package signing, cloud transfer, populated-workspace merge,
destructive conflict resolution, model assets, caches, or reproducible indexes.
