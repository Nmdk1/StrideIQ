"""Generate insights for testing"""
import requests

# Login first
login_resp = requests.post('http://localhost:8000/v1/auth/login', json={
    'email': 'mbshaf@gmail.com',
    'password': 'StrideIQ2026!'
})
token = login_resp.json().get('access_token')
print(f'Login: {login_resp.status_code}')

headers = {'Authorization': f'Bearer {token}'}

# Generate insights
print('\n--- GENERATE INSIGHTS ---')
resp = requests.post('http://localhost:8000/v1/insights/generate', headers=headers)
print(f'Status: {resp.status_code}')
if resp.status_code == 200:
    data = resp.json()
    print(f'Generated: {data.get("insights_generated")}')
    print(f'Saved: {data.get("insights_saved")}')
else:
    print(f'Error: {resp.text[:500]}')

# Now check active insights
print('\n--- ACTIVE INSIGHTS ---')
resp = requests.get('http://localhost:8000/v1/insights/active?limit=5', headers=headers)
print(f'Status: {resp.status_code}')
if resp.status_code == 200:
    data = resp.json()
    print(f'Insights count: {len(data.get("insights", []))}')
    for i in data.get('insights', []):
        print(f'  - {i.get("insight_type")}: {i.get("title")}')
else:
    print(f'Error: {resp.text[:500]}')
