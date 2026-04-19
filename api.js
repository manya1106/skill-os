const BASE = "http://localhost:8000";

function getToken() {
  return localStorage.getItem("skillos_token");
}

async function req(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
      ...options.headers,
    },
  });
  if (!res.ok) throw new Error(await res.text());
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
    req("/auth/register", { method: "POST", body: JSON.stringify({ name, email, password }) }),

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

  // ── Activity ──────────────────────────────────────────────────────────────
  heatmap: () => req("/activity/heatmap"),

  // ── Analytics (real data) ─────────────────────────────────────────────────
  weeklyAnalytics:  () => req("/analytics/weekly"),
  platformRadar:    () => req("/analytics/platform-radar"),
  forgettingCurve:  () => req("/analytics/forgetting-curve"),

  // ── ML recommendations ────────────────────────────────────────────────────
  recommendations: () => req("/recommendations"),
  struggles:       () => req("/users/me/struggles"),
  recommendationFeedback: (data) =>
    req("/recommendations/feedback", { method: "POST", body: JSON.stringify(data) }),

  // ── Study buddies ─────────────────────────────────────────────────────────
  buddyMatches:     ()      => req("/buddies/matches"),
  sendBuddyRequest: (toId)  =>
    req("/buddies/request", { method: "POST", body: JSON.stringify({ to_user_id: toId }) }),

  // ── ML admin ──────────────────────────────────────────────────────────────
  mlHealth:  ()       => req("/ml/health"),
  mlRetrain: (secret) =>
    req("/ml/retrain", { method: "POST", headers: { "X-Retrain-Secret": secret } }),
};
