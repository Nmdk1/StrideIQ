"""Verify fingerprint backfill results."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import SessionLocal
from models import Athlete, CorrelationFinding

db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email == "mbshaf@gmail.com").first()

findings = (
    db.query(CorrelationFinding)
    .filter(
        CorrelationFinding.athlete_id == user.id,
        CorrelationFinding.is_active == True,
    )
    .order_by(CorrelationFinding.times_confirmed.desc())
    .all()
)

total = len(findings)
surfaceable = sum(1 for f in findings if f.times_confirmed >= 3)

print(f"Total active findings: {total}")
print(f"Surfaceable (confirmed >= 3): {surfaceable}")
print()
print("Top findings:")
for f in findings[:20]:
    parts = [
        f"{f.input_name} -> {f.output_metric}: {f.direction} "
        f"(confirmed {f.times_confirmed}x, r={f.correlation_coefficient:.2f}, n={f.sample_size})"
    ]
    if f.threshold_value is not None:
        parts.append(f"  threshold: {f.threshold_value:.1f}")
    if f.asymmetry_ratio is not None:
        parts.append(f"  asymmetry: {f.asymmetry_ratio:.1f}x")
    if f.decay_half_life_days is not None:
        parts.append(f"  decay: {f.decay_half_life_days:.1f} days")
    print("  " + " | ".join(parts))

new_signal_keys = [
    "garmin_sleep_score", "garmin_body_battery_end", "avg_cadence",
    "dew_point_f", "avg_power_watts", "elevation_gain_m",
    "garmin_resting_hr", "garmin_stress_avg", "garmin_steps",
]
new_findings = [f for f in findings if f.input_name in new_signal_keys]
print(f"\nFindings from NEW signals: {len(new_findings)}")
for f in new_findings[:10]:
    print(
        f"  {f.input_name} -> {f.output_metric}: {f.direction} "
        f"(confirmed {f.times_confirmed}x, r={f.correlation_coefficient:.2f})"
    )

db.close()
