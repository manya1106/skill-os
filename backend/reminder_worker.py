"""
Daily FSRS review reminder worker
=================================

Scheduled checks for due flashcards; sends email reminders when configured.
Runs via APScheduler (started from main.py on API startup).
"""

from __future__ import annotations

import logging
import os
import smtplib
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Callable, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("skill_os.reminders")

_scheduler: Optional[BackgroundScheduler] = None
_supabase = None

REMINDER_HOUR = int(os.getenv("REMINDER_CRON_HOUR", "8"))
REMINDER_MINUTE = int(os.getenv("REMINDER_CRON_MINUTE", "0"))
APP_URL = os.getenv("APP_URL", "http://localhost:5173")

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
EMAIL_REMINDERS_ENABLED = os.getenv("EMAIL_REMINDERS_ENABLED", "false").lower() == "true"


def _email_configured() -> bool:
    return bool(SMTP_HOST and SMTP_FROM and EMAIL_REMINDERS_ENABLED)


def count_due_cards(supabase, user_id: str) -> int:
    """Count flashcards due today or earlier for a user."""
    decks = (
        supabase.table("flashcard_decks")
        .select("id")
        .eq("user_id", user_id)
        .execute()
    )
    deck_ids = [d["id"] for d in (decks.data or [])]
    if not deck_ids:
        return 0

    today = str(date.today())
    total = 0
    for deck_id in deck_ids:
        cards = (
            supabase.table("flashcards")
            .select("id", count="exact")
            .eq("deck_id", deck_id)
            .lte("due_date", today)
            .execute()
        )
        total += len(cards.data or [])
    return total


def get_due_summary(supabase, user_id: str) -> dict:
    """Per-deck due counts for API / push polling."""
    decks = (
        supabase.table("flashcard_decks")
        .select("id, title")
        .eq("user_id", user_id)
        .execute()
    )
    today = str(date.today())
    deck_summaries = []
    total_due = 0

    for deck in decks.data or []:
        cards = (
            supabase.table("flashcards")
            .select("id")
            .eq("deck_id", deck["id"])
            .lte("due_date", today)
            .execute()
        )
        due = len(cards.data or [])
        if due > 0:
            deck_summaries.append({
                "deck_id": deck["id"],
                "title": deck["title"],
                "due_count": due,
            })
        total_due += due

    return {
        "total_due": total_due,
        "decks": deck_summaries,
        "checked_at": datetime.utcnow().isoformat(),
    }


def _user_wants_reminders(supabase, user_id: str) -> bool:
    """Check notification_settings table; default True if table missing."""
    try:
        row = (
            supabase.table("notification_settings")
            .select("email_reminders_enabled, push_reminders_enabled")
            .eq("user_id", user_id)
            .execute()
        )
        if row.data:
            return row.data[0].get("email_reminders_enabled", True)
    except Exception:
        pass
    return True


def send_email_reminder(to_email: str, name: str, due_count: int) -> bool:
    if not _email_configured() or due_count <= 0:
        return False

    subject = f"SkillOS: {due_count} flashcard{'s' if due_count != 1 else ''} due for review"
    body = f"""Hi {name or 'there'},

You have {due_count} flashcard(s) due for review today on SkillOS.

Spaced repetition works best when you review on schedule — open the app to keep your retention high:

{APP_URL}

Happy learning!
— SkillOS
"""

    msg = MIMEMultipart()
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [to_email], msg.as_string())
        logger.info(f"[Reminders] Email sent to {to_email} ({due_count} due)")
        return True
    except Exception as e:
        logger.error(f"[Reminders] Email failed for {to_email}: {e}")
        return False


def _log_reminder(supabase, user_id: str, due_count: int, channel: str, sent: bool):
    try:
        supabase.table("review_reminder_log").insert({
            "user_id": user_id,
            "due_count": due_count,
            "channel": channel,
            "sent": sent,
            "sent_at": datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass


def daily_reminder_job():
    """Check all users for due FSRS cards and send reminders."""
    if _supabase is None:
        return

    logger.info("[Reminders] Daily due-card check started")
    users = _supabase.table("users").select("id, email, name").execute()
    sent_count = 0

    for user in users.data or []:
        user_id = user["id"]
        if not _user_wants_reminders(_supabase, user_id):
            continue

        due_count = count_due_cards(_supabase, user_id)
        if due_count <= 0:
            continue

        email_sent = send_email_reminder(
            user.get("email", ""),
            user.get("name", ""),
            due_count,
        )
        _log_reminder(_supabase, user_id, due_count, "email", email_sent)
        if email_sent:
            sent_count += 1

        logger.info(
            f"[Reminders] User {user_id}: {due_count} due, email={'sent' if email_sent else 'skipped'}"
        )

    logger.info(f"[Reminders] Done — {sent_count} emails sent")


def start_reminder_scheduler(supabase_client):
    """Start background scheduler for daily FSRS reminders."""
    global _scheduler, _supabase
    _supabase = supabase_client

    if _scheduler and _scheduler.running:
        return

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        daily_reminder_job,
        trigger=CronTrigger(hour=REMINDER_HOUR, minute=REMINDER_MINUTE, timezone="UTC"),
        id="fsrs_daily_reminders",
        name="FSRS Daily Review Reminders",
        replace_existing=True,
        misfire_grace_time=600,
    )
    _scheduler.start()
    logger.info(
        f"[Reminders] Scheduler started — daily check at {REMINDER_HOUR:02d}:{REMINDER_MINUTE:02d} UTC"
    )


def stop_reminder_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
