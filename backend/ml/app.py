"""
SkillOS Flask ML Service
-------------------------
Runs on port 8001.
Your FastAPI main.py calls this internally.

Start it with:
  cd backend
  python -m ml.app

Or in production:
  gunicorn "ml.app:app" --bind 0.0.0.0:8001 --workers 2
"""

import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

app = Flask(__name__)
CORS(app)

# ── Supabase client ───────────────────────────────────────────────────────
supabase: Client = create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_KEY", ""),
)

# ── Load ML components ────────────────────────────────────────────────────
from ml.recommend import get_tfidf_recommendations
from ml.struggle  import analyse_user_struggles
from ml.train_dae import DAERecommender

# DAE model loads at startup — silently falls back if not trained yet
dae = DAERecommender(model_dir=os.path.join(os.path.dirname(__file__), "model"))


# ── Routes ────────────────────────────────────────────────────────────────

@app.route("/ml/health")
def health():
    return jsonify({
        "status": "ok",
        "dae_model_ready": dae.is_ready(),
        "mode": "DAE-CF" if dae.is_ready() else "TF-IDF",
    })


@app.route("/ml/recommend/<user_id>")
def recommend(user_id: str):
    """
    GET /ml/recommend/{user_id}?top_n=6

    Returns top_n personalised recommendations.
    Uses DAE-CF if trained, otherwise TF-IDF.
    Called by FastAPI's  GET /recommendations  endpoint.
    """
    top_n = int(request.args.get("top_n", 6))

    # Try DAE-CF first
    if dae.is_ready():
        dae_results = dae.recommend(user_id, top_n=top_n)
        if dae_results:
            # Enrich with full resource metadata from Supabase
            enriched = _enrich_recommendations(dae_results, source="DAE-CF")
            return jsonify({"recommendations": enriched, "model": "dae_cf"})

    # Fall back to TF-IDF
    tfidf_results = get_tfidf_recommendations(user_id, supabase, top_n=top_n)
    return jsonify({"recommendations": tfidf_results, "model": "tfidf"})


@app.route("/ml/struggle/<user_id>")
def struggle(user_id: str):
    """
    GET /ml/struggle/{user_id}

    Returns resources the user is struggling with + interventions.
    Called by FastAPI's  GET /users/me/struggles  endpoint.
    """
    results = analyse_user_struggles(user_id, supabase)
    return jsonify({
        "struggling_count": len(results),
        "resources": results,
    })


@app.route("/ml/retrain", methods=["POST"])
def retrain():
    """
    POST /ml/retrain
    Protected by a simple secret header — call this from a cron job.

    Example:
      curl -X POST http://localhost:8001/ml/retrain \
           -H "X-Retrain-Secret: your-secret-here"
    """
    secret = request.headers.get("X-Retrain-Secret", "")
    if secret != os.getenv("RETRAIN_SECRET", "changemeplease"):
        return jsonify({"error": "Unauthorised"}), 401

    from ml.train_dae import train as train_dae
    try:
        result = train_dae(supabase=supabase, epochs=40)
        if result is None:
            return jsonify({"status": "skipped", "reason": "Not enough data yet"})
        global dae
        dae = DAERecommender(
            model_dir=os.path.join(os.path.dirname(__file__), "model")
        )
        return jsonify({"status": "ok", "model": "dae_cf"})
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 500


# ── Helpers ───────────────────────────────────────────────────────────────

def _enrich_recommendations(dae_results: list[dict], source: str) -> list[dict]:
    """Fetch full resource metadata for DAE output (which only has IDs)."""
    resource_ids = [r["resource_id"] for r in dae_results]
    resp = supabase.table("resources").select(
        "id, platform, title, tags, duration"
    ).in_("id", resource_ids).execute()
    meta = {r["id"]: r for r in (resp.data or [])}

    enriched = []
    for r in dae_results:
        m = meta.get(r["resource_id"], {})
        enriched.append({
            "id": r["resource_id"],
            "platform": m.get("platform", "Unknown"),
            "title": m.get("title", "Unknown resource"),
            "tags": m.get("tags") or [],
            "duration": m.get("duration"),
            "match_score": round(r["cf_score"] * 100, 1),
            "reason": f"Personalised by {source}",
        })
    return enriched


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, debug=True)