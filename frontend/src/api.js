const BASE = "http://localhost:8000";

function getToken() {
  return localStorage.getItem("skillos_token");
}

async function req(path, options = {}) {
  // Don't force JSON content-type — let callers override it fully
  const defaultHeaders = {
    ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
  };

  // Only add Content-Type: application/json when there's a JSON body
  // (not for form-encoded login, not for DELETE with no body)
  const hasJsonBody =
    options.body && typeof options.body === "string";
  if (hasJsonBody) {
    defaultHeaders["Content-Type"] = "application/json";
  }

  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers, // caller headers win
    },
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text);
  }

  // 204 No Content has no body
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  // ── Auth ──────────────────────────────────────────────────────────────────
  login: (email, password) =>
    req("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username: email, password }),
    }),
  register: (name, email, password) =>
    req("/auth/register", {
      method: "POST",
      body: JSON.stringify({ name, email, password }),
    }),

  // ── User ──────────────────────────────────────────────────────────────────
  me: () => req("/users/me"),
  achievements: () => req("/users/me/achievements"),

  // ── Resources ─────────────────────────────────────────────────────────────
  resources:      ()         => req("/resources"),
  createResource: (data)     => req("/resources", { method: "POST", body: JSON.stringify(data) }),
  updateResource: (id, data) => req(`/resources/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteResource: (id)       => req(`/resources/${id}`, { method: "DELETE" }),

  // ── Flashcard decks ───────────────────────────────────────────────────────
  decks:      ()        => req("/decks"),
  createDeck: (data)    => req("/decks", { method: "POST", body: JSON.stringify(data) }),
  cards:      (deckId)  => req(`/decks/${deckId}/cards?due_only=true`),
  createCard: (deckId, data) =>
    req(`/decks/${deckId}/cards`, { method: "POST", body: JSON.stringify(data) }),
  reviewCard: (id, rating) =>
    req(`/cards/${id}/review`, { method: "POST", body: JSON.stringify({ rating }) }),
  cardIntervalPreview: (id) => req(`/cards/${id}/interval-preview`),
  remindersDue: () => req("/reminders/due"),
  reminderSettings: () => req("/reminders/settings"),
  updateReminderSettings: (data) =>
    req("/reminders/settings", { method: "PATCH", body: JSON.stringify(data) }),

  // ── Activity ──────────────────────────────────────────────────────────────
  heatmap: () => req("/activity/heatmap"),

  // ── Analytics ─────────────────────────────────────────────────────────────
  weeklyAnalytics: () => req("/analytics/weekly"),
  platformRadar:   () => req("/analytics/platform-radar"),
  forgettingCurve: () => req("/analytics/forgetting-curve"),

  // ── ML recommendations ────────────────────────────────────────────────────
  recommendations: () => req("/recommendations"),
  struggles:       () => req("/users/me/struggles"),
  recommendationFeedback: (data) =>
    req("/recommendations/feedback", { method: "POST", body: JSON.stringify(data) }),

  // ── Goals & Learning Paths ────────────────────────────────────────
  createGoal: (data) =>
    req("/goals", { method: "POST", body: JSON.stringify(data) }),
  listGoals: () => req("/goals"),
  getGoal: (id) => req(`/goals/${id}`),
  updateGoal: (id, data) =>
    req(`/goals/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  
  updatePreferences: (data) =>
    req("/preferences", { method: "POST", body: JSON.stringify(data) }),
  getPreferences: () => req("/preferences"),
  goalPredictions: (goalId) => req(`/analytics/predictions/${goalId}`),

  // ── Study buddies ─────────────────────────────────────────────────────────
  buddyMatches:     ()      => req("/buddies/matches"),
  sendBuddyRequest: (toId)  =>
    req("/buddies/request", { method: "POST", body: JSON.stringify({ to_user_id: toId }) }),
  buddySessions: () => req("/buddies/sessions"),
  scheduleBuddySession: (buddyId, data) =>
    req(`/buddies/${buddyId}/schedule`, { method: "POST", body: JSON.stringify(data) }),
  buddySlots: (buddyId) => req(`/buddies/${buddyId}/slots`),

  // ── Streak freezes ────────────────────────────────────────────────────────
  freezeTokens: () => req("/streaks/tokens-remaining"),
  useFreezeToken: () => req("/streaks/freeze", { method: "POST" }),

  // ── ML admin ──────────────────────────────────────────────────────────────
  mlHealth:  ()       => req("/ml/health"),
  mlRetrain: (secret) =>
    req("/ml/retrain", { method: "POST", headers: { "X-Retrain-Secret": secret } }),
};