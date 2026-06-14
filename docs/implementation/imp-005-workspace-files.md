# IMP-005 workspace file service

IMP-005 adds the first authoritative managed-file creation boundary for doll.

The service creates new files only under the private workspace `artifacts/` directory,
computes SHA-256 and byte size, records an authoritative `artifact` envelope, and appends
an audit event attributed to the same operation ID.

## Create-new scope

This slice supports creation only.

It does not modify, replace, delete, import, or export existing artifacts. If the requested
destination already exists, the operation fails without changing the existing file,
record index, audit history, or state revision.

## Portable managed paths

Stored managed paths:

- are relative to `workspace/artifacts/`;
- use `/` separators;
- reject absolute paths, drives, UNC paths, backslashes, `.` and `..`;
- reject empty components, control characters, NUL bytes, Windows-reserved names,
  unsafe trailing characters, and a reserved temporary-file prefix;
- use conservative component and total-length limits.

Absolute host paths are not stored in artifact metadata and are not printed by artifact
CLI commands.

## Link and filesystem escape controls

The implementation rejects existing symbolic links and, where exposed by Python and the
platform, junctions and reparse points. Existing parent directories must be real
directories on the same filesystem device as the artifacts root. Nested mount points and
cross-device parents are rejected.

On POSIX systems, parent directories are opened one component at a time with directory
file descriptors and `O_NOFOLLOW` where available. Publication and rollback use the
retained parent descriptor, reducing path-replacement and symlink races.

On Windows, the implementation performs canonical path, junction/reparse, device, and
post-publication checks. The operating-system account and filesystem remain part of the
trusted computing base; the initial product does not claim protection from an attacker
who already controls that account.

## Atomic publication

The service:

1. validates the path and content size;
2. creates missing private parent directories;
3. writes a private uniquely named temporary file in the destination directory;
4. computes SHA-256 while writing;
5. flushes and fsyncs the temporary file;
6. creates a hard link at the final name, which fails if the destination exists;
7. removes the temporary name;
8. verifies that the final file is a regular confined file with the expected hash and size;
9. registers the artifact and audit event.

The completed final file becomes visible only after the temporary file is fully written.
Filesystems that cannot provide the required same-directory hard-link primitive fail
closed rather than falling back to an overwrite-prone publication path.

## Authoritative transaction

Artifact record insertion, success audit insertion, and state-revision advancement occur
inside one SQLite transaction.

The artifact record metadata includes:

- artifact type;
- title through the common record envelope;
- portable managed path;
- `sha256:` content hash;
- byte size;
- created-by category;
- operation ID;
- optional format and media type.

If the SQLite transaction fails, the service removes the exact newly published file using
the retained parent directory descriptor where supported and removes newly created empty
parents. Existing files are never removed by this cleanup path.

If SQLite commits but later `workspace.json` revision synchronization fails, the file and
authoritative database records remain intact. The existing writable-open recovery path
can synchronize the workspace revision from the authoritative database.

## Permissions and limits

The default service maximum is 16 MiB per artifact. Callers may lower the limit but cannot
raise it in this slice.

On POSIX systems:

- managed files are created with mode `0600`;
- new parent directories are created with mode `0700`.

On Windows, access control is inherited from the private workspace and user account.

## CLI

Create UTF-8 text from standard input:

```text
doll artifact create reports/example.txt \
  --workspace WORKSPACE \
  --title "Example" \
  --artifact-type report \
  --operation-id operation-123
```

List portable artifact records:

```text
doll artifact list [WORKSPACE]
```

Verify hash and size:

```text
doll artifact verify ARTIFACT_ID --workspace WORKSPACE
```

CLI output contains relative managed paths, record IDs, hashes, sizes, and operation IDs.
It does not print absolute workspace paths by default.

## Recovery and inspection

Artifact records can be listed without reading file content. Verification explicitly
re-reads the confined managed file and compares actual SHA-256 and byte size with the
authoritative record.

A missing, linked, non-regular, moved, oversized, or modified file fails verification.
Read-only state repositories permit listing and verification but reject creation.

## Scope boundary

IMP-005 does not include:

- artifact replacement or version chains;
- arbitrary external paths;
- external import or export;
- recursive directories;
- deletion or retention;
- backup and restore integration;
- model-generated capabilities;
- Capability Broker permission enforcement;
- malware scanning, content sniffing, encryption, or deduplication.
