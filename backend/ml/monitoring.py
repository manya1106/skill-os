"""
Monitoring & Alerting for SkillOS ML Pipeline
==============================================

Tracks:
  1. Model staleness (last training >24h old)
  2. Cache performance (hit rate <50%)
  3. Retraining failures (>3 consecutive failures)
  4. System health (memory usage, errors)

Alerts via:
  - /ml/alerts endpoint (JSON for dashboard)
  - Webhook post (to Slack, PagerDuty, etc.)
  - Email (for critical issues)

Integration:
  - Call check_alerts() periodically (via scheduler or cron)
  - Frontend polls /ml/alerts for UI badges
"""

import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from enum import Enum

import httpx
from supabase import create_client, Client

# ── Setup ─────────────────────────────────────────────────────────────────────
logger = logging.getLogger("skill_os.alerts")
LOG_DIR = Path(os.getenv("LOG_DIR", "/var/log/skillos"))
LOG_DIR.mkdir(exist_ok=True)

log_file = LOG_DIR / "alerts.log"
handler = logging.FileHandler(log_file)
handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
))
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

supabase: Client = create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_KEY", ""),
)

# ── Alert severity levels ─────────────────────────────────────────────────────

class AlertSeverity(str, Enum):
    CRITICAL = "critical"  # Service degraded, immediate action needed
    WARNING = "warning"    # Minor issue, monitor closely
    INFO = "info"         # Informational only


class Alert:
    """Single alert object."""
    
    def __init__(
        self,
        severity: AlertSeverity,
        component: str,
        message: str,
        details: Optional[Dict] = None,
    ):
        self.id = f"{component}_{datetime.utcnow().isoformat()}"
        self.severity = severity
        self.component = component  # "model", "cache", "scheduler", "system"
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.utcnow().isoformat()
        self.acknowledged = False
    
    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dict."""
        return {
            "id": self.id,
            "severity": self.severity.value,
            "component": self.component,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
            "acknowledged": self.acknowledged,
        }


class AlertManager:
    """Manages alert collection, storage, and delivery."""
    
    def __init__(self):
        self.alerts: List[Alert] = []
        self.alert_history_file = LOG_DIR / "alert_history.jsonl"
    
    def add_alert(self, alert: Alert) -> None:
        """Add alert and log to file."""
        self.alerts.append(alert)
        self._log_alert(alert)
        logger.log(
            logging.CRITICAL if alert.severity == AlertSeverity.CRITICAL else logging.WARNING,
            f"[{alert.component}] {alert.message}"
        )
    
    def _log_alert(self, alert: Alert) -> None:
        """Persist alert to history log."""
        try:
            with open(self.alert_history_file, "a") as f:
                f.write(json.dumps(alert.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Failed to log alert: {e}")
    
    def get_critical(self) -> List[Alert]:
        """Get all critical alerts."""
        return [a for a in self.alerts if a.severity == AlertSeverity.CRITICAL]
    
    def get_all(self) -> List[Alert]:
        """Get all active alerts."""
        return self.alerts
    
    def clear_old_alerts(self, hours: int = 24) -> int:
        """Remove alerts older than N hours."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        original_count = len(self.alerts)
        
        self.alerts = [
            a for a in self.alerts
            if datetime.fromisoformat(a.timestamp) > cutoff
        ]
        
        removed = original_count - len(self.alerts)
        if removed > 0:
            logger.info(f"[Manager] Cleared {removed} old alerts")
        return removed
    
    def to_dict(self) -> Dict:
        """Return manager state as dict."""
        return {
            "total_alerts": len(self.alerts),
            "critical_count": len(self.get_critical()),
            "alerts": [a.to_dict() for a in self.alerts],
            "timestamp": datetime.utcnow().isoformat(),
        }


# ── Checkers ──────────────────────────────────────────────────────────────────

class ModelStalenessChecker:
    """Monitor if DAE-CF model is too old."""
    
    @staticmethod
    def check(retrain_status: Dict) -> Optional[Alert]:
        """
        Check if model is stale.
        
        Args:
            retrain_status: dict from get_status()
        
        Returns:
            Alert if model is stale, None otherwise
        """
        if not retrain_status.get("last_success"):
            return Alert(
                severity=AlertSeverity.CRITICAL,
                component="model",
                message="No successful training yet — model is empty",
                details={"status": retrain_status},
            )
        
        last_train = datetime.fromisoformat(retrain_status["last_success"])
        age = datetime.utcnow() - last_train
        
        if age > timedelta(hours=24):
            return Alert(
                severity=AlertSeverity.CRITICAL,
                component="model",
                message=f"DAE-CF model is {age.days}d {age.seconds//3600}h old",
                details={
                    "last_training": retrain_status["last_success"],
                    "age_hours": age.total_seconds() / 3600,
                    "total_trains": retrain_status.get("total_trains", 0),
                },
            )
        
        if age > timedelta(hours=12):
            return Alert(
                severity=AlertSeverity.WARNING,
                component="model",
                message=f"DAE-CF model is {age.seconds//3600}h old",
                details={"last_training": retrain_status["last_success"]},
            )
        
        return None


class CacheHealthChecker:
    """Monitor cache hit rate and memory usage."""
    
    @staticmethod
    def check(cache_stats: Dict) -> Optional[Alert]:
        """
        Check cache health.
        
        Args:
            cache_stats: dict from cache.get_stats()
        
        Returns:
            Alert if cache is unhealthy, None otherwise
        """
        if not cache_stats.get("enabled"):
            return Alert(
                severity=AlertSeverity.WARNING,
                component="cache",
                message="Redis cache is disabled",
                details=cache_stats,
            )
        
        if cache_stats.get("error"):
            return Alert(
                severity=AlertSeverity.CRITICAL,
                component="cache",
                message=f"Cache error: {cache_stats['error']}",
                details=cache_stats,
            )
        
        hit_rate = cache_stats.get("hit_rate_pct", 0)
        if hit_rate < 20 and cache_stats.get("total_requests", 0) > 10:
            return Alert(
                severity=AlertSeverity.WARNING,
                component="cache",
                message=f"Low cache hit rate: {hit_rate}%",
                details={
                    "hits": cache_stats.get("hits"),
                    "misses": cache_stats.get("misses"),
                    "hit_rate_pct": hit_rate,
                },
            )
        
        return None


class SchedulerHealthChecker:
    """Monitor retraining scheduler for failures."""
    
    def __init__(self):
        self.failure_count = 0
        self.last_failure = None
    
    def check(self, retrain_status: Dict) -> Optional[Alert]:
        """
        Check scheduler health.
        
        Args:
            retrain_status: dict from get_status()
        
        Returns:
            Alert if scheduler has issues, None otherwise
        """
        # Reset if last_success is recent
        if retrain_status.get("last_success"):
            last_success = datetime.fromisoformat(retrain_status["last_success"])
            if (datetime.utcnow() - last_success) < timedelta(hours=1):
                self.failure_count = 0
                self.last_failure = None
                return None
        
        # Track consecutive failures
        if retrain_status.get("last_failure"):
            self.last_failure = retrain_status["last_failure"]
            self.failure_count += 1
        
        if self.failure_count >= 3:
            return Alert(
                severity=AlertSeverity.CRITICAL,
                component="scheduler",
                message=f"{self.failure_count} consecutive retraining failures",
                details={
                    "consecutive_failures": self.failure_count,
                    "last_failure": retrain_status.get("last_failure"),
                    "last_failure_reason": retrain_status.get("last_failure_reason"),
                },
            )
        
        if self.failure_count >= 2:
            return Alert(
                severity=AlertSeverity.WARNING,
                component="scheduler",
                message=f"{self.failure_count} recent retraining failures",
                details={
                    "last_failure_reason": retrain_status.get("last_failure_reason"),
                },
            )
        
        return None


# ── Notification handlers ─────────────────────────────────────────────────────

class AlertNotifier:
    """Send alerts to external systems."""
    
    @staticmethod
    def notify_critical(alert: Alert) -> bool:
        """
        Send critical alert to webhook/email.
        
        Args:
            alert: Alert object
        
        Returns:
            True if sent successfully
        """
        webhook_url = os.getenv("ALERT_WEBHOOK_URL")
        if not webhook_url:
            logger.warning("[Notifier] No webhook URL configured")
            return False
        
        try:
            payload = {
                "severity": alert.severity.value,
                "component": alert.component,
                "message": alert.message,
                "timestamp": alert.timestamp,
                "details": alert.details,
            }
            
            response = httpx.post(
                webhook_url,
                json=payload,
                timeout=5.0,
            )
            
            if response.status_code == 200:
                logger.info(f"[Notifier] Alert sent to webhook")
                return True
            else:
                logger.error(f"[Notifier] Webhook returned {response.status_code}")
                return False
        
        except Exception as e:
            logger.error(f"[Notifier] Failed to send alert: {e}")
            return False


# ── Main check function ───────────────────────────────────────────────────────

alert_manager = AlertManager()
scheduler_checker = SchedulerHealthChecker()


def check_all_alerts(retrain_status: Dict, cache_stats: Dict) -> AlertManager:
    """
    Run all health checks and update alert manager.
    
    Call this periodically (every 5-10 minutes) to keep alerts fresh.
    
    Args:
        retrain_status: from retrain_scheduler.get_status()
        cache_stats: from cache.get_stats()
    
    Returns:
        Updated AlertManager instance
    """
    # Clear alerts older than 24h
    alert_manager.clear_old_alerts(hours=24)
    
    # Run checks
    checks = [
        ModelStalenessChecker.check(retrain_status),
        CacheHealthChecker.check(cache_stats),
        scheduler_checker.check(retrain_status),
    ]
    
    # Add any new alerts
    for alert in checks:
        if alert and alert.severity == AlertSeverity.CRITICAL:
            # Check if we already have this alert
            has_duplicate = any(
                a.component == alert.component and a.message == alert.message
                for a in alert_manager.alerts
            )
            
            if not has_duplicate:
                alert_manager.add_alert(alert)
                AlertNotifier.notify_critical(alert)
        elif alert:
            alert_manager.add_alert(alert)
    
    return alert_manager


# ── Monitoring endpoints (for FastAPI/Flask wrapper) ────────────────────────────

def get_alerts_for_api() -> Dict:
    """
    Return current alerts as API response.
    
    Usage in main.py:
        @app.get("/ml/alerts")
        def get_alerts():
            return monitoring.get_alerts_for_api()
    """
    return alert_manager.to_dict()


# ── Test/standalone mode ───────────────────────────────────────────────────────

if __name__ == "__main__":
    # Example: create and manage test alerts
    print("[Test] Alert Manager Example\n")
    
    # Simulate stale model alert
    alert1 = Alert(
        severity=AlertSeverity.CRITICAL,
        component="model",
        message="DAE-CF model is 48h old",
        details={"age_hours": 48},
    )
    alert_manager.add_alert(alert1)
    
    # Simulate low cache hit rate
    alert2 = Alert(
        severity=AlertSeverity.WARNING,
        component="cache",
        message="Cache hit rate at 15%",
        details={"hits": 30, "misses": 170},
    )
    alert_manager.add_alert(alert2)
    
    # Print state
    print(f"Total alerts: {alert_manager.alert_manager.get_all()}")
    print(f"Critical count: {len(alert_manager.get_critical())}")
    print(f"\nAlert state:\n{json.dumps(alert_manager.to_dict(), indent=2)}")