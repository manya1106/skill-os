"""
SkillOS Flask ML Service
========================

Runs on port 8001.

Features:
  • DAE-CF with real user interaction vectors at inference
  • Hybrid ensemble: configurable CF + TF-IDF weights (default 0.7 / 0.3)
  • Redis cache (top-100 per user, <200ms target on hits)
  • APScheduler nightly retraining at 02:00 UTC

Start:
  cd backend
  python -m ml.app
"""

import os
import atexit
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

app = Flask(__name__)
CORS(app)

MODEL_DIR = os.path.join(os.path.dirname(__file__), "model")
DEFAULT_CF_WEIGHT = float(os.getenv("DEFAULT_CF_WEIGHT", "0.7"))
DEFAULT_TFIDF_WEIGHT = float(os.getenv("DEFAULT_TFIDF_WEIGHT", "0.3"))

# ── Supabase ──────────────────────────────────────────────────────────────────
supabase: Client = create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_KEY", ""),
)

# ── ML components ─────────────────────────────────────────────────────────────
from ml.recommend import get_tfidf_recommendations, get_tfidf_score_map
from ml.struggle import analyse_user_struggles
from ml.train_dae import DAERecommender
from ml.recommendation_cache import RecommendationCache, CACHE_TOP_N
from ml.retrain_scheduler import (
    start_scheduler,
    stop_scheduler,
    get_status,
    check_retrain_health,
    register_on_retrain_success,
)

dae = DAERecommender(model_dir=MODEL_DIR, supabase=supabase)

cache = RecommendationCache(
    redis_host=os.getenv("REDIS_HOST", "localhost"),
    redis_port=int(os.getenv("REDIS_PORT", 6379)),
    ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", 14400)),
    enabled=os.getenv("REDIS_ENABLED", "true").lower() == "true",
)


def reload_dae_model():
    """Reload DAE weights after retraining."""
    global dae
    dae = DAERecommender(model_dir=MODEL_DIR, supabase=supabase)
    app.logger.info("[ML Service] DAE model reloaded")


register_on_retrain_success(reload_dae_model)
register_on_retrain_success(lambda: cache.invalidate_all())


# ── Startup / shutdown ────────────────────────────────────────────────────────

_scheduler_started = False


def _ensure_scheduler():
    global _scheduler_started
    if not _scheduler_started:
        _scheduler_started = True
        try:
            start_scheduler()
            app.logger.info("[ML Service] Retrain scheduler started (02:00 UTC daily)")
        except Exception as e:
            app.logger.error(f"[ML Service] Scheduler failed to start: {e}")


_ensure_scheduler()


def shutdown_handler():
    try:
        stop_scheduler()
        app.logger.info("[ML Service] Scheduler stopped")
    except Exception as e:
        app.logger.error(f"[ML Service] Scheduler shutdown error: {e}")


atexit.register(shutdown_handler)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_blend_weights() -> dict:
    """Parse ?cf_weight=&tfidf_weight= query params (normalised to sum 1)."""
    cf = request.args.get("cf_weight", type=float)
    tfidf = request.args.get("tfidf_weight", type=float)

    if cf is None and tfidf is None:
        cf, tfidf = DEFAULT_CF_WEIGHT, DEFAULT_TFIDF_WEIGHT
    elif cf is None:
        cf = max(0.0, 1.0 - tfidf)
    elif tfidf is None:
        tfidf = max(0.0, 1.0 - cf)

    total = cf + tfidf
    if total <= 0:
        cf, tfidf = DEFAULT_CF_WEIGHT, DEFAULT_TFIDF_WEIGHT
        total = cf + tfidf

    return {"cf": cf / total, "tfidf": tfidf / total}


def _compute_recommendations(
    user_id: str,
    top_n: int,
    blend_weights: dict,
) -> tuple[list[dict], str]:
    """
    Hybrid recommendation pipeline:
      1. DAE-CF with user interaction vector
      2. Blend with TF-IDF scores (weighted ensemble)
      3. TF-IDF-only fallback for cold-start
    """
    tfidf_w = blend_weights["tfidf"]
    compute_n = max(top_n, CACHE_TOP_N)

    if dae.is_ready():
        tfidf_scores = (
            get_tfidf_score_map(user_id, supabase) if tfidf_w > 0 else None
        )
        dae_results = dae.recommend(
            user_id,
            top_n=compute_n,
            tfidf_weight=tfidf_w,
            tfidf_scores=tfidf_scores,
        )
        if dae_results:
            model_label = "hybrid" if tfidf_w > 0 and tfidf_scores else "dae_cf"
            enriched = _enrich_recommendations(dae_results[:top_n], source=model_label)
            return enriched, model_label

    tfidf_results = get_tfidf_recommendations(user_id, supabase, top_n=top_n)
    return tfidf_results, "tfidf"


def _enrich_recommendations(dae_results: list[dict], source: str) -> list[dict]:
    """Fetch resource metadata for DAE/hybrid output."""
    resource_ids = [r["resource_id"] for r in dae_results]
    if not resource_ids:
        return []

    resp = (
        supabase.table("resources")
        .select("id, platform, title, tags, duration")
        .in_("id", resource_ids)
        .execute()
    )
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
            "match_score": round(r.get("final_score", 0) * 100, 1),
            "cf_score": round(r.get("cf_score", 0) * 100, 1),
            "tfidf_score": round(r["tfidf_score"] * 100, 1)
            if r.get("tfidf_score") is not None
            else None,
            "reason": f"Personalised ({source})",
        })
    return enriched


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/ml/health")
def health():
    return jsonify({
        "status": "ok",
        "dae_model_ready": dae.is_ready(),
        "cache_enabled": cache.enabled,
        "mode": "hybrid" if dae.is_ready() else "TF-IDF",
        "default_blend": {"cf": DEFAULT_CF_WEIGHT, "tfidf": DEFAULT_TFIDF_WEIGHT},
        "timestamp": datetime.utcnow().isoformat(),
    })


@app.route("/ml/health-check")
def health_check():
    import sys

    try:
        import psutil

        mem_info = psutil.Process(os.getpid()).memory_info()
        memory_mb = round(mem_info.rss / 1024 / 1024)
    except Exception:
        memory_mb = None

    retrain_health = check_retrain_health()
    cache_stats = cache.get_stats()

    overall_status = "healthy"
    if retrain_health["status"] != "healthy":
        overall_status = "degraded"
    if cache_stats.get("error"):
        overall_status = "degraded"

    return jsonify({
        "overall_status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "model": {
            "type": "hybrid (DAE-CF + TF-IDF)" if dae.is_ready() else "TF-IDF (fallback)",
            "ready": dae.is_ready(),
            "user_count": len(dae.user_ids) if dae.is_ready() else 0,
            "resource_count": len(dae.resource_ids) if dae.is_ready() else 0,
        },
        "cache": {**cache_stats, "cache_top_n": CACHE_TOP_N},
        "retraining": retrain_health,
        "system": {
            "memory_mb": memory_mb,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        },
    })


@app.route("/ml/retrain-status")
def retrain_status():
    return jsonify({
        "retraining": get_status(),
        "timestamp": datetime.utcnow().isoformat(),
    })


@app.route("/ml/recommend/<user_id>")
def recommend(user_id: str):
    """
    GET /ml/recommend/{user_id}?top_n=6&cf_weight=0.7&tfidf_weight=0.3

    Pipeline: Redis cache → hybrid DAE-CF + TF-IDF → TF-IDF fallback.
    Caches top-100 per user for fast subsequent requests.
    """
    top_n = min(int(request.args.get("top_n", 6)), CACHE_TOP_N)
    blend_weights = _parse_blend_weights()

    cached = cache.get(user_id, top_n, blend_weights)
    if cached:
        return jsonify({
            "recommendations": cached,
            "model": "cache_hit",
            "cached": True,
            "blend_weights": blend_weights,
        })

    recs, model = _compute_recommendations(user_id, top_n, blend_weights)
    cache.set(user_id, recs, top_n, blend_weights)

    return jsonify({
        "recommendations": recs,
        "model": model,
        "cached": False,
        "blend_weights": blend_weights,
    })


@app.route("/ml/struggle/<user_id>")
def struggle(user_id: str):
    results = analyse_user_struggles(user_id, supabase)
    return jsonify({
        "struggling_count": len(results),
        "resources": results,
    })


@app.route("/ml/retrain", methods=["POST"])
def retrain():
    secret = request.headers.get("X-Retrain-Secret", "")
    if secret != os.getenv("RETRAIN_SECRET", "changemeplease"):
        return jsonify({"error": "Unauthorized"}), 401

    from ml.train_dae import train as train_dae

    try:
        result = train_dae(supabase=supabase, epochs=40, model_dir=MODEL_DIR)
        if result is None:
            return jsonify({"status": "skipped", "reason": "Not enough data yet"})

        reload_dae_model()
        cache.invalidate_all()

        return jsonify({
            "status": "ok",
            "model": "dae_cf",
            "timestamp": datetime.utcnow().isoformat(),
        })
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 500


@app.route("/ml/cache-stats")
def cache_stats_route():
    return jsonify(cache.get_stats())


@app.route("/ml/cache-clear", methods=["POST"])
def cache_clear():
    secret = request.headers.get("X-Retrain-Secret", "")
    if secret != os.getenv("RETRAIN_SECRET", "changemeplease"):
        return jsonify({"error": "Unauthorized"}), 401

    deleted = cache.invalidate_all()
    return jsonify({"cleared": deleted, "timestamp": datetime.utcnow().isoformat()})


@app.route("/ml/cache-clear/<user_id>", methods=["POST"])
def cache_clear_user(user_id: str):
    deleted = cache.invalidate_user(user_id)
    return jsonify({"user_id": user_id, "cleared": deleted})


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def server_error(e):
    app.logger.error(f"Internal error: {e}", exc_info=True)
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)
    app.run(host="0.0.0.0", port=8001, debug=True)
