# IMP-002 workspace initialization

This implementation adds the first explicit private-data operation to doll.

## Command

```text
doll init [PATH] [--instance-label TEXT] [--profile lite|heavy|auto]
```

When `PATH` is omitted, doll uses the operating system's standard per-user data directory through `platformdirs`.

## Safety behavior

- initialization is explicit;
- imports, CLI help, version output, and API creation do not create a workspace;
- an existing `workspace.json` is never overwritten;
- a non-empty unrelated directory is rejected;
- a path inside an identifiable doll repository checkout is rejected;
- `workspace.json` is written through a temporary file and atomic replacement;
- newly created directories are removed when initialization fails before completion;
- no network operation occurs.

## Initial layout

```text
workspace.json
state/
artifacts/
audit/
backups/
config/
temporary/
```

SQLite and durable state tables are intentionally deferred to IMP-003.
