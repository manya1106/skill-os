"""
Study buddy matching — tags, level, goals, pace, interaction mode.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

PACE_HOURS = {"slow": 5, "moderate": 10, "fast": 20}
INTERACTION_MODES = ("teaching", "collaborative", "discussion")


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 0.5
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _level_score(my_level: int, their_level: int) -> float:
    return max(0.0, 1.0 - abs(their_level - my_level) / 10.0)


def _pace_score(my_pace: str, their_pace: str) -> float:
    my_h = PACE_HOURS.get(my_pace, 10)
    their_h = PACE_HOURS.get(their_pace, 10)
    diff = abs(my_h - their_h)
    return max(0.0, 1.0 - diff / 20.0)


def _goal_score(my_goals: List[dict], their_goals: List[dict]) -> float:
    if not my_goals or not their_goals:
        return 0.3
    my_cats = {g.get("category", "").lower() for g in my_goals if g.get("category")}
    their_cats = {g.get("category", "").lower() for g in their_goals if g.get("category")}
    return _jaccard(my_cats, their_cats)


def _mode_score(my_mode: str, their_mode: str) -> float:
    if not my_mode or not their_mode:
        return 0.5
    if my_mode == their_mode:
        return 1.0
    compatible = {
        ("teaching", "collaborative"),
        ("collaborative", "teaching"),
        ("collaborative", "discussion"),
        ("discussion", "collaborative"),
    }
    if (my_mode, their_mode) in compatible:
        return 0.7
    return 0.35


def load_user_profile(supabase, user_id: str) -> dict:
    user = (
        supabase.table("users")
        .select("id, name, level, xp")
        .eq("id", user_id)
        .single()
        .execute()
        .data
    )
    resources = (
        supabase.table("resources")
        .select("tags, platform")
        .eq("user_id", user_id)
        .execute()
        .data
        or []
    )
    tags: Set[str] = set()
    for r in resources:
        for t in r.get("tags") or []:
            tags.add(str(t).lower())

    goals = (
        supabase.table("learning_goals")
        .select("category, title, status")
        .eq("user_id", user_id)
        .eq("status", "active")
        .execute()
        .data
        or []
    )

    prefs = {}
    try:
        row = (
            supabase.table("learning_preferences")
            .select("pace, preferred_interaction_mode")
            .eq("user_id", user_id)
            .single()
            .execute()
            .data
        )
        prefs = row or {}
    except Exception:
        pass

    return {
        "user": user,
        "tags": tags,
        "goals": goals,
        "pace": prefs.get("pace", "moderate"),
        "interaction_mode": prefs.get("preferred_interaction_mode", "collaborative"),
        "level": user.get("level") or 1,
    }


def score_buddy_match(my_profile: dict, their_profile: dict) -> dict:
    tag_s = _jaccard(my_profile["tags"], their_profile["tags"])
    level_s = _level_score(my_profile["level"], their_profile["level"])
    goal_s = _goal_score(my_profile["goals"], their_profile["goals"])
    pace_s = _pace_score(my_profile["pace"], their_profile["pace"])
    mode_s = _mode_score(
        my_profile["interaction_mode"],
        their_profile["interaction_mode"],
    )

    composite = (
        tag_s * 0.30
        + level_s * 0.15
        + goal_s * 0.25
        + pace_s * 0.15
        + mode_s * 0.15
    )

    return {
        "match_score": round(composite * 100, 1),
        "breakdown": {
            "tags": round(tag_s * 100, 1),
            "level": round(level_s * 100, 1),
            "goals": round(goal_s * 100, 1),
            "pace": round(pace_s * 100, 1),
            "interaction_mode": round(mode_s * 100, 1),
        },
        "shared_goals": list(
            {g.get("category") for g in my_profile["goals"] if g.get("category")}
            & {g.get("category") for g in their_profile["goals"] if g.get("category")}
        ),
        "their_pace": their_profile["pace"],
        "their_mode": their_profile["interaction_mode"],
    }


def find_buddy_matches(supabase, user_id: str, limit: int = 10) -> List[dict]:
    my_profile = load_user_profile(supabase, user_id)

    sent = (
        supabase.table("buddy_requests")
        .select("to_user_id")
        .eq("from_user_id", user_id)
        .execute()
        .data
        or []
    )
    exclude = {user_id, *(r["to_user_id"] for r in sent)}

    others = supabase.table("users").select("id, name, level, xp").execute().data or []
    scored = []

    for u in others:
        if u["id"] in exclude:
            continue
        their_profile = load_user_profile(supabase, u["id"])
        match = score_buddy_match(my_profile, their_profile)
        scored.append({**u, **match})

    scored.sort(key=lambda x: x["match_score"], reverse=True)
    return scored[:limit]
