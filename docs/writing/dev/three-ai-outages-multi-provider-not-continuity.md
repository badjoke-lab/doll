---
title: Three AI Providers Went Down at Once. Multi-Provider Is Still Not Continuity.
published: true
description: What the overlapping September 3 outages at ChatGPT, Claude, and Grok show about the difference between provider choice and user-owned AI continuity.
tags: ai, opensource, architecture, localfirst
series: doll
canonical_url: https://doll.badjoke-lab.com/notes/three-ai-outages-multi-provider-not-continuity/
---

On September 3, 2026, ChatGPT, Claude, and Grok all experienced availability problems during an overlapping period.

The incidents were not identical, and there is no evidence that they had one shared root cause. But for a short period, three major cloud AI providers were all impaired at the same time.

Anthropic reported elevated errors across multiple Claude models beginning at 13:26 UTC and said impact ended at 16:16 UTC. xAI reported a Grok models outage beginning at 13:30 UTC and lasting more than three and a half hours. OpenAI said a routing error beginning at 7:43 a.m. Pacific time made ChatGPT and Codex unavailable for some users across platforms, with a solution implemented around 8:17 a.m. Pacific time.

That leaves roughly half an hour in which the user-facing impact reported by all three providers overlapped.

The important lesson is not that three providers happened to have problems on the same day.

**Having several providers available is not the same thing as owning continuity.**

## The Obvious Answer Is Multi-Provider

The standard response to cloud dependence is straightforward: do not rely on only one provider.

If OpenAI is unavailable, switch to Anthropic. If Anthropic is unavailable, switch to xAI, Google, or another service. If one model is retired, route requests to another model.

This is useful. doll should support multiple model and provider options where they add value. A system that can switch providers is more resilient than one permanently tied to a single endpoint.

But provider switching solves only one layer of the problem: **where the next inference comes from**.

It does not automatically preserve the AI environment that has accumulated around that inference service.

## A Different Model Is Not the Same Environment

Long-running AI use accumulates more than prompts.

It accumulates memory, preferences, projects, decisions, procedures, files, work history, permissions, unresolved blockers, and the state needed to continue unfinished work.

If those things live only inside one provider's product, switching the model does not move the environment with it.

You may still have another capable model, but the new model may not know what was decided yesterday, what work is incomplete, which memory was confirmed by the user, what a failed attempt taught the project, or which local rule is allowed to authorize an action.

The user has changed engines, but the vehicle did not come with them.

That is why doll separates model capability from continuity state.

```text
user-owned state and work
memory / projects / decisions / provenance / permissions / recovery
                              ↓
                            doll
                              ↓
          local model / OpenAI / Anthropic / other provider
```

The lower layer can change. The upper layer should remain under the user's control.

## The September 3 Incidents Do Not Prove a Shared Failure Domain

The timing naturally invited speculation that the outages had one common cause. That should not be treated as established fact.

OpenAI described its own incident as a routing error. Anthropic described its outage as an infrastructure issue. SpaceX later said the Grok problems followed an outage at its Memphis compute center. Major infrastructure providers publicly reported no matching broad disruption at the time.

The incidents may therefore be more useful precisely because they do not need a common cause to make the point.

Independent services can fail independently and still overlap.

Redundancy lowers risk; it does not make external dependencies disappear.

## Local-First Is Not an Outage Trick

It would be easy to reduce doll's local-first rule to an outage workaround: keep a local model installed in case ChatGPT is down.

That is too narrow.

A local fallback can preserve some ability to reason or write during a network or provider outage. But doll's larger purpose is to keep the durable parts of the user's AI environment outside the failure boundary of any one model, provider, interface, account, or runtime.

Availability is only one failure mode.

The same architecture also matters when a provider changes pricing, retires a model, restricts an account, changes regional access, alters a product interface, modifies retention behavior, or shuts a service down.

It also matters when the problem is local: an application disappears, a runtime stops being maintained, a machine fails, or a preferred interface can no longer read its old state.

This is why doll's rule is not "use local AI instead of cloud AI."

**It is local-complete, cloud-optional.**

Cloud models can remain the best source of capability. The user's continuity should not be rented from them with the same dependency.

## What Multi-Provider Should Mean in doll

Multi-provider support is still valuable, but its role should be precise.

It should give the user replaceable sources of reasoning capability. It should not create several separate copies of the user's AI life, one inside each vendor.

The durable layer should preserve the information needed to continue across a provider change:

- confirmed memory and its provenance;
- project objectives, scope, work items, blockers, and next work;
- decisions and procedures;
- permissions and policy boundaries;
- project experience and correction history;
- artifacts and references;
- backup, restore, and recovery state.

A provider can then be selected for capability without becoming the canonical owner of those things.

## Provider Choice Is Resilience. User-Owned State Is Continuity.

The September 3 outages were resolved. They do not show that cloud AI is unusable, and they do not show that every provider will regularly fail at the same time.

They show something simpler.

Even when several excellent cloud providers exist, availability remains outside the user's control. Adding another provider improves resilience, but it does not by itself preserve the state, history, and authority that make an AI environment continuous.

doll is being built around that distinction.

**Provider choice is resilience. User-owned state is continuity.**

**Local-first is not an outage workaround. It is an ownership model for continuity.**

## Sources

- OpenAI Status — Elevated errors across ChatGPT and Codex, September 3, 2026: https://status.openai.com/incidents/01M1KWEDH417T2CF44YYHZDFCR
- Claude Status — September 3, 2026 incident history: https://status.claude.com/
- xAI Status — Grok models outage: https://status.x.ai/grok-com
- The Register — ChatGPT, Claude, and Grok all had outages at the same time: https://www.theregister.com/ai-and-ml/2026/09/03/chatgpt-claude-and-grok-all-had-outages-at-the-same-time/5294322
- WIRED — Nobody Is Saying Why OpenAI and Anthropic Had Outages Today: https://www.wired.com/story/nobody-is-saying-why-openai-and-anthropic-had-outages-today/

The incident times and provider descriptions above were checked on September 4, 2026. The overlap does not establish a common root cause, and this article does not claim one.

Disclosure: This article was prepared with AI assistance and reviewed, edited, and approved by the project maintainer.
