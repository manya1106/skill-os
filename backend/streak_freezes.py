"""
Streak freeze system — token inventory, consumption, and streak protection.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import HTTPException

FREEZES_PER_MONTH = 3


def _month_start(today: Optional[date] = None) -> date:
    today = today or date.today()
    return today.replace(day=1)


def count_used_this_month(supabase, user_id: str, today: Optional[date] = None) -> int:
    """Tokens consumed this calendar month."""
    today = today or date.today()
    try:
        rows = (
            supabase.table("streak_freezes")
            .select("id")
            .eq("user_id", user_id)
            .gte("used_at", str(_month_start(today)))
            .execute()
        )
        return len(rows.data or [])
    except Exception:
        return 0


def get_token_inventory(supabase, user_id: str) -> dict:
    """Remaining freeze tokens and any active protection."""
    used = count_used_this_month(supabase, user_id)
    remaining = max(0, FREEZES_PER_MONTH - used)

    active = None
    try:
        rows = (
            supabase.table("streak_freezes")
            .select("protected_date, used_at")
            .eq("user_id", user_id)
            .gte("protected_date", str(date.today() - timedelta(days=7)))
            .order("protected_date", desc=True)
            .limit(1)
            .execute()
        )
        if rows.data:
            active = rows.data[0]
    except Exception:
        pass

    return {
        "remaining": remaining,
        "total_per_month": FREEZES_PER_MONTH,
        "used_this_month": used,
        "active_freeze": active,
    }


def has_freeze_for_date(supabase, user_id: str, protected_date: date) -> bool:
    try:
        rows = (
            supabase.table("streak_freezes")
            .select("id")
            .eq("user_id", user_id)
            .eq("protected_date", str(protected_date))
            .limit(1)
            .execute()
        )
        return bool(rows.data)
    except Exception:
        return False


def activate_freeze(supabase, user_id: str) -> dict:
    """
    Consume one freeze token to protect a missed day (usually yesterday).

    Use when you skipped exactly one day and want to keep your streak.
    """
    today = date.today()
    inventory = get_token_inventory(supabase, user_id)

    if inventory["remaining"] <= 0:
        raise HTTPException(
            429,
            f"No freeze tokens left this month (max {FREEZES_PER_MONTH})",
        )

    user = (
        supabase.table("users")
        .select("last_active, streak")
        .eq("id", user_id)
        .single()
        .execute()
        .data
    )
    if not user:
        raise HTTPException(404, "User not found")

    last_active = user.get("last_active")
    if not last_active:
        raise HTTPException(400, "No streak to protect yet — learn today first")

    last_date = date.fromisoformat(str(last_active)[:10])
    gap = (today - last_date).days

    if gap == 0:
        raise HTTPException(400, "Already active today — freeze not needed")
    if gap == 1:
        raise HTTPException(400, "Streak is intact — freeze only needed after skipping a day")
    if gap > 2:
        raise HTTPException(
            400,
            f"Streak already broken ({gap - 1} days missed). Freeze only covers one missed day.",
        )

    protected_date = today - timedelta(days=1)

    if has_freeze_for_date(supabase, user_id, protected_date):
        raise HTTPException(400, "A freeze is already active for that day")

    supabase.table("streak_freezes").insert({
        "user_id": user_id,
        "protected_date": str(protected_date),
        "used_at": str(today),
    }).execute()

    new_streak = (user.get("streak") or 0) + 1
    supabase.table("users").update({
        "last_active": str(today),
        "streak": new_streak,
    }).eq("id", user_id).execute()

    return {
        "ok": True,
        "message": "Streak freeze activated — your streak is protected!",
        "protected_date": str(protected_date),
        "streak": new_streak,
        "tokens_remaining": inventory["remaining"] - 1,
    }


def update_streak(
    supabase,
    user_id: str,
    on_milestone: Optional[Callable[[str, int], None]] = None,
) -> int:
    """
    Update last_active and streak, applying freeze protection when applicable.

    Args:
        on_milestone: optional callback(user_id, streak_count) for XP/achievements
    """
    today = date.today()
    user_row = (
        supabase.table("users")
        .select("last_active, streak")
        .eq("id", user_id)
        .single()
        .execute()
        .data
    )
    last_active = user_row.get("last_active")
    current_streak = user_row.get("streak") or 0

    if last_active:
        last_date = date.fromisoformat(str(last_active)[:10])
        delta = (today - last_date).days
        if delta == 0:
            return current_streak
        if delta == 1:
            current_streak += 1
        elif delta == 2:
            yesterday = today - timedelta(days=1)
            if has_freeze_for_date(supabase, user_id, yesterday):
                current_streak += 1
            else:
                current_streak = 1
        else:
            protected = False
            for days_back in range(1, min(delta, 4)):
                check_date = today - timedelta(days=days_back)
                if has_freeze_for_date(supabase, user_id, check_date):
                    current_streak += 1
                    protected = True
                    break
            if not protected:
                current_streak = 1
    else:
        current_streak = 1

    supabase.table("users").update({
        "last_active": str(today),
        "streak": current_streak,
    }).eq("id", user_id).execute()

    if on_milestone and current_streak in (3, 7, 30):
        on_milestone(user_id, current_streak)

    return current_streak
