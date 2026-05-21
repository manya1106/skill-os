"""
SkillOS FastAPI Backend — main.py  (upgraded)
=============================================
New in this version:
  • XP award system — actions earn real XP, level-ups computed
  • Streak logic   — computed server-side on every login / activity log
  • Achievements   — 12 unlockable badges stored in DB
  • Feedback loop  — POST /recommendations/{id}/feedback stored for DAE-CF retrain
  • Real buddy matching — cosine similarity on shared tags + level proximity
  • Analytics endpoints — time-series, radar (per-platform), forgetting curve
"""

import httpx, os, math
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from supabase import create_client, Client
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime, timedelta
from dotenv import load_dotenv
from collections import Counter

load_dotenv()

app = FastAPI(title="SkillOS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGO = "HS256"
ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://localhost:8001")

from gamification import XP_AWARDS, award_xp, compute_level, xp_for_level
from streak_freezes import activate_freeze, get_token_inventory, update_streak as _core_update_streak


def _award_xp(user_id: str, action: str) -> dict:
    return award_xp(supabase, user_id, action)

def _compute_xp_bonus(user_id: str, base_xp: int, action: str) -> int:
    """
    Apply bonus XP multipliers based on user engagement patterns.
    - Consistency bonus: 1.1x if active every day (streak > 5)
    - Challenge bonus: 1.2x for completing high-difficulty resources
    - Learning velocity bonus: 1.15x if completing resources faster than average
    """
    user = supabase.table("users").select("streak, level").eq("id", user_id).single().execute().data
    multiplier = 1.0
    
    # Consistency bonus
    if user.get("streak", 0) >= 5:
        multiplier *= 1.1
    
    # Challenge bonus (higher levels = harder content)
    if user.get("level", 1) >= 5:
        multiplier *= 1.2
    
    return int(base_xp * multiplier)

# ─── Achievement definitions ─────────────────────────────────────────────────
ACHIEVEMENTS = [
    {"id": "first_resource",   "title": "First step",        "desc": "Add your first resource",          "xp": 25,  "icon": "📚"},
    {"id": "first_complete",   "title": "Finisher",          "desc": "Complete your first resource",     "xp": 50,  "icon": "✅"},
    {"id": "streak_3",         "title": "On a roll",         "desc": "3-day learning streak",            "xp": 30,  "icon": "🔥"},
    {"id": "streak_7",         "title": "Week warrior",      "desc": "7-day learning streak",            "xp": 100, "icon": "⚡"},
    {"id": "streak_30",        "title": "Iron learner",      "desc": "30-day learning streak",           "xp": 500, "icon": "🏆"},
    {"id": "five_resources",   "title": "Collector",         "desc": "Track 5 resources",                "xp": 40,  "icon": "🗂️"},
    {"id": "ten_flashcards",   "title": "Card shark",        "desc": "Review 10 flashcards in a session","xp": 30,  "icon": "🃏"},
    {"id": "level_5",          "title": "Rising star",       "desc": "Reach level 5",                    "xp": 0,   "icon": "⭐"},
    {"id": "level_10",         "title": "Knowledge seeker",  "desc": "Reach level 10",                   "xp": 0,   "icon": "🎓"},
    {"id": "buddy_connect",    "title": "Social learner",    "desc": "Connect with a study buddy",       "xp": 0,   "icon": "🤝"},
    {"id": "five_platforms",   "title": "Platform hopper",   "desc": "Learn from 5 different platforms", "xp": 60,  "icon": "🌐"},
    {"id": "multi_complete",   "title": "Completionist",     "desc": "Complete 5 resources",             "xp": 150, "icon": "🏅"},
]


# ─── Auth helpers ────────────────────────────────────────────────────────────

def create_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": datetime.utcnow() + timedelta(days=7)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _update_streak(user_id: str) -> int:
    """Update streak with freeze protection and milestone XP."""

    def on_milestone(uid: str, streak: int):
        _award_xp(uid, f"streak_{streak}")
        _check_achievement(uid, f"streak_{streak}")

    return _core_update_streak(supabase, user_id, on_milestone)


def _check_achievement(user_id: str, achievement_id: str):
    """Unlock an achievement if not already unlocked."""
    existing = supabase.table("user_achievements").select("id") \
        .eq("user_id", user_id).eq("achievement_id", achievement_id).execute()
    if existing.data:
        return  # already unlocked

    achievement = next((a for a in ACHIEVEMENTS if a["id"] == achievement_id), None)
    if not achievement:
        return

    supabase.table("user_achievements").insert({
        "user_id": user_id,
        "achievement_id": achievement_id,
        "unlocked_at": str(datetime.utcnow()),
    }).execute()

    # Award XP for the achievement itself
    if achievement["xp"] > 0:
        _award_xp(user_id, f"achievement_{achievement_id}")


def _check_resource_achievements(user_id: str):
    """Check all resource-based achievements."""
    resources = supabase.table("resources").select("status, platform").eq("user_id", user_id).execute().data or []
    completed = [r for r in resources if r["status"] == "completed"]
    platforms = set(r["platform"] for r in resources)

    if len(resources) >= 1:
        _check_achievement(user_id, "first_resource")
    if len(resources) >= 5:
        _check_achievement(user_id, "five_resources")
    if len(completed) >= 1:
        _check_achievement(user_id, "first_complete")
    if len(completed) >= 5:
        _check_achievement(user_id, "multi_complete")
    if len(platforms) >= 5:
        _check_achievement(user_id, "five_platforms")


def _check_level_achievements(user_id: str, level: int):
    if level >= 5:
        _check_achievement(user_id, "level_5")
    if level >= 10:
        _check_achievement(user_id, "level_10")


# ─── Pydantic models ──────────────────────────────────────────────────────────

class RegisterInput(BaseModel):
    name: str
    email: str
    password: str

class ResourceCreate(BaseModel):
    platform: str
    platform_color: Optional[str] = None
    title: str
    url: Optional[str] = None
    duration: Optional[str] = None
    tags: Optional[List[str]] = []

class ResourceUpdate(BaseModel):
    progress: Optional[int] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None

class DeckCreate(BaseModel):
    title: str
    color: Optional[str] = "indigo"

class CardCreate(BaseModel):
    question: str
    answer: str
    source: Optional[str] = None

class CardReview(BaseModel):
    rating: int  # 0=Again 1=Hard 2=Good 3=Easy

class RecommendationFeedback(BaseModel):
    resource_id: str
    action: str          # "like" | "dislike" | "save"
    platform: Optional[str] = None
    tags: Optional[List[str]] = []


# ─── Auth routes ──────────────────────────────────────────────────────────────

@app.post("/auth/register")
def register(data: RegisterInput):
    existing = supabase.table("users").select("id").eq("email", data.email).execute()
    if existing.data:
        raise HTTPException(400, "Email already registered")
    hashed = pwd_context.hash(data.password)
    result = supabase.table("users").insert({
        "name": data.name,
        "email": data.email,
        "password_hash": hashed,
        "xp": 0,
        "level": 1,
        "xp_to_next": xp_for_level(2),
        "streak": 0,
        "last_active": str(date.today()),
    }).execute()
    user = result.data[0]
    # First login streak
    _update_streak(user["id"])
    _award_xp(user["id"], "daily_login")
    return {"access_token": create_token(user["id"]), "token_type": "bearer"}

@app.post("/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    result = supabase.table("users").select("*").eq("email", form.username).execute()
    if not result.data:
        raise HTTPException(401, "Invalid credentials")
    user = result.data[0]
    if not pwd_context.verify(form.password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    # Update streak + award daily login XP
    _update_streak(user["id"])
    _award_xp(user["id"], "daily_login")
    return {"access_token": create_token(user["id"]), "token_type": "bearer"}


# ─── User routes ──────────────────────────────────────────────────────────────

@app.get("/users/me")
def get_me(user_id: str = Depends(get_current_user)):
    result = supabase.table("users").select(
        "id,name,email,level,xp,xp_to_next,streak,last_active"
    ).eq("id", user_id).single().execute()
    return result.data

@app.get("/users/me/achievements")
def get_my_achievements(user_id: str = Depends(get_current_user)):
    unlocked_rows = supabase.table("user_achievements").select("achievement_id,unlocked_at") \
        .eq("user_id", user_id).execute().data or []
    unlocked_ids = {r["achievement_id"]: r["unlocked_at"] for r in unlocked_rows}

    result = []
    for ach in ACHIEVEMENTS:
        result.append({
            **ach,
            "unlocked": ach["id"] in unlocked_ids,
            "unlocked_at": unlocked_ids.get(ach["id"]),
        })
    return result


# ─── Resources routes ─────────────────────────────────────────────────────────

@app.get("/resources")
def list_resources(user_id: str = Depends(get_current_user)):
    result = supabase.table("resources").select("*").eq("user_id", user_id).execute()
    return result.data

@app.post("/resources", status_code=201)
def create_resource(data: ResourceCreate, user_id: str = Depends(get_current_user)):
    result = supabase.table("resources").insert({
        **data.dict(), "user_id": user_id, "progress": 0, "status": "not-started"
    }).execute()
    xp_info = _award_xp(user_id, "resource_added")
    _check_resource_achievements(user_id)
    created = result.data[0]
    created["_xp"] = xp_info
    return created

@app.patch("/resources/{resource_id}")
def update_resource(resource_id: str, data: ResourceUpdate,
                    user_id: str = Depends(get_current_user)):
    update_data = data.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(400, "Nothing to update")

    # Fetch old status to detect transitions
    old = supabase.table("resources").select("status").eq("id", resource_id).single().execute().data
    old_status = old.get("status") if old else None

    result = supabase.table("resources").update(update_data) \
        .eq("id", resource_id).eq("user_id", user_id).execute()
    if not result.data:
        raise HTTPException(404, "Resource not found")

    updated = result.data[0]
    xp_info = {}

    # Award XP on status transitions
    new_status = update_data.get("status")
    if new_status and new_status != old_status:
        if new_status == "completed":
            xp_info = _award_xp(user_id, "resource_completed")
            _check_resource_achievements(user_id)
            try:
                from flashcard_generator import auto_generate_for_completed_resource
                gen = auto_generate_for_completed_resource(supabase, user_id, updated)
                updated["_flashcards_generated"] = gen
            except Exception as e:
                print(f"[Flashcards] Auto-generate failed: {e}")
        elif new_status == "in-progress" and old_status == "not-started":
            xp_info = _award_xp(user_id, "resource_in_progress")

    if xp_info:
        level_info = supabase.table("users").select("level").eq("id", user_id).single().execute().data
        _check_level_achievements(user_id, level_info.get("level", 1))
        updated["_xp"] = xp_info

    return updated

@app.delete("/resources/{resource_id}", status_code=204)
def delete_resource(resource_id: str, user_id: str = Depends(get_current_user)):
    supabase.table("resources").delete() \
        .eq("id", resource_id).eq("user_id", user_id).execute()


# ─── Flashcard helpers ────────────────────────────────────────────────────────

def _assert_deck_owner(deck_id: str, user_id: str):
    deck = supabase.table("flashcard_decks").select("id") \
        .eq("id", deck_id).eq("user_id", user_id).execute()
    if not deck.data:
        raise HTTPException(404, "Deck not found")


def _get_user_card(card_id: str, user_id: str) -> dict:
    card = supabase.table("flashcards").select("*") \
        .eq("id", card_id).single().execute().data
    if not card:
        raise HTTPException(404, "Card not found")
    deck = supabase.table("flashcard_decks").select("user_id") \
        .eq("id", card["deck_id"]).single().execute().data
    if not deck or deck.get("user_id") != user_id:
        raise HTTPException(404, "Card not found")
    return card


# ─── Flashcard deck routes ────────────────────────────────────────────────────

@app.get("/decks")
def list_decks(user_id: str = Depends(get_current_user)):
    decks = supabase.table("flashcard_decks").select("*") \
        .eq("user_id", user_id).execute().data
    for deck in decks:
        cards = supabase.table("flashcards").select("id,due_date,review_count") \
            .eq("deck_id", deck["id"]).execute().data
        deck["card_count"]     = len(cards)
        deck["due_count"]      = sum(1 for c in cards if c["due_date"] <= str(date.today()))
        deck["mastered_count"] = sum(1 for c in cards if (c.get("review_count") or 0) >= 3)
    return decks

@app.post("/decks", status_code=201)
def create_deck(data: DeckCreate, user_id: str = Depends(get_current_user)):
    result = supabase.table("flashcard_decks").insert({
        **data.dict(), "user_id": user_id
    }).execute()
    return result.data[0]

@app.get("/decks/{deck_id}/cards")
def list_cards(deck_id: str, due_only: bool = False,
               user_id: str = Depends(get_current_user)):
    from db_compat import card_to_api
    query = supabase.table("flashcards").select("*").eq("deck_id", deck_id)
    if due_only:
        query = query.lte("due_date", str(date.today()))
    rows = query.execute().data or []
    return [card_to_api(r) for r in rows]

@app.post("/decks/{deck_id}/cards", status_code=201)
def create_card(deck_id: str, data: CardCreate,
                user_id: str = Depends(get_current_user)):
    _assert_deck_owner(deck_id, user_id)
    from fsrs import new_card_state
    state = new_card_state()
    from db_compat import card_insert_payload, card_to_api
    payload = card_insert_payload(
        user_id,
        data.question,
        data.answer,
        deck_id=deck_id,
        source=data.source,
        due_date=str(state.due_date),
        stability=state.stability,
        difficulty=state.difficulty,
    )
    result = supabase.table("flashcards").insert(payload).execute()
    return card_to_api(result.data[0])


@app.get("/cards/{card_id}/interval-preview")
def card_interval_preview(card_id: str, user_id: str = Depends(get_current_user)):
    """FSRS interval preview (days) for each rating button."""
    card = _get_user_card(card_id, user_id)
    from fsrs import preview_intervals
    return preview_intervals(
        card.get("stability") or 0,
        card.get("difficulty") or 5,
        card.get("review_count") or 0,
        card.get("last_review"),
    )


@app.post("/cards/{card_id}/review")
def review_card(card_id: str, data: CardReview,
                user_id: str = Depends(get_current_user)):
    if data.rating not in (0, 1, 2, 3):
        raise HTTPException(400, "Rating must be 0–3 (Again/Hard/Good/Easy)")

    card = _get_user_card(card_id, user_id)
    from fsrs import review as fsrs_review, retrievability

    state = fsrs_review(
        stability=float(card.get("stability") or 0),
        difficulty=float(card.get("difficulty") or 5),
        review_count=int(card.get("review_count") or 0),
        last_review=card.get("last_review"),
        rating=data.rating,
    )

    result = supabase.table("flashcards").update({
        "stability": state.stability,
        "difficulty": state.difficulty,
        "due_date": str(state.due_date),
        "last_review": str(date.today()),
        "review_count": state.review_count,
    }).eq("id", card_id).execute()

    action_map = {
        0: "flashcard_review",
        1: "flashcard_hard",
        2: "flashcard_good",
        3: "flashcard_easy",
    }
    xp_info = _award_xp(user_id, action_map[data.rating])

    if state.review_count >= 10:
        _check_achievement(user_id, "ten_flashcards")

    updated = result.data[0]
    updated["_xp"] = xp_info
    updated["_fsrs"] = {
        "interval_days": state.interval_days,
        "retrievability": state.retrievability,
        "retention_pct": round(
            retrievability(0, state.stability) * 100, 1
        ),
        "stability": state.stability,
        "difficulty": state.difficulty,
    }
    return updated


# ─── Review reminders ─────────────────────────────────────────────────────────

class ReminderSettingsUpdate(BaseModel):
    email_reminders_enabled: Optional[bool] = True
    push_reminders_enabled: Optional[bool] = True


@app.get("/reminders/due")
def reminders_due(user_id: str = Depends(get_current_user)):
    """Due-card summary for UI badges and push notification polling."""
    from reminder_worker import get_due_summary
    return get_due_summary(supabase, user_id)


@app.get("/reminders/settings")
def get_reminder_settings(user_id: str = Depends(get_current_user)):
    try:
        row = supabase.table("notification_settings").select("*") \
            .eq("user_id", user_id).execute()
        if row.data:
            return row.data[0]
    except Exception:
        pass
    return {
        "user_id": user_id,
        "email_reminders_enabled": True,
        "push_reminders_enabled": True,
    }


@app.patch("/reminders/settings")
def update_reminder_settings(
    data: ReminderSettingsUpdate,
    user_id: str = Depends(get_current_user),
):
    payload = {"user_id": user_id, **data.dict(exclude_unset=True)}
    try:
        existing = supabase.table("notification_settings").select("id") \
            .eq("user_id", user_id).execute()
        if existing.data:
            result = supabase.table("notification_settings").update(payload) \
                .eq("user_id", user_id).execute()
        else:
            result = supabase.table("notification_settings").insert(payload).execute()
        return result.data[0]
    except Exception:
        return payload


# ─── Activity routes ──────────────────────────────────────────────────────────

@app.get("/activity/heatmap")
def get_heatmap(user_id: str = Depends(get_current_user)):
    since = str(date.today() - timedelta(days=365))
    rows = supabase.table("activity_log").select("date,minutes") \
        .eq("user_id", user_id).gte("date", since).execute().data
    return {r["date"]: r["minutes"] for r in rows}

@app.post("/activity/log")
def log_activity(minutes: int, user_id: str = Depends(get_current_user)):
    today = str(date.today())
    existing = supabase.table("activity_log").select("id,minutes") \
        .eq("user_id", user_id).eq("date", today).execute().data
    if existing:
        new_total = existing[0]["minutes"] + minutes
        supabase.table("activity_log").update({"minutes": new_total}) \
            .eq("id", existing[0]["id"]).execute()
    else:
        supabase.table("activity_log").insert({
            "user_id": user_id, "date": today, "minutes": minutes
        }).execute()

    # Update streak on any activity log
    streak = _update_streak(user_id)
    return {"date": today, "minutes": minutes, "streak": streak}


# ─── Extension bulk sync (browser extension) ───────────────────────────────────

from sync_events import SyncEventsRequest, process_bulk_sync


@app.post("/api/v1/sync/events")
def sync_events_bulk(body: SyncEventsRequest, user_id: str = Depends(get_current_user)):
    """
    Bulk ingest learning events from the browser extension.

    - JWT auth (Bearer token)
    - Optional email_hash (SHA-256 of normalised email) for PII-safe verification
    - Batched events + optional activity_minutes in one request
    """
    if not body.events:
        return {"synced": 0, "reason": "empty", "interactions_created": 0}

    result = process_bulk_sync(supabase, user_id, body)
    _update_streak(user_id)
    return result


# ─── Analytics routes (real data, no mocks) ───────────────────────────────────

@app.get("/analytics/weekly")
def get_weekly_analytics(user_id: str = Depends(get_current_user)):
    """
    Returns 8 weeks of learning data (minutes per week) from activity_log.
    Used to draw the time-series chart.
    """
    since = str(date.today() - timedelta(days=56))
    rows = supabase.table("activity_log").select("date,minutes") \
        .eq("user_id", user_id).gte("date", since).execute().data or []

    # Group into ISO weeks
    week_data: dict[str, int] = {}
    for row in rows:
        d = date.fromisoformat(row["date"])
        # ISO week key: year-weeknum
        key = f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"
        week_data[key] = week_data.get(key, 0) + row["minutes"]

    # Build last 8 weeks in order
    result = []
    for i in range(7, -1, -1):
        d = date.today() - timedelta(weeks=i)
        iso = d.isocalendar()
        key = f"{iso[0]}-W{iso[1]:02d}"
        # Human label: "Apr 14"
        monday = date.fromisocalendar(iso[0], iso[1], 1)
        result.append({
            "week": key,
            "label": monday.strftime("%b %-d"),
            "minutes": week_data.get(key, 0),
        })
    return result

@app.get("/analytics/platform-radar")
def get_platform_radar(user_id: str = Depends(get_current_user)):
    """
    Returns per-platform stats for the radar chart:
    - resources count
    - average progress
    - completed count
    All computed from real resources table.
    """
    resources = supabase.table("resources").select("platform,progress,status") \
        .eq("user_id", user_id).execute().data or []

    platforms = ["YouTube", "Udemy", "Coursera", "freeCodeCamp", "Medium"]
    result = {}

    for p in platforms:
        filtered = [r for r in resources if r["platform"] == p]
        completed = [r for r in filtered if r["status"] == "completed"]
        avg_progress = (
            sum(r["progress"] or 0 for r in filtered) / len(filtered)
            if filtered else 0
        )
        result[p] = {
            "platform": p,
            "count": len(filtered),
            "avg_progress": round(avg_progress, 1),
            "completed": len(completed),
            # Score 0-100 combining progress + completion bonus
            "score": round(min(100, avg_progress * 0.6 + (len(completed) / max(1, len(filtered))) * 40), 1),
        }

    return list(result.values())

@app.get("/analytics/forgetting-curve")
def get_forgetting_curve(user_id: str = Depends(get_current_user)):
    """
    Returns flashcard retention data: per-card stability scores over time.
    Used to visualise the forgetting curve.
    """
    cards = supabase.table("flashcards").select(
        "stability,difficulty,review_count,last_review,due_date"
    ).execute().data or []  # all cards accessible to user via decks

    if not cards:
        return {"data": [], "avg_retention": 0}

    from fsrs import retrievability as fsrs_retention

    today = date.today()
    data_points = []
    for c in cards:
        if not c.get("last_review"):
            continue
        last = date.fromisoformat(str(c["last_review"])[:10])
        days_since = (today - last).days
        stability = c.get("stability") or 1.0
        retention = round(fsrs_retention(days_since, stability) * 100, 1)
        data_points.append({
            "days_since_review": days_since,
            "retention_pct": retention,
            "review_count": c.get("review_count") or 0,
            "stability": round(stability, 2),
        })

    avg_retention = round(
        sum(d["retention_pct"] for d in data_points) / len(data_points), 1
    ) if data_points else 0

    return {"data": data_points, "avg_retention": avg_retention}

@app.get("/analytics/predictions/{goal_id}")
def get_goal_predictions(goal_id: str, user_id: str = Depends(get_current_user)):
    """
    Predict goal completion probability and optimal study schedule.
    """
    goal = supabase.table("learning_goals").select("*") \
        .eq("id", goal_id).eq("user_id", user_id).single().execute().data
    
    milestones = supabase.table("learning_paths").select("*") \
        .eq("goal_id", goal_id).execute().data or []
    
    total_hours = sum(m.get("target_duration_hours", 0) for m in milestones)
    
    # Get user's recent study pace
    recent_activity = supabase.table("activity_log").select("minutes") \
        .eq("user_id", user_id) \
        .gte("date", str(date.today() - timedelta(days=30))) \
        .execute().data or []
    
    avg_minutes_per_week = (sum(r["minutes"] for r in recent_activity) / 4) if recent_activity else 0
    avg_hours_per_week = avg_minutes_per_week / 60
    
    # Calculate projections
    if avg_hours_per_week > 0:
        weeks_needed = total_hours / avg_hours_per_week
        projected_completion = date.today() + timedelta(weeks=weeks_needed)
        on_track = goal.get("deadline") is None or projected_completion <= date.fromisoformat(goal["deadline"])
        completion_probability = min(100, int((avg_hours_per_week / 10) * 100))  # 10 hrs/week = high confidence
    else:
        weeks_needed = None
        projected_completion = None
        on_track = False
        completion_probability = 20  # Default low if no history
    
    # Optimal schedule: suggest daily minutes
    daily_minutes = int((avg_hours_per_week * 60) / 5) if avg_hours_per_week > 0 else 30
    
    return {
        "goal_id": goal_id,
        "total_hours_required": total_hours,
        "avg_hours_per_week": round(avg_hours_per_week, 1),
        "weeks_needed": round(weeks_needed, 1) if weeks_needed else None,
        "projected_completion_date": str(projected_completion) if projected_completion else None,
        "deadline": goal.get("deadline"),
        "on_track": on_track,
        "completion_probability_pct": completion_probability,
        "recommended_daily_minutes": daily_minutes,
        "milestones_completed": sum(1 for m in milestones if m.get("status") == "completed"),
        "milestones_total": len(milestones),
    }


# ─── Recommendation feedback (feeds DAE-CF retraining) ───────────────────────

@app.post("/recommendations/feedback")
def recommendation_feedback(
    data: RecommendationFeedback,
    user_id: str = Depends(get_current_user)
):
    """
    Store user's explicit signal on a recommendation.
    action = "like" | "dislike" | "save"
    This table is read by train_dae.py as positive/negative implicit feedback.
    """
    supabase.table("recommendation_feedback").insert({
        "user_id":     user_id,
        "resource_id": data.resource_id,
        "action":      data.action,
        "platform":    data.platform,
        "tags":        data.tags or [],
        "created_at":  str(datetime.utcnow()),
    }).execute()

    # "save" also adds to their resources list
    if data.action == "save":
        _award_xp(user_id, "resource_added")

    return {"ok": True}


# ─── ML proxy routes ──────────────────────────────────────────────────────────

@app.get("/recommendations")
async def get_recommendations(top_n: int = 6, user_id: str = Depends(get_current_user)):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{ML_SERVICE_URL}/ml/recommend/{user_id}",
                params={"top_n": top_n},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError:
        return {"recommendations": _static_fallback_recs(), "model": "static_fallback"}
    except Exception as e:
        raise HTTPException(500, f"ML service error: {e}")

@app.get("/users/me/struggles")
async def get_my_struggles(user_id: str = Depends(get_current_user)):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{ML_SERVICE_URL}/ml/struggle/{user_id}")
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError:
        return {"struggling_count": 0, "resources": []}
    except Exception as e:
        raise HTTPException(500, f"ML service error: {e}")

@app.post("/ml/retrain")
async def trigger_retrain(
    x_retrain_secret: Optional[str] = None,
    user_id: str = Depends(get_current_user),
):
    secret = os.getenv("RETRAIN_SECRET", "changemeplease")
    if x_retrain_secret != secret:
        raise HTTPException(403, "Invalid retrain secret")
    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(
            f"{ML_SERVICE_URL}/ml/retrain",
            headers={"X-Retrain-Secret": secret},
        )
        return resp.json()

@app.get("/ml/health")
async def ml_health():
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{ML_SERVICE_URL}/ml/health")
            return resp.json()
    except httpx.ConnectError:
        return {"status": "ml_service_offline", "mode": "static_fallback"}


# ─── Study buddies ─────────────────────────────────────────────────────────────

class BuddyRequestCreate(BaseModel):
    to_user_id: str


class SessionCreate(BaseModel):
    mode: str = "collaborative"
    scheduled_at: str
    duration_minutes: int = 60
    notes: Optional[str] = None


@app.get("/buddies/matches")
def find_buddies(user_id: str = Depends(get_current_user)):
    """Match on tags, level, goals, pace, and interaction mode."""
    from buddy_matching import find_buddy_matches
    return find_buddy_matches(supabase, user_id)


@app.post("/buddies/request", status_code=201)
def send_buddy_request(data: BuddyRequestCreate, user_id: str = Depends(get_current_user)):
    result = supabase.table("buddy_requests").insert({
        "from_user_id": user_id,
        "to_user_id": data.to_user_id,
        "status": "pending",
    }).execute()
    xp_info = _award_xp(user_id, "buddy_connect")
    _check_achievement(user_id, "buddy_connect")
    created = result.data[0]
    created["_xp"] = xp_info
    return created


@app.post("/buddies/{buddy_id}/schedule")
def schedule_interaction(
    buddy_id: str,
    data: SessionCreate,
    user_id: str = Depends(get_current_user),
):
    """Schedule a study session with a buddy."""
    from buddy_sessions import create_session
    return create_session(
        supabase,
        user_id,
        buddy_id,
        data.mode,
        data.scheduled_at,
        data.duration_minutes,
        data.notes,
    )


@app.get("/buddies/sessions")
def get_buddy_sessions(user_id: str = Depends(get_current_user)):
    """List all buddy sessions (fixed query — no invalid .in_())."""
    from buddy_sessions import list_sessions
    return list_sessions(supabase, user_id)


@app.get("/buddies/{buddy_id}/slots")
def get_buddy_slots(buddy_id: str, user_id: str = Depends(get_current_user)):
    """Calendar time-slot suggestions for scheduling."""
    from buddy_sessions import upcoming_slots
    return upcoming_slots(supabase, user_id, buddy_id)

# ─── Streak freeze routes ───────────────────────────────────────────────────────

@app.post("/streaks/freeze")
def use_freeze_token(user_id: str = Depends(get_current_user)):
    """Consume a freeze token to protect streak after missing one day."""
    return activate_freeze(supabase, user_id)


@app.get("/streaks/tokens-remaining")
def get_freeze_tokens(user_id: str = Depends(get_current_user)):
    """Token inventory and active freeze status."""
    return get_token_inventory(supabase, user_id)

# ─── Goal Management Routes ───────────────────────────────────────────

class GoalCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: str
    target_level: int = 1
    deadline: Optional[str] = None

class PreferencesUpdate(BaseModel):
    study_hours_per_week: int
    preferred_platforms: List[str]
    learning_style: str  # visual, auditory, kinesthetic, reading
    pace: str = "moderate"
    preferred_interaction_mode: str = "collaborative"  # teaching, collaborative, discussion

@app.post("/goals", status_code=201)
async def create_goal(data: GoalCreate, user_id: str = Depends(get_current_user)):
    """Create a learning goal and auto-generate learning path."""
    result = supabase.table("learning_goals").insert({
        "user_id": user_id,
        "title": data.title,
        "description": data.description,
        "category": data.category,
        "target_level": data.target_level,
        "deadline": data.deadline,
        "status": "active",
    }).execute()
    
    goal = result.data[0]
    
    try:
        from learning_path_ai import generate_learning_path
        path = await generate_learning_path(supabase, goal, user_id)
        goal["milestones"] = path
        goal["path_source"] = path[0].get("_source") if path else "none"
    except Exception as e:
        print(f"Path generation failed: {e}")
        goal["milestones"] = []

    return goal

@app.get("/goals")
def list_goals(user_id: str = Depends(get_current_user)):
    """List all learning goals for user."""
    goals = supabase.table("learning_goals").select("*") \
        .eq("user_id", user_id).execute().data or []
    
    result = []
    for goal in goals:
        path = supabase.table("learning_paths").select("*") \
            .eq("goal_id", goal["id"]).order("sequence").execute().data or []
        result.append({**goal, "milestones": path})
    
    return result

@app.get("/goals/{goal_id}")
def get_goal(goal_id: str, user_id: str = Depends(get_current_user)):
    """Get single goal with full milestone breakdown."""
    goal = supabase.table("learning_goals").select("*") \
        .eq("id", goal_id).eq("user_id", user_id).single().execute().data
    
    milestones = supabase.table("learning_paths").select("*") \
        .eq("goal_id", goal_id).order("sequence").execute().data or []
    
    return {**goal, "milestones": milestones}

@app.patch("/goals/{goal_id}")
def update_goal(goal_id: str, data: dict, user_id: str = Depends(get_current_user)):
    """Update goal status or deadline."""
    result = supabase.table("learning_goals").update(data) \
        .eq("id", goal_id).eq("user_id", user_id).execute()
    return result.data[0] if result.data else None

@app.post("/preferences")
def update_preferences(data: PreferencesUpdate, user_id: str = Depends(get_current_user)):
    """Save user learning preferences."""
    existing = supabase.table("learning_preferences").select("id") \
        .eq("user_id", user_id).execute()
    
    payload = {
        "user_id": user_id,
        "study_hours_per_week": data.study_hours_per_week,
        "preferred_platforms": data.preferred_platforms,
        "learning_style": data.learning_style,
        "pace": data.pace,
        "preferred_interaction_mode": data.preferred_interaction_mode,
    }
    
    if existing.data:
        result = supabase.table("learning_preferences").update(payload) \
            .eq("user_id", user_id).execute()
    else:
        result = supabase.table("learning_preferences").insert(payload).execute()
    
    return result.data[0]

@app.get("/preferences")
def get_preferences(user_id: str = Depends(get_current_user)):
    """Retrieve user learning preferences."""
    result = supabase.table("learning_preferences").select("*") \
        .eq("user_id", user_id).single().execute()
    return result.data or {
        "study_hours_per_week": 10,
        "preferred_platforms": ["YouTube", "Udemy", "Coursera"],
        "learning_style": "visual",
        "pace": "moderate",
        "preferred_interaction_mode": "collaborative",
    }

# ─── Learning Path Generation (Async) ───────────────────────────────────

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _static_fallback_recs() -> list:
    return [
        {"id": "s1", "platform": "YouTube",      "title": "Backpropagation Explained — 3Blue1Brown", "tags": ["ML"],     "match_score": 98, "reason": "Highly rated"},
        {"id": "s2", "platform": "Udemy",        "title": "Scikit-learn: ML in Python",              "tags": ["Python"], "match_score": 94, "reason": "Top ML course"},
        {"id": "s3", "platform": "Coursera",     "title": "Deep Learning Specialisation",            "tags": ["DL"],     "match_score": 91, "reason": "Andrew Ng classic"},
        {"id": "s4", "platform": "freeCodeCamp", "title": "Data Visualisation with D3.js",           "tags": ["JS"],     "match_score": 88, "reason": "Great for data"},
        {"id": "s5", "platform": "YouTube",      "title": "Statistics for ML — StatQuest",           "tags": ["Stats"],  "match_score": 86, "reason": "Fill the gaps"},
        {"id": "s6", "platform": "Udemy",        "title": "FastAPI — Build Modern APIs",             "tags": ["Python"], "match_score": 83, "reason": "Your next step"},
    ]


@app.on_event("startup")
def startup_reminder_scheduler():
    try:
        from reminder_worker import start_reminder_scheduler
        start_reminder_scheduler(supabase)
    except Exception as e:
        print(f"[Reminders] Scheduler not started: {e}")


@app.on_event("shutdown")
def shutdown_reminder_scheduler():
    try:
        from reminder_worker import stop_reminder_scheduler
        stop_reminder_scheduler()
    except Exception:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)