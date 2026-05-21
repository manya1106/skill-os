"""
Redis Caching Layer for ML Recommendations
===========================================

Features:
- Sub-10ms cache hits
- Configurable TTL (1-6 hours)
- Smart invalidation (user activity, retrain, explicit bust)
- Graceful degradation if Redis unavailable
- Metrics: hit rate, latency, memory usage
"""

import redis
import os
import json
import hashlib
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger("skill_os.cache")

# Cache up to 100 recommendations per user for fast top-N slicing
CACHE_TOP_N = int(os.getenv("CACHE_TOP_N", 100))


class RecommendationCache:
    """
    Redis-backed caching for ML recommendations.
    
    Key structure:
    - recs:{user_id}:{top_n}:{blend_weights} = cached result
    - cache_meta:{user_id} = metadata (timestamp, model_version)
    - cache_stats = overall metrics
    
    TTL: 3-6 hours (configurable)
    """
    
    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        ttl_seconds: int = 3600 * 4,  # 4 hours default
        enabled: bool = True,
    ):
        self.enabled = enabled
        self.ttl_seconds = ttl_seconds
        self.hits = 0
        self.misses = 0
        
        if not enabled:
            logger.info("[Cache] Disabled (pass enabled=True to activate)")
            self.redis = None
            return
        
        try:
            self.redis = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                decode_responses=True,
                socket_connect_timeout=3,
            )
            # Test connection
            self.redis.ping()
            logger.info(f"[Cache] Connected to Redis at {redis_host}:{redis_port}")
        except redis.ConnectionError as e:
            logger.warning(f"[Cache] Redis unavailable: {e} — caching disabled")
            self.redis = None
            self.enabled = False
    
    def _make_key(self, user_id: str, top_n: int, blend_weights: Optional[Dict] = None) -> str:
        """Generate cache key from parameters."""
        if blend_weights:
            # Hash weights to avoid key explosion
            weight_str = json.dumps(blend_weights, sort_keys=True)
            weight_hash = hashlib.md5(weight_str.encode()).hexdigest()[:8]
            return f"recs:{user_id}:{top_n}:{weight_hash}"
        return f"recs:{user_id}:{top_n}:default"
    
    def get(
        self,
        user_id: str,
        top_n: int = 6,
        blend_weights: Optional[Dict] = None,
    ) -> Optional[List[dict]]:
        """
        Retrieve cached recommendations.
        
        Returns:
            List of recommendation dicts OR None if miss/expired/disabled
        """
        if not self.enabled or not self.redis:
            return None
        
        try:
            key = self._make_key(user_id, CACHE_TOP_N, blend_weights)
            cached = self.redis.get(key)

            if cached:
                self.hits += 1
                logger.debug(f"[Cache] HIT: {key}")
                data = json.loads(cached)
                if isinstance(data, dict) and "recommendations" in data:
                    recs = data["recommendations"]
                elif isinstance(data, list):
                    recs = data
                else:
                    return None
                return recs[:top_n]
            
            self.misses += 1
            logger.debug(f"[Cache] MISS: {key}")
            return None
        
        except Exception as e:
            logger.error(f"[Cache] GET failed: {e}")
            return None
    
    def set(
        self,
        user_id: str,
        recommendations: List[dict],
        top_n: int = 6,
        blend_weights: Optional[Dict] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Cache recommendations.
        
        Args:
            user_id: User ID
            recommendations: List of recommendation dicts
            top_n: Top N parameter
            blend_weights: Optional blending params
            ttl: Override default TTL (seconds)
        
        Returns:
            True if set successfully, False otherwise
        """
        if not self.enabled or not self.redis:
            return False
        
        try:
            # Always store up to CACHE_TOP_N for sub-200ms top-N slicing
            to_store = recommendations[:CACHE_TOP_N]
            key = self._make_key(user_id, CACHE_TOP_N, blend_weights)
            ttl = ttl or self.ttl_seconds

            cache_data = {
                "recommendations": to_store,
                "cached_at": datetime.utcnow().isoformat(),
                "ttl_seconds": ttl,
                "stored_top_n": len(to_store),
            }

            self.redis.setex(key, ttl, json.dumps(cache_data))
            
            logger.debug(f"[Cache] SET: {key} (TTL {ttl}s)")
            return True
        
        except Exception as e:
            logger.error(f"[Cache] SET failed: {e}")
            return False
    
    def invalidate_user(self, user_id: str) -> int:
        """
        Invalidate all cached recommendations for a user.
        
        Triggered by:
        - User activity (resource added, progress changed)
        - User feedback submitted
        
        Returns:
            Number of keys deleted
        """
        if not self.enabled or not self.redis:
            return 0
        
        try:
            # Match pattern: recs:{user_id}:*
            pattern = f"recs:{user_id}:*"
            keys = self.redis.keys(pattern)
            
            if keys:
                deleted = self.redis.delete(*keys)
                logger.info(f"[Cache] Invalidated {deleted} keys for user {user_id}")
                return deleted
            
            return 0
        
        except Exception as e:
            logger.error(f"[Cache] INVALIDATE failed: {e}")
            return 0
    
    def invalidate_all(self) -> int:
        """
        Clear all recommendation cache.
        
        Triggered by:
        - Model retraining
        - System maintenance
        
        Returns:
            Number of keys deleted
        """
        if not self.enabled or not self.redis:
            return 0
        
        try:
            pattern = "recs:*"
            keys = self.redis.keys(pattern)
            
            if keys:
                deleted = self.redis.delete(*keys)
                logger.info(f"[Cache] Invalidated entire recommendation cache ({deleted} keys)")
                return deleted
            
            return 0
        
        except Exception as e:
            logger.error(f"[Cache] INVALIDATE_ALL failed: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Return cache statistics.
        
        Useful for monitoring hit rate, memory usage, etc.
        """
        if not self.enabled or not self.redis:
            return {"enabled": False}
        
        try:
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100) if total > 0 else 0
            
            # Get Redis memory usage
            info = self.redis.info("memory")
            used_memory = info.get("used_memory_human", "N/A")
            
            # Count cached keys
            pattern = "recs:*"
            keys_count = len(self.redis.keys(pattern))
            
            return {
                "enabled": True,
                "hits": self.hits,
                "misses": self.misses,
                "total_requests": total,
                "hit_rate_pct": round(hit_rate, 2),
                "cached_keys": keys_count,
                "redis_memory": used_memory,
            }
        
        except Exception as e:
            logger.error(f"[Cache] STATS failed: {e}")
            return {"enabled": True, "error": str(e)}


# ── Integration with Flask ML service ──────────────────────────────────────

def create_cached_recommender(redis_cache: RecommendationCache, dae_model, tfidf_func):
    """
    Factory function to wrap recommendation functions with caching.
    
    Usage in ml/app.py:
    
        cache = RecommendationCache()
        
        @app.route("/ml/recommend/<user_id>")
        def recommend(user_id: str):
            top_n = int(request.args.get("top_n", 6))
            blend_weights = {"cf": 0.7, "tfidf": 0.3}
            
            # Try cache first
            cached = cache.get(user_id, top_n, blend_weights)
            if cached:
                return jsonify({"recommendations": cached, "model": "cache"})
            
            # Compute
            recs = compute_recommendations(user_id, top_n, blend_weights)
            
            # Cache result
            cache.set(user_id, recs, top_n, blend_weights)
            
            return jsonify({"recommendations": recs, "model": "fresh"})
    """
    
    def cached_recommend(
        user_id: str,
        top_n: int = 6,
        blend_weights: Optional[Dict] = None,
    ) -> tuple[List[dict], str]:
        """
        Wrapped recommendation function.
        
        Returns:
            (recommendations, source) where source ∈ {"cache", "dae_cf", "tfidf"}
        """
        # Default blending
        blend_weights = blend_weights or {"cf": 0.7, "tfidf": 0.3}
        
        # 1. Try cache
        cached = redis_cache.get(user_id, top_n, blend_weights)
        if cached:
            return cached, "cache"
        
        # 2. Try DAE-CF
        if dae_model.is_ready():
            cf_recs = dae_model.recommend(user_id, top_n=top_n * 2)
            if cf_recs:
                # 3. Get TF-IDF scores for blending
                tfidf_recs = tfidf_func(user_id, top_n=len(cf_recs))
                tfidf_scores = {r["id"]: r["match_score"] / 100 for r in tfidf_recs}
                
                # 4. Blend
                blend_weight = blend_weights.get("tfidf", 0.3)
                blended = []
                for rec in cf_recs:
                    tfidf_score = tfidf_scores.get(rec["resource_id"], 0.5)
                    final_score = (
                        (1 - blend_weight) * rec["cf_score"] +
                        blend_weight * tfidf_score
                    )
                    rec["final_score"] = final_score
                    blended.append(rec)
                
                # Re-rank
                blended.sort(key=lambda x: x["final_score"], reverse=True)
                result = blended[:top_n]
                
                # Cache and return
                redis_cache.set(user_id, result, top_n, blend_weights)
                return result, "dae_cf_blended"
        
        # 5. Fallback to TF-IDF
        tfidf_recs = tfidf_func(user_id, top_n=top_n)
        redis_cache.set(user_id, tfidf_recs, top_n, blend_weights)
        return tfidf_recs, "tfidf"
    
    return cached_recommend


# ── Monitoring endpoint ────────────────────────────────────────────────────

def add_cache_monitoring_routes(app, cache: RecommendationCache):
    """
    Add monitoring endpoints to Flask app.
    
    Usage in ml/app.py:
        cache = RecommendationCache()
        add_cache_monitoring_routes(app, cache)
    """
    
    @app.route("/ml/cache-stats")
    def cache_stats():
        from flask import jsonify
        return jsonify(cache.get_stats())
    
    @app.route("/ml/cache-clear", methods=["POST"])
    def cache_clear():
        from flask import jsonify, request
        secret = request.headers.get("X-Retrain-Secret", "")
        if secret != os.getenv("RETRAIN_SECRET", "changemeplease"):
            return jsonify({"error": "Unauthorized"}), 401
        
        deleted = cache.invalidate_all()
        return jsonify({"cleared": deleted})
    
    @app.route("/ml/cache-clear/<user_id>", methods=["POST"])
    def cache_clear_user(user_id: str):
        from flask import jsonify
        deleted = cache.invalidate_user(user_id)
        return jsonify({"user_id": user_id, "cleared": deleted})


if __name__ == "__main__":
    # Test caching locally
    print("[Cache] Testing Redis caching layer...")
    
    cache = RecommendationCache(enabled=True)
    
    # Mock recommendation
    test_recs = [
        {"id": "res_1", "title": "Python Basics", "score": 0.95},
        {"id": "res_2", "title": "ML Intro", "score": 0.87},
    ]
    
    # Set
    cache.set("user_123", test_recs, top_n=6)
    print("✓ Set cache")
    
    # Get
    cached = cache.get("user_123", top_n=6)
    print(f"✓ Retrieved: {cached}")
    
    # Stats
    stats = cache.get_stats()
    print(f"✓ Stats: {stats}")
    
    # Invalidate
    cache.invalidate_user("user_123")
    print("✓ Invalidated user")
    
    print("\nTo use in production:")
    print("1. Install Redis: docker run -d -p 6379:6379 redis")
    print("2. Create cache instance in app.py")
    print("3. Wrap recommendation functions")
    print("4. Add monitoring routes")