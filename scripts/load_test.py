"""
Load Testing Script

Tests API performance under load using Locust.
Run with: locust -f scripts/load_test.py --host=http://localhost:8000
"""
from locust import HttpUser, task, between
import random
import json


class PerformanceFocusedUser(HttpUser):
    """Simulates a typical user session."""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between requests
    
    def on_start(self):
        """Login and get auth token."""
        # Register/login
        email = f"test_{random.randint(1000, 9999)}@example.com"
        password = "testpassword123"
        
        try:
            # Try to register
            response = self.client.post(
                "/v1/auth/register",
                json={
                    "email": email,
                    "password": password,
                    "display_name": "Test User"
                }
            )
            
            if response.status_code == 201:
                self.token = response.json()["access_token"]
            else:
                # Try login instead
                response = self.client.post(
                    "/v1/auth/login",
                    json={"email": email, "password": password}
                )
                if response.status_code == 200:
                    self.token = response.json()["access_token"]
                else:
                    self.token = None
        except Exception:
            self.token = None
        
        self.headers = {}
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"
    
    @task(3)
    def get_efficiency_trends(self):
        """Get efficiency trends (most common operation)."""
        if not self.token:
            return
        
        days = random.choice([30, 60, 90, 120])
        self.client.get(
            f"/v1/analytics/efficiency-trends?days={days}",
            headers=self.headers,
            name="/v1/analytics/efficiency-trends"
        )
    
    @task(2)
    def get_activities(self):
        """List activities."""
        if not self.token:
            return
        
        self.client.get(
            "/v1/activities?limit=20",
            headers=self.headers,
            name="/v1/activities"
        )
    
    @task(1)
    def get_correlations(self):
        """Get correlations (expensive operation)."""
        if not self.token:
            return
        
        days = random.choice([60, 90])
        endpoint = random.choice([
            "/v1/correlations/what-works",
            "/v1/correlations/what-doesnt-work"
        ])
        self.client.get(
            f"{endpoint}?days={days}",
            headers=self.headers,
            name=endpoint
        )
    
    @task(1)
    def get_activity_summary(self):
        """Get activity summary."""
        if not self.token:
            return
        
        days = random.choice([7, 30, 90])
        self.client.get(
            f"/v1/activities/summary?days={days}",
            headers=self.headers,
            name="/v1/activities/summary"
        )
    
    @task(1)
    def health_check(self):
        """Health check (no auth required)."""
        self.client.get("/health", name="/health")


# Performance targets (documented for reference)
PERFORMANCE_TARGETS = {
    "dashboard_load": {
        "endpoint": "/v1/analytics/efficiency-trends",
        "target_ms": 500,
        "concurrent_users": 1000,
        "description": "Dashboard should load in <500ms at 1k concurrent users"
    },
    "correlation_job": {
        "endpoint": "/v1/correlations/discover",
        "target_ms": 5000,
        "concurrent_users": 10,
        "description": "Correlation job should complete in <5s for 90-day dataset"
    },
    "activity_list": {
        "endpoint": "/v1/activities",
        "target_ms": 200,
        "concurrent_users": 100,
        "description": "Activity list should load in <200ms at 100 concurrent users"
    },
    "cached_endpoints": {
        "endpoint": "Cached endpoints (efficiency-trends, correlations)",
        "target_ms": 100,
        "concurrent_users": 1000,
        "description": "Cached endpoints should respond in <100ms"
    }
}


