// SkillOS Extension Popup

const API_BASE = "http://localhost:8000";

const SITE_META = {
  youtube:      { label: "YouTube",      emoji: "📺", color: "#E24B4A" },
  udemy:        { label: "Udemy",        emoji: "🎓", color: "#7C3AED" },
  coursera:     { label: "Coursera",     emoji: "📘", color: "#2563EB" },
  freecodecamp: { label: "freeCodeCamp", emoji: "💻", color: "#16A34A" },
  medium:       { label: "Medium",       emoji: "✍️", color: "#64748B" }
};

// ── Init ──────────────────────────────────────────────────────
async function init() {
  const status = await bg("GET_STATUS");
  renderStatus(status);

  if (status.loggedIn) {
    showMain(status);
    fetchUserStats();
    detectCurrentTab();
  } else {
    showAuth();
  }
}

// ── Message helpers ───────────────────────────────────────────
function bg(type, payload = {}) {
  return new Promise(resolve =>
    chrome.runtime.sendMessage({ type, ...payload }, resolve)
  );
}

// ── Render helpers ────────────────────────────────────────────
function showAuth() {
  document.getElementById("auth-section").style.display = "block";
  document.getElementById("main-section").style.display = "none";
}

function showMain(status) {
  document.getElementById("auth-section").style.display = "none";
  document.getElementById("main-section").style.display = "block";

  document.getElementById("queue-count").textContent = status.queueLength;
  document.getElementById("stat-synced").textContent = status.totalSynced;

  if (status.lastSync) {
    const d = new Date(status.lastSync);
    const ago = formatAgo(d);
    document.getElementById("last-sync-sub").textContent = `Last synced ${ago}`;
    document.getElementById("footer-status").textContent = `Synced ${ago}`;
  }

  renderSiteToggles(status.settings);
}

function renderStatus(status) {
  const dot = document.getElementById("status-dot");
  dot.className = "status-dot" + (status.loggedIn ? "" : " offline");
}

function renderSiteToggles(settings) {
  const grid = document.getElementById("sites-grid");
  grid.innerHTML = "";
  for (const [key, meta] of Object.entries(SITE_META)) {
    const isOn = settings.sites[key] !== false;
    const div = document.createElement("div");
    div.className = `site-toggle ${isOn ? "on" : ""}`;
    div.dataset.site = key;
    div.innerHTML = `
      <span class="site-emoji">${meta.emoji}</span>
      <span class="site-name">${meta.label}</span>
      <div class="toggle-pill"></div>
    `;
    div.addEventListener("click", () => toggleSite(key, div, settings));
    grid.appendChild(div);
  }
}

async function toggleSite(key, el, settings) {
  settings.sites[key] = !settings.sites[key];
  el.className = `site-toggle ${settings.sites[key] ? "on" : ""}`;
  await bg("UPDATE_SETTINGS", { settings });
}

// ── Fetch user stats from API ─────────────────────────────────
async function fetchUserStats() {
  try {
    const token = await getToken();
    if (!token) return;

    const res = await fetch(`${API_BASE}/users/me`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!res.ok) return;

    const user = await res.json();
    document.getElementById("stat-streak").textContent = `${user.streak ?? 0}d`;
    document.getElementById("stat-xp").textContent = formatXP(user.xp ?? 0);
  } catch (_) {
    // Network down or backend not running — fail silently
  }
}

async function getToken() {
  return new Promise(resolve =>
    chrome.storage.local.get("skillos_token", r => resolve(r.skillos_token || null))
  );
}

// ── Detect current tab ────────────────────────────────────────
async function detectCurrentTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.url) return;

  const url = tab.url;
  const card = document.getElementById("page-card");
  const iconEl = document.getElementById("page-icon");
  const platformEl = document.getElementById("page-platform");
  const titleEl = document.getElementById("page-title");
  const badgeEl = document.getElementById("tracking-badge");

  for (const [key, meta] of Object.entries(SITE_META)) {
    const domains = {
      youtube: "youtube.com",
      udemy: "udemy.com",
      coursera: "coursera.org",
      freecodecamp: "freecodecamp.org",
      medium: "medium.com"
    };

    if (url.includes(domains[key])) {
      card.style.display = "flex";
      iconEl.textContent = meta.emoji;
      iconEl.style.background = meta.color + "22";
      platformEl.textContent = meta.label;
      platformEl.style.color = meta.color;
      titleEl.textContent = tab.title.replace(/ - YouTube$/, "").replace(/ \| Udemy$/, "").replace(/ \| Coursera$/, "").replace(/ | Medium$/, "").trim();

      const status = await bg("GET_STATUS");
      const siteEnabled = status.settings?.sites?.[key] !== false;
      badgeEl.textContent = siteEnabled ? "Tracking" : "Off";
      badgeEl.className = `tracking-badge ${siteEnabled ? "active" : "inactive"}`;
      break;
    }
  }
}

// ── Connect (token input) ─────────────────────────────────────
document.getElementById("connect-btn").addEventListener("click", async () => {
  const input = document.getElementById("token-input");
  const token = input.value.trim();
  const errorEl = document.getElementById("auth-error");
  errorEl.style.display = "none";

  if (!token) return;

  // Validate token by calling /users/me
  try {
    const res = await fetch(`${API_BASE}/users/me`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!res.ok) throw new Error("Invalid");

    await bg("SET_TOKEN", { token });
    input.value = "";
    const status = await bg("GET_STATUS");
    renderStatus(status);
    showMain(status);
    fetchUserStats();
    detectCurrentTab();

  } catch (_) {
    errorEl.style.display = "block";
  }
});

// ── Sync now ──────────────────────────────────────────────────
document.getElementById("sync-btn").addEventListener("click", async () => {
  const btn = document.getElementById("sync-btn");
  btn.disabled = true;
  btn.textContent = "Syncing…";

  const result = await bg("FORCE_SYNC");

  btn.disabled = false;
  btn.textContent = "Sync now";

  const status = await bg("GET_STATUS");
  document.getElementById("queue-count").textContent = status.queueLength;
  document.getElementById("stat-synced").textContent = status.totalSynced;

  if (status.lastSync) {
    document.getElementById("last-sync-sub").textContent = `Last synced just now`;
    document.getElementById("footer-status").textContent = `Synced just now`;
  }
});

// ── Sign out ──────────────────────────────────────────────────
document.getElementById("signout-btn").addEventListener("click", async () => {
  await bg("CLEAR_TOKEN");
  document.getElementById("stat-streak").textContent = "—";
  document.getElementById("stat-xp").textContent = "—";
  document.getElementById("page-card").style.display = "none";
  showAuth();
  renderStatus({ loggedIn: false });
});

// ── Utilities ─────────────────────────────────────────────────
function formatAgo(date) {
  const diff = Math.round((Date.now() - date.getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
  return `${Math.round(diff / 86400)}d ago`;
}

function formatXP(xp) {
  return xp >= 1000 ? `${(xp / 1000).toFixed(1)}k` : `${xp}`;
}

// ── Boot ──────────────────────────────────────────────────────
init();
