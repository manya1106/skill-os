# load-tests/locustfile.py
from locust import HttpUser, task, between, events
from datetime import datetime
import json
import time

class SkillOSUser(HttpUser):
    """Simulates a typical SkillOS user"""
    
    wait_time = between(1, 5)  # Wait 1-5 seconds between tasks
    
    def on_start(self):
        """Run once when user starts"""
        # Try to log in
        response = self.client.post("/auth/login", data={
            "username": f"test{self.client_id}@example.com",
            "password": "TestPassword123!"
        })
        
        if response.status_code == 200:
            token = response.json()["access_token"]
            self.client.headers.update({"Authorization": f"Bearer {token}"})
    
    @task(5)  # Weight: 5
    def view_dashboard(self):
        """View main dashboard"""
        self.client.get("/users/me")
    
    @task(3)  # Weight: 3
    def list_resources(self):
        """View resources"""
        self.client.get("/resources")
    
    @task(2)
    def view_analytics(self):
        """View analytics"""
        self.client.get("/analytics/weekly")
        self.client.get("/analytics/platform-radar")
    
    @task(1)
    def view_recommendations(self):
        """Get AI recommendations"""
        self.client.get("/recommendations")
    
    @task(2)
    def view_decks(self):
        """View flashcard decks"""
        self.client.get("/decks")
    
    @task(1)
    def find_buddies(self):
        """Find study buddies"""
        self.client.get("/buddies/matches")

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Print test start info"""
    print("\n" + "="*60)
    print("🔥 LOCUST LOAD TEST STARTED")
    print("="*60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print test summary"""
    print("\n" + "="*60)
    print("✅ LOAD TEST COMPLETE")
    print("="*60)
    print(environment.stats)