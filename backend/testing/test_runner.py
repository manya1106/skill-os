# backend/testing/test_runner.py
import sys
import time
from datetime import datetime
from supabase_seeder import SupabaseSeeder
from config import TestConfig
import requests

class TestRunner:
    """Orchestrate the entire testing pipeline"""
    
    def __init__(self):
        self.config = TestConfig()
        self.seeder = SupabaseSeeder()
        self.start_time = None
        self.metrics = {
            "users_created": 0,
            "events_generated": 0,
            "api_calls": 0,
            "errors": 0,
        }
    
    def run_full_test(self, num_users: int = 50, num_days: int = 30):
        """Run complete test pipeline"""
        self.start_time = datetime.now()
        
        print("=" * 60)
        print("🚀 SkillOS Mock User Testing System")
        print("=" * 60)
        print(f"📊 Test Parameters:")
        print(f"   Users: {num_users}")
        print(f"   Days: {num_days}")
        print(f"   Start: {self.config.START_DATE.date()}")
        print(f"   End: {self.config.END_DATE.date()}")
        print("=" * 60)
        
        try:
            # Step 1: Create users
            print("\n[1/4] Creating fake users...")
            user_ids = self.seeder.seed_users(num_users)
            self.metrics["users_created"] = len(user_ids)
            
            # Step 2: Create resources
            print("\n[2/4] Creating sample resources...")
            self.seeder.seed_resources(count=min(100, num_users * 3))
            
            # Step 3: Generate activity
            print("\n[3/4] Generating user activities...")
            self.seeder.seed_activities(user_ids, days=num_days)
            
            # Step 4: Verify data
            print("\n[4/4] Verifying data integrity...")
            self._verify_data()
            
            # Print summary
            self._print_summary()
            
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            self.metrics["errors"] += 1
            raise
    
    def _verify_data(self):
        """Verify created data in database"""
        try:
            # Check users
            users = self.seeder.supabase.table("users").select("count").execute()
            print(f"  ✓ Users in DB: {len(users.data) if users.data else 0}")
            
            # Check resources
            resources = self.seeder.supabase.table("resources").select("count").execute()
            print(f"  ✓ Resources in DB: {len(resources.data) if resources.data else 0}")
            
            # Check interactions
            interactions = self.seeder.supabase.table("interactions").select("count").execute()
            print(f"  ✓ Events in DB: {len(interactions.data) if interactions.data else 0}")
            
        except Exception as e:
            print(f"  ⚠️  Verification warning: {e}")
    
    def _print_summary(self):
        """Print test execution summary"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        print("\n" + "=" * 60)
        print("✅ TEST EXECUTION SUMMARY")
        print("=" * 60)
        print(f"Users Created:     {self.metrics['users_created']}")
        print(f"Events Generated:  {self.metrics['events_generated']}")
        print(f"API Calls:         {self.metrics['api_calls']}")
        print(f"Errors:            {self.metrics['errors']}")
        print(f"Time Elapsed:      {elapsed:.2f}s")
        print(f"Users/Second:      {self.metrics['users_created']/elapsed:.2f}")
        print("=" * 60)
        print("\n🎉 Ready for testing! Check your dashboard at:")
        print(f"   {self.config.FRONTEND_URL}")
        print("=" * 60 + "\n")

if __name__ == "__main__":
    runner = TestRunner()
    
    # Parse command line args
    num_users = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    num_days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    
    runner.run_full_test(num_users=num_users, num_days=num_days)