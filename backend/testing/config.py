# backend/testing/config.py
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
import dotenv


dotenv.load_dotenv()

class TestConfig:
    """Configuration for mock user testing system"""
    
    # Supabase
    SUPABASE_URL = os.getenv("SUPABASE_URL", "http://localhost:54321")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJ...")
    
    # Backend API
    BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
    
    # Frontend
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
    
    # Test Parameters
    NUM_USERS = 50  # Start small, scale up
    NUM_DAYS = 30   # Simulate 30 days of activity
    
    # Learning Platforms
    PLATFORMS = ["YouTube", "Udemy", "Coursera", "freeCodeCamp", "Medium"]
    
    # Learning Tags
    LEARNING_TAGS = [
        "Python", "JavaScript", "React", "Web Development",
        "Data Science", "Machine Learning", "Statistics",
        "SQL", "APIs", "DevOps", "Cloud Computing",
        "UI/UX Design", "Mobile Development", "AI"
    ]
    
    # Learning Goals
    LEARNING_GOALS = [
        "Web Development",
        "Data Science",
        "Machine Learning",
        "Career Switch",
        "Skill Enhancement"
    ]
    
    # Learner personas distribution
    PERSONA_DISTRIBUTION = {
        "consistent_learner": 0.30,      # 30% of users
        "struggling_learner": 0.20,      # 20%
        "binge_learner": 0.15,           # 15%
        "casual_learner": 0.20,          # 20%
        "perfectionist_learner": 0.10,   # 10%
        "procrastinator": 0.05            # 5%
    }
    
    # Date range for simulation
    START_DATE = datetime.now() - timedelta(days=NUM_DAYS)
    END_DATE = datetime.now()

class AnalyticsConfig:
    """Config for monitoring test execution"""
    METRICS_INTERVAL = 5  # Update metrics every 5 seconds
    LOG_LEVEL = "INFO"