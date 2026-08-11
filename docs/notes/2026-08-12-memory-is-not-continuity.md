# Memory Is Not Continuity: Why doll Is Changing Its Design Without Becoming a Memory Product

**Status:** Publication-ready draft; non-normative  
**Date:** 2026-08-12

Doll started from a simple concern: access to a powerful AI model is not the same thing as owning a durable AI environment.

A provider can disappear. Pricing can change. A model can be retired. Regulation can limit access. A local runtime can stop being maintained. A preferred interface can lose data or become incompatible. Even if none of those failures happen, a user may simply want to replace one model with another.

The original design answer was therefore not “store chat history.” It was to keep the parts that make an AI-assisted environment continuous on the user's side: memory, preferences, projects, decisions, policies, permissions, artifacts, provenance, runtime and model metadata, backup, restore, migration, and recovery.

A recent review of Portable AI Memory (PAM), PLUR, and PROJECTMEM forced us to sharpen that idea. Each project solves a real part of the problem, and each exposes a gap in doll. The review did **not** show that doll should become another portable-memory implementation. It showed the opposite: memory portability is important precisely because memory is only one layer of continuity.

This document explains what we are changing, what we are deliberately not changing, and why.

## The distinction we were missing

The word “memory” is overloaded in AI systems.

It can mean a remembered preference. It can mean a vector retrieved because it is semantically similar to the current prompt. It can mean a transcript. It can mean a record of a failed debugging attempt. It can even mean a hidden provider-side profile that the user cannot export.

Those are not the same kind of state.

For doll, the useful distinction is now explicit.

The **memory layer** answers:

> What should a later model be able to remember or recall?

The **continuity layer** answers:

> If the model, provider, runtime, interface, conversation, or machine is replaced, what user-owned state is required to reconstruct and safely resume the AI-assisted environment?

The second question contains the first, but it is much larger.

A portable memory file may preserve facts, preferences, relationships, and conversational context. It does not necessarily preserve the user's current project objective, a blocked work item, an approved procedure, a permission rule, a model binding, a portability-loss report, a verified checkpoint, or a recovery path.

That is why doll remains a personal AI continuity system. Portable memory becomes one subsystem and one interoperability surface.

## Change 1: use PAM for interchange instead of inventing a Doll memory standard

PAM's most useful idea for doll is also its simplest: a memory interchange format should be separate from an application's internal storage.

Doll already has an internal canonical state model and the broader Doll State Package. Replacing those with PAM would throw away distinctions that matter to continuity. But creating a competing “Doll Portable Memory Format” would be unnecessary ecosystem fragmentation if a suitable open format already exists.

The design change is therefore:

- keep Doll State canonical inside doll;
- keep the Doll State Package as the broad continuity package;
- add a version-bound PAM import/export adapter for memory interchange;
- report mapping and loss explicitly;
- never treat a PAM file as complete doll continuity.

This also means that PAM-specific identifiers, hashes, access metadata, or signatures do not silently become Doll authority. They are source-format data until the Doll import and trust boundary interprets them.

One seemingly small detail matters here. PAM's content hash is defined for PAM interoperability. Doll should calculate it when required by the PAM adapter, but it should not adopt that hash as the canonical identity of a Doll memory. Interchange conformance and internal semantic identity are different responsibilities.

## Change 2: separate the truth of a memory from how often it is recalled

PLUR's Engram design demonstrates something doll currently lacks: memory gets more useful when retrieval quality can improve through use.

Frequency, recency, positive feedback, negative feedback, semantic similarity, and associations can all improve context selection. A local system should eventually be able to use those signals instead of searching every memory with one fixed rule forever.

But PLUR also makes a design choice that doll should not copy literally. In an activation-based memory engine, retrieval strength can decay and influence whether an item is active, fading, dormant, or a retirement candidate. That is sensible for retrieval. It is dangerous if the same score controls the authoritative truth or lifecycle of user-owned memory.

A preference that has not been recalled for six months does not become false. A technical constraint that is rarely used does not become safe to delete. A memory that ranks poorly under one embedding model should not lose status when that model is replaced.

So doll is splitting the state:

**Authoritative MemoryRecord** keeps semantic content, provenance, confirmation, validity, sensitivity, contradictions, and lifecycle.

**MemoryUsageSignalRecord**, when persistence is useful, records bounded events such as recall, explicit reinforcement, helpfulness, irrelevance, or surfaced contradiction without rewriting the memory itself.

**RecallState** is derived. It can include lexical scores, semantic scores, recency, usefulness, ranking, embedding references, and algorithm version. It must be rebuildable.

This is a consequential change because the earlier memory specification allowed `last_recalled_at` and `recall_count` to live directly on MemoryRecord. The new specification deprecates those as new authoritative memory fields. Retrieval should not increment the revision of the thing being remembered.

The practical test is simple: delete the entire semantic index. The memories must still exist, still mean the same thing, still export, and still be recoverable. Rebuild the index with a different embedding model. The ranking may change; the memories must not.

## Change 3: add consolidation, but keep it review-controlled

A growing memory store eventually has another problem: duplicates, contradictions, stale validity, and overly broad records.

Doll already separates suggested and confirmed memory, but it does not yet have a mature consolidation loop. The new design allows deterministic rules or models to identify likely duplicates and contradictions and propose merges, splits, supersession, or revised validity.

The important word is **propose**.

A consolidation engine cannot decide that a confirmed memory is obsolete because it was not recalled. A model cannot merge two confirmed memories because they look semantically similar. Repetition by several models does not become user confirmation.

This keeps the useful part of adaptive memory while preserving doll's existing authority model.

## Change 4: record project experience separately from system audit

PROJECTMEM exposed a different gap.

Doll already has strong current project state. It can represent objectives, scope, WorkItems, decisions, procedures, checkpoints, blockers, verification evidence, deterministic project status, and Resume Bundles.

What it does not represent cleanly enough is the narrative of work:

- we observed this;
- we suspected that;
- we tried this approach;
- it failed;
- another approach partially worked;
- this was the resolution;
- this is the lesson we should not have to rediscover next week.

AuditEventRecord is not the right place for that. Audit records operational history: who or what performed a mutation, what operation ran, and whether it succeeded. That is necessary for accountability, but it is not the semantic history of the work.

The new `ProjectExperienceRecord` fills that gap.

Its initial event vocabulary covers observations, hypotheses, attempts, outcomes, resolutions, and lessons. It can link to WorkItems, evidence, sources, and other records. Published semantic events are append-oriented: if an old record is wrong, a new record supersedes or corrects it instead of silently rewriting the past.

This deliberately borrows the strongest part of PROJECTMEM without copying its entire architecture.

Doll is **not** becoming globally event-sourced. Current policy, permission, project, decision, work, checkpoint, and model-binding state remains revisioned current state. Event history is useful for what happened; it is not automatically the best representation of what is currently true.

## Change 5: use past experience before an action, but do not create a second permission system

The most interesting PROJECTMEM idea is not storage. It is the pre-action warning.

Remembering that an approach failed is useful. Warning before repeating it is more useful.

Doll will generalize that concept as `ContinuityPreflight`: a deterministic, model-independent read-only check that can look at applicable policy, permission, decisions, approved procedures, work blockers, and prior project experience before a proposed action proceeds.

This is where the distinction between memory and authority matters most.

A prior failed attempt should usually produce a warning, not a new hard prohibition. An imported event saying “never do this” should not become a security rule. A model-written lesson should not grant or revoke permission.

Hard denial still comes from the existing authoritative safety boundary: policy, permission, capability rules, blockers, and required confirmation.

ContinuityPreflight therefore does not replace the Capability Broker. It gives the broker and the user better continuity evidence before an action.

It also runs outside model reasoning. A model cannot avoid a known blocker merely because the relevant record did not fit into its prompt.

## Change 6: use MCP as an interface, not as state

Several current memory systems expose their operations through Model Context Protocol. Doll should eventually do the same where interoperability benefits justify it.

But MCP answers a different question: how does another agent or tool call doll?

It does not answer: what is doll's canonical state?

The initial direction is therefore conservative:

- scoped read-only inspection;
- deterministic search and retrieval;
- proposal-only creation where doll already has a proposal state;
- no protocol message that can directly grant permission, approve a procedure, confirm a checkpoint, complete work, retrieve a credential, or create high-risk confirmation.

A local MCP server also does not imply a remote network listener. Remote or cross-machine access needs a separate threat model.

## Change 7: future package signatures must authenticate the whole continuity package

Doll already verifies State Package contents with hashes. Long-term operation will eventually benefit from authenticity signatures as well.

The portability review highlighted an important rule: signing only a selected memory checksum is not enough for doll's broader package.

A future signed Doll State Package should authenticate a canonical manifest that binds every declared member by path, category, size, and digest. Remove a file, substitute a relationship file, or move bytes into a different declared category, and verification should fail.

Signing and encryption stay separate. A signed package is not necessarily confidential. An encrypted package is not necessarily authenticated by a known signer.

And doll should not invent cryptography. Canonicalization and signatures should use established standards and reviewed libraries.

## What is not changing

The review did not overturn doll's original architecture.

The following remain intact:

- local-complete, cloud-optional;
- SQLite as the initial authoritative metadata store;
- documented portable exports in addition to SQLite;
- Doll State Package for complete doll-to-doll continuity;
- model-independent policy, permission, trust, and capability boundaries;
- imported content as data, not authority;
- user-controlled confirmation for authoritative memory and project transitions;
- deterministic Resume Bundles;
- cloud adapters as removable optional extensions;
- models and embedding models as replaceable components.

There is no reason to move canonical state to YAML because PLUR uses YAML. There is no reason to move everything to JSONL because PROJECTMEM uses an append-only event log. There is no reason to move Doll State into PAM because PAM is a good interchange format.

The point of interoperability is to avoid letting another implementation choice become doll's new lock-in.

## What changes in the roadmap

The implementation sequence changes after IMP-083, but the earlier gates do not.

IMP-083 itself is a bounded local resource-measurement and evidence step. It does not implement the adaptive-memory or interoperability work described here.

The next memory-related work is ordered around one dependency: **separate recall mechanics from authoritative memory before making recall adaptive**.

The sequence is therefore:

1. preserve the existing explicit context-selection path;
2. add bounded usage-signal and derived RecallState foundations;
3. upgrade local retrieval in steps, with lexical fallback before optional semantic search;
4. add review-controlled consolidation;
5. add PAM v1.x memory import/export through the existing portability boundary;
6. add ProjectExperienceRecord with package, backup, restore, and fresh-process coverage;
7. add ContinuityPreflight after the experience record exists;
8. keep PLUR, PROJECTMEM, and MCP as later interoperability work unless a concrete need justifies an earlier bounded slice;
9. keep complete package signing in the long-term-operation phase.

None of these items receives an IMP number merely because it appears in a roadmap. Doll's existing rule remains: an implementation identifier is assigned only when the bounded issue is actually opened.

## Why this is a design change rather than a feature list

The easiest way to misuse the comparison would have been to copy features:

“PAM has signatures; add signatures.”

“PLUR has decay; add decay.”

“PROJECTMEM has events; make everything an event log.”

That would create a collection of mechanisms without a coherent ownership model.

The useful result of the comparison is a set of boundaries:

- **interchange is not canonical storage;**
- **recall priority is not truth;**
- **project history is not current state;**
- **past experience is not permission;**
- **an agent protocol is not authority;**
- **integrity, authenticity, and confidentiality are different properties.**

Those boundaries are the actual change.

They allow doll to borrow useful concepts without becoming dependent on PAM, PLUR, PROJECTMEM, MCP, a particular embedding model, or a particular retrieval algorithm.

That is the same principle doll started with, applied one level deeper: the useful capability may be replaceable, but the user's continuity must remain theirs.

## References reviewed for this design update

- Portable AI Memory (PAM), Specification v1.0 — https://portable-ai-memory.org/spec/v1.0/
- PLUR, The Engram Specification v2.1 — https://www.plur.ai/spec.html
- PROJECTMEM repository — https://github.com/riponcm/projectmem
- PROJECTMEM paper, arXiv:2606.12329 — https://arxiv.org/abs/2606.12329

These references informed the design review. They are not runtime dependencies, sources of Doll authority, or claims of complete compatibility.