// SkillOS Background Service Worker
// Manages event queue, batched sync to backend, and alarms

const API_BASE = "http://localhost:8000";
const SYNC_INTERVAL_MINUTES = 2;
const BATCH_KEY = "skillos_event_queue";
const TOKEN_KEY = "skillos_token";
const SETTINGS_KEY = "skillos_settings";

// ── Default settings ──────────────────────────────────────────
const DEFAULT_SETTINGS = {
  enabled: true,
  sites: {
    youtube: true,
    udemy: true,
    coursera: true,
    freecodecamp: true,
    medium: true
  },
  minFocusSeconds: 10
};

// ── Alarm setup ───────────────────────────────────────────────
chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create("skillos_sync", { periodInMinutes: SYNC_INTERVAL_MINUTES });
  chrome.storage.local.set({ [SETTINGS_KEY]: DEFAULT_SETTINGS });
  console.log("[SkillOS] Extension installed, sync alarm set.");
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "skillos_sync") {
    flushEventQueue();
  }
});

// ── Message handler (from content scripts) ───────────────────
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "SKILLOS_EVENT") {
    enqueueEvent(msg.event);
    sendResponse({ ok: true });
  }

  if (msg.type === "GET_STATUS") {
    getStatus().then(sendResponse);
    return true; // async
  }

  if (msg.type === "SET_TOKEN") {
    chrome.storage.local.set({ [TOKEN_KEY]: msg.token });
    sendResponse({ ok: true });
  }

  if (msg.type === "CLEAR_TOKEN") {
    chrome.storage.local.remove(TOKEN_KEY);
    sendResponse({ ok: true });
  }

  if (msg.type === "UPDATE_SETTINGS") {
    chrome.storage.local.set({ [SETTINGS_KEY]: msg.settings });
    sendResponse({ ok: true });
  }

  if (msg.type === "FORCE_SYNC") {
    flushEventQueue().then(sendResponse);
    return true;
  }
});

// ── Enqueue event ─────────────────────────────────────────────
async function enqueueEvent(event) {
  const result = await chrome.storage.local.get(BATCH_KEY);
  const queue = result[BATCH_KEY] || [];

  // Dedup: same resource_id + event within 30 seconds
  const isDup = queue.some(e =>
    e.resource_id === event.resource_id &&
    e.event === event.event &&
    (Date.now() - new Date(e.timestamp).getTime()) < 30000
  );

  if (!isDup) {
    queue.push({ ...event, timestamp: new Date().toISOString() });
    await chrome.storage.local.set({ [BATCH_KEY]: queue });
  }
}

// ── Flush queue to backend ────────────────────────────────────
async function flushEventQueue() {
  const { [BATCH_KEY]: queue, [TOKEN_KEY]: token } = await chrome.storage.local.get([BATCH_KEY, TOKEN_KEY]);

  if (!token) {
    console.log("[SkillOS] No token, skipping sync.");
    return { synced: 0, reason: "no_token" };
  }

  if (!queue || queue.length === 0) {
    return { synced: 0, reason: "empty_queue" };
  }

  try {
    // Also log activity minutes to the /activity/log endpoint
    const minutesByDate = {};
    for (const evt of queue) {
      if (evt.duration_seconds) {
        const date = evt.timestamp.slice(0, 10);
        minutesByDate[date] = (minutesByDate[date] || 0) + Math.round(evt.duration_seconds / 60);
      }
    }

    // Log activity for today
    const todayMinutes = Object.values(minutesByDate).reduce((a, b) => a + b, 0);
    if (todayMinutes > 0) {
      await fetch(`${API_BASE}/activity/log?minutes=${todayMinutes}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        }
      });
    }

    // Try to save resources detected
    for (const evt of queue) {
      if (evt.event === "start" && evt.title) {
        try {
          await fetch(`${API_BASE}/resources`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({
              platform: capitalize(evt.source),
              title: evt.title,
              url: evt.url,
              duration: evt.duration_seconds ? `${Math.round(evt.duration_seconds / 60)} min` : null,
              tags: evt.tags || [],
              platform_color: PLATFORM_COLORS[evt.source] || null
            })
          });
        } catch (_) {
          // Resource might already exist; silently ignore
        }
      }
    }

    // Clear queue on success
    await chrome.storage.local.set({ [BATCH_KEY]: [] });
    await chrome.storage.local.set({ "skillos_last_sync": new Date().toISOString(), "skillos_total_synced": (await getTotalSynced()) + queue.length });

    console.log(`[SkillOS] Synced ${queue.length} events.`);
    return { synced: queue.length };

  } catch (err) {
    console.error("[SkillOS] Sync failed:", err);
    return { synced: 0, reason: "network_error" };
  }
}

async function getTotalSynced() {
  const r = await chrome.storage.local.get("skillos_total_synced");
  return r.skillos_total_synced || 0;
}

async function getStatus() {
  const data = await chrome.storage.local.get([TOKEN_KEY, BATCH_KEY, "skillos_last_sync", "skillos_total_synced", SETTINGS_KEY]);
  return {
    loggedIn: !!data[TOKEN_KEY],
    queueLength: (data[BATCH_KEY] || []).length,
    lastSync: data.skillos_last_sync || null,
    totalSynced: data.skillos_total_synced || 0,
    settings: data[SETTINGS_KEY] || DEFAULT_SETTINGS
  };
}

const PLATFORM_COLORS = {
  youtube: "#E24B4A",
  udemy: "#7C3AED",
  coursera: "#2563EB",
  freecodecamp: "#16A34A",
  medium: "#64748B"
};

function capitalize(s) {
  if (!s) return "";
  return s.charAt(0).toUpperCase() + s.slice(1);
}
