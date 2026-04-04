"""
Day-0 gate: Verify Garmin exerciseSets endpoint is accessible.

Run on production server inside the API container.
Finds Brian's most recent strength activity (if any) and probes the endpoint.
If no strength activity exists, probes with a known run activity to check
whether the endpoint exists at all (expect 404 or empty for non-strength).
"""
import sys
sys.path.insert(0, "/app/apps/api")
sys.path.insert(0, "/app")
from database import SessionLocal
from models import Activity, Athlete
from services.garmin_oauth import ensure_fresh_garmin_token
import requests
import json

_GARMIN_ACTIVITY_BASE = "https://apis.garmin.com/wellness-api/rest"
_TIMEOUT_S = 15

db = SessionLocal()

print("=== All athletes ===")
all_athletes = db.query(Athlete).all()
for a in all_athletes:
    print(f"  {a.display_name} | garmin={a.garmin_connected} | id={a.id}")

brian = None
for a in all_athletes:
    if a.display_name and a.display_name.strip().upper() == "BHL":
        brian = a
        break

if not brian:
    for a in all_athletes:
        if a.display_name and "michael" in a.display_name.lower():
            brian = a
            break

if not brian:
    garmin_athletes = [a for a in all_athletes if a.garmin_connected]
    if garmin_athletes:
        brian = garmin_athletes[0]
        print(f"No BHL/Michael found, using first Garmin-connected athlete: {brian.display_name}")
    else:
        print("ERROR: No Garmin-connected athletes found")
        db.close()
        exit(1)

print("Found athlete:", brian.display_name, "id:", brian.id)
print("garmin_connected:", brian.garmin_connected)

token = ensure_fresh_garmin_token(brian, db)
if not token:
    print("ERROR: No valid Garmin token for Brian")
    db.close()
    exit(1)

print("Token obtained (first 20 chars):", token[:20] + "...")

strength = db.query(Activity).filter(
    Activity.athlete_id == brian.id,
    Activity.sport == "strength",
).order_by(Activity.start_time.desc()).first()

if strength:
    target_id = strength.garmin_activity_id
    print("Using strength activity:", strength.name, "garmin_id:", target_id)
else:
    print("No strength activities found - using most recent run for endpoint probe")
    run = db.query(Activity).filter(
        Activity.athlete_id == brian.id,
        Activity.sport == "run",
        Activity.garmin_activity_id != None,
    ).order_by(Activity.start_time.desc()).first()
    if not run:
        print("ERROR: No activities with garmin_activity_id found")
        db.close()
        exit(1)
    target_id = run.garmin_activity_id
    print("Using run activity:", run.name, "garmin_id:", target_id)

headers = {"Authorization": "Bearer " + token}

url = _GARMIN_ACTIVITY_BASE + "/backfill/activities"
print("\n--- Probing exerciseSets endpoint ---")

exercise_url = "https://apis.garmin.com/wellness-api/rest/activities/" + str(target_id) + "/exerciseSets"
print("URL:", exercise_url)

try:
    resp = requests.get(exercise_url, headers=headers, timeout=_TIMEOUT_S)
    print("Status:", resp.status_code)
    print("Headers:", dict(resp.headers))
    if resp.status_code == 200:
        data = resp.json()
        print("Response type:", type(data).__name__)
        print("Response (first 2000 chars):", json.dumps(data, indent=2, default=str)[:2000])
        print("\nGATE RESULT: PASS - endpoint accessible")
    elif resp.status_code == 404:
        print("Response:", resp.text[:500])
        print("\nGATE RESULT: ENDPOINT EXISTS BUT 404 FOR THIS ACTIVITY")
        print("May need to try a different URL pattern or a real strength activity")
    elif resp.status_code == 403:
        print("Response:", resp.text[:500])
        print("\nGATE RESULT: FAIL - 403 Forbidden. Endpoint not authorized.")
    else:
        print("Response:", resp.text[:500])
        print("\nGATE RESULT: INCONCLUSIVE - unexpected status code")
except Exception as e:
    print("ERROR:", e)
    print("\nGATE RESULT: FAIL - request error")

db.close()
