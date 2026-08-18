---
title: How Comparing PAM, PLUR, and PROJECTMEM Changed doll's Design
published: false
description: Five concrete design changes in doll that became clearer after comparing PAM, PLUR, and PROJECTMEM: derived recall, adapter boundaries, project experience, authority, and deterministic continuity preflight.
tags: ai, opensource, architecture, localfirst
series: doll
canonical_url: https://doll.badjoke-lab.com/notes/pam-plur-projectmem-changed-doll-design/
---

The previous article compared Portable AI Memory (PAM), PLUR's Engram specification, PROJECTMEM, and doll.

The useful result was not choosing a winner. It was deciding which ideas belong in which layer.

Several things I had been calling "memory" were actually different kinds of state with different authority. That distinction changed concrete parts of doll's design.

The five most important changes are these:

1. confirmed memory was separated from derived recall state;
2. interchange formats became adapters instead of candidates for Doll State itself;
3. project experience became its own append-oriented history rather than current project authority;
4. imported and model-proposed information was kept below user-confirmed authority;
5. pre-action continuity checks became a separate deterministic read model rather than another execution authority.

This article is about those design changes, not another comparison of the external projects.

## 1. MemoryRecord Is Not RecallState

PLUR was useful because its Engram design makes retrieval dynamics visible: activation, decay, reinforcement, associations, usage feedback, and search all affect which memory is useful now.

That is a different question from whether the memory itself is still true.

The distinction sounds obvious until a memory system starts storing retrieval metadata next to the memory content and gradually treats both as one object.

In doll, confirmed `MemoryRecord` content is canonical durable state. Retrieval ranking, activation-like signals, search scores, and other recall signals are derived state. They can change, expire, or be rebuilt without rewriting what the memory says.

That means a memory is not made "less true" because it has not been retrieved recently, and it is not made "more true" because the system used it many times.

It also gives doll a cleaner failure mode. If a search index or future activation cache is lost, recall quality may temporarily degrade, but confirmed memory does not disappear with it.

**Recall can be derived from memory. Memory should not be silently rewritten by recall.**

## 2. PAM Became an Adapter Boundary, Not Doll State

PAM made another boundary much clearer.

Its specification explicitly describes PAM as an interchange format rather than a storage format. That is exactly the kind of boundary doll needs at the edge.

PAM v1.0 specification:
https://portable-ai-memory.org/spec/v1.0/

The tempting alternative would be to adopt a portable external schema as the canonical internal database simply because portability matters. But portability and internal authority are not the same problem.

doll therefore treats PAM v1.0 as an adapter target. Imported data is parsed and mapped into a staged form first. Unsupported or ambiguous semantics remain visible. Imported memories do not become normal confirmed MemoryRecords until they pass the appropriate review boundary.

Export works in the other direction: confirmed non-secret memory can be represented in bounded PAM output without pretending that PAM is a complete Doll State Package.

That last distinction matters. A memory interchange export is not a complete continuity export. It does not by itself contain every project, work item, decision, permission, procedure, recovery state, or execution boundary that makes a long-running AI environment resumable.

**Use external standards where they fit the boundary. Do not force the internal authority model to become the interchange format.**

## 3. Project Experience Became History, Not Authority

PROJECTMEM sharpened a different problem: project history should survive beyond chat transcripts and should be useful before the same mistake is repeated.

PROJECTMEM paper:
https://arxiv.org/abs/2606.12329

PROJECTMEM source repository:
https://github.com/riponcm/projectmem

That led doll to make project experience a first-class record instead of leaving failed attempts and lessons trapped inside conversation history.

The implemented `ProjectExperienceRecord` is append-oriented and can represent observations, hypotheses, attempts, outcomes, resolutions, and lessons. Corrections are represented through linked replacement or supersession rather than silently rewriting the semantic history.

ProjectExperienceRecord implementation:
https://github.com/badjoke-lab/doll/blob/main/src/doll/project_experience.py

But the most important part is what the record is *not* allowed to do.

An experience record does not complete or reopen a WorkItem. It does not change ProjectRecord scope. It does not create a DecisionRecord. It does not approve a required procedure. It does not grant a permission.

That boundary prevents a very easy category error: confusing "this happened before" with "this is the current authoritative state."

Historical experience can be valuable without being sovereign.

## 4. Imported and Model-Proposed Information Stay Below Authority

Once interchange and project experience are both first-class concepts, another problem appears immediately: what happens when imported or model-generated records make strong claims?

An imported record might say that a project is complete. A model-generated lesson might say that a particular action should never be attempted again. An external memory format might contain an access field that looks similar to a local permission.

doll does not allow those similarities to manufacture authority.

Imported or model-proposed information can be preserved, linked to provenance, surfaced to the user, and used as evidence. But it cannot silently become policy, permission, current work state, or a hard denial.

This is also why mapping loss has to stay visible. If an external concept does not map exactly onto a Doll concept, the system should preserve the ambiguity instead of inventing a clean equivalence.

A field named `confidence` is a simple example. One system may mean extraction confidence; another may mean user-reviewed trust. Treating those as equivalent because the names match would make migration look cleaner while damaging the authority model.

**Preserve imported knowledge. Preserve uncertainty too.**

## 5. ContinuityPreflight Became a Separate Read Model

The PROJECTMEM comparison also made pre-action checks more concrete. It is useful for a system to look at accepted project history before repeating an action that already failed.

But doll already had separate authority boundaries for policy, work state, procedures, permissions, and capabilities. Folding all of that into one new "memory judgment" layer would have made the architecture harder to reason about.

The resulting implementation is `ContinuityPreflight`: a deterministic, model-independent read model over explicit accepted project and action scope.

ContinuityPreflight implementation:
https://github.com/badjoke-lab/doll/blob/main/src/doll/continuity_preflight.py

It composes existing authoritative signals such as applicable policy denials, WorkItem blockers and incomplete dependencies, required procedure state, permission resolution, and capability safety state. It can also surface directly relevant prior failures from ProjectExperienceRecord as evidence-linked warnings.

The distinction between warning and authority is intentional. A past failed attempt can warn without becoming a permanent prohibition. Imported or model-proposed experience cannot manufacture a hard deny.

And a preflight result of `clear` does not grant execution permission. The Capability Broker remains the execution authorization boundary.

**A continuity check can inform execution without becoming the thing that authorizes execution.**

## The Comparison Changed the Boundaries More Than the Feature List

None of these changes means doll should absorb PAM, PLUR, or PROJECTMEM wholesale. In fact, the comparison pushed the design in the opposite direction.

The useful pieces belong at different layers:

- PAM belongs at the interchange boundary;
- PLUR-like activation and retrieval ideas belong in derived recall state;
- PROJECTMEM-like project experience belongs in append-oriented work history;
- current project state, permissions, policy, and execution authority remain separate;
- pre-action continuity is a deterministic composition over accepted state, not a new source of truth.

That is more important than adding another feature named "memory."

## What I Deliberately Did Not Adopt

Comparison is also useful because it identifies ideas that should remain external, derived, or later work.

doll does not currently claim a PLUR adapter or PROJECTMEM adapter. MCP is not implemented as part of this work. PAM interoperability does not mean complete state-package interoperability. ProjectExperienceRecord is not a replacement for WorkItem, DecisionRecord, PolicyRecord, ProcedureRecord, or PermissionRecord.

The project also does not claim that Phase 6, Lite v1.0, primary Intel Mac resource acceptance, or a general anti-lock-in standard is complete.

Those limits matter because architectural comparison is easy to turn into a story about a finished universal layer. doll is not there, and this work does not pretend otherwise.

## A More Precise Definition of Continuity

The comparison left doll with a more precise definition of what it is trying to preserve.

Continuity is not just the ability to export a list of memories. It is not just a better retrieval algorithm. It is not just a durable project log. And it is not just an agent remembering previous failures.

Those are all useful parts.

But continuity also requires keeping authority explicit: what is confirmed, what is derived, what is historical, what was imported, what is currently blocked, what requires permission, what may execute, and what can be rebuilt after a model, provider, runtime, interface, or machine changes.

**Standardize interchange. Derive recall. Preserve experience. Keep authority explicit.**

---

## Sources

1. Previous doll article — Portable Memory Is Not AI Continuity: PAM, PLUR, PROJECTMEM, and doll  
https://doll.badjoke-lab.com/notes/portable-memory-not-ai-continuity/

2. Portable AI Memory — Specification v1.0  
https://portable-ai-memory.org/spec/v1.0/

3. PLUR — The Engram Specification v2.1  
https://plur.ai/spec.html

4. PROJECTMEM paper  
https://arxiv.org/abs/2606.12329

5. PROJECTMEM source repository  
https://github.com/riponcm/projectmem

6. doll — Memory Interoperability, Recall, and Project Experience specification  
https://github.com/badjoke-lab/doll/blob/main/docs/spec/03c-memory-interoperability-recall-and-project-experience.md

7. doll — ProjectExperienceRecord implementation  
https://github.com/badjoke-lab/doll/blob/main/src/doll/project_experience.py

8. doll — ContinuityPreflight implementation  
https://github.com/badjoke-lab/doll/blob/main/src/doll/continuity_preflight.py

Canonical doll article:
https://doll.badjoke-lab.com/notes/pam-plur-projectmem-changed-doll-design/

External specifications and project descriptions referenced here were checked for the preceding comparison article on August 16, 2026. This article focuses on doll's resulting design decisions and merged implementation boundaries. It does not imply that PAM, PLUR, or PROJECTMEM endorse doll's architecture.

Disclosure: This article was prepared with AI assistance and reviewed, edited, and approved by the project maintainer.
