# IMP-077 — Optional local image OCR adapter

## Status

Implemented on the IMP-077 branch pending final integration evidence.

## Objective

Add the Lite v1.0-required basic OCR path without making OCR, a network service, a subprocess, or a model download part of doll core startup.

The bounded user surface is:

```text
doll ocr extract SOURCE
```

`SOURCE` is exactly one caller-selected PNG or JPEG raster image.

## Boundary

The stable IMP-077 boundary is deliberately small:

- `.png`, `.jpg`, and `.jpeg` only;
- one regular non-symlink file selected explicitly by the caller;
- maximum source size 8 MiB;
- maximum width 10,000 pixels;
- maximum height 10,000 pixels;
- maximum decoded area 25,000,000 pixels;
- animated or multi-frame input rejected;
- maximum 1,000 recognized lines;
- maximum 20,000 characters per recognized line;
- maximum 200,000 aggregate recognized characters;
- deterministic human-readable and JSON output;
- optional `--metadata-only` output.

No directory traversal, globbing, automatic discovery, PDF rendering, attachment integration, or automatic context injection is introduced.

## Source validation

Before OCR inference, doll validates the selected file through the same fail-closed path/open-handle pattern used by the preceding local document adapters:

1. extension allowlist;
2. `lstat` regular-file and symlink rejection;
3. bounded source size;
4. open-handle identity verification;
5. bounded read;
6. post-read identity, size, and modification-time verification;
7. content signature and structural validation;
8. extension/content format agreement;
9. image dimension and pixel limits.

PNG validation is standard-library-only and checks the PNG signature, chunk lengths, CRC values, first `IHDR`, duplicate `IHDR`, presence of image data, exact `IEND`, and APNG animation marker rejection.

JPEG validation is standard-library-only and walks bounded marker segments until it obtains dimensions from a Start Of Frame marker and confirms an image scan with an end marker.

The optional OCR stack therefore receives bytes only after the core has established the bounded source envelope.

## Adapter contract

OCR remains replaceable through the `OcrAdapter` contract. The first real adapter is macOS Vision through `ocrmac` and is loaded only when OCR is invoked.

The package declaration is platform-scoped:

```text
ocrmac==1.0.1; sys_platform == 'darwin'
```

The generated lock currently resolves the macOS OCR stack to:

- `ocrmac 1.0.1`;
- `Pillow 12.3.0`;
- `pyobjc-framework-Vision 12.2.1` and its matching PyObjC framework dependencies.

The lock includes Python 3.12 macOS x86_64 Pillow wheels and Python 3.12 Universal2 PyObjC Vision wheels, preserving the primary Intel Mac compatibility requirement.

`ocrmac`, Pillow, and PyObjC are not imported by doll core startup, `doll --help`, or non-OCR commands. On a non-macOS platform, or when the optional adapter is absent, explicit OCR invocation fails closed while the rest of doll remains available.

The adapter decodes the already-validated source bytes in memory and passes a Pillow image object to Apple Vision. No source path or URL is passed to the OCR engine.

## Trust and provenance

Every recognized line is classified as:

```text
origin_class = external_content
actor_type = extractor
acquisition_method = ocr
authority_class = untrusted_data
```

OCR output is data, not authority. It cannot grant permission, confirmation, capability authority, credential scope, memory authority, project authority, or completion authority.

## Side-effect boundary

IMP-077 performs none of the following:

- source overwrite;
- output-file creation;
- workspace mutation;
- Doll State mutation;
- artifact mutation;
- audit mutation;
- persistent index creation;
- memory or project mutation;
- model execution;
- runtime fallback;
- capability execution;
- shell execution;
- external process launch;
- network access;
- cloud access;
- credential access;
- automatic dependency installation;
- automatic OCR-model download;
- automatic context injection.

Errors expose only stable error classes through the CLI and do not render native paths, filenames, usernames, hostnames, credentials, or source content.

## Output

Successful metadata includes only bounded, path-free information:

- schema version;
- adapter ID and version;
- source byte count and SHA-256;
- image format;
- width, height, and pixel count;
- ordered line count;
- aggregate recognized character count;
- empty-text state;
- fixed origin classification;
- fixed no-side-effect flags.

Recognized line text is omitted when `--metadata-only` is requested.

An image with no recognized text is a successful empty result rather than an implicit fallback request.

## Acceptance

Dedicated acceptance covers:

- PNG and JPEG parsing;
- Unicode and Japanese adapter-return preservation;
- deterministic hashes, dimensions, ordering, counts, and metadata-only output;
- empty OCR output;
- optional-adapter absence;
- help without adapter loading;
- malformed, truncated, signature-mismatched, animated, oversized, over-dimension, and over-pixel input;
- symlink, directory, missing, changed-before-read, and changed-during-read rejection;
- adapter failure and malformed adapter output;
- recognized-line and aggregate-output bounds;
- path-free human and JSON failures;
- exact source/workspace/state preservation;
- hosted macOS execution through the real pinned `ocrmac`/Vision adapter using a deterministic locally generated high-contrast text image;
- standard Ubuntu, macOS, and Windows CI.

Hosted macOS Vision evidence proves the dependency and in-process adapter path on the GitHub runner. It is not the primary Intel Mac real-machine release gate and does not broaden the previously accepted primary-machine evidence.

## Out of scope

IMP-077 does not establish:

- PDF page rendering or scanned-PDF OCR;
- automatic fallback from `doll pdf extract`;
- TIFF, GIF, WebP animation, or multipage image support;
- handwriting-specific tuning;
- layout or table reconstruction;
- OCR bounding-box publication;
- image enhancement pipelines;
- image extraction from documents;
- directory traversal or globbing;
- camera capture;
- attachment integration;
- persistent OCR records;
- artifact publication;
- persistent indexing;
- semantic retrieval;
- model-selected context;
- Web retrieval;
- cross-platform real OCR adapters;
- performance acceptance;
- accessibility presentation;
- the release-candidate soak;
- complete Phase 6;
- Lite v1.0 completion;
- stable general anti-lock-in.
