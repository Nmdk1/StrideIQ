"""Post-deploy verification for correlation engine input wiring."""
from datetime import datetime, timedelta, timezone
from core.database import SessionLocal
from models import Athlete
from services.correlation_engine import (
    aggregate_daily_inputs,
    aggregate_activity_level_inputs,
    aggregate_feedback_inputs,
    aggregate_training_pattern_inputs,
)

db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email == "mbshaf@gmail.com").first()
aid = str(user.id)
end = datetime.now(timezone.utc)
start = end - timedelta(days=90)

daily = aggregate_daily_inputs(aid, start, end, db)
activity = aggregate_activity_level_inputs(aid, start, end, db)
feedback = aggregate_feedback_inputs(aid, start, end, db)
patterns = aggregate_training_pattern_inputs(aid, start, end, db)

print(f"Daily inputs: {len(daily)} signals")
for k, v in sorted(daily.items()):
    print(f"  {k}: {len(v)} data points")

print(f"Activity inputs: {len(activity)} signals")
for k, v in sorted(activity.items()):
    print(f"  {k}: {len(v)} data points")

print(f"Feedback inputs: {len(feedback)} signals")
for k, v in sorted(feedback.items()):
    print(f"  {k}: {len(v)} data points")

print(f"Pattern inputs: {len(patterns)} signals")
for k, v in sorted(patterns.items()):
    print(f"  {k}: {len(v)} data points")

total = len(daily) + len(activity) + len(feedback) + len(patterns)
print(f"TOTAL: {total} input signals")

required_daily = {
    "garmin_sleep_score", "garmin_body_battery_end", "garmin_avg_stress",
    "sleep_quality_1_5", "body_fat_pct", "daily_calories",
}
required_activity = {
    "dew_point_f", "avg_cadence", "run_start_hour", "activity_intensity_score",
}
required_feedback = {
    "feedback_perceived_effort", "feedback_leg_feel", "reflection_vs_expected",
}
required_patterns = {
    "days_since_quality", "consecutive_run_days", "weekly_volume_km", "long_run_ratio",
}

missing = []
missing += [f"daily:{k}" for k in required_daily if k not in daily]
missing += [f"activity:{k}" for k in required_activity if k not in activity]
missing += [f"feedback:{k}" for k in required_feedback if k not in feedback]
missing += [f"patterns:{k}" for k in required_patterns if k not in patterns]
if missing:
    raise SystemExit(f"MISSING REQUIRED WIRED KEYS: {missing}")

if total < 70:
    raise SystemExit(f"INPUT WIRING INCOMPLETE: expected >=70 keys, got {total}")

print("ALL VERIFICATION GATES PASSED")
db.close()
