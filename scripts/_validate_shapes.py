"""Gate L validation: shape extractor against ground truth activities."""
import sys; sys.path.insert(0, '.')
import json
from core.database import SessionLocal
from models import Activity, ActivityStream, Athlete, AthleteTrainingPaceProfile
from services.shape_extractor import extract_shape, PaceProfile, pace_profile_from_rpi

METERS_PER_MILE = 1609.344
db = SessionLocal()

GROUND_TRUTH = [
    {
        'uuid': '65543f5b-8ae7-455e-9b8f-26891a8a1203',
        'label': "Founder's progressive run (Mar 4)",
        'expected_class': 'progression',
        'notes': 'Splits: 8:12→7:49→7:41→7:46→7:39→7:15. Should be building.',
    },
    {
        'uuid': '04ed985d-7f1c-4243-aea2-988ce5453f2d',
        'label': "Larry's run with strides",
        'expected_class': 'strides',
        'notes': '~1.1 miles. Should detect end-of-run accelerations.',
    },
    {
        'uuid': '51c8cdb6-5f37-46ab-b0ae-b87dec3d0910',
        'label': "BHL's threshold workout",
        'expected_class': 'threshold_intervals',
        'notes': '1mi warmup, 2@8:00, 1@7:30, 1mi cooldown.',
    },
]

def get_pace_profile(athlete_id):
    prof = db.query(AthleteTrainingPaceProfile).filter(
        AthleteTrainingPaceProfile.athlete_id == athlete_id
    ).order_by(AthleteTrainingPaceProfile.computed_at.desc()).first()
    if prof and prof.paces:
        from services.shape_extractor import pace_profile_from_training_paces
        pp = pace_profile_from_training_paces(prof.paces)
        if pp:
            return pp
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if athlete and athlete.threshold_pace_per_km:
        thr_sec_km = athlete.threshold_pace_per_km
        if thr_sec_km < 30:
            thr_sec_km = thr_sec_km * 60
        thr_v = 1000.0 / thr_sec_km
        thr_sec_mi = METERS_PER_MILE / thr_v if thr_v > 0 else 450
        return PaceProfile(
            easy_sec=int(thr_sec_mi * 1.35),
            marathon_sec=int(thr_sec_mi * 1.10),
            threshold_sec=int(thr_sec_mi),
            interval_sec=int(thr_sec_mi * 0.88),
            repetition_sec=int(thr_sec_mi * 0.80),
        )
    if athlete and athlete.rpi:
        rpi_prof = pace_profile_from_rpi(float(athlete.rpi))
        if rpi_prof:
            return rpi_prof
    return None


for gt in GROUND_TRUTH:
    print(f"\n{'='*70}")
    print(f"  {gt['label']}")
    print(f"  Expected: {gt['expected_class']}")
    print(f"  Notes: {gt['notes']}")
    print(f"{'='*70}")

    act = db.query(Activity).filter(Activity.id == gt['uuid']).first()
    if not act:
        print(f"  ACTIVITY NOT FOUND")
        continue

    stream = db.query(ActivityStream).filter(
        ActivityStream.activity_id == act.id
    ).first()
    if not stream:
        print(f"  NO STREAM DATA")
        continue

    prof = get_pace_profile(act.athlete_id)
    if prof:
        print(f"  Pace profile: easy={prof.easy_sec}s, thr={prof.threshold_sec}s, "
              f"int={prof.interval_sec}s, rep={prof.repetition_sec}s")
    else:
        print(f"  No pace profile — using stream-relative")

    shape = extract_shape(stream.stream_data, pace_profile=prof)
    if not shape:
        print(f"  SHAPE EXTRACTION RETURNED None")
        continue

    s = shape.summary
    print(f"\n  Classification: {s.workout_classification}")
    match = s.workout_classification == gt['expected_class']
    print(f"  Match expected: {'YES' if match else 'NO'}")
    print(f"  Phases: {s.total_phases}")
    print(f"  Accelerations: {s.acceleration_count}")
    print(f"  Clustering: {s.acceleration_clustering}")
    print(f"  Progression: {s.pace_progression}")
    print(f"  Elevation: {s.elevation_profile}")
    print(f"  Has warmup: {s.has_warmup}, Has cooldown: {s.has_cooldown}")
    print(f"  Longest sustained: {s.longest_sustained_effort_s}s ({s.longest_sustained_zone})")

    print(f"\n  Phases detail:")
    for i, p in enumerate(shape.phases):
        pace_min = int(p.avg_pace_sec_per_mile // 60)
        pace_sec = int(p.avg_pace_sec_per_mile % 60)
        dur_min = p.duration_s // 60
        dur_sec = p.duration_s % 60
        hr_str = f"HR {p.avg_hr:.0f}" if p.avg_hr else "no HR"
        print(f"    {i+1}. {p.phase_type:20s} | {dur_min}:{dur_sec:02d} | "
              f"{pace_min}:{pace_sec:02d}/mi ({p.pace_zone:10s}) | {hr_str}")

    if shape.accelerations:
        print(f"\n  Accelerations:")
        for i, a in enumerate(shape.accelerations):
            pace_min = int(a.avg_pace_sec_per_mile // 60)
            pace_sec = int(a.avg_pace_sec_per_mile % 60)
            print(f"    {i+1}. {a.duration_s}s at {pace_min}:{pace_sec:02d}/mi "
                  f"({a.pace_zone}) | pos={a.position_in_run:.2f} | "
                  f"recovery={a.recovery_after_s}s")


# Also find an easy run to check for over-detection
print(f"\n{'='*70}")
print(f"  Over-detection test: plain easy run")
print(f"{'='*70}")
founder_id = '4368ec7f-c30d-45ff-a6ee-58db7716be24'
prog_run_id = '65543f5b-8ae7-455e-9b8f-26891a8a1203'
easy_acts = db.query(Activity).filter(
    Activity.athlete_id == founder_id,
    Activity.id != prog_run_id,
    Activity.workout_type.in_(['easy_run', 'recovery_run']),
    Activity.distance_m.between(6000, 14000),
).order_by(Activity.start_time.desc()).limit(5).all()

for act in easy_acts:
    stream = db.query(ActivityStream).filter(
        ActivityStream.activity_id == act.id
    ).first()
    if not stream:
        continue
    prof = get_pace_profile(act.athlete_id)
    shape = extract_shape(stream.stream_data, pace_profile=prof)
    if shape:
        s = shape.summary
        name = (act.name or '?')[:40]
        print(f"\n  {name} ({act.start_time.date()})")
        print(f"    Classification: {s.workout_classification}")
        print(f"    Phases: {s.total_phases}, Accels: {s.acceleration_count}")
        for i, p in enumerate(shape.phases):
            pace_min = int(p.avg_pace_sec_per_mile // 60)
            pace_sec = int(p.avg_pace_sec_per_mile % 60)
            print(f"      {i+1}. {p.phase_type:15s} | {p.duration_s//60}:{p.duration_s%60:02d} | "
                  f"{pace_min}:{pace_sec:02d}/mi ({p.pace_zone})")
        break

db.close()
