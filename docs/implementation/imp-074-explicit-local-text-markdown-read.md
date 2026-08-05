# IMP-074 — Explicit local text and Markdown reading

## Status

Implemented with deterministic synthetic CI evidence after merge. This document describes the bounded implementation and does not claim complete Phase 6 or Lite v1.0.

## Objective

Provide the Lite v1.0-blocking local text and Markdown support as one explicit, local-only, read-only document path.

The implementation also satisfies the bounded CONT-P007 foundation for a caller-selected local text or Markdown file: content is read through an approved path, receives fixed instruction-origin metadata, and remains outside the workspace unless a later explicit copy or publication path is separately invoked.

## User surface

The root CLI exposes:

```text
doll document read SOURCE
```

Supported options are:

- `--json` for deterministic machine-readable output;
- `--metadata-only` to omit document content from output.

The caller must explicitly provide one `.txt`, `.md`, or `.markdown` path. No directory discovery, globbing, recent-file scan, background lookup, or automatic retrieval occurs.

## Stable source boundary

A selected source must:

- use one supported extension;
- exist as one regular file;
- not be a symbolic link;
- remain within the one-megabyte source limit;
- remain unchanged across path and open-handle verification;
- decode as strict UTF-8 after deterministic optional UTF-8 BOM removal;
- remain within the character limit;
- contain no NUL, DEL, or prohibited control character.

Missing, unreadable, unsupported, linked, non-regular, oversized, invalid UTF-8, binary-like, changed-before-read, or changed-during-read inputs fail closed.

Encoding detection, fallback encodings, lossy replacement, Markdown rendering, and binary extraction are not performed.

## Returned content and metadata

A successful read preserves the decoded text exactly, including Unicode, Japanese text, and existing line endings after optional UTF-8 BOM removal.

The content-free metadata includes only:

- schema version;
- document kind;
- media type;
- normalized extension;
- source byte count;
- returned-content byte count;
- character count;
- line count;
- exact source SHA-256;
- exact returned-content SHA-256;
- whether a UTF-8 BOM was removed;
- fixed instruction-origin classification;
- explicit false flags for source persistence, workspace mutation, state mutation, model execution, and network access.

Native paths, filenames, usernames, hostnames, credentials, and secret values are not included in metadata or errors. JSON failures and human failures expose only a bounded error class.

## Instruction and authority boundary

Every returned document is classified as:

```text
origin_class = external_content
actor_type = extractor
acquisition_method = extraction
authority_class = untrusted_data
```

Reading a file does not convert its text into a task instruction, user approval, durable policy, permission, confirmation, capability request, credential scope, confirmed memory, confirmed fact, project state, work completion, procedure approval, checkpoint confirmation, or model binding.

IMP-074 does not inject the returned content into any model context. A later workflow that consumes selected document content must retain this origin and authority classification and pass through the accepted external-content and prompt-defense boundary.

## State and side effects

The reader performs no:

- workspace initialization or mutation;
- SQLite open or state mutation;
- artifact copy or publication;
- audit write;
- memory, project, decision, work-item, procedure, or checkpoint mutation;
- permission, confirmation, or capability operation;
- model or runtime execution;
- process or shell execution;
- network or cloud request;
- credential or binding access;
- persistent indexing or search-result persistence.

The source remains outside the workspace. The command is an explicit read only.

## Acceptance coverage

Dedicated tests cover:

- exact UTF-8 text and Markdown reads;
- Japanese, Unicode, CRLF, and Markdown preservation;
- deterministic UTF-8 BOM handling;
- source and returned-content hashes;
- fixed untrusted instruction origin;
- path-free metadata and failures;
- content-inclusive and metadata-only JSON;
- stable human output;
- exact workspace and authoritative-state preservation;
- unsupported extensions;
- invalid UTF-8, NUL, DEL, and prohibited control characters;
- missing files, directories, symlinks, oversized files, changed files, and identity mismatch;
- CLI help without workspace initialization;
- Ubuntu, macOS, and Windows CI.

## Non-claims

IMP-074 does not establish:

- file copying or artifact publication;
- automatic discovery, directory reading, or globbing;
- local full-text indexing of file contents;
- semantic retrieval or model-selected context;
- writing-workflow attachments;
- PDF, OCR, CSV, office-document, HTML, or Web processing;
- encoding detection beyond strict UTF-8;
- Markdown rendering;
- model execution or tool use;
- cloud services;
- complete Phase 6;
- Lite v1.0 completion;
- Lite performance acceptance;
- the release-candidate soak;
- stable general anti-lock-in.
