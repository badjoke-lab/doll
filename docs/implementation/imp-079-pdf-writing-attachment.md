# IMP-079 — Explicit PDF writing attachment

Status: implementation and CI acceptance in progress.

Issue: #241

## Objective

Allow one explicitly selected local PDF to replace inline or text/Markdown primary source material for the existing bounded `revise`, `summarize`, and `translate` writing modes while preserving the accepted task-versus-material authority boundary.

## Accepted foundations

IMP-079 composes existing contracts rather than creating a new PDF parser or writing engine:

- IMP-063/IMP-064 bounded local writing workflow and accepted primary Intel Mac evidence;
- IMP-068 explicit translation mode;
- IMP-076 optional local in-process PDF text extraction;
- IMP-078 exactly-one-primary-source attachment selection and data-only document-source boundary.

## Source selection

The writing workflow accepts four source kinds: `none`, `inline`, `document`, and `pdf`.

- `draft` accepts no primary source;
- `revise`, `summarize`, and `translate` require exactly one of inline text, one explicit `.txt`/`.md`/`.markdown` document, or one explicit `.pdf`;
- PDF page selection is caller-controlled and is valid only when a PDF source is selected;
- source selection and basic page-selection type validation happen before target preflight, but no PDF bytes are opened before the accepted conversation, parent, capacity, active-binding, and runtime-declaration preflight succeeds.

## PDF extraction and writing material

The selected PDF is passed to the unchanged IMP-076 `extract_local_pdf_text` boundary. That path provides:

- regular-file and symlink checks;
- eight-megabyte source limit;
- path/open-handle identity, size, and modification-time verification;
- PDF signature and strict parser validation;
- encrypted-document rejection;
- maximum 200-document-page inventory;
- at most 100 explicit unique one-based selected pages, preserving caller order;
- per-page and aggregate extracted-text limits;
- no OCR or image fallback;
- optional invocation-only `pypdf` adapter loading;
- no process, shell, network, cloud, model, persistence, or source overwrite behavior.

After successful extraction, selected page text is deterministically joined in caller order with two newline characters between page strings. The joined text then passes the existing writing-source validation and 16,000-character limit. A PDF whose selected pages produce only blank writing material fails closed. No writing source InstructionOrigin is created until both PDF extraction and the writing-source validation succeed.

## Trust and instruction origin

Extracted PDF text remains only writing material. The resulting source InstructionOrigin uses the existing writing source classification:

- origin class: `external_content`;
- actor type: `extractor`;
- acquisition method: `extraction`;
- effective authority: `untrusted_data`;
- data-only prompt channel: `untrusted_content`.

The current user request remains the only task-authority instruction. Instructions embedded in PDF text cannot change mode, target language, permissions, confirmations, capabilities, bindings, memory, facts, project state, decisions, work completion, procedures, checkpoints, or any other authoritative state.

## Result metadata

The content-free writing result identifies `source_kind = "pdf"` and exposes only bounded path-free PDF metadata:

- adapter ID and version;
- source byte count and SHA-256;
- document page count;
- selected page numbers in caller order;
- empty-text selected page numbers;
- aggregate raw PDF extracted-character count;
- existing writing-source character count after deterministic page joining.

Native path, filename, source text, prompt text, generated response text, username, hostname, credential, and secret values are not added to the writing result.

## Failure preservation

Invalid source combinations, PDF page metadata without a PDF, invalid page-selection types, unavailable targets, missing optional adapter, malformed or encrypted PDFs, unsafe files, invalid page numbers, extraction limits, blank selected material, the 16,000-character writing-source limit, and runtime failure fail without modifying the source PDF.

Extraction failures occur before writing-source origin creation. Runtime failures retain the existing canonical local-writing user/context/error persistence contract and do not grant the source additional authority.

## Acceptance

Dedicated synthetic acceptance covers:

- real `pypdf` extraction through the writing workflow;
- explicit selected-page order reaching `untrusted_content`;
- path-free PDF metadata and hashes;
- exact source-form conflict denial;
- draft denial and PDF-page-without-PDF denial;
- page-selection type validation;
- proof that target preflight occurs before PDF extraction;
- optional adapter failure before source-origin creation;
- blank extraction and 16,000-character writing-source limit failure before source-origin creation;
- hostile PDF instructions remaining data-only;
- runtime failure and exact source-file byte/size/mtime preservation;
- regression of existing inline and text/Markdown source behavior through the full suite.

Standard CI is required on Ubuntu, macOS, and Windows. IMP-079 does not require or broaden accepted primary Intel Mac real-machine evidence.

## Explicit non-claims

IMP-079 does not establish OCR or scanned-PDF fallback, image extraction, layout reconstruction, tables, forms, annotations, embedded attachments, password entry, PDF repair, multiple attachments, mixed primary sources, draft reference attachments, attachment persistence, SourceRecord creation, artifact publication, persistent indexing, automatic file discovery, semantic retrieval, embeddings, ranking, model-selected context, Web retrieval, process or shell execution, tools, capability execution, network or cloud access, target-specific export, accessibility presentation, Lite performance acceptance, the release-candidate soak, complete Phase 6, Lite v1.0 completion, or stable general anti-lock-in.
