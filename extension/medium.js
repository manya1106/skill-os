// SkillOS — Medium Content Script
// Tracks article reading via scroll depth
(function () {
  "use strict";

  const SOURCE = "medium";
  let lastArticleId = null;
  let maxScrollPct = 0;
  let hasSentStart = false;
  let readTimer = null;

  function getArticleId() {
    // Medium article IDs appear at the end of slugs
    const match = window.location.pathname.match(/-([a-f0-9]{10,12})$/);
    return match ? match[1] : window.location.pathname.replace(/\//g, "_");
  }

  function getMeta() {
    const title = document.querySelector("h1, [data-testid='storyTitle']")?.textContent?.trim()
      || document.title.replace(" | Medium", "").trim();

    const author = document.querySelector("[data-testid='authorName'], .pw-author-name")?.textContent?.trim() || "";

    // Estimate read time from Medium's own badge
    const readTimeBadge = document.querySelector("[data-testid='storyReadTime'], .readingTime")?.textContent?.trim() || "";
    const readMinutes = parseInt(readTimeBadge) || 5;
    const durationSeconds = readMinutes * 60;

    const tags = [];
    // Grab topic tags
    document.querySelectorAll("[href*='/tag/'], [data-testid='tag']").forEach(el => {
      const tag = el.textContent?.trim().toLowerCase().replace(/\s+/g, "-");
      if (tag && !tags.includes(tag)) tags.push(tag);
    });

    return { title, author, durationSeconds, tags: tags.slice(0, 5) };
  }

  function getScrollPct() {
    const scrollTop = window.scrollY;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    return docHeight > 0 ? Math.round((scrollTop / docHeight) * 100) : 0;
  }

  function sendEvent(eventType, extra = {}) {
    const articleId = getArticleId();
    if (!articleId) return;
    const meta = getMeta();

    chrome.runtime.sendMessage({
      type: "SKILLOS_EVENT",
      event: {
        source: SOURCE,
        resource_id: `medium_${articleId}`,
        url: window.location.href,
        event: eventType,
        title: meta.title,
        duration_seconds: meta.durationSeconds,
        watch_percentage: maxScrollPct,
        tags: meta.tags,
        ...extra
      }
    });
  }

  function onScroll() {
    const pct = getScrollPct();
    if (pct > maxScrollPct) maxScrollPct = pct;

    // Fire progress milestones
    for (const m of [25, 50, 75, 90]) {
      if (maxScrollPct >= m && hasSentStart) {
        // Use a flag per milestone to avoid duplicate fires
        const flagKey = `_skillos_m${m}`;
        if (!window[flagKey]) {
          window[flagKey] = true;
          sendEvent("progress", { watch_percentage: m });
        }
      }
    }

    // "Completed" if user scrolled to 85%+
    if (maxScrollPct >= 85 && !window._skillosCompleted) {
      window._skillosCompleted = true;
      sendEvent("complete", { watch_percentage: maxScrollPct });
    }
  }

  function checkArticle() {
    const articleId = getArticleId();
    if (!articleId || articleId === lastArticleId) return;
    if (!document.querySelector("article, [data-testid='post-content']")) return;

    lastArticleId = articleId;
    maxScrollPct = 0;
    hasSentStart = false;
    window._skillosCompleted = false;
    window._skillos_m25 = window._skillos_m50 = window._skillos_m75 = window._skillos_m90 = false;

    // 8s focus threshold before registering a "start"
    clearTimeout(readTimer);
    readTimer = setTimeout(() => {
      sendEvent("start");
      hasSentStart = true;
    }, 8000);
  }

  window.addEventListener("scroll", onScroll, { passive: true });

  const observer = new MutationObserver(checkArticle);
  observer.observe(document.body, { childList: true, subtree: true });
  checkArticle();
})();
