"""
SkillOS FastAPI Backend — main.py
Updated to include ML proxy routes that call the Flask ML service.

New endpoints added:
  GET  /recommendations       → proxied to Flask ML service
  GET  /users/me/struggles    → proxied to Flask ML service
  POST /ml/retrain            → proxied to Flask ML service (admin only)

All existing routes (auth, resources, decks, cards, etc.) unchanged.
"""

import httpx
import os
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

# URL of the Flask ML microservice
ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://localhost:8001")


# ─── Auth helpers ────────────────────────────────────────────────────────

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


# ─── Pydantic models ──────────────────────────────────────────────────────

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


# ─── Auth routes ──────────────────────────────────────────────────────────

@app.post("/auth/register")
def register(data: RegisterInput):
    existing = supabase.table("users").select("id").eq("email", data.email).execute()
    if existing.data:
        raise HTTPException(400, "Email already registered")
    hashed = pwd_context.hash(data.password)
    result = supabase.table("users").insert({
        "name": data.name,
        "email": data.email,
        "password_hash": hashed
    }).execute()
    user = result.data[0]
    return {"access_token": create_token(user["id"]), "token_type": "bearer"}

@app.post("/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    result = supabase.table("users").select("*").eq("email", form.username).execute()
    if not result.data:
        raise HTTPException(401, "Invalid credentials")
    user = result.data[0]
    if not pwd_context.verify(form.password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    return {"access_token": create_token(user["id"]), "token_type": "bearer"}


# ─── User routes ──────────────────────────────────────────────────────────

@app.get("/users/me")
def get_me(user_id: str = Depends(get_current_user)):
    result = supabase.table("users").select(
        "id,name,email,level,xp,xp_to_next,streak,last_active"
    ).eq("id", user_id).single().execute()
    return result.data


# ─── Resources routes ─────────────────────────────────────────────────────

@app.get("/resources")
def list_resources(user_id: str = Depends(get_current_user)):
    result = supabase.table("resources").select("*").eq("user_id", user_id).execute()
    return result.data

@app.post("/resources", status_code=201)
def create_resource(data: ResourceCreate, user_id: str = Depends(get_current_user)):
    result = supabase.table("resources").insert({
        **data.dict(), "user_id": user_id, "progress": 0, "status": "not-started"
    }).execute()
    return result.data[0]

@app.patch("/resources/{resource_id}")
def update_resource(resource_id: str, data: ResourceUpdate,
                    user_id: str = Depends(get_current_user)):
    update_data = data.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(400, "Nothing to update")
    result = supabase.table("resources").update(update_data)\
        .eq("id", resource_id).eq("user_id", user_id).execute()
    if not result.data:
        raise HTTPException(404, "Resource not found")
    return result.data[0]

@app.delete("/resources/{resource_id}", status_code=204)
def delete_resource(resource_id: str, user_id: str = Depends(get_current_user)):
    supabase.table("resources").delete()\
        .eq("id", resource_id).eq("user_id", user_id).execute()


# ─── Flashcard deck routes ────────────────────────────────────────────────

@app.get("/decks")
def list_decks(user_id: str = Depends(get_current_user)):
    decks = supabase.table("flashcard_decks").select("*")\
        .eq("user_id", user_id).execute().data
    for deck in decks:
        cards = supabase.table("flashcards").select("id,due_date,review_count")\
            .eq("deck_id", deck["id"]).execute().data
        deck["card_count"]    = len(cards)
        deck["due_count"]     = sum(1 for c in cards if c["due_date"] <= str(date.today()))
        deck["mastered_count"]= sum(1 for c in cards if (c.get("review_count") or 0) >= 3)
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
    card = supabase.table("flashcards").select("*")\
        .eq("id", card_id).single().execute().data

    intervals = {0: 1, 1: 3, 2: 7, 3: 14}
    new_stability  = card["stability"] * (1 + 0.1 * data.rating)
    new_difficulty = max(0.1, card["difficulty"] - 0.05 * (data.rating - 2))
    next_due = date.today() + timedelta(days=intervals.get(data.rating, 7))

    result = supabase.table("flashcards").update({
        "stability":    new_stability,
        "difficulty":   new_difficulty,
        "due_date":     str(next_due),
        "last_review":  str(date.today()),
        "review_count": card["review_count"] + 1,
    }).eq("id", card_id).execute()
    return result.data[0]


# ─── Activity routes ──────────────────────────────────────────────────────

@app.get("/activity/heatmap")
def get_heatmap(user_id: str = Depends(get_current_user)):
    since = str(date.today() - timedelta(days=365))
    rows = supabase.table("activity_log").select("date,minutes")\
        .eq("user_id", user_id).gte("date", since).execute().data
    return {r["date"]: r["minutes"] for r in rows}

@app.post("/activity/log")
def log_activity(minutes: int, user_id: str = Depends(get_current_user)):
    today = str(date.today())
    existing = supabase.table("activity_log").select("id,minutes")\
        .eq("user_id", user_id).eq("date", today).execute().data
    if existing:
        new_total = existing[0]["minutes"] + minutes
        supabase.table("activity_log").update({"minutes": new_total})\
            .eq("id", existing[0]["id"]).execute()
    else:
        supabase.table("activity_log").insert({
            "user_id": user_id, "date": today, "minutes": minutes
        }).execute()
    return {"date": today, "minutes": minutes}


# ─── ML proxy routes ──────────────────────────────────────────────────────
# These proxy to the Flask ML microservice so the frontend only talks to one
# backend (port 8000). The ML service runs separately on port 8001.

@app.get("/recommendations")
async def get_recommendations(
    top_n: int = 6,
    user_id: str = Depends(get_current_user),
):
    """
    Proxy to Flask ML service.
    Returns personalised resource recommendations.
    Uses TF-IDF until DAE-CF model is trained.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{ML_SERVICE_URL}/ml/recommend/{user_id}",
                params={"top_n": top_n},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError:
        # ML service not running yet — return static fallback
        return {
            "recommendations": _static_fallback_recs(),
            "model": "static_fallback",
        }
    except Exception as e:
        raise HTTPException(500, f"ML service error: {e}")


@app.get("/users/me/struggles")
async def get_my_struggles(user_id: str = Depends(get_current_user)):
    """
    Proxy to Flask ML service.
    Returns resources the user is currently struggling with.
    """
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
    """Trigger DAE-CF retraining. Pass X-Retrain-Secret header."""
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
    """Check whether the ML service is reachable and which model is active."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{ML_SERVICE_URL}/ml/health")
            return resp.json()
    except httpx.ConnectError:
        return {"status": "ml_service_offline", "mode": "static_fallback"}


# ─── Study buddies ────────────────────────────────────────────────────────

@app.get("/buddies/matches")
def find_buddies(user_id: str = Depends(get_current_user)):
    sent = supabase.table("buddy_requests").select("to_user_id")\
        .eq("from_user_id", user_id).execute().data
    exclude_ids = {r["to_user_id"] for r in sent} | {user_id}
    others = supabase.table("users").select("id,name,level,xp").execute().data
    return [u for u in others if u["id"] not in exclude_ids][:10]

@app.post("/buddies/request", status_code=201)
def send_buddy_request(data: BuddyRequestCreate,
                        user_id: str = Depends(get_current_user)):
    result = supabase.table("buddy_requests").insert({
        "from_user_id": user_id, "to_user_id": data.to_user_id
    }).execute()
    return result.data[0]


# ─── Helpers ──────────────────────────────────────────────────────────────

def _static_fallback_recs() -> list[dict]:
    """Shown only if ML service is completely offline."""
    return [
        {"id": "s1", "platform": "YouTube",      "title": "Backpropagation Explained — 3Blue1Brown", "tags": ["ML"],      "match_score": 98, "reason": "Highly rated"},
        {"id": "s2", "platform": "Udemy",        "title": "Scikit-learn: ML in Python",              "tags": ["Python"],  "match_score": 94, "reason": "Top ML course"},
        {"id": "s3", "platform": "Coursera",     "title": "Deep Learning Specialisation",            "tags": ["DL"],      "match_score": 91, "reason": "Andrew Ng classic"},
        {"id": "s4", "platform": "freeCodeCamp", "title": "Data Visualisation with D3.js",           "tags": ["JS"],      "match_score": 88, "reason": "Great for data"},
        {"id": "s5", "platform": "YouTube",      "title": "Statistics for ML — StatQuest",           "tags": ["Stats"],   "match_score": 86, "reason": "Fill the gaps"},
        {"id": "s6", "platform": "Udemy",        "title": "FastAPI — Build Modern APIs",             "tags": ["Python"],  "match_score": 83, "reason": "Your next step"},
    ]


# ─── Run ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)