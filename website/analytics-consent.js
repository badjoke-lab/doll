"use strict";

(() => {
  const cookieName = "doll_analytics";
  const granted = "granted";
  const denied = "denied";
  let panel = null;

  function readChoice() {
    const prefix = `${cookieName}=`;
    const value = document.cookie
      .split(";")
      .map((part) => part.trim())
      .find((part) => part.startsWith(prefix));

    if (!value) {
      return null;
    }

    const choice = decodeURIComponent(value.slice(prefix.length));
    return choice === granted || choice === denied ? choice : null;
  }

  function writeChoice(value) {
    const oneYear = 60 * 60 * 24 * 365;
    document.cookie = `${cookieName}=${encodeURIComponent(value)}; Path=/; Max-Age=${oneYear}; SameSite=Lax; Secure`;
  }

  function closePanel() {
    if (panel) {
      panel.remove();
      panel = null;
    }
    delete document.documentElement.dataset.analyticsPanel;
  }

  function select(value) {
    writeChoice(value);
    closePanel();
    window.location.reload();
  }

  function showPanel() {
    closePanel();

    const consentPanel = document.createElement("aside");
    consentPanel.className = "analytics-consent";
    consentPanel.setAttribute("role", "dialog");
    consentPanel.setAttribute("aria-labelledby", "analytics-consent-title");

    const inner = document.createElement("div");
    inner.className = "analytics-consent-inner";

    const copy = document.createElement("div");
    copy.className = "analytics-consent-copy";

    const title = document.createElement("p");
    title.id = "analytics-consent-title";
    const strong = document.createElement("strong");
    strong.textContent = "Optional analytics";
    title.appendChild(strong);

    const explanation = document.createElement("p");
    explanation.textContent = "Google Analytics is off unless you allow it. Declining keeps the analytics tag disabled.";

    const actions = document.createElement("p");
    actions.className = "analytics-consent-actions";

    const allowButton = document.createElement("button");
    allowButton.type = "button";
    allowButton.textContent = "Allow analytics";
    allowButton.addEventListener("click", () => select(granted));

    const declineButton = document.createElement("button");
    declineButton.type = "button";
    declineButton.textContent = "Decline";
    declineButton.addEventListener("click", () => select(denied));

    const privacyLink = document.createElement("a");
    privacyLink.href = "/privacy/";
    privacyLink.textContent = "Privacy";

    actions.append(allowButton, declineButton, privacyLink);
    copy.append(title, explanation);
    inner.append(copy, actions);
    consentPanel.appendChild(inner);
    document.body.prepend(consentPanel);
    document.documentElement.dataset.analyticsPanel = "open";
    panel = consentPanel;
  }

  function initialize() {
    const choice = readChoice();
    document.documentElement.dataset.analyticsConsent = choice || "unset";

    if (!choice) {
      showPanel();
    }

    document.querySelectorAll("[data-analytics-settings]").forEach((control) => {
      control.addEventListener("click", showPanel);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize, { once: true });
  } else {
    initialize();
  }
})();
