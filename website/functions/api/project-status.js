const REPOSITORY = "badjoke-lab/doll";
const CACHE_SECONDS = 10 * 60;
const IMPLEMENTATION_TITLE = /^IMP-(\d+)\s*:/i;

function githubHeaders(env) {
  const headers = {
    Accept: "application/vnd.github+json",
    "User-Agent": "doll-public-site",
    "X-GitHub-Api-Version": "2022-11-28",
  };

  if (env.GITHUB_TOKEN) {
    headers.Authorization = `Bearer ${env.GITHUB_TOKEN}`;
  }

  return headers;
}

function implementationNumber(title) {
  const match = IMPLEMENTATION_TITLE.exec(title || "");
  return match ? Number.parseInt(match[1], 10) : null;
}

function publicEntry(item, kind) {
  return {
    kind,
    number: item.number,
    implementation: implementationNumber(item.title),
    title: item.title,
    url: item.html_url,
    updated_at: item.updated_at,
    merged_at: item.merged_at || null,
  };
}

async function githubJson(path, env) {
  const response = await fetch(`https://api.github.com/repos/${REPOSITORY}${path}`, {
    headers: githubHeaders(env),
  });

  if (!response.ok) {
    throw new Error(`GitHub API returned ${response.status}`);
  }

  return response.json();
}

async function buildStatus(env) {
  const [openPulls, closedPulls, openIssues] = await Promise.all([
    githubJson("/pulls?state=open&per_page=50&sort=updated&direction=desc", env),
    githubJson("/pulls?state=closed&per_page=100&sort=updated&direction=desc", env),
    githubJson("/issues?state=open&per_page=100&sort=updated&direction=desc", env),
  ]);

  const mergedImplementationPulls = closedPulls
    .filter((pull) => pull.merged_at && implementationNumber(pull.title) !== null)
    .sort((a, b) => b.merged_at.localeCompare(a.merged_at));

  const latestMergedImplementation = mergedImplementationPulls.reduce(
    (latest, pull) => Math.max(latest, implementationNumber(pull.title)),
    -1,
  );

  const implementationPulls = openPulls
    .filter((pull) => {
      const number = implementationNumber(pull.title);
      return number !== null && number > latestMergedImplementation;
    })
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at));

  const implementationIssues = openIssues
    .filter((issue) => {
      if (issue.pull_request) {
        return false;
      }

      const number = implementationNumber(issue.title);
      return number !== null && number > latestMergedImplementation;
    })
    .sort((a, b) => {
      const numberDifference = implementationNumber(a.title) - implementationNumber(b.title);
      return numberDifference || a.created_at.localeCompare(b.created_at);
    });

  const currentPull = implementationPulls[0] || null;
  const currentIssue = implementationIssues[0] || null;
  const currentSource = currentPull || currentIssue;
  const current = currentSource
    ? publicEntry(currentSource, currentPull ? "pull_request" : "issue")
    : null;

  const currentImplementation = current?.implementation ?? latestMergedImplementation;
  const nextSource = implementationIssues.find(
    (issue) => implementationNumber(issue.title) > currentImplementation,
  );
  const next = nextSource ? publicEntry(nextSource, "issue") : null;

  const recent = mergedImplementationPulls
    .slice(0, 3)
    .map((pull) => publicEntry(pull, "pull_request"));

  return {
    schema_version: 1,
    repository: REPOSITORY,
    latest_merged_implementation:
      latestMergedImplementation >= 0 ? latestMergedImplementation : null,
    current,
    next,
    recent,
    fetched_at: new Date().toISOString(),
  };
}

function jsonResponse(
  body,
  status = 200,
  cacheControl = `public, max-age=60, s-maxage=${CACHE_SECONDS}`,
) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": cacheControl,
    },
  });
}

export async function onRequestGet(context) {
  const cache = caches.default;
  const cacheUrl = new URL(context.request.url);
  cacheUrl.pathname = "/__doll-public-project-status-v2";
  cacheUrl.search = "";
  const cacheKey = new Request(cacheUrl.toString(), { method: "GET" });

  const cached = await cache.match(cacheKey);
  if (cached) {
    return cached;
  }

  try {
    const status = await buildStatus(context.env);
    const response = jsonResponse(status);
    context.waitUntil(cache.put(cacheKey, response.clone()));
    return response;
  } catch (error) {
    return jsonResponse(
      {
        schema_version: 1,
        repository: REPOSITORY,
        latest_merged_implementation: null,
        current: null,
        next: null,
        recent: [],
        fetched_at: new Date().toISOString(),
        error: "Project activity is temporarily unavailable.",
      },
      503,
      "no-store",
    );
  }
}
