"""
Bulk extension event sync — POST /api/v1/sync/events
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field

PLATFORM_NAMES = {
    "youtube": "YouTube",
    "udemy": "Udemy",
    "coursera": "Coursera",
    "freecodecamp": "freeCodeCamp",
    "medium": "Medium",
}

PLATFORM_COLORS = {
    "youtube": "#E24B4A",
    "udemy": "#7C3AED",
    "coursera": "#2563EB",
    "freecodecamp": "#16A34A",
    "medium": "#64748B",
}

MAX_BATCH_SIZE = 500


class SyncEvent(BaseModel):
    source: str
    resource_id: str
    url: Optional[str] = None
    event: str
    title: Optional[str] = None
    duration_seconds: Optional[int] = None
    watch_percentage: Optional[int] = None
    tags: Optional[List[str]] = []
    timestamp: str


class SyncEventsRequest(BaseModel):
    email_hash: Optional[str] = None
    events: List[SyncEvent] = Field(default_factory=list)
    activity_minutes: Optional[int] = 0


def hash_email(email: str) -> str:
    """SHA-256 of normalised email (matches extension background.js)."""
    normalized = email.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def verify_email_hash(supabase, user_id: str, provided_hash: Optional[str]) -> None:
    """Verify client PII hash matches account email; persist hash on first sync."""
    if not provided_hash:
        return

    user = (
        supabase.table("users")
        .select("email")
        .eq("id", user_id)
        .single()
        .execute()
        .data
    )
    if not user or not user.get("email"):
        raise HTTPException(400, "User email not found")

    expected = hash_email(user["email"])
    if provided_hash != expected:
        raise HTTPException(403, "Email hash does not match account")

    try:
        supabase.table("users").update({"email_hash": provided_hash}).eq("id", user_id).execute()
    except Exception:
        pass


def _event_value(evt: SyncEvent) -> float:
    if evt.event == "complete":
        return 100.0
    if evt.watch_percentage is not None:
        return float(evt.watch_percentage)
    return 0.0


def _map_event_type(evt: SyncEvent) -> str:
    mapping = {
        "start": "start",
        "progress": "progress",
        "complete": "complete",
        "watch": "watch",
    }
    return mapping.get(evt.event, evt.event)


def _platform_label(source: str) -> str:
    return PLATFORM_NAMES.get(source.lower(), source.capitalize())


def _find_resource(supabase, user_id: str, url: Optional[str], title: Optional[str], platform: str):
    if url:
        rows = (
            supabase.table("resources")
            .select("id, status, progress")
            .eq("user_id", user_id)
            .eq("url", url)
            .limit(1)
            .execute()
        )
        if rows.data:
            return rows.data[0]

    if title:
        rows = (
            supabase.table("resources")
            .select("id, status, progress")
            .eq("user_id", user_id)
            .eq("platform", platform)
            .eq("title", title)
            .limit(1)
            .execute()
        )
        if rows.data:
            return rows.data[0]

    return None


def _create_resource(supabase, user_id: str, evt: SyncEvent) -> dict:
    platform = _platform_label(evt.source)
    payload = {
        "user_id": user_id,
        "platform": platform,
        "title": evt.title or "Untitled",
        "url": evt.url,
        "duration": (
            f"{max(1, round(evt.duration_seconds / 60))} min"
            if evt.duration_seconds
            else None
        ),
        "tags": evt.tags or [],
        "platform_color": PLATFORM_COLORS.get(evt.source.lower()),
        "progress": 0,
        "status": "not-started",
    }
    result = supabase.table("resources").insert(payload).execute()
    return result.data[0]


def _update_resource_progress(supabase, resource: dict, evt: SyncEvent) -> Optional[str]:
    """
    Update progress from extension events.

    Returns:
      "lesson" — video/lesson finished (25 XP, not full course)
      None — no milestone
    """
    pct = int(evt.watch_percentage or 0)
    if evt.event == "complete":
        pct = 100

    updates = {"progress": max(resource.get("progress") or 0, pct)}
    lesson_done = False

    if evt.event == "complete" and resource.get("status") != "completed":
        lesson_done = True
        if resource.get("status") == "not-started":
            updates["status"] = "in-progress"
    elif pct > 0 and resource.get("status") == "not-started":
        updates["status"] = "in-progress"

    if (
        updates.get("progress") != resource.get("progress")
        or updates.get("status") != resource.get("status")
    ):
        supabase.table("resources").update(updates).eq("id", resource["id"]).execute()

    return "lesson" if lesson_done else None


def process_bulk_sync(supabase, user_id: str, body: SyncEventsRequest) -> dict:
    """Ingest batched extension events."""
    if len(body.events) > MAX_BATCH_SIZE:
        raise HTTPException(400, f"Maximum {MAX_BATCH_SIZE} events per batch")

    verify_email_hash(supabase, user_id, body.email_hash)

    resource_cache: dict[str, str] = {}
    interactions_created = 0
    resources_created = 0
    resources_updated = 0
    errors: list[dict] = []

    for evt in body.events:
        try:
            cache_key = evt.url or f"{evt.source}:{evt.resource_id}"
            db_resource_id = resource_cache.get(cache_key)

            if not db_resource_id:
                existing = _find_resource(
                    supabase, user_id, evt.url, evt.title, _platform_label(evt.source)
                )
                if existing:
                    db_resource_id = existing["id"]
                    if evt.event in ("progress", "complete", "watch"):
                        milestone = _update_resource_progress(supabase, existing, evt)
                        if milestone == "lesson":
                            try:
                                from gamification import award_lesson_complete
                                award_lesson_complete(supabase, user_id, db_resource_id)
                            except Exception:
                                pass
                        resources_updated += 1
                elif evt.event == "start" and evt.title:
                    created = _create_resource(supabase, user_id, evt)
                    db_resource_id = created["id"]
                    resources_created += 1
                else:
                    errors.append({
                        "resource_id": evt.resource_id,
                        "reason": "resource_not_found",
                    })
                    continue

                resource_cache[cache_key] = db_resource_id

            from db_compat import interaction_insert_payload

            supabase.table("interactions").insert(
                interaction_insert_payload(
                    user_id,
                    db_resource_id,
                    _map_event_type(evt),
                    _event_value(evt),
                    evt.timestamp,
                )
            ).execute()
            interactions_created += 1

        except Exception as e:
            errors.append({
                "resource_id": evt.resource_id,
                "reason": str(e),
            })

    activity_logged = 0
    if body.activity_minutes and body.activity_minutes > 0:
        today = str(date.today())
        existing = (
            supabase.table("activity_log")
            .select("id, minutes")
            .eq("user_id", user_id)
            .eq("date", today)
            .execute()
        )
        if existing.data:
            new_total = existing.data[0]["minutes"] + body.activity_minutes
            supabase.table("activity_log").update({"minutes": new_total}).eq(
                "id", existing.data[0]["id"]
            ).execute()
        else:
            supabase.table("activity_log").insert({
                "user_id": user_id,
                "date": today,
                "minutes": body.activity_minutes,
            }).execute()
        activity_logged = body.activity_minutes

    return {
        "synced": interactions_created,
        "interactions_created": interactions_created,
        "resources_created": resources_created,
        "resources_updated": resources_updated,
        "activity_minutes_logged": activity_logged,
        "errors": errors,
        "timestamp": datetime.utcnow().isoformat(),
    }
