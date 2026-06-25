# IMP-037 Phase 4A portability acceptance

## Status

Accepted. The primary Intel Mac offline gate passed on exact merged `main` commit `839a4ca7a37753fadf81c3e8e79f140e6d66bc03` on 2026-06-25.

Accepted evidence:

- `docs/testing/results/IMP-037-primary-intel-mac-2026-06-25.json`

Phase 4A is complete for the generic, model-independent portability foundation covered by PORT-004 through PORT-012. This does not establish the later local-migration or stable anti-lock-in claims.

## Verified boundary

The accepted run verified:

- generic import staging and reviewed publication;
- canonical conversation and event persistence;
- deterministic JSON, JSONL, Markdown, manifest, and checksum export;
- source provenance and identity separation;
- unchanged re-import idempotency;
- explicit material loss and quarantine;
- imported-content authority restrictions;
- restart and separate-process inspection;
- no model, runtime, preferred UI, running service, network request, cloud account, or credential.

## Accepted environment

- commit: `839a4ca7a37753fadf81c3e8e79f140e6d66bc03`;
- operating system: `Darwin`;
- architecture: `x86_64`;
- Python: `3.12.13`;
- network mode: `offline-confirmed`;
- evidence level: `real-machine`.

Result:

```text
result = pass
primary_intel_mac_gate = pass
phase4a_gate_complete = true
stable_anti_lock_in_claim = false
```

The stored result contains no absolute paths, usernames, hostnames, credentials, secret values, private fixture content, or personal conversation data.

## CI validation

```bash
python scripts/run_imp_037_portability_acceptance.py \
  --commit-sha "$(git rev-parse HEAD)" \
  --evidence-level ci
```

CI validates the stored real-machine result against the matrix commit, platform, architecture, completion time, offline mode, and passing checks.

## Deliberate limitations

- PORT-001 through PORT-003 and PORT-013 through PORT-016 remain incomplete.
- Generic export currently covers canonical conversations and conversation events only.
- No provider-specific, local-application, runtime, model, cloud, or private-history adapter is exercised.
- This does not establish a local migration claim or stable anti-lock-in claim.
