"""Test insights API endpoints"""
import requests

# Login first
login_resp = requests.post('http://localhost:8000/v1/auth/login', json={
    'email': 'mbshaf@gmail.com',
    'password': 'StrideIQ2026!'
})
token = login_resp.json().get('access_token')
print(f'Login: {login_resp.status_code}')

headers = {'Authorization': f'Bearer {token}'}

# Test build status
print('\n--- BUILD STATUS ---')
resp = requests.get('http://localhost:8000/v1/insights/build-status', headers=headers)
print(f'Status: {resp.status_code}')
if resp.status_code == 200:
    data = resp.json()
    print(f'Has active plan: {data.get("has_active_plan")}')
    print(f'Plan name: {data.get("plan_name")}')
    print(f'Week: {data.get("current_week")} of {data.get("total_weeks")}')
else:
    print(f'Error: {resp.text[:500]}')

# Test active insights
print('\n--- ACTIVE INSIGHTS ---')
resp = requests.get('http://localhost:8000/v1/insights/active?limit=5', headers=headers)
print(f'Status: {resp.status_code}')
if resp.status_code == 200:
    data = resp.json()
    print(f'Insights count: {len(data.get("insights", []))}')
    for i in data.get('insights', [])[:3]:
        print(f'  - {i.get("insight_type")}: {i.get("title")[:50]}...')
else:
    print(f'Error: {resp.text[:500]}')
