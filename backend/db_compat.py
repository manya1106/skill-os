"""
Database column compatibility — aligns code with Supabase ERD.
ERD flashcards: user_id, front, back | App UI: question, answer, deck_id
ERD interactions: ts | Some code paths: created_at
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional


def card_to_api(row: dict) -> dict:
    """Normalize DB row for frontend (question/answer aliases)."""
    if not row:
        return row
    out = dict(row)
    out["question"] = row.get("question") or row.get("front") or ""
    out["answer"] = row.get("answer") or row.get("back") or ""
    return out


def card_insert_payload(
    user_id: str,
    question: str,
    answer: str,
    deck_id: Optional[str] = None,
    source: Optional[str] = None,
    due_date: Optional[str] = None,
    stability: float = 0,
    difficulty: float = 5,
    review_count: int = 0,
) -> dict:
    """Build insert dict supporting both ERD and legacy columns."""
    today = str(date.today())
    payload = {
        "user_id": user_id,
        "front": question,
        "back": answer,
        "question": question,
        "answer": answer,
        "source": source,
        "due_date": due_date or today,
        "stability": stability,
        "difficulty": difficulty,
        "review_count": review_count,
    }
    if deck_id:
        payload["deck_id"] = deck_id
    return payload


def interaction_insert_payload(
    user_id: str,
    resource_id: str,
    event_type: str,
    value: float,
    timestamp: str,
) -> dict:
    """Write both ts (ERD) and created_at for compatibility."""
    return {
        "user_id": user_id,
        "resource_id": resource_id,
        "event_type": event_type,
        "value": value,
        "ts": timestamp,
        "created_at": timestamp,
    }
