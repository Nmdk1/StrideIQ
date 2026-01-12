"""Test calendar API with inline insights."""
import requests

# Login first
login_resp = requests.post('http://localhost:8000/v1/auth/login', json={
    'email': 'mbshaf@gmail.com',
    'password': 'StrideIQ2026!'
})
token = login_resp.json().get('access_token')
print(f'Login: {login_resp.status_code}')

# Test calendar endpoint
headers = {'Authorization': f'Bearer {token}'}
resp = requests.get('http://localhost:8000/calendar', headers=headers)
print(f'Calendar: {resp.status_code}')

if resp.status_code == 200:
    data = resp.json()
    
    print(f'\n--- CALENDAR DATA ---')
    print(f'Start: {data["start_date"]}')
    print(f'End: {data["end_date"]}')
    print(f'Active plan: {data.get("active_plan", {}).get("name", "None")}')
    print(f'Current week: {data.get("current_week")}')
    print(f'Current phase: {data.get("current_phase")}')
    print(f'Days: {len(data["days"])}')
    print(f'Week summaries: {len(data.get("week_summaries", []))}')
    
    # Check for inline insights
    days_with_insights = [d for d in data['days'] if d.get('inline_insight')]
    print(f'\n--- INLINE INSIGHTS ---')
    print(f'Days with inline insights: {len(days_with_insights)}')
    for d in days_with_insights[:5]:
        insight = d['inline_insight']
        print(f'  {d["date"]}: {insight["metric"]} = {insight["value"]} ({insight["sentiment"]})')
    
    # Check activities
    days_with_activities = [d for d in data['days'] if d.get('activities')]
    print(f'\n--- ACTIVITIES ---')
    print(f'Days with activities: {len(days_with_activities)}')
else:
    print(resp.text)
