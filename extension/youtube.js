// SkillOS — YouTube Content Script
// Detects learning videos, tracks watch percentage, fires events to background

(function () {
  "use strict";

  const SOURCE = "youtube";
  let lastVideoId = null;
  let sessionStart = null;
  let lastWatchPct = 0;
  let focusTimer = null;
  let hasSentStart = false;

  function isLearningVideo() {
    const title = document.title.toLowerCase();
    const LEARNING_KEYWORDS = ["tutorial", "course", "learn", "lesson", "lecture",
      "explained", "how to", "introduction", "bootcamp", "crash course", "guide",
      "workshop", "masterclass", "tips", "tricks", "beginner", "advanced"];
    return LEARNING_KEYWORDS.some(kw => title.includes(kw));
  }

  function getVideoId() {
    const params = new URLSearchParams(window.location.search);
    return params.get("v");
  }

  function getVideoMeta() {
    const title = document.querySelector("h1.ytd-video-primary-info-renderer, yt-formatted-string.style-scope.ytd-watch-metadata")?.textContent?.trim()
      || document.title.replace(" - YouTube", "").trim();

    const channel = document.querySelector("#channel-name a, ytd-channel-name a")?.textContent?.trim() || "";

    const video = document.querySelector("video");
    const duration = video ? Math.round(video.duration) : 0;
    const currentTime = video ? Math.round(video.currentTime) : 0;
    const watchPct = duration > 0 ? Math.round((currentTime / duration) * 100) : 0;

    const tags = [];
    if (channel) tags.push(channel.toLowerCase().replace(/\s+/g, "-"));

    return { title, channel, duration, currentTime, watchPct, tags };
  }

  function sendEvent(eventType, extra = {}) {
    const videoId = getVideoId();
    if (!videoId) return;

    const meta = getVideoMeta();

    chrome.runtime.sendMessage({
      type: "SKILLOS_EVENT",
      event: {
        source: SOURCE,
        resource_id: `yt_${videoId}`,
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

  function onVideoChange() {
    const videoId = getVideoId();
    if (!videoId || videoId === lastVideoId) return;
    if (!window.location.pathname.includes("/watch")) return;

    lastVideoId = videoId;
    sessionStart = Date.now();
    lastWatchPct = 0;
    hasSentStart = false;

    // Only fire start event for likely-learning videos
    clearTimeout(focusTimer);
    focusTimer = setTimeout(() => {
      if (isLearningVideo() || true) { // track all YT for now
        sendEvent("start");
        hasSentStart = true;
      }
    }, 10000); // 10s focus threshold
  }

  function onTimeUpdate() {
    const video = document.querySelector("video");
    if (!video || !hasSentStart) return;

    const pct = video.duration > 0 ? Math.round((video.currentTime / video.duration) * 100) : 0;

    // Fire progress event at 25%, 50%, 75%, 90%
    for (const milestone of [25, 50, 75, 90]) {
      if (lastWatchPct < milestone && pct >= milestone) {
        sendEvent("progress", { watch_percentage: pct });
        break;
      }
    }
    lastWatchPct = pct;
  }

  function onEnded() {
    if (!hasSentStart) return;
    sendEvent("complete", { watch_percentage: 100 });
  }

  function attachVideoListeners() {
    const video = document.querySelector("video");
    if (!video || video._skillosAttached) return;
    video._skillosAttached = true;
    video.addEventListener("timeupdate", onTimeUpdate);
    video.addEventListener("ended", onEnded);
  }

  // YouTube is an SPA — watch for navigation
  const observer = new MutationObserver(() => {
    onVideoChange();
    attachVideoListeners();
  });

  observer.observe(document.body, { childList: true, subtree: true });

  // Initial check
  onVideoChange();
  attachVideoListeners();
})();
