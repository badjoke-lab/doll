import { REPOSITORY, buildProjectActivity } from "../../project-status-core.mjs";

const CACHE_SECONDS = 10 * 60;

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

  return {
    ...buildProjectActivity({ openPulls, closedPulls, openIssues }),
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
  cacheUrl.pathname = "/__doll-public-project-status-v4";
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
        schema_version: 2,
        repository: REPOSITORY,
        numbering_policy: {
          mode: "monotonic",
          retired_implementations: [24, 25, 26, 27, 28, 29],
          next_planned_implementation: null,
        },
        latest_merged_implementation: null,
        current: null,
        last_completed: null,
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
