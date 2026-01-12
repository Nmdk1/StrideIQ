"""Test Strava PB sync"""
import requests

# Login
login_resp = requests.post('http://localhost:8000/v1/auth/login', json={
    'email': 'mbshaf@gmail.com',
    'password': 'StrideIQ2026!'
})
token = login_resp.json().get('access_token')
print(f'Login: {login_resp.status_code}')

headers = {'Authorization': f'Bearer {token}'}

# Get profile to get athlete ID
profile_resp = requests.get('http://localhost:8000/v1/athletes/me', headers=headers)
athlete_id = profile_resp.json().get('id')
print(f'Athlete ID: {athlete_id}')

# Recalculate PBs (now uses Strava sync)
print('\n--- RECALCULATING PBs (Strava sync) ---')
resp = requests.post(f'http://localhost:8000/v1/athletes/{athlete_id}/recalculate-pbs', headers=headers)
print(f'Status: {resp.status_code}')
if resp.status_code == 200:
    data = resp.json()
    print(f'Strava synced: {data.get("strava_synced")} activities')
    print(f'Strava updated: {data.get("strava_updated")} PBs')
    print(f'Strava created: {data.get("strava_created")} PBs')
    print(f'Total PBs: {data.get("total_pbs")}')
else:
    print(f'Error: {resp.text[:500]}')

# Get current PBs
print('\n--- CURRENT PBs ---')
resp = requests.get(f'http://localhost:8000/v1/athletes/{athlete_id}/personal-bests', headers=headers)
if resp.status_code == 200:
    pbs = resp.json()
    for pb in pbs:
        mins = pb['time_seconds'] // 60
        secs = pb['time_seconds'] % 60
        print(f"  {pb['distance_category']}: {mins}:{secs:02d} ({pb['achieved_at'][:10]})")
