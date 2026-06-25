"use strict";

function setText(selector, value) {
  document.querySelectorAll(selector).forEach((element) => {
    element.textContent = value;
  });
}

function setLink(container, entry, fallback) {
  if (!container) {
    return;
  }

  container.replaceChildren();

  if (!entry) {
    container.textContent = fallback;
    return;
  }

  const link = document.createElement("a");
  link.href = entry.url;
  link.textContent = entry.title;
  container.appendChild(link);
}

function displayState(value) {
  if (typeof value !== "string" || value.length === 0) {
    return "Status unavailable";
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function renderRoadmap(status) {
  const completed = new Set(Array.isArray(status.completed_phases) ? status.completed_phases : []);
  const currentPhase = status.phase?.id || null;

  document.querySelectorAll("[data-roadmap-phase]").forEach((item) => {
    const phaseId = item.dataset.roadmapPhase;
    const state = item.querySelector("[data-roadmap-state]");
    if (!state) {
      return;
    }

    if (completed.has(phaseId)) {
      state.textContent = "Complete";
    } else if (phaseId === currentPhase) {
      state.textContent = displayState(status.phase?.state);
    } else {
      state.textContent = "Planned";
    }
  });
}

function renderCanonicalStatus(status) {
  if (!status || typeof status !== "object") {
    return;
  }

  setText("[data-project-maturity]", status.maturity || "Status unavailable");

  const phase = status.phase;
  if (phase && phase.id && phase.name && phase.state) {
    setText(
      "[data-project-phase]",
      `Phase ${phase.id} — ${phase.name} — ${phase.state}`,
    );
  }

  const runtime = status.model_runtime;
  if (runtime && typeof runtime.message === "string") {
    setText("[data-project-runtime]", runtime.message);
  }

  renderRoadmap(status);
}

function renderPrimaryActivity(activity) {
  const active = activity?.current || null;
  const entry = active || activity?.last_completed || null;
  const headerLabel = active ? "Current" : "Latest completed";
  const developmentLabel = active ? "Current implementation" : "Latest completed implementation";
  const fallback = "Project implementation activity is temporarily unavailable.";

  setText("#project-primary-label", headerLabel);
  setText("#development-primary-label", developmentLabel);
  setLink(document.getElementById("project-primary"), entry, fallback);
  setLink(document.getElementById("development-primary"), entry, fallback);
}

function renderUpNext(activity) {
  const section = document.getElementById("development-up-next-section");
  const container = document.getElementById("development-up-next");
  if (!section || !container) {
    return;
  }

  const next = activity?.next || null;
  section.hidden = !next;
  if (next) {
    setLink(container, next, "");
  } else {
    container.replaceChildren();
  }
}

function renderRecentDevelopment(activity) {
  const developmentLog = document.getElementById("development-log");
  if (!developmentLog) {
    return;
  }

  developmentLog.replaceChildren();

  const recent = Array.isArray(activity?.recent) ? activity.recent : [];
  if (recent.length === 0) {
    const fallback = document.createElement("p");
    fallback.textContent = "Recent development history is available on GitHub.";
    developmentLog.appendChild(fallback);
    return;
  }

  recent.forEach((entry) => {
    const wrapper = document.createElement("div");
    wrapper.className = "development-entry";

    const date = document.createElement("p");
    date.textContent = entry.merged_at ? entry.merged_at.slice(0, 10) : "";

    const title = document.createElement("p");
    const strong = document.createElement("strong");
    strong.textContent = entry.title;
    title.appendChild(strong);

    const linkLine = document.createElement("p");
    const link = document.createElement("a");
    link.href = entry.url;
    link.textContent = `PR #${entry.number}`;
    linkLine.appendChild(link);

    wrapper.append(date, title, linkLine);
    developmentLog.appendChild(wrapper);
  });
}

function renderActivity(activity) {
  renderPrimaryActivity(activity);
  renderUpNext(activity);
  renderRecentDevelopment(activity);
}

async function readJson(url) {
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`${url} returned ${response.status}`);
  }

  return response.json();
}

async function loadStatus() {
  const [canonicalResult, activityResult] = await Promise.allSettled([
    readJson("/project-status.json"),
    readJson("/api/project-status"),
  ]);

  if (canonicalResult.status === "fulfilled") {
    renderCanonicalStatus(canonicalResult.value);
  }

  if (activityResult.status === "fulfilled") {
    renderActivity(activityResult.value);
  } else {
    renderActivity(null);
  }
}

loadStatus();
