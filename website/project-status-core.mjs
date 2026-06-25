export const REPOSITORY = "badjoke-lab/doll";
export const RETIRED_IMPLEMENTATION_IDS = Object.freeze([24, 25, 26, 27, 28, 29]);

const IMPLEMENTATION_TITLE = /^IMP-(\d+)\s*:/i;
const WEBSITE_TITLE = /^WEB-\d+\s*:/i;
const PHASE_OR_GATE_COMPLETION =
  /(?:\b(?:complete|completed|pass|passed)\b.*\b(?:phase|gate)\b|\b(?:phase|gate)\b.*\b(?:complete|completed|pass|passed)\b)/i;

export function implementationNumber(title) {
  const match = IMPLEMENTATION_TITLE.exec(title || "");
  return match ? Number.parseInt(match[1], 10) : null;
}

export function publicEntry(item, kind) {
  return {
    kind,
    number: item.number ?? null,
    implementation: implementationNumber(item.title),
    title: item.title,
    url: item.html_url,
    updated_at: item.updated_at ?? null,
    merged_at: item.merged_at ?? null,
  };
}

export function isMeaningfulDevelopmentPull(pull) {
  if (!pull?.merged_at || typeof pull.title !== "string") {
    return false;
  }

  if (WEBSITE_TITLE.test(pull.title)) {
    return false;
  }

  return implementationNumber(pull.title) !== null || PHASE_OR_GATE_COMPLETION.test(pull.title);
}

function byImplementationAscending(a, b) {
  const difference = implementationNumber(a.title) - implementationNumber(b.title);
  return difference || (b.updated_at || "").localeCompare(a.updated_at || "");
}

function byImplementationDescending(a, b) {
  const difference = implementationNumber(b.title) - implementationNumber(a.title);
  return difference || (b.merged_at || "").localeCompare(a.merged_at || "");
}

export function buildProjectActivity({ openPulls = [], closedPulls = [], openIssues = [] }) {
  const mergedImplementationPulls = closedPulls
    .filter((pull) => pull.merged_at && implementationNumber(pull.title) !== null)
    .sort(byImplementationDescending);

  const lastCompletedSource = mergedImplementationPulls[0] || null;
  const latestMergedImplementation = lastCompletedSource
    ? implementationNumber(lastCompletedSource.title)
    : null;
  const completedFloor = latestMergedImplementation ?? 0;

  const implementationPulls = openPulls
    .filter((pull) => {
      const number = implementationNumber(pull.title);
      return number !== null && number > completedFloor;
    })
    .sort(byImplementationAscending);

  const implementationIssues = openIssues
    .filter((issue) => {
      if (issue.pull_request) {
        return false;
      }

      const number = implementationNumber(issue.title);
      return number !== null && number > completedFloor;
    })
    .sort(byImplementationAscending);

  const currentPull = implementationPulls[0] || null;
  const currentIssue = implementationIssues[0] || null;
  const currentSource = currentPull || currentIssue;
  const current = currentSource
    ? publicEntry(currentSource, currentPull ? "pull_request" : "issue")
    : null;

  const currentImplementation = current?.implementation ?? completedFloor;
  const nextIssue = implementationIssues.find(
    (issue) => implementationNumber(issue.title) > currentImplementation,
  );
  const nextImplementation = nextIssue
    ? implementationNumber(nextIssue.title)
    : currentImplementation + 1;

  const recent = closedPulls
    .filter(isMeaningfulDevelopmentPull)
    .sort((a, b) => b.merged_at.localeCompare(a.merged_at))
    .slice(0, 3)
    .map((pull) => publicEntry(pull, "pull_request"));

  return {
    schema_version: 2,
    repository: REPOSITORY,
    numbering_policy: {
      mode: "monotonic",
      retired_implementations: [...RETIRED_IMPLEMENTATION_IDS],
      next_planned_implementation: nextImplementation,
    },
    latest_merged_implementation: latestMergedImplementation,
    current,
    last_completed: lastCompletedSource
      ? publicEntry(lastCompletedSource, "pull_request")
      : null,
    next: nextIssue ? publicEntry(nextIssue, "issue") : null,
    recent,
  };
}
