# backend/testing/learner_personas.py
from dataclasses import dataclass
from typing import List
from datetime import datetime, timedelta
import random

@dataclass
class LearnerPersona:
    """Base learner persona with behavior patterns"""
    name: str
    daily_activity_probability: float  # 0-1: chance to be active each day
    study_hours_per_session: tuple      # (min, max)
    completion_rate: float              # % of courses completed
    rewatch_frequency: float            # How often they rewatch
    flashcard_consistency: float        # How consistently they review flashcards
    quiz_success_rate: float            # How often they pass quizzes
    dropout_probability: float          # Chance to abandon a resource
    
    def get_daily_probability(self) -> bool:
        """Decide if user is active today"""
        return random.random() < self.daily_activity_probability
    
    def get_session_duration(self) -> int:
        """Get study duration in minutes"""
        return random.randint(*self.study_hours_per_session) * 60
    
    def should_rewatch(self) -> bool:
        return random.random() < self.rewatch_frequency
    
    def should_dropout(self) -> bool:
        return random.random() < self.dropout_probability

# Define persona types
PERSONAS = {
    "consistent_learner": LearnerPersona(
        name="Consistent Learner",
        daily_activity_probability=0.85,      # Active 85% of days
        study_hours_per_session=(1, 3),       # 1-3 hours per session
        completion_rate=0.90,                 # Completes 90% of courses
        rewatch_frequency=0.05,               # Rarely rewatches
        flashcard_consistency=0.95,           # Very consistent with flashcards
        quiz_success_rate=0.85,               # Good at quizzes
        dropout_probability=0.05              # Rarely drops out
    ),
    
    "struggling_learner": LearnerPersona(
        name="Struggling Learner",
        daily_activity_probability=0.50,
        study_hours_per_session=(0.5, 2),
        completion_rate=0.40,
        rewatch_frequency=0.50,               # Rewatches often
        flashcard_consistency=0.30,           # Inconsistent
        quiz_success_rate=0.40,               # Struggles with quizzes
        dropout_probability=0.40              # Often drops out
    ),
    
    "binge_learner": LearnerPersona(
        name="Binge Learner",
        daily_activity_probability=0.20,      # Not active often
        study_hours_per_session=(4, 8),       # But long sessions
        completion_rate=0.70,
        rewatch_frequency=0.15,
        flashcard_consistency=0.10,           # Rarely does spaced rep
        quiz_success_rate=0.75,
        dropout_probability=0.25
    ),
    
    "casual_learner": LearnerPersona(
        name="Casual Learner",
        daily_activity_probability=0.35,
        study_hours_per_session=(0.5, 1.5),
        completion_rate=0.50,
        rewatch_frequency=0.20,
        flashcard_consistency=0.25,
        quiz_success_rate=0.60,
        dropout_probability=0.35
    ),
    
    "perfectionist_learner": LearnerPersona(
        name="Perfectionist Learner",
        daily_activity_probability=0.80,
        study_hours_per_session=(2, 4),
        completion_rate=0.95,
        rewatch_frequency=0.40,               # Rewatches to perfect understanding
        flashcard_consistency=0.99,           # Never misses spaced rep
        quiz_success_rate=0.95,
        dropout_probability=0.02
    ),
    
    "procrastinator": LearnerPersona(
        name="Procrastinator",
        daily_activity_probability=0.10,
        study_hours_per_session=(1, 2),
        completion_rate=0.25,
        rewatch_frequency=0.30,
        flashcard_consistency=0.05,
        quiz_success_rate=0.50,
        dropout_probability=0.70                # Very likely to drop out
    ),
}

def get_persona(persona_name: str) -> LearnerPersona:
    return PERSONAS.get(persona_name, PERSONAS["casual_learner"])