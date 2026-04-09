"""
Struggle Detector
-----------------
Formula-based, no ML training needed.
Reads interaction data from Supabase and computes a Struggle Score per resource.

Struggle Score = (rewatch_count × 0.25)
               + (review_failures × 0.30)
               + (slow_progress_flag × 0.20)
               + (low_retention × 0.25)

If score > STRUGGLE_THRESHOLD → user is flagged as struggling on that resource.
"""

from datetime import date, timedelta

STRUGGLE_THRESHOLD = 0.55  # tune this based on real data later

def compute_struggle_score(
    rewatch_count: int,
    review_failures: int,
    slow_progress: bool,
    low_retention: bool,
) -> float:
    score = (
        min(rewatch_count / 5, 1.0) * 0.25   # normalise rewatches (cap at 5)
        + min(review_failures / 5, 1.0) * 0.30
        + (1.0 if slow_progress else 0.0) * 0.20
        + (1.0 if low_retention else 0.0) * 0.25
    )
    return round(score, 3)


def analyse_user_struggles(user_id: str, supabase) -> list[dict]:
    """
    Pull interaction data for a user from Supabase and return a list of
    resources they are struggling with, plus recommended interventions.

    Call this from main.py at  GET /ml/struggle/{user_id}
    """
    # ── 1. Load the user's resources ────────────────────────────────────
    resources_resp = (
        supabase.table("resources")
        .select("id, title, platform, progress, status")
        .eq("user_id", user_id)
        .execute()
    )
    resources = {r["id"]: r for r in (resources_resp.data or [])}

    if not resources:
        return []

    resource_ids = list(resources.keys())

    # ── 2. Load interactions for those resources ─────────────────────────
    interactions_resp = (
        supabase.table("interactions")
        .select("resource_id, event_type, value, ts")
        .eq("user_id", user_id)
        .in_("resource_id", resource_ids)
        .execute()
    )
    interactions = interactions_resp.data or []

    # ── 3. Aggregate signals per resource ────────────────────────────────
    from collections import defaultdict
    signals = defaultdict(lambda: {
        "rewatch_count": 0,
        "total_events": 0,
        "last_progress": 0,
        "progress_history": [],
    })

    for evt in interactions:
        rid = evt["resource_id"]
        signals[rid]["total_events"] += 1
        if evt["event_type"] == "rewatch":
            signals[rid]["rewatch_count"] += 1
        if evt["event_type"] == "progress":
            signals[rid]["progress_history"].append(evt.get("value", 0))

    # ── 4. Load flashcard review failures ────────────────────────────────
    reviews_resp = (
        supabase.table("flashcards")
        .select("id, deck_id, review_count, stability")
        .execute()
    )
    # Count reviews with stability < 1.5 (= struggling)
    low_stability_cards = [
        c for c in (reviews_resp.data or []) if (c.get("stability") or 1.0) < 1.5
    ]
    # Simple heuristic: map failing cards → the resource they came from
    # (You'd need a resource_id FK on flashcards for precision; for now use count)
    global_review_failures = len(low_stability_cards)

    # ── 5. Score every resource ───────────────────────────────────────────
    struggling = []

    for rid, resource in resources.items():
        sig = signals[rid]
        current_progress = resource.get("progress") or 0

        # Slow progress: in-progress resource but stuck below 30%
        slow = (
            resource.get("status") == "in-progress"
            and current_progress < 30
            and sig["total_events"] > 3
        )

        # Low retention: progress history going backwards or stalling
        hist = sig["progress_history"]
        low_ret = False
        if len(hist) >= 3:
            recent_delta = hist[-1] - hist[0]
            low_ret = recent_delta < 5  # less than 5% gain over last 3 events

        score = compute_struggle_score(
            rewatch_count=sig["rewatch_count"],
            review_failures=min(global_review_failures, 5),  # use as proxy
            slow_progress=slow,
            low_retention=low_ret,
        )

        if score > STRUGGLE_THRESHOLD:
            interventions = _get_interventions(score, slow, low_ret, resource)
            struggling.append({
                "resource_id": rid,
                "title": resource["title"],
                "platform": resource["platform"],
                "progress": current_progress,
                "struggle_score": score,
                "interventions": interventions,
            })

    # Return sorted worst-first
    return sorted(struggling, key=lambda x: x["struggle_score"], reverse=True)


def _get_interventions(score: float, slow: bool, low_ret: bool, resource: dict) -> list[str]:
    """Return a list of plain-English intervention suggestions."""
    tips = []
    if slow:
        tips.append("Try breaking this course into 15-minute daily sessions.")
        tips.append("Look for a shorter prerequisite resource first.")
    if low_ret:
        tips.append("Create flashcards for the sections you've already watched.")
        tips.append("Consider switching to a video-based resource for this topic.")
    if score > 0.75:
        tips.append("Connect with a study buddy who is also learning this topic.")
    tips.append("Spaced repetition review scheduled — check your flashcard deck.")
    return tips[:3]  # cap at 3 suggestions