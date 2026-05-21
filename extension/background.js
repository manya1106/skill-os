// SkillOS Background Service Worker
// Manages event queue, batched sync to backend, PII-safe email hashing

const API_BASE = "http://localhost:8000";
const SYNC_ENDPOINT = `${API_BASE}/api/v1/sync/events`;
const SYNC_INTERVAL_MINUTES = 2;
const BATCH_KEY = "skillos_event_queue";
const TOKEN_KEY = "skillos_token";
const EMAIL_HASH_KEY = "skillos_email_hash";
const SETTINGS_KEY = "skillos_settings";

const DEFAULT_SETTINGS = {
  enabled: true,
  sites: {
    youtube: true,
    udemy: true,
    coursera: true,
    freecodecamp: true,
    medium: true,
  },
  minFocusSeconds: 10,
};

// ── SHA-256 email hashing (PII never stored or transmitted raw) ───────────────

async function sha256Hex(text) {
  const normalized = text.trim().toLowerCase();
  const buf = new TextEncoder().encode(normalized);
  const hash = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/**
 * Fetch account email once via JWT, hash locally, discard raw email.
 * Only the hash is persisted and sent with sync payloads.
 */
async function refreshEmailHash(token) {
  if (!token) return null;

  try {
    const res = await fetch(`${API_BASE}/users/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return null;

    const user = await res.json();
    if (!user.email) return null;

    const emailHash = await sha256Hex(user.email);
    await chrome.storage.local.set({ [EMAIL_HASH_KEY]: emailHash });
    console.log("[SkillOS] Email hash refreshed (raw email not stored).");
    return emailHash;
  } catch (err) {
    console.warn("[SkillOS] Could not refresh email hash:", err);
    return null;
  }
}

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

// ── Message handler ───────────────────────────────────────────

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "SKILLOS_EVENT") {
    enqueueEvent(msg.event);
    sendResponse({ ok: true });
  }

  if (msg.type === "GET_STATUS") {
    getStatus().then(sendResponse);
    return true;
  }

  if (msg.type === "SET_TOKEN") {
    chrome.storage.local.set({ [TOKEN_KEY]: msg.token }, async () => {
      await refreshEmailHash(msg.token);
      sendResponse({ ok: true });
    });
    return true;
  }

  if (msg.type === "REFRESH_EMAIL_HASH") {
    chrome.storage.local.get(TOKEN_KEY, async (data) => {
      const hash = await refreshEmailHash(data[TOKEN_KEY]);
      sendResponse({ ok: !!hash, email_hash: hash });
    });
    return true;
  }

  if (msg.type === "CLEAR_TOKEN") {
    chrome.storage.local.remove([TOKEN_KEY, EMAIL_HASH_KEY]);
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

  const isDup = queue.some(
    (e) =>
      e.resource_id === event.resource_id &&
      e.event === event.event &&
      Date.now() - new Date(e.timestamp).getTime() < 30000
  );

  if (!isDup) {
    queue.push({ ...event, timestamp: new Date().toISOString() });
    await chrome.storage.local.set({ [BATCH_KEY]: queue });
  }
}

// ── Bulk sync to POST /api/v1/sync/events ────────────────────

async function flushEventQueue() {
  const data = await chrome.storage.local.get([BATCH_KEY, TOKEN_KEY, EMAIL_HASH_KEY]);
  const queue = data[BATCH_KEY];
  const token = data[TOKEN_KEY];

  if (!token) {
    console.log("[SkillOS] No token, skipping sync.");
    return { synced: 0, reason: "no_token" };
  }

  if (!queue || queue.length === 0) {
    return { synced: 0, reason: "empty_queue" };
  }

  let emailHash = data[EMAIL_HASH_KEY];
  if (!emailHash) {
    emailHash = await refreshEmailHash(token);
  }

  const minutesByDate = {};
  for (const evt of queue) {
    if (evt.duration_seconds) {
      const dateKey = evt.timestamp.slice(0, 10);
      minutesByDate[dateKey] =
        (minutesByDate[dateKey] || 0) + Math.round(evt.duration_seconds / 60);
    }
  }
  const activityMinutes = Object.values(minutesByDate).reduce((a, b) => a + b, 0);

  try {
    const res = await fetch(SYNC_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        email_hash: emailHash || undefined,
        events: queue,
        activity_minutes: activityMinutes,
      }),
    });

    if (!res.ok) {
      const detail = await res.text();
      console.error("[SkillOS] Bulk sync failed:", res.status, detail);
      return { synced: 0, reason: "api_error", status: res.status };
    }

    const result = await res.json();
    const synced = result.synced ?? result.interactions_created ?? queue.length;

    await chrome.storage.local.set({ [BATCH_KEY]: [] });
    await chrome.storage.local.set({
      skillos_last_sync: new Date().toISOString(),
      skillos_total_synced: (await getTotalSynced()) + synced,
    });

    console.log(
      `[SkillOS] Bulk synced ${synced} events (${result.resources_created || 0} new resources).`
    );
    return {
      synced,
      resources_created: result.resources_created,
      errors: result.errors,
    };
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
  const data = await chrome.storage.local.get([
    TOKEN_KEY,
    EMAIL_HASH_KEY,
    BATCH_KEY,
    "skillos_last_sync",
    "skillos_total_synced",
    SETTINGS_KEY,
  ]);
  return {
    loggedIn: !!data[TOKEN_KEY],
    hasEmailHash: !!data[EMAIL_HASH_KEY],
    queueLength: (data[BATCH_KEY] || []).length,
    lastSync: data.skillos_last_sync || null,
    totalSynced: data.skillos_total_synced || 0,
    settings: data[SETTINGS_KEY] || DEFAULT_SETTINGS,
  };
}
