# IMP-010 verified local backup creation and verification

IMP-010 turns the portable Doll State package boundary into explicit local backup
operations. Restore remains a separate IMP-011 concern.

## Backup kinds

### State backup

A state backup contains one fully verified Doll State Package v1 at
`payload/state-package.zip`. Secret records remain omitted by the state-package
contract, and the omission count is recorded in the backup manifest.

### Workspace backup

A workspace backup contains:

- `workspace.json`;
- a consistent SQLite snapshot created with the SQLite backup API;
- every authoritative managed artifact represented by an active or archived artifact
  record.

The first workspace slice is deliberately conservative. It rejects secret records,
unknown top-level workspace content, unknown state files, files in `audit/` or
`config/`, mismatched artifact files, and symbolic links. It excludes previous
backups, temporary content, model assets, runtime assets, caches, and reproducible
indexes.

## Publication and inventory

Creation uses a sibling temporary file, reopens and verifies the complete archive,
fsyncs it, publishes with an atomic replacement, fsyncs the parent directory, and
verifies the published bytes again. Existing outputs are never overwritten.

Only then does doll register a `backup_manifest` common-envelope record. The record,
a `backup.create` audit event, and one state-revision increment are committed in one
SQLite transaction. Inventory metadata stores only the backup ID, kind, versions,
workspace identity, source revision, timestamps, hashes, byte size, categories, and
file name. It never stores an absolute local path.

If inventory registration fails, the newly published archive is removed and the
operation fails closed.

## Verification

Verification checks:

- ZIP readability and regular-file entry types;
- normalized portable member names;
- traversal, absolute, Windows-drive, UNC/backslash, duplicate, and case-fold
  collisions;
- member, total-size, and compression-ratio limits;
- exact checksum inventory, byte sizes, and SHA-256 values;
- format version, backup kind, workspace identity, state schema, and source revision;
- included and excluded category contracts;
- nested Doll State Package verification for state backups;
- SQLite integrity, identity, revision, record counts, audit counts, secret absence,
  artifact records, artifact paths, sizes, hashes, and bytes for workspace backups;
- complete-file SHA-256 and byte size.

Backup content is treated only as data and is never executed.

## CLI

```text
doll backup create-state OUTPUT --workspace WORKSPACE
doll backup create-workspace OUTPUT --workspace WORKSPACE
doll backup inspect BACKUP
doll backup verify BACKUP
doll backup list --workspace WORKSPACE
```

Normal output reports portable IDs, counts, file name, byte size, and SHA-256. It does
not print workspace, backup, temporary, staging, database, home-directory, user, or
host paths.

## State-package compatibility

Doll State Package v1 now exports and imports
`records/backup-manifests.jsonl`. Packages produced before IMP-010 remain accepted;
a missing backup-manifest member and missing corresponding count fields are treated
as zero records. Unknown authoritative record types still fail closed.

## Exclusions

IMP-010 does not implement restore, encryption, signing, scheduling, rotation,
pruning, cloud transfer, model execution, or network access.
