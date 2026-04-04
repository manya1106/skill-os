// SkillOS — freeCodeCamp Content Script
// Tracks challenge visits and completions
(function () {
  "use strict";

  const SOURCE = "freecodecamp";
  let lastPath = null;
  let pageStart = null;

  function getChallengeId() {
    const path = window.location.pathname;
    if (!path.includes("/learn/")) return null;
    return path.replace(/\//g, "_").replace(/^_/, "");
  }

  function getMeta() {
    const title = document.querySelector("h1, [class*='challenge-title']")?.textContent?.trim()
      || document.title.replace(" | freeCodeCamp.org", "").trim();

    const curriculum = document.querySelector("[class*='breadcrumb'], nav a:last-child")?.textContent?.trim() || "";
    const tags = curriculum ? [curriculum.toLowerCase().replace(/\s+/g, "-").slice(0, 30)] : ["coding"];

    return { title, tags };
  }

  function sendEvent(eventType, extra = {}) {
    const challengeId = getChallengeId();
    if (!challengeId) return;
    const meta = getMeta();

    chrome.runtime.sendMessage({
      type: "SKILLOS_EVENT",
      event: {
        source: SOURCE,
        resource_id: `fcc_${challengeId}`,
        url: window.location.href,
        event: eventType,
        title: meta.title,
        tags: meta.tags,
        ...extra
      }
    });
  }

  function checkPage() {
    const path = window.location.pathname;
    if (!path.includes("/learn/") || path === lastPath) return;

    lastPath = path;
    pageStart = Date.now();
    sendEvent("start");
  }

  // Detect challenge completion by watching for the "Run the Tests" / success button
  function watchCompletion() {
    const successObserver = new MutationObserver(() => {
      const successMsg = document.querySelector("[class*='success'], [data-cy='completion-success']");
      if (successMsg && pageStart) {
        const durationSeconds = Math.round((Date.now() - pageStart) / 1000);
        sendEvent("complete", { duration_seconds: durationSeconds, watch_percentage: 100 });
        pageStart = null;
      }
    });
    successObserver.observe(document.body, { childList: true, subtree: true });
  }

  const navObserver = new MutationObserver(checkPage);
  navObserver.observe(document.body, { childList: true, subtree: false });

  checkPage();
  watchCompletion();
})();
