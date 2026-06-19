"use strict";

(() => {
  const storageKey = "doll-analytics-consent-v1";
  const granted = "granted";
  const denied = "denied";
  let panel = null;

  function readChoice() {
    try {
      const value = localStorage.getItem(storageKey);
      return value === granted || value === denied ? value : null;
    } catch {
      return null;
    }
  }

  function writeChoice(value) {
    try {
      localStorage.setItem(storageKey, value);
    } catch {
      // The current page still respects the selected choice.
    }
  }

  function closePanel() {
    if (panel) {
      panel.remove();
      panel = null;
    }
  }

  function select(value) {
    writeChoice(value);
    document.documentElement.dataset.analyticsConsent = value;
    closePanel();
    document.dispatchEvent(new CustomEvent("doll:analytics-consent", { detail: value }));
  }

  function showPanel() {
    closePanel();

    panel = document.createElement("aside");
    panel.className = "analytics-consent";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-labelledby", "analytics-consent-title");

    const inner = document.createElement("div");
    inner.className = "analytics-consent-inner";

    const title = document.createElement("p");
    title.id = "analytics-consent-title";
    title.innerHTML = "<strong>Optional analytics</strong>";

    const explanation = document.createElement("p");
    explanation.textContent = "Google Analytics is off unless you allow it.";

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

    actions.append(allowButton, " ", declineButton, " ", privacyLink);
    inner.append(title, explanation, actions);
    panel.appendChild(inner);
    document.body.appendChild(panel);
    allowButton.focus();
  }

  function initialize() {
    const choice = readChoice();
    if (choice) {
      document.documentElement.dataset.analyticsConsent = choice;
    } else {
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
