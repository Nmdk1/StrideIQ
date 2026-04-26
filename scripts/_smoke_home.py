import json, sys, urllib.request

sys.path.insert(0, "/app")
from core.security import create_access_token
from database import SessionLocal
from models import Athlete

db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email == "mbshaf@gmail.com").first()
token = create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role})
db.close()

req = urllib.request.Request(
    "https://strideiq.run/v1/home",
    headers={"Authorization": f"Bearer {token}"}
)
d = json.loads(urllib.request.urlopen(req, timeout=20).read())

b = d.get("coach_briefing") or {}
print("=== morning_voice ===")
print(b.get("morning_voice") or "NOT FOUND")
print()
print("=== week_assessment ===")
print(b.get("week_assessment") or "NOT FOUND")
print()
print("=== today_context ===")
print(b.get("today_context") or "NOT FOUND")
print()
print("=== coach_noticed (top-level) ===")
cn = d.get("coach_noticed")
if isinstance(cn, list):
    for item in cn:
        print(" -", item)
else:
    print(cn)
print()
print("briefing_state:", d.get("briefing_state"))
