# backend/testing/fake_users.py
from faker import Faker
from typing import List, Dict
import random
from .config import TestConfig

fake = Faker()

class FakeUserGenerator:
    """Generate realistic fake users"""
    
    def __init__(self):
        self.config = TestConfig()
        self.created_users = []
    
    def generate_user(self) -> Dict:
        """Generate a single fake user"""
        return {
            "name": fake.name(),
            "email": fake.unique.email(),
            "password": "TestPassword123!",  # Same for all (testing only)
            "learning_goal": random.choice(self.config.LEARNING_GOALS),
            "interested_tags": random.sample(self.config.LEARNING_TAGS, k=random.randint(2, 5)),
            "daily_study_hours": random.randint(1, 6),
            "preferred_platform": random.choice(self.config.PLATFORMS),
            "timezone": fake.timezone(),
        }
    
    def generate_batch(self, count: int) -> List[Dict]:
        """Generate multiple users"""
        return [self.generate_user() for _ in range(count)]
    
    def generate_with_personas(self, count: int) -> List[Dict]:
        """Generate users with assigned personas"""
        users = self.generate_batch(count)
        personas = self.config.PERSONA_DISTRIBUTION
        
        persona_list = []
        for persona, pct in personas.items():
            num = int(count * pct)
            persona_list.extend([persona] * num)
        
        # Shuffle and assign
        random.shuffle(persona_list)
        
        for i, user in enumerate(users):
            user["persona"] = persona_list[i] if i < len(persona_list) else "casual_learner"
        
        return users

# Usage
if __name__ == "__main__":
    gen = FakeUserGenerator()
    
    # Generate 50 users with personas
    users = gen.generate_with_personas(50)
    
    for user in users[:3]:
        print(f"Name: {user['name']}")
        print(f"Email: {user['email']}")
        print(f"Persona: {user['persona']}")
        print(f"Interested in: {', '.join(user['interested_tags'][:2])}")
        print("---")