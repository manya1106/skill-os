"""
FSRS (Free Spaced Repetition Scheduler) — Algorithm implementation
==================================================================

Implements FSRS-4.5 core mechanics:
  • Stability (S) and Difficulty (D) updates per review
  • Retention modeling: R(t) = (1 + FACTOR × t/S)^DECAY
  • Next interval: I = S × ln(target_retention) / ln(0.9)  (exponential scaling)
  • Rating scale: 0=Again, 1=Hard, 2=Good, 3=Easy (mapped to FSRS 1–4)

Reference: https://github.com/open-spaced-repetition/fsrs4anki
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

# FSRS-4.5 default weights (19 parameters)
_W = (
    0.4072, 1.1829, 3.1262, 15.4722, 7.2102, 0.5316, 1.0651, 0.0234, 1.616,
    0.1544, 1.0824, 1.9813, 0.0953, 0.2975, 2.2042, 0.2407, 2.9466, 0.5034, 0.6567,
)

REQUEST_RETENTION = float(__import__("os").getenv("FSRS_REQUEST_RETENTION", "0.9"))
MAXIMUM_INTERVAL = int(__import__("os").getenv("FSRS_MAX_INTERVAL_DAYS", "36500"))
MIN_STABILITY = 0.1
MIN_DIFFICULTY = 1.0
MAX_DIFFICULTY = 10.0

# Retention decay constants (FSRS-4.5)
_DECAY = -0.5
_FACTOR = 19.0 / 81.0
_LN_DECAY_TARGET = math.log(0.9)  # ln(0.9) for interval formula base


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def to_fsrs_rating(rating: int) -> int:
    """Map app rating 0–3 → FSRS rating 1–4."""
    return _clamp(rating + 1, 1, 4)


def retrievability(elapsed_days: float, stability: float) -> float:
    """
    Retention probability at elapsed_days since last review.
    R(t) = (1 + FACTOR × t/S)^DECAY
    """
    if stability < MIN_STABILITY:
        stability = MIN_STABILITY
    if elapsed_days < 0:
        elapsed_days = 0
    return (1 + _FACTOR * elapsed_days / stability) ** _DECAY


def next_interval_days(stability: float, target_retention: float = REQUEST_RETENTION) -> int:
    """
    Exponential interval scaling:
      next_interval = S × ln(target_retention) / ln(0.9)
    """
    if stability < MIN_STABILITY:
        stability = MIN_STABILITY
    if target_retention <= 0 or target_retention >= 1:
        target_retention = REQUEST_RETENTION
    interval = stability * math.log(target_retention) / _LN_DECAY_TARGET
    return max(1, min(MAXIMUM_INTERVAL, round(interval)))


def _initial_stability(rating: int) -> float:
    return _W[rating - 1]


def _initial_difficulty(rating: int) -> float:
    d = _W[4] - _W[5] * (rating - 3)
    return _clamp(d, MIN_DIFFICULTY, MAX_DIFFICULTY)


def _mean_reversion(init: float, current: float) -> float:
    return _W[7] * init + (1 - _W[7]) * current


def _next_difficulty(difficulty: float, rating: int) -> float:
    d0 = _initial_difficulty(3)
    delta = -_W[6] * (rating - 3)
    d = _mean_reversion(d0, difficulty + delta)
    return _clamp(d, MIN_DIFFICULTY, MAX_DIFFICULTY)


def _stability_after_success(
    stability: float,
    difficulty: float,
    retrievability_at_review: float,
    rating: int,
) -> float:
    hard_penalty = _W[15] if rating == 2 else 1.0
    easy_bonus = _W[16] if rating == 4 else 1.0
    return stability * (
        1
        + math.exp(_W[10])
        * (11 - difficulty)
        * math.pow(stability, _W[11])
        * (math.exp((1 - retrievability_at_review) * _W[12]) - 1)
        * hard_penalty
        * easy_bonus
    )


def _stability_after_failure(stability: float, difficulty: float) -> float:
    return (
        _W[13]
        * math.pow(difficulty, _W[14])
        * math.pow(stability, _W[11])
        * math.exp((1 - 0) * _W[12])
    )


def _stability_short_term(stability: float) -> float:
    return stability * math.exp(_W[17] * (_W[18] - 1))


def _elapsed_days(last_review: Optional[str], today: Optional[date] = None) -> float:
    today = today or date.today()
    if not last_review:
        return 0.0
    try:
        last = date.fromisoformat(str(last_review)[:10])
        return max(0.0, (today - last).days)
    except ValueError:
        return 0.0


@dataclass
class FSRSState:
    stability: float
    difficulty: float
    due_date: date
    interval_days: int
    retrievability: float
    review_count: int


def new_card_state() -> FSRSState:
    """State for a card that has never been reviewed."""
    return FSRSState(
        stability=0.0,
        difficulty=_initial_difficulty(3),
        due_date=date.today(),
        interval_days=0,
        retrievability=0.0,
        review_count=0,
    )


def review(
    stability: float,
    difficulty: float,
    review_count: int,
    last_review: Optional[str],
    rating: int,
    today: Optional[date] = None,
    target_retention: float = REQUEST_RETENTION,
) -> FSRSState:
    """
    Apply one FSRS review and return updated scheduling state.

    Args:
        stability: Current stability (days)
        difficulty: Current difficulty (1–10)
        review_count: Number of prior reviews
        last_review: ISO date string of last review
        rating: 0=Again, 1=Hard, 2=Good, 3=Easy
    """
    today = today or date.today()
    fsrs_rating = to_fsrs_rating(rating)
    elapsed = _elapsed_days(last_review, today)

    # First review — initialise S and D from rating
    if review_count == 0:
        new_s = _initial_stability(fsrs_rating)
        new_d = _initial_difficulty(fsrs_rating)
        if fsrs_rating == 1:
            interval = 1
            new_d = _next_difficulty(new_d, fsrs_rating)
        else:
            interval = next_interval_days(new_s, target_retention)
        return FSRSState(
            stability=round(new_s, 4),
            difficulty=round(new_d, 4),
            due_date=today + timedelta(days=interval),
            interval_days=interval,
            retrievability=1.0,
            review_count=1,
        )

    # Ensure sane defaults for legacy rows
    if stability < MIN_STABILITY:
        stability = _initial_stability(3)
    if difficulty < MIN_DIFFICULTY:
        difficulty = _initial_difficulty(3)

    r_at_review = retrievability(elapsed, stability)
    new_d = _next_difficulty(difficulty, fsrs_rating)

    if fsrs_rating == 1:
        new_s = _stability_after_failure(stability, new_d)
        new_s = _stability_short_term(new_s)
        interval = 1
    else:
        new_s = _stability_after_success(stability, new_d, r_at_review, fsrs_rating)
        interval = next_interval_days(new_s, target_retention)

    return FSRSState(
        stability=round(max(new_s, MIN_STABILITY), 4),
        difficulty=round(new_d, 4),
        due_date=today + timedelta(days=interval),
        interval_days=interval,
        retrievability=round(r_at_review, 4),
        review_count=review_count + 1,
    )


def preview_intervals(
    stability: float,
    difficulty: float,
    review_count: int,
    last_review: Optional[str],
) -> dict[str, int]:
    """Preview next interval (days) for each rating button."""
    previews = {}
    labels = ["again", "hard", "good", "easy"]
    for rating, label in enumerate(labels):
        state = review(stability, difficulty, review_count, last_review, rating)
        previews[label] = state.interval_days
    return previews
