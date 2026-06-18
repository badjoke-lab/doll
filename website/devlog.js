"use strict";

const endpoint = "https://api.github.com/repos/badjoke-lab/doll/pulls?state=closed&per_page=30&sort=updated&direction=desc";
const cacheKey = "doll-development-log-v1";
const cacheMaxAgeMs = 6 * 60 * 60 * 1000;
const container = document.getElementById("development-log");

function render(entries) {
  if (!container || !Array.isArray(entries) || entries.length === 0) {
    return;
  }

  container.replaceChildren();

  entries.slice(0, 10).forEach((entry) => {
    const wrapper = document.createElement("div");
    wrapper.className = "development-entry";

    const date = document.createElement("p");
    date.textContent = entry.merged_at.slice(0, 10);

    const title = document.createElement("p");
    const strong = document.createElement("strong");
    strong.textContent = entry.title;
    title.appendChild(strong);

    const linkLine = document.createElement("p");
    const link = document.createElement("a");
    link.href = entry.html_url;
    link.textContent = `PR #${entry.number}`;
    linkLine.appendChild(link);

    wrapper.append(date, title, linkLine);
    container.appendChild(wrapper);
  });
}

function readCache() {
  try {
    const cached = JSON.parse(localStorage.getItem(cacheKey));
    if (!cached || Date.now() - cached.savedAt > cacheMaxAgeMs) {
      return null;
    }
    return cached.entries;
  } catch {
    return null;
  }
}

function writeCache(entries) {
  try {
    localStorage.setItem(cacheKey, JSON.stringify({ savedAt: Date.now(), entries }));
  } catch {
    // The static fallback remains visible when storage is unavailable.
  }
}

async function load() {
  const cached = readCache();
  if (cached) {
    render(cached);
    return;
  }

  try {
    const response = await fetch(endpoint, {
      headers: { Accept: "application/vnd.github+json" },
    });

    if (!response.ok) {
      return;
    }

    const pulls = await response.json();
    const merged = pulls
      .filter((pull) => pull.merged_at)
      .sort((a, b) => b.merged_at.localeCompare(a.merged_at))
      .map((pull) => ({
        number: pull.number,
        title: pull.title,
        merged_at: pull.merged_at,
        html_url: pull.html_url,
      }));

    writeCache(merged);
    render(merged);
  } catch {
    // The static fallback remains visible when GitHub is unavailable.
  }
}

load();
