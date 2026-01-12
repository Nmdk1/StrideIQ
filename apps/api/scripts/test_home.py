"""Test home API endpoint."""
import requests
import json

# Login first
login_resp = requests.post('http://localhost:8000/v1/auth/login', json={
    'email': 'mbshaf@gmail.com',
    'password': 'StrideIQ2026!'
})
token = login_resp.json().get('access_token')
print(f'Login: {login_resp.status_code}')

# Test home endpoint
headers = {'Authorization': f'Bearer {token}'}
resp = requests.get('http://localhost:8000/home', headers=headers)
print(f'Home: {resp.status_code}')

if resp.status_code == 200:
    data = resp.json()
    
    print('\n--- TODAY ---')
    today = data['today']
    print(f'Has workout: {today["has_workout"]}')
    if today['has_workout']:
        print(f'  Title: {today.get("title")}')
        print(f'  Distance: {today.get("distance_mi")} mi')
        print(f'  Pace: {today.get("pace_guidance")}')
        print(f'  Why: {today.get("why_context")}')
        print(f'  Week: {today.get("week_number")}, Phase: {today.get("phase")}')
    
    print('\n--- YESTERDAY ---')
    yesterday = data['yesterday']
    print(f'Has activity: {yesterday["has_activity"]}')
    if yesterday['has_activity']:
        print(f'  Name: {yesterday.get("activity_name")}')
        print(f'  Distance: {yesterday.get("distance_mi")} mi at {yesterday.get("pace_per_mi")}')
        print(f'  Insight: {yesterday.get("insight")}')
    
    print('\n--- WEEK ---')
    week = data['week']
    print(f'Status: {week["status"]}')
    print(f'Progress: {week["completed_mi"]}/{week["planned_mi"]} mi ({week["progress_pct"]}%)')
    print(f'Week: {week.get("week_number")}/{week.get("total_weeks")}, Phase: {week.get("phase")}')
    print('Days:')
    for d in week['days']:
        status = '✓' if d['completed'] else '○' if d['is_today'] else '·'
        dist = d.get('distance_mi', '-')
        print(f'  {d["day_abbrev"]}: {status} {dist}')
else:
    print(resp.text)
