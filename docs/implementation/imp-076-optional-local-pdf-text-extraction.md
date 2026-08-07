# IMP-076 — Optional local PDF text extraction adapter

## Status

Implemented with deterministic synthetic and in-process `pypdf` CI evidence.

## Objective

Add the Lite v1.0-required PDF text extraction path without making PDF support a mandatory core dependency and without broadening local files into trusted instructions, persistent state, automatic context, or executable capability authority.

## Implemented boundary

IMP-076 adds one explicit `doll pdf extract SOURCE` command and one replaceable `PdfTextAdapter` contract. The default implementation loads `pypdf` only when extraction is invoked. Importing doll, showing root or PDF help, and using every non-PDF command do not load or require the adapter.

The optional `pdf` project extra and development environment use the locked compatible range `pypdf>=6.14.2,<7`; the core dependency set remains unchanged when that extra is not installed.

The caller selects exactly one `.pdf` source. The source must be a regular non-symlink file, remain within the eight-megabyte source limit, preserve path/open-handle identity, size, and modification time throughout the read, and begin with a PDF signature. Native paths and filenames are excluded from result metadata and failures.

The in-process adapter opens source bytes through `PdfReader(..., strict=True)`. Encrypted or password-protected documents are rejected before page inventory or extraction. Documents are bounded to 200 pages. The caller may extract all pages or repeat exact one-based page selections in caller order, with at most 100 selected pages. Duplicate, non-positive, boolean, and unavailable selections fail closed.

Each selected page is extracted independently. `None` becomes an empty text result and identifies a page with no extractable text; no OCR or image fallback is attempted. Per-page text is limited to 100,000 characters and aggregate selected text to 1,000,000 characters. NUL, DEL, and prohibited control characters are rejected.

Results include only bounded adapter identity/version, source byte count and SHA-256, document and selected page counts, ordered selected page numbers, aggregate character count, empty-text page numbers, and page-numbered text or metadata-only page counts. Extracted text is always classified as `external_content`, actor `extractor`, acquisition `extraction`, authority `untrusted_data`.

## No-authority and no-side-effect rules

IMP-076 performs no source overwrite, output-file creation, workspace write, state write, artifact write, audit write, index creation, memory or project mutation, permission or confirmation change, capability execution, model or runtime execution, process or shell launch, network or cloud access, credential access, binding change, OCR, image extraction, JavaScript execution, remote-resource fetch, automatic discovery, or automatic context injection.

Adapter absence, malformed structure, encryption, missing or unsafe files, changed files, excessive limits, invalid selections, invalid adapter metadata, and invalid extracted text fail before any persistent mutation because this workflow has no persistent mutation path.

## Evidence

Dedicated acceptance covers:

- real in-process `pypdf` text extraction;
- optional-adapter absence and help without adapter loading;
- explicit page order and metadata-only output;
- Unicode and Japanese text through a deterministic synthetic adapter;
- empty-text page reporting without OCR;
- source hashes and bounded counts;
- encrypted, empty, excessive, malformed, unsupported, missing, directory, symlink, oversized, changed, invalid-page, invalid-adapter, invalid-text, inventory, open, and extraction failures;
- exact source, workspace, and authoritative-state preservation;
- path-safe human and JSON failures;
- root CLI registration;
- Ruff, formatting, strict mypy, dependency lock, generated specification, public-status validation, implementation numbering, and full Ubuntu, macOS, and Windows CI.

## Evidence boundary

This is CI-only evidence. IMP-076 does not establish OCR, image extraction, layout reconstruction, table extraction, forms, annotations, attachments, password entry, PDF repair, JavaScript execution, external processes, arbitrary plugins, automatic discovery, semantic retrieval, model-selected context, writing-workflow attachment integration, artifact publication, persistent extraction results, Web retrieval, complete Phase 6, Lite v1.0 completion, performance acceptance, the release-candidate soak, or stable general anti-lock-in.
