"""
APScheduler-based Automatic Retraining for DAE-CF Model
========================================================

Runs daily at 2am UTC (configurable via RETRAIN_CRON_HOUR/MINUTE).
Retrains when >=50 new interactions since last success.
Invalidates Redis cache and reloads model on success.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, List

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from supabase import create_client, Client

logger = logging.getLogger("skill_os.retrain")
LOG_DIR = Path(os.getenv("LOG_DIR", os.path.join(os.path.dirname(__file__), "logs")))
LOG_DIR.mkdir(parents=True, exist_ok=True)

log_file = LOG_DIR / "retrain.log"
handler = logging.FileHandler(log_file)
handler.setLevel(logging.DEBUG)
handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

supabase: Client = create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_KEY", ""),
)

MODEL_DIR = os.path.join(os.path.dirname(__file__), "model")
STATUS_FILE = LOG_DIR / "retrain_status.json"
MIN_NEW_INTERACTIONS = int(os.getenv("RETRAIN_MIN_INTERACTIONS", "50"))

_on_success_callbacks: List[Callable[[], None]] = []


def register_on_retrain_success(callback: Callable[[], None]):
    """Register hooks (model reload, cache bust) after successful retrain."""
    _on_success_callbacks.append(callback)


class RetrainStatus:
    def __init__(self):
        self.is_running = False
        self.last_success = None
        self.last_failure = None
        self.last_failure_reason = None
        self.last_check = None
        self.total_trains = 0
        self._load()

    def _load(self):
        if STATUS_FILE.exists():
            try:
                with open(STATUS_FILE) as f:
                    data = json.load(f)
                self.last_success = data.get("last_success")
                self.last_failure = data.get("last_failure")
                self.last_failure_reason = data.get("last_failure_reason")
                self.total_trains = data.get("total_trains", 0)
            except Exception as e:
                logger.error(f"[Status] Failed to load: {e}")

    def _save(self):
        try:
            with open(STATUS_FILE, "w") as f:
                json.dump(
                    {
                        "last_success": self.last_success,
                        "last_failure": self.last_failure,
                        "last_failure_reason": self.last_failure_reason,
                        "total_trains": self.total_trains,
                        "is_running": self.is_running,
                    },
                    f,
                    indent=2,
                )
        except Exception as e:
            logger.error(f"[Status] Failed to save: {e}")

    def start_train(self):
        self.is_running = True
        self.last_check = datetime.utcnow().isoformat()

    def success(self):
        self.is_running = False
        self.last_success = datetime.utcnow().isoformat()
        self.last_failure = None
        self.last_failure_reason = None
        self.total_trains += 1
        self._save()

    def failure(self, reason: str):
        self.is_running = False
        self.last_failure = datetime.utcnow().isoformat()
        self.last_failure_reason = reason
        self._save()

    def to_dict(self):
        return {
            "is_running": self.is_running,
            "last_success": self.last_success,
            "last_failure": self.last_failure,
            "last_failure_reason": self.last_failure_reason,
            "last_check": self.last_check,
            "total_trains": self.total_trains,
            "schedule": f"{os.getenv('RETRAIN_CRON_HOUR', '2')}:{os.getenv('RETRAIN_CRON_MINUTE', '0')} UTC",
        }


status = RetrainStatus()


def count_new_interactions() -> int:
    if not status.last_success:
        resp = supabase.table("interactions").select("id").execute()
        return len(resp.data or [])

    try:
        resp = (
            supabase.table("interactions")
            .select("id")
            .gte("created_at", status.last_success)
            .execute()
        )
        return len(resp.data or [])
    except Exception as e:
        logger.error(f"[Check] Failed to count interactions: {e}")
        return 0


def should_retrain() -> tuple[bool, str]:
    if status.is_running:
        return False, "Training already in progress"

    count = count_new_interactions()
    if count < MIN_NEW_INTERACTIONS:
        return False, f"Only {count} interactions (threshold: {MIN_NEW_INTERACTIONS})"

    return True, f"{count} new interactions since last train"


def train_dae_model() -> bool:
    status.start_train()
    try:
        from ml.train_dae import train as train_dae

        logger.info("[Train] Starting DAE-CF retraining...")
        result = train_dae(supabase=supabase, epochs=40, model_dir=MODEL_DIR)

        if result is None:
            status.failure("Insufficient data for training")
            return False

        status.success()
        logger.info("[Train] DAE-CF model trained successfully")
        return True

    except Exception as e:
        logger.exception(f"[Train] Failed: {e}")
        status.failure(str(e))
        return False


def _run_success_callbacks():
    for cb in _on_success_callbacks:
        try:
            cb()
        except Exception as e:
            logger.warning(f"[Schedule] Post-retrain callback failed: {e}")


def scheduled_retrain_job():
    logger.info("=" * 60)
    logger.info("[Schedule] Daily retrain job triggered")

    should_train, reason = should_retrain()
    if not should_train:
        logger.info(f"[Schedule] Skipping: {reason}")
        return

    logger.info(f"[Schedule] Starting: {reason}")
    if train_dae_model():
        _run_success_callbacks()
        logger.info("[Schedule] Retraining completed — model reloaded, cache cleared")
    else:
        logger.error("[Schedule] Retraining failed — model unchanged")

    logger.info("=" * 60)


scheduler = None


def start_scheduler():
    global scheduler

    if scheduler and scheduler.running:
        return

    hour = int(os.getenv("RETRAIN_CRON_HOUR", "2"))
    minute = int(os.getenv("RETRAIN_CRON_MINUTE", "0"))

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        scheduled_retrain_job,
        trigger=CronTrigger(hour=hour, minute=minute, timezone="UTC"),
        id="dae_retrain_daily",
        name="Daily DAE-CF Retraining",
        replace_existing=True,
        misfire_grace_time=300,
    )
    scheduler.start()
    logger.info(f"[Scheduler] Started — daily retrain at {hour:02d}:{minute:02d} UTC")


def stop_scheduler():
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=True)
    scheduler = None


def get_status():
    return status.to_dict()


def check_retrain_health() -> dict:
    health = {"status": "healthy", "alerts": [], **status.to_dict()}

    if status.last_failure:
        last_fail = datetime.fromisoformat(status.last_failure)
        if datetime.utcnow() - last_fail < timedelta(hours=6):
            health["status"] = "degraded"
            health["alerts"].append(f"Training failed: {status.last_failure_reason}")

    if not status.last_success:
        health["status"] = "degraded"
        health["alerts"].append("No successful training yet")
    elif datetime.utcnow() - datetime.fromisoformat(status.last_success) > timedelta(hours=24):
        health["status"] = "degraded"
        health["alerts"].append("Model is >24h stale")

    return health


if __name__ == "__main__":
    import time

    start_scheduler()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        stop_scheduler()
