"""Verify calendar API returns coach_notes (paces)."""
import requests

# Login
resp = requests.post('http://localhost:8000/v1/auth/login', json={
    'email': 'mbshaf@gmail.com', 
    'password': 'StrideIQ2026!'
})
token = resp.json()['access_token']
print(f'Login: {resp.status_code}')

# Get calendar
headers = {'Authorization': f'Bearer {token}'}
resp = requests.get('http://localhost:8000/calendar', 
    params={'start_date': '2026-01-13', 'end_date': '2026-01-17'},
    headers=headers)

data = resp.json()
print(f'Calendar: {resp.status_code}')

for day in data.get('days', []):
    pw = day.get('planned_workout')
    if pw:
        print(f"\n{day['date']}: {pw.get('workout_type')} - {pw.get('title')}")
        notes = pw.get('coach_notes')
        if notes:
            print(f"  PACE: {notes}")
        else:
            print(f"  ERROR: coach_notes is MISSING!")
