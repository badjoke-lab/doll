# IMP-078 — Text and Markdown writing attachments

## Status

Implemented on the IMP-078 branch pending final integration evidence.

## Objective

Connect one explicitly selected local UTF-8 text or Markdown document to the accepted local writing workflow without introducing automatic file discovery, semantic retrieval, or model-selected context.

The standalone IMP-074 document reader already established a bounded local read path. IMP-078 composes that path with the IMP-063 through IMP-068 writing boundary so a user can revise, summarize, or translate a local document without first copying its contents into an inline `source_text` argument.

## Bounded source selection

`LocalWritingWorkflowService.execute(...)` now accepts:

```text
source_document_path: Path | None
```

For `revise`, `summarize`, and `translate`, exactly one primary source form is permitted:

- inline `source_text`; or
- one explicit `.txt`, `.md`, or `.markdown` document.

Supplying neither or both fails before source-origin creation or runtime execution.

`draft` remains source-free and rejects both inline and document primary source material.

## Validation sequence

The document path is not opened during basic request validation. IMP-078 performs the following sequence:

1. validate writing mode, request, source-form selection, target language, and operation ID;
2. require the writing operation to be unused;
3. preflight the selected conversation, parent event, active binding, runtime declaration, and target scope;
4. only then read the selected document through the unchanged IMP-074 `read_local_document` boundary;
5. apply the existing writing-source character limit to the returned text;
6. only after all source validation succeeds, create the data-only writing source InstructionOrigin;
7. prepare any explicitly selected writing context;
8. execute the unchanged canonical local conversation path.

This ordering prevents a missing, malformed, unsafe, changed, or over-limit source document from leaving a partially prepared writing source record or reaching the runtime.

## Reused IMP-074 boundary

Document attachments inherit the existing reader constraints:

- `.txt`, `.md`, and `.markdown` only;
- one caller-selected regular non-symlink file;
- maximum 1 MiB source bytes;
- strict UTF-8;
- deterministic optional UTF-8 BOM removal;
- path/open-handle identity, size, and modification-time verification;
- binary-like and prohibited-control rejection;
- deterministic source/content SHA-256 metadata;
- no file copying, persistence, model execution, process launch, or network access.

IMP-078 additionally applies the writing workflow's existing 16,000-character primary-source limit before source-origin creation.

## Authority boundary

Document-derived writing text uses the same source channel as accepted inline writing material:

```text
origin_class = external_content
actor_type = extractor
acquisition_method = extraction
authority_class = untrusted_data
```

The current user request remains the only task-authority instruction. Document content is never concatenated into that task payload and cannot change:

- writing mode;
- translation target language;
- permission or confirmation state;
- capability authority;
- model binding;
- memory, project, or decision authority;
- work-completion authority.

Hostile instructions inside the document remain visible to the existing prompt-injection boundary but stay data-only.

## Result metadata

The content-free `LocalWritingWorkflowResult` now distinguishes the primary source kind:

```text
none | inline | document
```

For a document source it additionally reports path-free metadata:

- document kind;
- source byte count;
- source SHA-256;
- returned-content SHA-256;
- UTF-8 BOM removal state;
- existing writing source character count.

No native path, filename, username, hostname, source text, prompt text, response text, credential, or secret value is added to the public result.

Existing inline-source callers remain supported and return `source_kind = inline` with empty document metadata. Draft turns return `source_kind = none`.

## Persistence and side effects

IMP-078 creates no new persistent document representation. It does not:

- copy the selected document into the workspace;
- create a SourceRecord for the selected file;
- create an artifact or persistent index;
- overwrite or modify the source file;
- create an output file;
- discover files automatically;
- traverse directories or expand globs;
- perform semantic retrieval or ranking;
- let the model choose a file or context record;
- execute a capability, process, or shell command;
- access network or cloud services;
- access credentials;
- change model bindings.

As with existing inline writing source text, the validated document text may participate only in the accepted instruction-origin and canonical conversation persistence required for that explicit writing turn.

## Acceptance

Dedicated acceptance covers:

- Markdown and UTF-8 BOM input through the real IMP-074 reader;
- exact path-free hashes, byte counts, document kind, BOM state, and writing character count;
- document content in the untrusted channel and absence from the task-authority payload;
- unchanged inline-source behavior;
- neither-source and both-source rejection;
- draft-plus-source-document rejection;
- document read failure after target preflight but before source-origin creation;
- unsupported document type and writing-source character-limit rejection;
- hostile document instructions remaining data-only;
- runtime failure while preserving source bytes, size, and modification time;
- no runtime call or source-origin record for invalid source selection or invalid document input;
- existing local-writing regression coverage and standard Ubuntu, macOS, and Windows CI.

## Out of scope

IMP-078 does not establish:

- PDF attachment integration;
- image or OCR attachment integration;
- CSV attachment integration;
- multiple attachments;
- draft reference attachments;
- attachment persistence;
- source-record creation;
- artifact publication;
- persistent file indexing;
- automatic file discovery;
- directory traversal or globbing;
- semantic retrieval, embeddings, or ranking;
- model-selected context;
- Web retrieval;
- cloud inference;
- tools;
- target-specific export;
- accessibility presentation;
- Lite performance acceptance;
- the release-candidate soak;
- primary Intel Mac evidence for this extension;
- complete Phase 6;
- Lite v1.0 completion;
- stable general anti-lock-in.
