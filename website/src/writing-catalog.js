export const OFFICIAL_NOTES = Object.freeze([
  Object.freeze({
    id: "access-is-not-continuity",
    kind: "official",
    title: "Being Able to Use Powerful AI Is Not the Same as Being Able to Keep Using It",
    path: "/notes/access-is-not-continuity/",
    description: "Why temporary access to powerful cloud AI is not the same as continuity, and why doll keeps memory, identity, settings, data, and recovery paths on the user's side.",
    summary: "Why doll treats cloud models as replaceable performance extensions while keeping memory, identity, settings, data, and continuity under the user's control.",
    published: "2026-06-27",
    related: Object.freeze(["permissioned-ai-access", "ai-will-remain", "ai-permission-divide"]),
    externalVersions: Object.freeze([]),
  }),
  Object.freeze({
    id: "permissioned-ai-access",
    kind: "official",
    title: "Is Access to Frontier AI Becoming Permissioned?",
    path: "/notes/permissioned-ai-access/",
    description: "What the reported GPT-5.6 rollout and Anthropic's suspension of Fable 5 and Mythos 5 suggest about the future of cloud AI access.",
    summary: "A source-based look at how pre-release review, export controls, and government-selected early access are changing the continuity risks of relying on cloud AI.",
    published: "2026-06-26",
    related: Object.freeze(["access-is-not-continuity", "ai-permission-divide", "ai-will-remain"]),
    externalVersions: Object.freeze([
      Object.freeze({
        publisher: "DEV Community",
        url: "https://dev.to/sohachi/is-access-to-frontier-ai-becoming-permissioned-e84",
      }),
    ]),
  }),
  Object.freeze({
    id: "ai-permission-divide",
    kind: "official",
    title: "The AI Divide Will Be About Permission, Not Access",
    path: "/notes/ai-permission-divide/",
    description: "What corporate restrictions on AI agents may tell us about a future in which access is widespread but meaningful capability is tiered by permission.",
    summary: "How ordinary restrictions on powerful AI agents may point toward a wider division based on which capabilities people and institutions are permitted to use.",
    published: "2026-06-21",
    related: Object.freeze(["access-is-not-continuity", "permissioned-ai-access", "ai-will-remain"]),
    externalVersions: Object.freeze([]),
  }),
  Object.freeze({
    id: "ai-will-remain",
    kind: "official",
    title: "AI Will Remain. Your Access Conditions May Not.",
    path: "/notes/ai-will-remain/",
    description: "Why personal AI continuity requires user-owned state and resumable work outside any one model, provider, runtime, interface, or machine.",
    summary: "A translated conversation with GPT-5.5 Thinking about whether the conditions that made doll seem necessary are already beginning to emerge.",
    published: "2026-06-19",
    updated: "2026-06-20",
    related: Object.freeze(["access-is-not-continuity", "permissioned-ai-access", "ai-permission-divide", "why-im-building-doll"]),
    externalVersions: Object.freeze([]),
  }),
]);

export const EXTERNAL_PUBLICATIONS = Object.freeze([
  Object.freeze({
    id: "why-im-building-doll",
    kind: "external-only",
    title: "Why I'm Building doll: A Personal AI Continuity System",
    publisher: "DEV Community",
    url: "https://dev.to/badjoke-lab/why-im-building-doll-a-personal-ai-continuity-system-1a1c",
    published: "2026-06-20",
    summary: "An introduction to the motivation and basic idea behind doll.",
  }),
]);

export const ALL_WRITING = Object.freeze([...OFFICIAL_NOTES, ...EXTERNAL_PUBLICATIONS]);

export function normalizeWritingPath(pathname) {
  if (!pathname || pathname === "/") {
    return pathname || "/";
  }

  const withoutIndex = pathname.endsWith("/index.html")
    ? pathname.slice(0, -"index.html".length)
    : pathname;

  return withoutIndex.endsWith("/") ? withoutIndex : `${withoutIndex}/`;
}

export function findOfficialNote(pathname) {
  const normalized = normalizeWritingPath(pathname);
  return OFFICIAL_NOTES.find((entry) => entry.path === normalized) || null;
}

export function findWritingById(id) {
  return ALL_WRITING.find((entry) => entry.id === id) || null;
}
