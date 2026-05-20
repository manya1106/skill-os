# backend/testing/supabase_seeder.py
"""
Seed Supabase with realistic test data for existing users.
This focuses on generating resources, interactions, and activity logs
without trying to create users (users are created via registration).
"""

from supabase import create_client, Client
from testing.config import TestConfig
from testing.event_simulator import EventSimulator
from testing.learner_personas import get_persona
import time
from datetime import datetime, timedelta
import random

class SupabaseSeeder:
    """Generate realistic test data for existing users"""
    
    def __init__(self):
        self.config = TestConfig()
        self.supabase: Client = create_client(
            self.config.SUPABASE_URL,
            self.config.SUPABASE_KEY
        )
        self.user_ids = []
    
    def fetch_existing_users(self, limit: int = 50) -> list:
        """Fetch existing users from Supabase (created via registration)"""
        print(f"\n👥 Fetching existing users (max {limit})…")
        try:
            result = self.supabase.schema("public").table("users").select("id, name, level, xp").limit(limit).execute()
            self.user_ids = [u["id"] for u in (result.data or [])]
            print(f"✓ Found {len(self.user_ids)} users")
            return result.data or []
        except Exception as e:
            print(f"✗ Error fetching users: {e}")
            return []
    
    def assign_personas_to_users(self, users: list) -> dict:
        """Assign learning personas to existing users"""
        print(f"\n🎭 Assigning learning personas to {len(users)} users…")
        from testing.config import TestConfig
        config = TestConfig()
        
        user_personas = {}
        personas = config.PERSONA_DISTRIBUTION
        persona_list = []
        
        for persona, pct in personas.items():
            num = max(1, int(len(users) * pct))
            persona_list.extend([persona] * num)
        
        random.shuffle(persona_list)
        
        for i, user in enumerate(users):
            persona = persona_list[i] if i < len(persona_list) else "casual_learner"
            user_personas[user["id"]] = {
                "persona": persona,
                "persona_obj": get_persona(persona)
            }
        
        print(f"✓ Personas assigned")
        return user_personas
    
    # def seed_resources(self, users: list, resources_per_user: int = 5):
    #     """Create sample learning resources for existing users"""
    #     print(f"\n📚 Creating {resources_per_user} resources per user…")
    #     from testing.config import TestConfig
    #     config = TestConfig()
        
    #     total_created = 0
    #     for user in users:
    #         for _ in range(resources_per_user):
    #             resource = {
    #                 "user_id": user["id"],
    #                 "platform": random.choice(config.PLATFORMS),
    #                 "title": f"{random.choice(config.LEARNING_TAGS)} — {random.choice(['Tutorial', 'Course', 'Guide', 'Masterclass'])}",
    #                 "progress": random.randint(0, 100),
    #                 "status": random.choice(["not-started", "in-progress", "completed"]),
    #                 "tags": random.sample(config.LEARNING_TAGS, k=min(3, len(config.LEARNING_TAGS))),
    #                 "duration": f"{random.randint(1, 50)}h" if random.random() > 0.3 else None,
    #                 "created_at": datetime.now().isoformat(),
    #             }
    #             try:
    #                 self.supabase.table("resources").insert(resource).execute()
    #                 total_created += 1
    #             except Exception as e:
    #                 print(f"  ⚠ Skipping resource: {e}")
        
    #     print(f"✓ Created {total_created} resources")
    
    # def seed_interactions(self, user_personas: dict, days: int = 30):
    #     """Simulate user interactions (watch events, quizzes, etc.)"""
    #     print(f"\n🎮 Generating {len(user_personas)} users × {days} days of interactions…")
        
    #     resources = self.supabase.table("resources").select("id, user_id").execute().data or []
    #     if not resources:
    #         print("  ⚠ No resources found, skipping interactions")
    #         return
        
    #     created = 0
    #     for i, (user_id, persona_data) in enumerate(user_personas.items()):
    #         persona_obj = persona_data["persona_obj"]
    #         user_resources = [r for r in resources if r["user_id"] == user_id]
            
    #         if not user_resources:
    #             continue
            
    #         current_date = self.config.START_DATE
    #         for day in range(days):
    #             current_date = self.config.START_DATE + timedelta(days=day)
                
    #             # Skip day based on persona activity probability
    #             if not persona_obj.get_daily_probability():
    #                 continue
                
    #             # Simulate 1-3 sessions per active day
    #             num_sessions = random.randint(1, 3)
    #             for _ in range(num_sessions):
    #                 # Random activity time
    #                 hour = random.randint(9, 23)
    #                 minute = random.randint(0, 59)
    #                 timestamp = current_date.replace(hour=hour, minute=minute, second=0)
                    
    #                 # Pick a random resource
    #                 resource = random.choice(user_resources)
                    
    #                 # Generate event
    #                 event_type = random.choice(["watch", "quiz", "progress"])
    #                 value = random.randint(10, 100) if event_type in ["watch", "progress"] else (1 if random.random() > 0.3 else 0)
                    
    #                 event = {
    #                     "user_id": user_id,
    #                     "resource_id": resource["id"],
    #                     "event_type": event_type,
    #                     "value": value,
    #                     "ts": timestamp.isoformat(),
    #                 }
                    
    #                 try:
    #                     self.supabase.table("interactions").insert(event).execute()
    #                     created += 1
    #                 except Exception:
    #                     pass  # Silently skip duplicates
            
    #         if (i + 1) % 5 == 0:
    #             print(f"  ✓ {i + 1}/{len(user_personas)} users")
        
    #     print(f"✓ Created {created} interactions")
    
    # def seed_activity_log(self, user_personas: dict, days: int = 30):
    #     """Create activity log entries (learning minutes per day)"""
    #     print(f"\n⏱ Generating activity logs…")
        
    #     created = 0
    #     for user_id, persona_data in user_personas.items():
    #         persona_obj = persona_data["persona_obj"]
    #         current_date = self.config.START_DATE
            
    #         for day in range(days):
    #             current_date = self.config.START_DATE + timedelta(days=day)
                
    #             # Only log on active days
    #             if not persona_obj.get_daily_probability():
    #                 continue
                
    #             # Minutes based on persona
    #             duration_hours = persona_obj.get_session_duration() / 60
    #             minutes = int(duration_hours * 60)
                
    #             if minutes > 0:
    #                 try:
    #                     self.supabase.table("activity_log").insert({
    #                         "user_id": user_id,
    #                         "date": current_date.date().isoformat(),
    #                         "minutes": minutes,
    #                     }).execute()
    #                     created += 1
    #                 except Exception:
    #                     pass  # Duplicate or conflict
        
    #     print(f"✓ Created {created} activity log entries")
    
    # def seed_flashcards(self, users: list, decks_per_user: int = 2, cards_per_deck: int = 10):
    #     """Create flashcard decks and cards for existing users"""
    #     print(f"\n🃏 Creating flashcard decks and cards…")
        
    #     from testing.config import TestConfig
    #     config = TestConfig()
        
    #     decks_created = 0
    #     cards_created = 0
        
    #     for user in users:
    #         for _ in range(decks_per_user):
    #             deck_data = {
    #                 "user_id": user["id"],
    #                 "title": f"{random.choice(config.LEARNING_TAGS)} Deck",
    #                 "color": random.choice(["indigo", "purple", "blue"]),
    #                 "created_at": datetime.now().isoformat(),
    #             }
                
    #             try:
    #                 deck_result = self.supabase.table("flashcard_decks").insert(deck_data).execute()
    #                 deck_id = deck_result.data[0]["id"]
    #                 decks_created += 1
                    
    #                 # Add cards to deck
    #                 for i in range(cards_per_deck):
    #                     card_data = {
    #                         "deck_id": deck_id,
    #                         "question": f"Question {i+1} about {random.choice(config.LEARNING_TAGS)}?",
    #                         "answer": f"Answer {i+1}: Key concept or definition here.",
    #                         "source": f"Lesson {random.randint(1, 10)}",
    #                         "due_date": (datetime.now() + timedelta(days=random.randint(-5, 14))).date().isoformat(),
    #                         "stability": random.uniform(0.5, 3.0),
    #                         "difficulty": random.uniform(0.1, 0.9),
    #                         "review_count": random.randint(0, 10),
    #                         "last_review": (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat() if random.random() > 0.4 else None,
    #                         "created_at": datetime.now().isoformat(),
    #                     }
                        
    #                     try:
    #                         self.supabase.table("flashcards").insert(card_data).execute()
    #                         cards_created += 1
    #                     except Exception:
    #                         pass
                
    #             except Exception as e:
    #                 print(f"  ⚠ Error creating deck: {e}")
        
    #     print(f"✓ Created {decks_created} decks and {cards_created} cards")
    
    def seed_learning_goals(self, users: list):
        """Create sample learning goals for users"""
        print(f"\n🎯 Creating learning goals…")
        
        from testing.config import TestConfig
        config = TestConfig()
        
        created = 0
        for user in users:
            if random.random() > 0.6:  # 40% of users have goals
                goal_category = random.choice(config.LEARNING_GOALS)
                goal_data = {
                    "user_id": user["id"],
                    "title": f"Master {goal_category}",
                    "description": f"Complete a comprehensive learning path in {goal_category}.",
                    "category": goal_category,
                    "target_level": random.randint(1, 4),
                    "deadline": (datetime.now() + timedelta(days=random.randint(60, 180))).isoformat(),
                    "status": "active",
                    "created_at": datetime.now().isoformat(),
                }
                
                try:
                    print(user)
                    self.supabase.table("learning_goals").insert(goal_data).execute()
                    created += 1
                except Exception as e:
                    print(f"Error creating goal for user {user['id']}: {e}")
        
        print(f"✓ Created {created} learning goals")
    
    def clear_test_data(self, user_id: str):
        """Delete all test data for a specific user (careful!)"""
        print(f"\n⚠️  Clearing data for user {user_id}…")
        try:
            # Delete in order of foreign key dependencies
            self.supabase.table("interactions").delete().eq("user_id", user_id).execute()
            self.supabase.table("activity_log").delete().eq("user_id", user_id).execute()
            self.supabase.table("resources").delete().eq("user_id", user_id).execute()
            self.supabase.table("flashcard_decks").delete().eq("user_id", user_id).execute()
            self.supabase.table("learning_goals").delete().eq("user_id", user_id).execute()
            print(f"✓ Data cleared for user {user_id}")
        except Exception as e:
            print(f"Error clearing data for user {user_id}: {e}")

# Usage
if __name__ == "__main__":
    seeder = SupabaseSeeder()
    
    # Fetch existing users
    users = seeder.fetch_existing_users(limit=50)
    
    if not users:
        print("\n❌ No users found. Please create users via registration first.")
        exit(1)
    
    # Assign personas to users
    user_personas = seeder.assign_personas_to_users(users)
    
    # Generate test data
    # seeder.seed_resources(users, resources_per_user=5)
    # seeder.seed_interactions(user_personas, days=30)
    # seeder.seed_activity_log(user_personas, days=30)
    # seeder.seed_flashcards(users, decks_per_user=2, cards_per_deck=8)
    seeder.seed_learning_goals(users)
    
    print("\n" + "="*60)
    print("✅ TEST DATA SEEDING COMPLETE")
    print("="*60)
    print(f"Users:        {len(users)}")
    print(f"Ready for testing!")
    print("="*60 + "\n")