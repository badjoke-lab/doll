export const OFFICIAL_NOTES = Object.freeze([
  Object.freeze({
    id: "ai-will-remain",
    kind: "official",
    title: "AI Will Remain. Your Access Conditions May Not.",
    path: "/notes/ai-will-remain/",
    description: "Why personal AI continuity requires user-owned state and resumable work outside any one model, provider, runtime, interface, or machine.",
    summary: "A translated conversation with GPT-5.5 Thinking about whether the conditions that made doll seem necessary are already beginning to emerge.",
    published: "2026-06-19",
    updated: "2026-06-20",
    related: Object.freeze(["why-im-building-doll"]),
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
