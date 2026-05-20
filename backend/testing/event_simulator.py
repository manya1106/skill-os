# backend/testing/event_simulator.py
import random
from datetime import datetime, timedelta
from typing import List, Dict
import json
from learner_personas import get_persona
from config import TestConfig

class EventSimulator:
    """Simulate realistic user behavior events"""
    
    def __init__(self, user_id: str, user_data: Dict):
        self.user_id = user_id
        self.user_data = user_data
        self.persona = get_persona(user_data.get("persona", "casual_learner"))
        self.config = TestConfig()
        self.events = []
    
    def simulate_days(self, num_days: int) -> List[Dict]:
        """Simulate user activity over N days"""
        events = []
        current_date = self.config.START_DATE
        
        for day in range(num_days):
            current_date = self.config.START_DATE + timedelta(days=day)
            
            # Skip day based on persona probability
            if not self.persona.get_daily_probability():
                continue
            
            # Simulate activities for this day
            num_sessions = random.randint(1, 3)
            for session in range(num_sessions):
                session_start = self._random_time_of_day(current_date)
                
                # Watch video
                if random.random() < 0.7:
                    events.append(self._create_watch_event(session_start))
                
                # Rewatch if persona does that
                if self.persona.should_rewatch():
                    events.append(self._create_watch_event(session_start, rewatch=True))
                
                # Flashcard review
                if random.random() < self.persona.flashcard_consistency:
                    events.append(self._create_flashcard_event(session_start))
                
                # Quiz
                if random.random() < 0.4:
                    events.append(self._create_quiz_event(session_start))
        
        self.events = events
        return events
    
    def _random_time_of_day(self, date: datetime) -> datetime:
        """Random time between 9am-11pm"""
        hour = random.randint(9, 23)
        minute = random.randint(0, 59)
        return date.replace(hour=hour, minute=minute, second=0)
    
    def _create_watch_event(self, timestamp: datetime, rewatch: bool = False) -> Dict:
        """Create a video watch event"""
        duration = random.randint(300, 3600)  # 5min - 1hr
        watch_pct = random.randint(30, 100) if not rewatch else random.randint(50, 100)
        
        return {
            "user_id": self.user_id,
            "event_type": "rewatch" if rewatch else "watch",
            "resource_id": f"resource_{random.randint(1, 100)}",
            "platform": self.user_data.get("preferred_platform", "YouTube"),
            "duration_seconds": duration,
            "watch_percentage": watch_pct,
            "timestamp": timestamp.isoformat()
        }
    
    def _create_flashcard_event(self, timestamp: datetime) -> Dict:
        """Create a flashcard review event"""
        # Rating: 0=Again, 1=Hard, 2=Good, 3=Easy
        # Personas have different success rates
        rating = 3 if random.random() < self.persona.quiz_success_rate else random.randint(0, 2)
        
        return {
            "user_id": self.user_id,
            "event_type": "flashcard_review",
            "card_id": f"card_{random.randint(1, 500)}",
            "rating": rating,
            "timestamp": timestamp.isoformat()
        }
    
    def _create_quiz_event(self, timestamp: datetime) -> Dict:
        """Create a quiz attempt event"""
        passed = random.random() < self.persona.quiz_success_rate
        score = random.randint(70, 100) if passed else random.randint(20, 65)
        
        return {
            "user_id": self.user_id,
            "event_type": "quiz",
            "resource_id": f"resource_{random.randint(1, 100)}",
            "passed": passed,
            "score": score,
            "timestamp": timestamp.isoformat()
        }
    
    def export_to_json(self, filename: str):
        """Export events to JSON file"""
        with open(filename, 'w') as f:
            json.dump(self.events, f, indent=2)

# Usage
if __name__ == "__main__":
    test_user = {
        "id": "user_123",
        "name": "Test User",
        "persona": "consistent_learner"
    }
    
    sim = EventSimulator("user_123", test_user)
    events = sim.simulate_days(30)
    
    print(f"Generated {len(events)} events")
    print("\nSample events:")
    for event in events[:3]:
        print(json.dumps(event, indent=2))