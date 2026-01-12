"""Test calendar API to verify plan workouts appear."""
import requests
import json

# Login
login_resp = requests.post('http://localhost:8000/v1/auth/login', json={
    'email': 'mbshaf@gmail.com',
    'password': 'StrideIQ2026!'
})
token = login_resp.json().get('access_token')
print(f'Login: {login_resp.status_code}')

# Get calendar data for January 2026
headers = {'Authorization': f'Bearer {token}'}
resp = requests.get(
    'http://localhost:8000/calendar',
    params={'start_date': '2026-01-12', 'end_date': '2026-01-18'},
    headers=headers
)

data = resp.json()
print(f'Calendar response: {resp.status_code}')

# Debug full response
if resp.status_code != 200:
    print(f'Error: {data}')
else:
    print(f'Days returned: {len(data.get("days", []))}')
    print(f'Active plan: {data.get("active_plan")}')
    print(f'Current week: {data.get("current_week")}')
    print(f'Current phase: {data.get("current_phase")}')

for day in data.get('days', []):
    date_str = day['date']
    planned = day.get('planned_workout')  # Singular!
    activities = day.get('activities', [])
    
    print(f"\n{date_str}:")
    if planned:
        notes = planned.get('coach_notes', '')[:60] if planned.get('coach_notes') else 'No pace'
        print(f"  Planned: {planned.get('workout_type')} - {planned['title']}")
        print(f"    Pace: {notes}")
    else:
        print("  (no planned workout)")
