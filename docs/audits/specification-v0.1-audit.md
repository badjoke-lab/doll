# Specification set 0.1 audit and freeze report

**Audit status:** Complete  
**Specification set:** 0.1  
**Freeze decision:** Accepted for implementation  
**Date:** 2026-06-14

## 1. Scope

The audit reviewed the normative files under `docs/spec/`, the accepted ADRs under `docs/decisions/`, the generated `DOLL_FINAL_SPEC.md`, and the mapping from release claims to acceptance tests.

The review covered:

- product identity and first-user purpose;
- Local-complete, cloud-optional consistency;
- Lite and Heavy boundaries;
- cloud and mobile deferral;
- authoritative-state ownership;
- permission and network boundaries;
- backup, restore, migration, and recovery;
- Model Vault lifecycle and local fallback;
- test-ID uniqueness and release-gate coverage;
- implementation ordering.

## 2. Measurements

Before freeze normalization, the generated specification contained:

- 11 normative source documents;
- 6,810 generated lines;
- 56 acceptance-test IDs;
- 56 unique acceptance-test IDs;
- no duplicate acceptance-test IDs;
- 11 stale `Draft for acceptance` status labels.

## 3. Findings and resolutions

### AUD-001 — Merged specifications retained draft metadata

**Severity:** Documentation consistency  
**Resolution:** All normative source documents now state `Accepted for implementation`. Accepted ADRs now state `Accepted`.

### AUD-002 — Requirement-keyword casing was inconsistent

**Severity:** Interpretation clarity  
**Resolution:** `00-index.md` now states that MUST, SHOULD, and MAY are interpreted case-insensitively for specification set 0.1. Future changes should use uppercase forms.

### AUD-003 — Personal Lite document-read requirement appeared after the proof gate

**Severity:** Blocking implementation-order contradiction  
**Problem:** The Personal Lite proof requires a user-selected local document, while the roadmap previously placed document intake after the first proof gate.

**Resolution:** A minimal user-controlled text and Markdown intake slice is now IMP-012, before runtime integration and the first complete continuity drill. The later Capability Broker document slice remains responsible for richer model-requested tool behavior.

### AUD-004 — Phase 0 follow-up text was stale after specification generation

**Severity:** Roadmap clarity  
**Resolution:** The roadmap now marks the specification baseline as complete and points directly to IMP-001 after the v0.1 freeze.

## 4. Consistency conclusions

No unresolved blocking contradiction remains in the reviewed v0.1 specification set.

The following principles are consistently preserved:

- doll is a personal AI continuity system, initially built for one user's real local needs;
- the durable core is user-controlled state rather than a model, UI, runtime, or provider;
- local operation is required and cloud inference is optional;
- local failure never silently causes cloud submission;
- Lite and Heavy share one state, security, backup, and migration foundation;
- models and external content are untrusted inputs to a default-deny capability boundary;
- backup creation is not accepted as recovery evidence without restore;
- Heavy cannot be declared stable without real Heavy hardware;
- personality, voice, avatar, cloud, mobile, and broad autonomy remain optional or deferred;
- stable claims require test evidence.

## 5. Known intentional limitations

The freeze does not select:

- a permanent model catalog;
- a Heavy computer;
- cloud providers;
- a dedicated doll UI;
- mobile frameworks;
- exact Lite hardware requirements before measurement;
- a foundation-model training program.

These are deliberate deferred decisions, not missing v0.1 requirements.

## 6. Freeze rule

Specification set 0.1 is accepted as the implementation baseline.

Future changes that weaken local completeness, state portability, workspace confinement, explicit approval, recoverability, or evidence-based release gates require a dedicated specification change and, where applicable, a new ADR.

Implementation begins with IMP-001. The first major gate remains the Personal Lite continuity proof.
