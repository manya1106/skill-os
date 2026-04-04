// SkillOS — Coursera Content Script
(function () {
  "use strict";

  const SOURCE = "coursera";
  let lastItemId = null;
  let hasSentStart = false;
  let lastPct = 0;

  function getItemId() {
    const match = window.location.pathname.match(/\/learn\/([^/]+)\/(lecture|quiz|supplement)\/([^/]+)/);
    return match ? `${match[1]}_${match[3]}` : null;
  }

  function getMeta() {
    const title = document.querySelector("h1[data-test='lesson-name'], .rc-CML h3, h1")?.textContent?.trim()
      || document.title.replace(" | Coursera", "").trim();

    const courseName = document.querySelector("[class*='course-name'], .headline-1-text")?.textContent?.trim() || "";

    const video = document.querySelector("video");
    const duration = video ? Math.round(video.duration) : 0;
    const currentTime = video ? Math.round(video.currentTime) : 0;
    const watchPct = duration > 0 ? Math.round((currentTime / duration) * 100) : 0;

    const tags = [];
    if (courseName) tags.push(courseName.toLowerCase().replace(/\s+/g, "-").slice(0, 30));

    return { title, duration, watchPct, tags };
  }

  function sendEvent(eventType, extra = {}) {
    const itemId = getItemId();
    if (!itemId) return;
    const meta = getMeta();

    chrome.runtime.sendMessage({
      type: "SKILLOS_EVENT",
      event: {
        source: SOURCE,
        resource_id: `coursera_${itemId}`,
        url: window.location.href,
        event: eventType,
        title: meta.title,
        duration_seconds: meta.duration,
        watch_percentage: meta.watchPct,
        tags: meta.tags,
        ...extra
      }
    });
  }

  function onTimeUpdate() {
    const video = document.querySelector("video");
    if (!video || !hasSentStart) return;
    const pct = video.duration > 0 ? Math.round((video.currentTime / video.duration) * 100) : 0;
    for (const m of [25, 50, 75, 90]) {
      if (lastPct < m && pct >= m) {
        sendEvent("progress", { watch_percentage: pct });
        break;
      }
    }
    lastPct = pct;
  }

  function attachVideo() {
    const video = document.querySelector("video");
    if (!video || video._skillosAttached) return;
    video._skillosAttached = true;
    video.addEventListener("timeupdate", onTimeUpdate);
    video.addEventListener("ended", () => sendEvent("complete", { watch_percentage: 100 }));
  }

  function checkItem() {
    const itemId = getItemId();
    if (!itemId || itemId === lastItemId) return;
    lastItemId = itemId;
    hasSentStart = false;
    lastPct = 0;

    setTimeout(() => {
      sendEvent("start");
      hasSentStart = true;
      attachVideo();
    }, 5000);
  }

  const observer = new MutationObserver(() => { checkItem(); attachVideo(); });
  observer.observe(document.body, { childList: true, subtree: true });
  checkItem();
})();
