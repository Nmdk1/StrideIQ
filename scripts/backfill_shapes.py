"""Backfill all activity shapes and sentences with the corrected zone model.

Run inside the API container:
  docker exec -w /app strideiq_api python /tmp/backfill_shapes.py
"""
import sys
sys.path.insert(0, ".")

from core.database import SessionLocal
from models import Activity, Athlete, AthleteTrainingPaceProfile, ActivityStream
from services.shape_extractor import (
    extract_shape, generate_shape_sentence, PaceProfile,
    pace_profile_from_training_paces, pace_profile_from_rpi,
)
from datetime import datetime, timedelta
import statistics

db = SessionLocal()

athletes = db.query(Athlete).all()

for athlete in athletes:
    pace_prof = None

    profile_row = db.query(AthleteTrainingPaceProfile).filter(
        AthleteTrainingPaceProfile.athlete_id == athlete.id,
    ).order_by(AthleteTrainingPaceProfile.created_at.desc()).first()

    if profile_row and profile_row.paces:
        pace_prof = pace_profile_from_training_paces(profile_row.paces)

    if not pace_prof and athlete.threshold_pace_per_km:
        thr_sec_km = float(athlete.threshold_pace_per_km)
        if thr_sec_km < 30:
            thr_sec_km = thr_sec_km * 60
        thr_v = 1000.0 / thr_sec_km
        thr_sec_mi = 1609.34 / thr_v if thr_v > 0 else 450
        pace_prof = PaceProfile(
            easy_sec=int(thr_sec_mi * 1.35),
            marathon_sec=int(thr_sec_mi * 1.10),
            threshold_sec=int(thr_sec_mi),
            interval_sec=int(thr_sec_mi * 0.88),
            repetition_sec=int(thr_sec_mi * 0.80),
        )

    if not pace_prof and athlete.rpi:
        pace_prof = pace_profile_from_rpi(float(athlete.rpi))

    if not pace_prof:
        print(f"SKIP {athlete.email}: no pace profile available")
        continue

    def fmt(s):
        m, sec = divmod(int(s), 60)
        return f"{m}:{sec:02d}"
    print(f"\n=== {athlete.email} ===")
    print(f"  Profile: easy={fmt(pace_prof.easy_sec)} mar={fmt(pace_prof.marathon_sec)} thr={fmt(pace_prof.threshold_sec)} int={fmt(pace_prof.interval_sec)} rep={fmt(pace_prof.repetition_sec)}")

    cutoff = datetime.utcnow() - timedelta(days=30)
    durations = db.query(Activity.duration_s).filter(
        Activity.athlete_id == athlete.id,
        Activity.start_time >= cutoff,
        Activity.duration_s.isnot(None),
        Activity.duration_s > 0,
    ).all()
    median_dur = None
    if len(durations) >= 3:
        vals = sorted([float(d[0]) for d in durations])
        median_dur = vals[len(vals) // 2]

    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete.id,
    ).order_by(Activity.start_time.desc()).all()

    shaped = 0
    use_km = getattr(athlete, 'preferred_units', 'imperial') == 'metric'

    for act in activities:
        stream = db.query(ActivityStream).filter(
            ActivityStream.activity_id == act.id,
        ).first()
        if not stream or not stream.stream_data:
            continue

        heat_adj = float(act.heat_adjustment_pct) if act.heat_adjustment_pct else None
        shape = extract_shape(stream.stream_data, pace_profile=pace_prof, heat_adjustment_pct=heat_adj, median_duration_s=median_dur)
        if shape:
            act.run_shape = shape.to_dict()
            total_dist = float(act.distance_m) if act.distance_m else 0
            total_dur = float(act.duration_s or 0)
            act.shape_sentence = generate_shape_sentence(
                shape, total_dist, total_dur,
                pace_profile=pace_prof,
                median_duration_s=median_dur,
                use_km=use_km,
            )
            shaped += 1
            cls = shape.summary.workout_classification or "null"
            phases = shape.summary.total_phases
            accels = shape.summary.acceleration_count
            date = act.start_time.strftime("%Y-%m-%d") if act.start_time else "?"
            sentence = act.shape_sentence or "(suppressed)"
            print(f"  {date} | {phases}ph {accels}acc | {cls:20s} | {sentence}")

    if shaped:
        db.commit()
        print(f"  -> Updated {shaped} activities")
    else:
        print(f"  -> No activities with stream data")

db.close()
print("\nDone.")
