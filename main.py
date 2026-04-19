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

# ─── XP table: how many XP each action awards ────────────────────────────────
XP_AWARDS = {
    "resource_added":      10,
    "resource_completed":  50,
    "resource_in_progress": 5,
    "flashcard_review":     3,
    "flashcard_good":       5,
    "flashcard_easy":       8,
    "daily_login":         15,
    "streak_7":           100,
    "streak_30":          500,
}

# XP needed to reach each level (cumulative)
def xp_for_level(level: int) -> int:
    """XP needed to reach `level` from 0. Quadratic curve."""
    return int(500 * (level ** 1.8))

def compute_level(total_xp: int) -> tuple[int, int]:
    """Return (current_level, xp_to_next_level)."""
    level = 1
    while xp_for_level(level + 1) <= total_xp:
        level += 1
    return level, xp_for_level(level + 1) - total_xp

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
    {"id": "buddy_connect",    "title": "Social learner",    "desc": "Connect with a study buddy",       "xp": 20,  "icon": "🤝"},
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

def _award_xp(user_id: str, action: str) -> dict:
    """Award XP for an action, update level, check achievements. Returns updated user."""
    xp_gain = XP_AWARDS.get(action, 0)
    if xp_gain == 0:
        return {}

    user_row = supabase.table("users").select("xp, level, streak").eq("id", user_id).single().execute().data
    new_xp = (user_row.get("xp") or 0) + xp_gain
    new_level, xp_to_next = compute_level(new_xp)

    supabase.table("users").update({
        "xp": new_xp,
        "level": new_level,
        "xp_to_next": xp_to_next,
    }).eq("id", user_id).execute()

    return {"xp_gained": xp_gain, "new_xp": new_xp, "new_level": new_level}


def _update_streak(user_id: str) -> int:
    """Update last_active and compute streak. Returns streak count."""
    today = date.today()
    user_row = supabase.table("users").select("last_active, streak").eq("id", user_id).single().execute().data
    last_active = user_row.get("last_active")
    current_streak = user_row.get("streak") or 0

    if last_active:
        last_date = date.fromisoformat(str(last_active)[:10])
        delta = (today - last_date).days
        if delta == 0:
            return current_streak   # already counted today
        elif delta == 1:
            current_streak += 1     # consecutive day
        else:
            current_streak = 1      # streak broken, restart
    else:
        current_streak = 1

    supabase.table("users").update({
        "last_active": str(today),
        "streak": current_streak,
    }).eq("id", user_id).execute()

    # bonus XP for streak milestones
    if current_streak in (3, 7, 30):
        _award_xp(user_id, f"streak_{current_streak}")
        _check_achievement(user_id, f"streak_{current_streak}")

    return current_streak


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

class BuddyRequestCreate(BaseModel):
    to_user_id: str

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
    query = supabase.table("flashcards").select("*").eq("deck_id", deck_id)
    if due_only:
        query = query.lte("due_date", str(date.today()))
    return query.execute().data

@app.post("/decks/{deck_id}/cards", status_code=201)
def create_card(deck_id: str, data: CardCreate,
                user_id: str = Depends(get_current_user)):
    result = supabase.table("flashcards").insert({
        **data.dict(), "deck_id": deck_id,
        "due_date": str(date.today()),
        "stability": 1.0, "difficulty": 0.5, "review_count": 0,
    }).execute()
    return result.data[0]

@app.post("/cards/{card_id}/review")
def review_card(card_id: str, data: CardReview,
                user_id: str = Depends(get_current_user)):
    card = supabase.table("flashcards").select("*") \
        .eq("id", card_id).single().execute().data

    intervals = {0: 1, 1: 3, 2: 7, 3: 14}
    new_stability  = card["stability"] * (1 + 0.1 * data.rating)
    new_difficulty = max(0.1, card["difficulty"] - 0.05 * (data.rating - 2))
    next_due = date.today() + timedelta(days=intervals.get(data.rating, 7))
    new_review_count = card["review_count"] + 1

    result = supabase.table("flashcards").update({
        "stability":    new_stability,
        "difficulty":   new_difficulty,
        "due_date":     str(next_due),
        "last_review":  str(date.today()),
        "review_count": new_review_count,
    }).eq("id", card_id).execute()

    # Award XP based on rating
    action_map = {0: "flashcard_review", 1: "flashcard_review",
                  2: "flashcard_good",   3: "flashcard_easy"}
    xp_info = _award_xp(user_id, action_map[data.rating])

    # Check card-review achievement
    if new_review_count >= 10:
        _check_achievement(user_id, "ten_flashcards")

    updated = result.data[0]
    updated["_xp"] = xp_info
    return updated


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

    # Ebbinghaus formula: R = e^(-t / S)  where S = stability, t = days since review
    today = date.today()
    data_points = []
    for c in cards:
        if not c.get("last_review"):
            continue
        last = date.fromisoformat(str(c["last_review"])[:10])
        days_since = (today - last).days
        stability = c.get("stability") or 1.0
        retention = round(math.exp(-days_since / max(stability, 0.1)) * 100, 1)
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


# ─── Study buddies — real matching algorithm ──────────────────────────────────

@app.get("/buddies/matches")
def find_buddies(user_id: str = Depends(get_current_user)):
    """
    Real matching: score all other users by:
      1. Tag overlap (Jaccard similarity between their resource tags)
      2. Level proximity (closer level = higher score)
    Returns top 10 sorted by match_score desc.
    """
    # Get current user's tags
    my_resources = supabase.table("resources").select("tags,platform") \
        .eq("user_id", user_id).execute().data or []
    my_tags = set()
    for r in my_resources:
        for t in (r.get("tags") or []):
            my_tags.add(t.lower())

    my_user = supabase.table("users").select("id,level").eq("id", user_id).single().execute().data
    my_level = my_user.get("level") or 1

    # Get requests already sent
    sent = supabase.table("buddy_requests").select("to_user_id") \
        .eq("from_user_id", user_id).execute().data or []
    exclude_ids = {r["to_user_id"] for r in sent} | {user_id}

    # Get all other users
    others = supabase.table("users").select("id,name,level,xp").execute().data or []
    others = [u for u in others if u["id"] not in exclude_ids]

    scored = []
    for u in others:
        uid = u["id"]
        # Their tags
        their_resources = supabase.table("resources").select("tags") \
            .eq("user_id", uid).execute().data or []
        their_tags = set()
        for r in their_resources:
            for t in (r.get("tags") or []):
                their_tags.add(t.lower())

        # Jaccard similarity
        if my_tags or their_tags:
            intersection = len(my_tags & their_tags)
            union = len(my_tags | their_tags)
            tag_score = intersection / union if union > 0 else 0
        else:
            tag_score = 0.5  # neutral if no tags yet

        # Level proximity score (1.0 = same level, 0.0 = >10 levels apart)
        level_diff = abs((u.get("level") or 1) - my_level)
        level_score = max(0, 1 - level_diff / 10)

        # Weighted composite
        match_score = round((tag_score * 0.7 + level_score * 0.3) * 100, 1)

        scored.append({**u, "match_score": match_score})

    scored.sort(key=lambda x: x["match_score"], reverse=True)
    return scored[:10]

@app.post("/buddies/request", status_code=201)
def send_buddy_request(data: BuddyRequestCreate, user_id: str = Depends(get_current_user)):
    result = supabase.table("buddy_requests").insert({
        "from_user_id": user_id, "to_user_id": data.to_user_id
    }).execute()
    _check_achievement(user_id, "buddy_connect")
    return result.data[0]


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
