"""
Buddy session scheduling — create, list, calendar slots.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import HTTPException

VALID_MODES = ("teaching", "collaborative", "discussion")


def _buddy_request_for_pair(supabase, user_id: str, buddy_id: str) -> Optional[dict]:
    """Find accepted or pending request between two users."""
    as_sender = (
        supabase.table("buddy_requests")
        .select("*")
        .eq("from_user_id", user_id)
        .eq("to_user_id", buddy_id)
        .execute()
        .data
    )
    if as_sender:
        return as_sender[0]

    as_receiver = (
        supabase.table("buddy_requests")
        .select("*")
        .eq("from_user_id", buddy_id)
        .eq("to_user_id", user_id)
        .execute()
        .data
    )
    return as_receiver[0] if as_receiver else None


def create_session(
    supabase,
    user_id: str,
    buddy_id: str,
    mode: str,
    scheduled_at: str,
    duration_minutes: int = 60,
    notes: Optional[str] = None,
) -> dict:
    if mode not in VALID_MODES:
        raise HTTPException(400, f"mode must be one of {VALID_MODES}")

    req = _buddy_request_for_pair(supabase, user_id, buddy_id)
    if not req:
        raise HTTPException(404, "Buddy connection not found — send a request first")

    result = (
        supabase.table("buddy_interactions")
        .insert({
            "buddy_request_id": req["id"],
            "mode": mode,
            "scheduled_at": scheduled_at,
            "duration_minutes": duration_minutes,
            "status": "scheduled",
            "notes": notes,
        })
        .execute()
    )
    return result.data[0]


def list_sessions(supabase, user_id: str) -> List[dict]:
    """
    All sessions for user. Fixes invalid .in_('from_user_id,to_user_id', ...) query.
    """
    sent = (
        supabase.table("buddy_requests")
        .select("*")
        .eq("from_user_id", user_id)
        .execute()
        .data
        or []
    )
    received = (
        supabase.table("buddy_requests")
        .select("*")
        .eq("to_user_id", user_id)
        .execute()
        .data
        or []
    )

    seen_ids = set()
    requests = []
    for r in sent + received:
        if r["id"] not in seen_ids:
            seen_ids.add(r["id"])
            requests.append(r)

    sessions = []
    for req in requests:
        interactions = (
            supabase.table("buddy_interactions")
            .select("*")
            .eq("buddy_request_id", req["id"])
            .order("scheduled_at")
            .execute()
            .data
            or []
        )
        other_id = (
            req["to_user_id"] if req["from_user_id"] == user_id else req["from_user_id"]
        )
        other = (
            supabase.table("users")
            .select("id, name, level")
            .eq("id", other_id)
            .single()
            .execute()
            .data
        )
        for inter in interactions:
            sessions.append({
                **inter,
                "buddy": other,
                "buddy_request_id": req["id"],
            })

    return sessions


def upcoming_slots(
    supabase,
    user_id: str,
    buddy_id: str,
    days_ahead: int = 14,
) -> List[dict]:
    """Suggest open calendar slots (morning/evening) without conflicts."""
    existing = list_sessions(supabase, user_id)
    busy = set()
    for s in existing:
        if s.get("scheduled_at"):
            try:
                dt = datetime.fromisoformat(str(s["scheduled_at"]).replace("Z", "+00:00"))
                busy.add(dt.strftime("%Y-%m-%d-%H"))
            except ValueError:
                pass

    slots = []
    today = date.today()
    for d in range(1, days_ahead + 1):
        day = today + timedelta(days=d)
        for hour in (9, 14, 19):
            key = f"{day.isoformat()}-{hour}"
            if key not in busy:
                slots.append({
                    "start": f"{day.isoformat()}T{hour:02d}:00:00",
                    "label": day.strftime("%a %b %d") + f" at {hour}:00",
                    "duration_minutes": 60,
                })
    return slots[:21]
