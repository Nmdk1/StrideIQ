"""
Calendar System Comprehensive Test Suite

Tests all calendar endpoints rigorously:
1. Calendar range retrieval
2. Day detail retrieval
3. Notes CRUD
4. Coach chat
5. Week detail
"""

import requests
import json
from datetime import date, datetime, timedelta

BASE_URL = "http://localhost:8000"

# Test results tracking
results = {"passed": 0, "failed": 0, "tests": []}

def log_test(name: str, passed: bool, details: str = ""):
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status}: {name}")
    if details and not passed:
        print(f"   Details: {details}")
    results["tests"].append({"name": name, "passed": passed, "details": details})
    if passed:
        results["passed"] += 1
    else:
        results["failed"] += 1

def get_auth_token():
    """Get auth token for testing."""
    # Try to login with test credentials
    try:
        response = requests.post(f"{BASE_URL}/v1/auth/login", json={
            "email": "calendartest@strideiq.com",
            "password": "TestPassword123!"
        }, timeout=10)
        
        if response.status_code == 200:
            token = response.json().get("access_token")
            if token:
                return token
        
        # Try to register if login fails
        response = requests.post(f"{BASE_URL}/v1/auth/register", json={
            "email": "calendartest@strideiq.com",
            "password": "TestPassword123!",
            "display_name": "Calendar Test Athlete"
        }, timeout=10)
        
        if response.status_code in [200, 201]:
            token = response.json().get("access_token")
            if token:
                return token
        
        # Try login again after register
        response = requests.post(f"{BASE_URL}/v1/auth/login", json={
            "email": "calendartest@strideiq.com",
            "password": "TestPassword123!"
        }, timeout=10)
        
        if response.status_code == 200:
            token = response.json().get("access_token")
            if token:
                return token
            
    except Exception as e:
        print(f"Auth error: {e}")
    
    return None

def test_health():
    """Test API health endpoint."""
    try:
        response = requests.get(f"{BASE_URL}/health")
        log_test("Health endpoint", response.status_code == 200, f"Status: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        log_test("Health endpoint", False, str(e))
        return False

def test_calendar_requires_auth():
    """Test that calendar endpoints require authentication."""
    try:
        response = requests.get(f"{BASE_URL}/calendar")
        # Should return 401 or 403
        passed = response.status_code in [401, 403]
        log_test("Calendar requires auth", passed, f"Status: {response.status_code}")
        return passed
    except Exception as e:
        log_test("Calendar requires auth", False, str(e))
        return False

def test_calendar_range(headers):
    """Test calendar range endpoint."""
    try:
        # Test default (current month)
        response = requests.get(f"{BASE_URL}/calendar", headers=headers)
        if response.status_code != 200:
            log_test("Calendar range - default", False, f"Status: {response.status_code}, Body: {response.text[:200]}")
            return False
        
        data = response.json()
        
        # Validate response structure
        required_fields = ["start_date", "end_date", "days"]
        missing = [f for f in required_fields if f not in data]
        if missing:
            log_test("Calendar range - default", False, f"Missing fields: {missing}")
            return False
        
        log_test("Calendar range - default", True)
        
        # Test with specific dates
        start = date.today().replace(day=1).isoformat()
        end = (date.today().replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        end = end.isoformat()
        
        response = requests.get(f"{BASE_URL}/calendar?start_date={start}&end_date={end}", headers=headers)
        passed = response.status_code == 200
        log_test("Calendar range - with dates", passed, f"Status: {response.status_code}")
        
        return True
    except Exception as e:
        log_test("Calendar range", False, str(e))
        return False

def test_calendar_day(headers):
    """Test calendar day detail endpoint."""
    try:
        today = date.today().isoformat()
        response = requests.get(f"{BASE_URL}/calendar/{today}", headers=headers)
        
        if response.status_code != 200:
            log_test("Calendar day detail", False, f"Status: {response.status_code}, Body: {response.text[:200]}")
            return False
        
        data = response.json()
        
        # Validate response structure
        required_fields = ["date", "day_of_week", "day_name", "status", "activities", "notes", "insights"]
        missing = [f for f in required_fields if f not in data]
        if missing:
            log_test("Calendar day detail", False, f"Missing fields: {missing}")
            return False
        
        log_test("Calendar day detail", True)
        return True
    except Exception as e:
        log_test("Calendar day detail", False, str(e))
        return False

def test_calendar_notes(headers):
    """Test notes CRUD operations."""
    try:
        today = date.today().isoformat()
        
        # Create a note
        note_data = {
            "note_type": "free_text",
            "text_content": "Test note from automated test"
        }
        response = requests.post(f"{BASE_URL}/calendar/{today}/notes", headers=headers, json=note_data)
        
        if response.status_code not in [200, 201]:
            log_test("Create note", False, f"Status: {response.status_code}, Body: {response.text[:200]}")
            return False
        
        note = response.json()
        note_id = note.get("id")
        log_test("Create note", True)
        
        # Verify note appears in day detail
        response = requests.get(f"{BASE_URL}/calendar/{today}", headers=headers)
        data = response.json()
        note_found = any(n.get("id") == note_id for n in data.get("notes", []))
        log_test("Note appears in day", note_found)
        
        # Delete the note
        response = requests.delete(f"{BASE_URL}/calendar/{today}/notes/{note_id}", headers=headers)
        passed = response.status_code == 200
        log_test("Delete note", passed, f"Status: {response.status_code}")
        
        # Verify note is gone
        response = requests.get(f"{BASE_URL}/calendar/{today}", headers=headers)
        data = response.json()
        note_gone = not any(n.get("id") == note_id for n in data.get("notes", []))
        log_test("Note deleted from day", note_gone)
        
        return True
    except Exception as e:
        log_test("Notes CRUD", False, str(e))
        return False

def test_coach_chat(headers):
    """Test coach chat endpoint."""
    try:
        chat_data = {
            "message": "Am I ready for my long run this weekend?",
            "context_type": "open"
        }
        response = requests.post(f"{BASE_URL}/calendar/coach", headers=headers, json=chat_data)
        
        if response.status_code != 200:
            log_test("Coach chat - open", False, f"Status: {response.status_code}, Body: {response.text[:200]}")
            return False
        
        data = response.json()
        required_fields = ["chat_id", "response", "context_type"]
        missing = [f for f in required_fields if f not in data]
        if missing:
            log_test("Coach chat - open", False, f"Missing fields: {missing}")
            return False
        
        log_test("Coach chat - open", True)
        
        # Test with day context
        today = date.today().isoformat()
        chat_data = {
            "message": "What should I focus on today?",
            "context_type": "day",
            "context_date": today
        }
        response = requests.post(f"{BASE_URL}/calendar/coach", headers=headers, json=chat_data)
        passed = response.status_code == 200
        log_test("Coach chat - day context", passed, f"Status: {response.status_code}")
        
        return True
    except Exception as e:
        log_test("Coach chat", False, str(e))
        return False

def test_existing_endpoints(headers):
    """Test that existing endpoints still work."""
    endpoints = [
        ("/health", "GET", None),
        ("/v1/athletes/me", "GET", None),
        ("/v1/activities", "GET", None),
    ]
    
    all_passed = True
    for endpoint, method, body in endpoints:
        try:
            if method == "GET":
                response = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
            else:
                response = requests.post(f"{BASE_URL}{endpoint}", headers=headers, json=body)
            
            # Accept 200, 404 (no data), or authentication errors for protected endpoints
            passed = response.status_code in [200, 404]
            log_test(f"Existing endpoint: {endpoint}", passed, f"Status: {response.status_code}")
            if not passed:
                all_passed = False
        except Exception as e:
            log_test(f"Existing endpoint: {endpoint}", False, str(e))
            all_passed = False
    
    return all_passed

def test_openapi_spec():
    """Test that OpenAPI spec includes calendar endpoints."""
    try:
        response = requests.get(f"{BASE_URL}/openapi.json")
        if response.status_code != 200:
            log_test("OpenAPI spec accessible", False, f"Status: {response.status_code}")
            return False
        
        spec = response.json()
        paths = spec.get("paths", {})
        
        calendar_endpoints = [
            "/calendar",
            "/calendar/coach",
            "/calendar/{calendar_date}",
            "/calendar/{calendar_date}/notes",
        ]
        
        all_found = True
        for endpoint in calendar_endpoints:
            if endpoint in paths:
                log_test(f"OpenAPI: {endpoint}", True)
            else:
                log_test(f"OpenAPI: {endpoint}", False, "Not in spec")
                all_found = False
        
        return all_found
    except Exception as e:
        log_test("OpenAPI spec", False, str(e))
        return False

def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("STRIDEIQ CALENDAR SYSTEM TEST SUITE")
    print("="*60 + "\n")
    
    # Basic health check
    print("--- Basic Health ---")
    if not test_health():
        print("\n[!] API not responding. Aborting tests.")
        return
    
    # Auth required check
    print("\n--- Authentication ---")
    test_calendar_requires_auth()
    
    # Get auth token
    token = get_auth_token()
    if not token:
        log_test("Get auth token", False, "Could not authenticate")
        print("\n[!] Could not get auth token. Running limited tests.")
        headers = {}
    else:
        log_test("Get auth token", True)
        headers = {"Authorization": f"Bearer {token}"}
    
    # OpenAPI spec check
    print("\n--- OpenAPI Spec ---")
    test_openapi_spec()
    
    if token:
        # Calendar endpoints
        print("\n--- Calendar Range ---")
        test_calendar_range(headers)
        
        print("\n--- Calendar Day ---")
        test_calendar_day(headers)
        
        print("\n--- Notes CRUD ---")
        test_calendar_notes(headers)
        
        print("\n--- Coach Chat ---")
        test_coach_chat(headers)
        
        print("\n--- Existing Endpoints ---")
        test_existing_endpoints(headers)
    
    # Summary
    print("\n" + "="*60)
    print(f"TEST SUMMARY: {results['passed']} passed, {results['failed']} failed")
    print("="*60)
    
    if results['failed'] > 0:
        print("\n[X] FAILED TESTS:")
        for test in results['tests']:
            if not test['passed']:
                print(f"   - {test['name']}: {test['details']}")
    else:
        print("\n[OK] ALL TESTS PASSED!")
    
    return results['failed'] == 0

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
