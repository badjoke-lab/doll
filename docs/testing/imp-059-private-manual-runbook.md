# IMP-059 private manual runbook

## Purpose

This runbook covers the privacy-sensitive completion step for the bounded ChatGPT `conversations.json` source adapter.

The source JSON and the selected-conversation file must remain outside the repository. The runner emits only counts, hashes, bounded classifications, platform metadata, check results, and explicit limitations. It does not emit source paths, conversation IDs, titles, prompt or response text, provider model names, usernames, hostnames, credentials, or private fixture content.

The runner verifies that:

- the accepted IMP-059 implementation merge commit is recorded as the implementation evidence binding;
- the working runner matches its exact runner commit;
- portability-critical implementation files match the fixed blob manifest from the accepted IMP-059 implementation merge commit;
- the adapter contract remains offline;
- review output is content-free;
- canonical publication occurs only after explicit review confirmation;
- selected history publication accepts either `published` or `partially_published` batch status only when the selected conversation and supported-message counts are preserved exactly;
- exact source preservation, generic export, and shutdown escape succeed in a temporary local workspace;
- imported content remains external data and creates no authority records.

## Inputs

Prepare these outside the repository:

- one caller-extracted `conversations.json` file;
- one UTF-8 text file containing one selected conversation ID per line.

Prepare explicit environment values:

```bash
export CHATGPT_CONVERSATIONS_JSON="/absolute/path/outside/repo/conversations.json"
export CHATGPT_SELECTION_FILE="/absolute/path/outside/repo/selected-conversations.txt"
export SOURCE_ENVIRONMENT_ID="$(uv run python -c 'import uuid; print(uuid.uuid4())')"
export IMPORT_BATCH_ID="$(uv run python -c 'import uuid; print(uuid.uuid4())')"
export OBSERVED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

## Review

Run the content-free review first:

```bash
uv run python scripts/run_imp_059_private_manual.py \
  --mode review \
  --source "$CHATGPT_CONVERSATIONS_JSON" \
  --selection-file "$CHATGPT_SELECTION_FILE" \
  --source-environment-id "$SOURCE_ENVIRONMENT_ID" \
  --import-batch-id "$IMPORT_BATCH_ID" \
  --observed-at "$OBSERVED_AT" \
  --runner-commit "$(git rev-parse HEAD)"
```

Review these fields before continuing:

- `conversation_count`
- `selected_conversation_count`
- `selected_message_count`
- `supported_message_count`
- `unsupported_message_count`
- `attachment_reference_count`
- `malformed_object_count`
- `unknown_field_count`
- `duplicate_object_count`
- `quarantine_count`
- `material_loss_count`

Do not continue if the result contains unexpected private values or if the bounded loss surface is not acceptable.

## Complete

Disable network access at the machine level, then run:

```bash
uv run python scripts/run_imp_059_private_manual.py \
  --mode complete \
  --source "$CHATGPT_CONVERSATIONS_JSON" \
  --selection-file "$CHATGPT_SELECTION_FILE" \
  --source-environment-id "$SOURCE_ENVIRONMENT_ID" \
  --import-batch-id "$IMPORT_BATCH_ID" \
  --observed-at "$OBSERVED_AT" \
  --runner-commit "$(git rev-parse HEAD)" \
  --confirm-network-disabled \
  --confirm-reviewed
```

Store the JSON output outside the repository first. Inspect it for privacy leakage before copying only the reviewed privacy-safe result into a completion branch.

## Non-claims

This private manual drill does not establish ZIP ingestion, numbered-file aggregation, attachment-byte recovery, account restoration, memory migration, GPT migration, settings migration, file restoration, provider round-trip fidelity, the complete Phase 6 gate, or stable general anti-lock-in.
