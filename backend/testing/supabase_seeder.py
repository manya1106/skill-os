# backend/testing/supabase_seeder.py
from itertools import count
from urllib import response

from supabase import create_client, Client
from config import TestConfig
from fake_users import FakeUserGenerator
from event_simulator import EventSimulator
import requests
import json
from typing import List, Dict
import time
import random

class SupabaseSeeder:
    """Seed Supabase with fake users and events"""
    
    def __init__(self):
        self.config = TestConfig()
        self.supabase: Client = create_client(
            self.config.SUPABASE_URL,
            self.config.SUPABASE_KEY
        )
        self.created_user_ids = []
        self.backend_url = self.config.BACKEND_URL
    
    def seed_users(self, count: int) -> List[Dict]:
        """Create fake users via backend registration"""
        print(f"\n📝 Creating {count} fake users...")
        
        gen = FakeUserGenerator()
        fake_users = gen.generate_with_personas(count)
        
        for i, user_data in enumerate(fake_users):
            try:
                response = requests.post(
                    f"{self.backend_url}/auth/register",
                    json={
                        "name": user_data["name"],
                        "email": user_data["email"],
                        "password": user_data["password"],
                    }
                )
                
                if response.status_code == 200:
                    self.created_user_ids.append(response.json())

                    user_id = response.json().get("user_id")
                    self._store_user_metadata(user_id, user_data)

                    if (i + 1) % 10 == 0:
                        print(f"  ✓ {i + 1}/{count} users created")

                else:   
                    print(f"  ✗ Registration failed: {response.status_code}")
                    print(response.text)
                
                # Rate limit: 100ms between requests
                time.sleep(0.1)
                
            except Exception as e:
                print(f"  ✗ Error creating user: {e}")
        
        print(f"\n✅ Successfully created {len(self.created_user_ids)} users")
        return self.created_user_ids
    
    def _store_user_metadata(self, user_id: str, user_data: Dict):
        """Store persona and preferences in a metadata table"""
        try:
            self.supabase.table("user_metadata").insert({
                "user_id": user_id,
                "persona": user_data.get("persona"),
                "interested_tags": user_data.get("interested_tags", []),
                "daily_study_hours": user_data.get("daily_study_hours"),
                "preferred_platform": user_data.get("preferred_platform"),
                "created_at": "now()"
            }).execute()
        except Exception as e:
            print(f"Could not store metadata: {e}")
    
    def seed_activities(self, user_ids: List[str], days: int = 30):
        """Simulate and store user activities"""
        print(f"\n🎮 Generating {len(user_ids)} users × {days} days of activity...")
        
        for i, user_id in enumerate(user_ids):
            try:
                # Get user metadata
                user_data = self._get_user_metadata(user_id)
                
                # Simulate events
                sim = EventSimulator(user_id, user_data)
                events = sim.simulate_days(days)
                
                # Store events in interactions table
                for event in events:
                    self.supabase.table("interactions").insert(event).execute()
                
                if (i + 1) % 5 == 0:
                    print(f"  ✓ Activities for {i + 1}/{len(user_ids)} users")
                
                time.sleep(0.05)
                
            except Exception as e:
                print(f"  ✗ Error for user {user_id}: {e}")
        
        print(f"\n✅ Activity simulation complete!")
    
    def _get_user_metadata(self, user_id: str) -> Dict:
        """Retrieve stored user metadata"""
        try:
            result = self.supabase.table("user_metadata").select("*").eq(
                "user_id", user_id
            ).single().execute()
            return result.data if result.data else {"persona": "casual_learner"}
        except:
            return {"persona": "casual_learner"}
    
    def seed_resources(self, count: int = 100):
        """Create sample learning resources"""
        print(f"\n📚 Creating {count} sample resources...")
        
        from config import TestConfig
        config = TestConfig()
        
        for i in range(count):
            resource = {
                "user_id": self.created_user_ids[i % len(self.created_user_ids)],
                "platform": random.choice(config.PLATFORMS),
                "title": f"Course {i+1}: {' '.join(random.choices(config.LEARNING_TAGS, k=2))}",
                "progress": random.randint(0, 100),
                "status": random.choice(["not-started", "in-progress", "completed"]),
                "tags": random.sample(config.LEARNING_TAGS, k=3),
                "created_at": "now()"
            }
            
            try:
                self.supabase.table("resources").insert(resource).execute()
            except Exception as e:
                print(f"Error creating resource: {e}")
        
        print(f"✅ {count} resources created!")
    
    def clear_test_data(self):
        """Delete all test data (CAREFUL!)"""
        print("\n⚠️  WARNING: This will delete all test data!")
        confirm = input("Type 'YES' to confirm: ")
        
        if confirm == "YES":
            try:
                # Delete in order of foreign key dependencies
                self.supabase.table("interactions").delete().neq("user_id", "").execute()
                self.supabase.table("resources").delete().neq("user_id", "").execute()
                print("✅ Test data cleared!")
            except Exception as e:
                print(f"Error clearing data: {e}")

# Usage
if __name__ == "__main__":
    seeder = SupabaseSeeder()
    
    # Create 50 fake users
    seeder.seed_users(50)
    
    # Simulate 30 days of activity
    seeder.seed_activities(seeder.created_user_ids, days=30)
    
    # Create sample resources
    seeder.seed_resources(100)