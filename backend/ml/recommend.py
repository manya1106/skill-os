"""
TF-IDF Cold-Start Recommender
------------------------------
Works from day 1 — no training data or users required.
Uses cosine similarity between a user's saved resource tags/titles
and a catalogue of all resources in the system.

When you have 50+ users, swap in the DAE-CF model (train_dae.py).
The endpoint signature stays identical — frontend never changes.
"""

import re
from collections import Counter
import math


# ── Simple TF-IDF implementation (no sklearn dependency needed) ────────────

def _tokenise(text: str) -> list[str]:
    """Lowercase, remove punctuation, split on whitespace."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return [t for t in text.split() if len(t) > 1]


def _build_tfidf(docs: list[list[str]]) -> tuple[list[dict], dict]:
    """
    Returns:
      - tfidf_vectors: list of {term: tfidf_score} dicts, one per doc
      - idf: {term: idf_score} global dict
    """
    N = len(docs)
    if N == 0:
        return [], {}

    # Document frequency
    df: dict[str, int] = Counter()
    for doc in docs:
        for term in set(doc):
            df[term] += 1

    # IDF
    idf = {term: math.log((N + 1) / (cnt + 1)) + 1 for term, cnt in df.items()}

    # TF-IDF per document
    tfidf_vectors = []
    for doc in docs:
        tf = Counter(doc)
        total = len(doc) or 1
        vec = {term: (count / total) * idf.get(term, 0) for term, count in tf.items()}
        tfidf_vectors.append(vec)

    return tfidf_vectors, idf


def _cosine_similarity(vec_a: dict, vec_b: dict) -> float:
    """Cosine similarity between two sparse TF-IDF vectors."""
    dot = sum(vec_a.get(t, 0) * vec_b.get(t, 0) for t in vec_b)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values())) or 1e-9
    norm_b = math.sqrt(sum(v * v for v in vec_b.values())) or 1e-9
    return dot / (norm_a * norm_b)


def _resource_to_tokens(resource: dict) -> list[str]:
    """Combine title + tags into a token list for one resource."""
    parts = [resource.get("title", ""), " ".join(resource.get("tags") or [])]
    return _tokenise(" ".join(parts))


# ── Main recommendation function ───────────────────────────────────────────

def get_tfidf_recommendations(
    user_id: str,
    supabase,
    top_n: int = 6,
) -> list[dict]:
    """
    Return top_n resource recommendations for user_id using TF-IDF similarity.

    Algorithm:
      1. Load all resources in the system (the catalogue).
      2. Load this user's saved resources.
      3. Build a "user profile" vector = average TF-IDF of their resources.
      4. Score every unsaved catalogue resource against the profile.
      5. Return the top_n highest-scoring unsaved resources.

    Called from main.py at  GET /recommendations
    """
    # ── 1. Full catalogue ────────────────────────────────────────────────
    # In production you'd keep a shared catalogue table.
    # For now we use all resources from all users as the catalogue.
    all_resp = supabase.table("resources").select(
        "id, user_id, platform, title, tags, progress, status"
    ).execute()
    all_resources = all_resp.data or []

    if not all_resources:
        return _fallback_recommendations()

    # ── 2. User's own resources ──────────────────────────────────────────
    user_resources = [r for r in all_resources if r["user_id"] == user_id]
    user_resource_ids = {r["id"] for r in user_resources}

    # Candidate pool: resources NOT already saved by this user
    candidates = [r for r in all_resources if r["user_id"] != user_id]

    if not candidates:
        # No other users yet → return hardcoded popular resources
        return _fallback_recommendations()

    # ── 3. Build TF-IDF over all docs (user + candidates) ───────────────
    all_docs_resources = user_resources + candidates
    all_tokens = [_resource_to_tokens(r) for r in all_docs_resources]
    tfidf_vectors, idf = _build_tfidf(all_tokens)

    n_user = len(user_resources)
    user_vectors = tfidf_vectors[:n_user]
    candidate_vectors = tfidf_vectors[n_user:]

    # ── 4. User profile = average of user's TF-IDF vectors ───────────────
    if user_vectors:
        all_terms = set(t for vec in user_vectors for t in vec)
        profile = {
            term: sum(v.get(term, 0) for v in user_vectors) / len(user_vectors)
            for term in all_terms
        }
    else:
        # New user with no resources → use IDF scores as proxy for "interesting"
        profile = {term: score for term, score in sorted(
            idf.items(), key=lambda x: x[1], reverse=True
        )[:50]}

    # ── 5. Score candidates ───────────────────────────────────────────────
    scored = []
    for resource, vec in zip(candidates, candidate_vectors):
        sim = _cosine_similarity(profile, vec)
        scored.append((sim, resource))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Deduplicate by title (same course may be saved by multiple users)
    seen_titles: set[str] = set()
    results = []
    for sim, resource in scored:
        title = resource["title"].strip().lower()
        if title in seen_titles:
            continue
        seen_titles.add(title)
        results.append({
            "id": resource["id"],
            "platform": resource["platform"],
            "title": resource["title"],
            "tags": resource.get("tags") or [],
            "match_score": round(sim * 100, 1),
            "reason": _explain_recommendation(resource, profile, idf),
        })
        if len(results) >= top_n:
            break

    return results if results else _fallback_recommendations()


def _explain_recommendation(resource: dict, profile: dict, idf: dict) -> str:
    """Generate a plain-English reason string."""
    tokens = _resource_to_tokens(resource)
    # Find token with highest IDF that also appears in user profile
    overlap = [(t, profile.get(t, 0) * idf.get(t, 0)) for t in tokens if t in profile]
    if overlap:
        best_term = max(overlap, key=lambda x: x[1])[0]
        return f"Based on your interest in {best_term}"
    platform = resource.get("platform", "")
    return f"Popular on {platform}" if platform else "Recommended for you"


def _fallback_recommendations() -> list[dict]:
    """
    Hardcoded popular resources shown when no real data exists yet.
    Replace with a curated list relevant to your target users.
    """
    return [
        {"id": "static_1", "platform": "YouTube",      "title": "Backpropagation Explained — 3Blue1Brown", "tags": ["Math", "ML"],          "match_score": 98, "reason": "Highly rated by learners like you"},
        {"id": "static_2", "platform": "Udemy",        "title": "Scikit-learn: ML in Python",              "tags": ["Python", "ML"],        "match_score": 94, "reason": "Top ML course for Python learners"},
        {"id": "static_3", "platform": "Coursera",     "title": "Deep Learning Specialisation — Andrew Ng","tags": ["Deep Learning"],       "match_score": 91, "reason": "Industry-standard deep learning course"},
        {"id": "static_4", "platform": "freeCodeCamp", "title": "Data Visualisation with D3.js",           "tags": ["D3", "JavaScript"],    "match_score": 88, "reason": "Great follow-up to Python data work"},
        {"id": "static_5", "platform": "YouTube",      "title": "Statistics for ML — StatQuest",           "tags": ["Stats", "ML"],         "match_score": 86, "reason": "Fills key gaps in ML foundations"},
        {"id": "static_6", "platform": "Udemy",        "title": "FastAPI — Build Modern APIs",             "tags": ["Python", "APIs"],      "match_score": 83, "reason": "Based on your Python background"},
    ]