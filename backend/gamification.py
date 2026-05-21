"""
Gamification — XP awards and level curve (report-aligned).
"""

from __future__ import annotations

from typing import Callable, Optional

# Report specification alignment
XP_AWARDS = {
    "resource_added": 15,
    "lesson_video_complete": 25,
    "resource_completed": 200,
    "resource_in_progress": 5,
    "flashcard_review": 3,
    "flashcard_hard": 8,
    "flashcard_good": 15,
    "flashcard_easy": 15,
    "daily_login": 10,
    "buddy_connect": 50,
    "streak_3": 30,
    "streak_7": 100,
    "streak_30": 500,
}


def xp_for_level(level: int) -> int:
    return int(500 * (level ** 1.8))


def compute_level(total_xp: int) -> tuple[int, int]:
    level = 1
    while xp_for_level(level + 1) <= total_xp:
        level += 1
    return level, xp_for_level(level + 1) - total_xp


def award_xp(supabase, user_id: str, action: str) -> dict:
    """Award XP for an action and update level."""
    xp_gain = XP_AWARDS.get(action, 0)
    if xp_gain == 0:
        return {}

    user_row = (
        supabase.table("users")
        .select("xp, level, streak")
        .eq("id", user_id)
        .single()
        .execute()
        .data
    )
    new_xp = (user_row.get("xp") or 0) + xp_gain
    new_level, xp_to_next = compute_level(new_xp)

    supabase.table("users").update({
        "xp": new_xp,
        "level": new_level,
        "xp_to_next": xp_to_next,
    }).eq("id", user_id).execute()

    return {"xp_gained": xp_gain, "new_xp": new_xp, "new_level": new_level}


def award_lesson_complete(supabase, user_id: str, resource_id: str) -> dict:
    """Award 25 XP once per resource for lesson/video completion (extension)."""
    resource = (
        supabase.table("resources")
        .select("id, lesson_xp_awarded")
        .eq("id", resource_id)
        .eq("user_id", user_id)
        .single()
        .execute()
        .data
    )
    if not resource or resource.get("lesson_xp_awarded"):
        return {}

    result = award_xp(supabase, user_id, "lesson_video_complete")
    if result:
        supabase.table("resources").update({"lesson_xp_awarded": True}).eq(
            "id", resource_id
        ).execute()
    return result
