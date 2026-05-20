# backend/testing/test_runner.py
"""
Orchestrate test data generation for existing users.
Uses users created via the registration flow, no need to create them again.
"""

import sys
import time
from datetime import datetime
from .supabase_seeder import SupabaseSeeder
from .config import TestConfig

class TestRunner:
    """Orchestrate the entire test data generation pipeline"""
    
    def __init__(self):
        self.config = TestConfig()
        self.seeder = SupabaseSeeder()
        self.start_time = None
        self.metrics = {
            "users_found": 0,
            "resources_created": 0,
            "interactions_created": 0,
            "activity_logs_created": 0,
            "decks_created": 0,
            "errors": 0,
        }
    
    def run_full_test(self, num_users: int = 50, num_days: int = 30):
        """Generate test data for existing users"""
        self.start_time = datetime.now()
        
        print("=" * 60)
        print("🚀 SkillOS Test Data Generator")
        print("=" * 60)
        print(f"📊 Configuration:")
        print(f"   Target users: {num_users}")
        print(f"   Days to simulate: {num_days}")
        print(f"   Start date: {self.config.START_DATE.date()}")
        print(f"   End date: {self.config.END_DATE.date()}")
        print("=" * 60)
        
        try:
            # Step 1: Fetch existing users
            print("\n[1/5] Fetching existing users…")
            users = self.seeder.fetch_existing_users(limit=num_users)
            self.metrics["users_found"] = len(users)
            
            if not users:
                print("\n❌ No users found!")
                print("   → First, create users via the registration page:")
                print("   → http://localhost:5173/register")
                return
            
            # Step 2: Assign personas
            print("\n[2/5] Assigning learning personas…")
            user_personas = self.seeder.assign_personas_to_users(users)
            
            # Step 3: Create resources
            print("\n[3/5] Generating learning resources…")
            self.seeder.seed_resources(users, resources_per_user=5)
            
            # Step 4: Simulate interactions
            print("\n[4/5] Simulating user interactions…")
            self.seeder.seed_interactions(user_personas, days=num_days)
            self.seeder.seed_activity_log(user_personas, days=num_days)
            
            # Step 5: Create flashcards & goals
            print("\n[5/5] Creating flashcards and learning goals…")
            self.seeder.seed_flashcards(users, decks_per_user=2, cards_per_deck=8)
            self.seeder.seed_learning_goals(users)
            
            # Print summary
            self._print_summary()
            
        except Exception as e:
            print(f"\n❌ Test generation failed: {e}")
            self.metrics["errors"] += 1
            raise
    
    def _print_summary(self):
        """Print test execution summary"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        print("\n" + "=" * 60)
        print("✅ TEST DATA GENERATION SUMMARY")
        print("=" * 60)
        print(f"Users found:          {self.metrics['users_found']}")
        print(f"Time elapsed:         {elapsed:.2f}s")
        print(f"Errors:               {self.metrics['errors']}")
        print("=" * 60)
        print("\n🎉 Ready for testing!")
        print("   → Open http://localhost:5173 in your browser")
        print("   → Log in with any registered user account")
        print("   → Check the Dashboard to see generated data")
        print("=" * 60 + "\n")

if __name__ == "__main__":
    runner = TestRunner()
    
    # Parse command line args
    num_users = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    num_days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    
    print("\n✓ Make sure you have registered users first!")
    print("  If you haven't, sign up at: http://localhost:5173/register\n")
    
    runner.run_full_test(num_users=num_users, num_days=num_days)