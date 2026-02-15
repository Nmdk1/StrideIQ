"""
Provision a realistic demo athlete with month-long streamed run data.

Why this exists:
- Gives reviewers a "golden path" account they can log into immediately.
- Uses real app models (Athlete/Activity/ActivityStream/CachedStreamAnalysis),
  not frontend mocks.
- Can optionally shape demo runs from a real recent stream so it feels authentic.

Security:
- Password is read from an env var, never from CLI args.
- DRY_RUN by default. Use --commit to persist.

Usage (inside api container):
  export STRIDEIQ_DEMO_PASSWORD="change-me"
  python scripts/provision_demo_athlete.py --commit

Optional:
  python scripts/provision_demo_athlete.py --commit --source-email you@example.com
  python scripts/provision_demo_athlete.py --commit --days 30 --runs-per-week 5
"""

from __future__ import annotations

import argparse
import math
import os
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Sequence, Tuple
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.security import get_password_hash
from models import (
    Activity,
    ActivityReflection,
    ActivitySplit,
    ActivityStream,
    Athlete,
    CachedStreamAnalysis,
)
from services.run_stream_analysis import AthleteContext
from services.stream_analysis_cache import get_or_compute_analysis


# Email and password sourced from environment only — no hardcoded PII.
# Set STRIDEIQ_DEMO_EMAIL and STRIDEIQ_DEMO_PASSWORD before running.
DEFAULT_EMAIL_ENV = "STRIDEIQ_DEMO_EMAIL"
DEFAULT_PASSWORD_ENV = "STRIDEIQ_DEMO_PASSWORD"


@dataclass(frozen=True)
class RunProfile:
    run_type: str
    duration_s: int
    speed_scale: float
    hr_shift: float
    cadence_shift: float
    name: str


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _resample_numeric(series: Sequence[float], target_len: int) -> List[float]:
    if target_len <= 0:
        return []
    if not series:
        return [0.0] * target_len
    if len(series) == 1:
        return [float(series[0])] * target_len

    src_last = len(series) - 1
    out: List[float] = []
    for i in range(target_len):
        pos = (i / (target_len - 1)) * src_last if target_len > 1 else 0.0
        lo = int(math.floor(pos))
        hi = min(lo + 1, src_last)
        frac = pos - lo
        val = float(series[lo]) * (1.0 - frac) + float(series[hi]) * frac
        out.append(val)
    return out


def _resample_bool(series: Sequence[bool], target_len: int) -> List[bool]:
    if target_len <= 0:
        return []
    if not series:
        return [True] * target_len
    if len(series) == 1:
        return [bool(series[0])] * target_len

    src_last = len(series) - 1
    out: List[bool] = []
    for i in range(target_len):
        pos = int(round((i / (target_len - 1)) * src_last)) if target_len > 1 else 0
        pos = max(0, min(src_last, pos))
        out.append(bool(series[pos]))
    return out


def _extract_template_stream(
    db: Session,
    source_email: Optional[str],
    template_activity_id: Optional[UUID],
) -> Optional[Dict[str, List]]:
    if template_activity_id is not None:
        stream = (
            db.query(ActivityStream)
            .join(Activity, Activity.id == ActivityStream.activity_id)
            .filter(Activity.id == template_activity_id)
            .first()
        )
        return stream.stream_data if stream else None

    if source_email:
        athlete = db.query(Athlete).filter(Athlete.email == source_email).first()
        if athlete is None:
            return None
        row = (
            db.query(ActivityStream)
            .join(Activity, Activity.id == ActivityStream.activity_id)
            .filter(
                Activity.athlete_id == athlete.id,
                Activity.stream_fetch_status == "success",
            )
            .order_by(Activity.start_time.desc())
            .first()
        )
        return row.stream_data if row else None

    row = (
        db.query(ActivityStream)
        .join(Activity, Activity.id == ActivityStream.activity_id)
        .filter(
            Activity.stream_fetch_status == "success",
            Activity.provider != "demo",
        )
        .order_by(Activity.start_time.desc())
        .first()
    )
    return row.stream_data if row else None


def _make_base_synthetic_stream(duration_s: int, rng: random.Random) -> Dict[str, List]:
    duration_s = int(_clamp(duration_s, 1400, 9000))
    time = list(range(duration_s))
    velocity: List[float] = []
    heartrate: List[float] = []
    cadence: List[float] = []
    altitude: List[float] = []
    grade: List[float] = []
    distance: List[float] = []
    moving: List[bool] = []

    base_speed = rng.uniform(2.7, 3.5)  # ~6:10/km to ~4:45/km
    hr_base = rng.uniform(132, 148)
    hr_range = rng.uniform(18, 30)
    cad_base = rng.uniform(168, 178)
    alt = rng.uniform(35.0, 120.0)
    cum_dist = 0.0

    for t in time:
        frac = t / duration_s
        warmup = _clamp(frac / 0.12, 0.0, 1.0)
        cooldown = _clamp((1.0 - frac) / 0.08, 0.0, 1.0)
        shape = 0.88 + 0.12 * min(warmup, cooldown)
        undulation = 1.0 + 0.05 * math.sin((2.0 * math.pi * t) / 900.0)
        fatigue = 1.0 - 0.03 * frac
        v = base_speed * shape * undulation * fatigue
        v = _clamp(v, 1.9, 4.9)

        hill = 2.8 * math.sin((2.0 * math.pi * t) / 1500.0) + 0.6 * math.sin(
            (2.0 * math.pi * t) / 420.0
        )
        g = _clamp(hill, -8.0, 8.0)
        grade_penalty = 1.0 - max(0.0, g) * 0.012 + max(0.0, -g) * 0.004
        v *= _clamp(grade_penalty, 0.75, 1.08)

        hr_effort = (v / 3.4) * hr_range
        drift = 5.0 * frac
        hr = hr_base + hr_effort + drift + max(0.0, g) * 0.5
        hr = _clamp(hr, 92.0, 193.0)

        cad = cad_base + (v - base_speed) * 9.0 + rng.uniform(-1.8, 1.8)
        cad = _clamp(cad, 155.0, 194.0)

        alt += v * (g / 100.0)
        cum_dist += v

        velocity.append(round(v, 3))
        heartrate.append(round(hr, 1))
        cadence.append(round(cad, 1))
        altitude.append(round(alt, 2))
        grade.append(round(g, 2))
        distance.append(round(cum_dist, 2))
        moving.append(v > 0.7)

    return {
        "time": time,
        "velocity_smooth": velocity,
        "heartrate": heartrate,
        "cadence": cadence,
        "altitude": altitude,
        "grade_smooth": grade,
        "distance": distance,
        "moving": moving,
    }


def _shape_from_template(
    template: Dict[str, List],
    profile: RunProfile,
    rng: random.Random,
) -> Dict[str, List]:
    t_time = template.get("time") or []
    base_duration = len(t_time) if t_time else profile.duration_s
    duration_s = int(_clamp(profile.duration_s, 1400, 9000))
    if base_duration < 100:
        return _make_base_synthetic_stream(duration_s, rng)

    velocity_tpl = [float(v) for v in (template.get("velocity_smooth") or [])]
    hr_tpl = [float(h) for h in (template.get("heartrate") or [])]
    cad_tpl = [float(c) for c in (template.get("cadence") or [])]
    alt_tpl = [float(a) for a in (template.get("altitude") or [])]
    grd_tpl = [float(g) for g in (template.get("grade_smooth") or [])]
    mov_tpl = [bool(m) for m in (template.get("moving") or [])]

    velocity = _resample_numeric(velocity_tpl, duration_s) if velocity_tpl else []
    heartrate = _resample_numeric(hr_tpl, duration_s) if hr_tpl else []
    cadence = _resample_numeric(cad_tpl, duration_s) if cad_tpl else []
    altitude = _resample_numeric(alt_tpl, duration_s) if alt_tpl else []
    grade = _resample_numeric(grd_tpl, duration_s) if grd_tpl else []
    moving = _resample_bool(mov_tpl, duration_s) if mov_tpl else [True] * duration_s

    if not velocity:
        return _make_base_synthetic_stream(duration_s, rng)

    distance: List[float] = []
    cum_dist = 0.0
    for i in range(duration_s):
        wobble = 1.0 + 0.025 * math.sin((2.0 * math.pi * i) / 780.0)
        v = velocity[i] * profile.speed_scale * wobble
        v = _clamp(v, 1.8, 5.2)
        velocity[i] = round(v, 3)
        cum_dist += v
        distance.append(round(cum_dist, 2))

        if heartrate:
            hr = heartrate[i] + profile.hr_shift + (profile.speed_scale - 1.0) * 18.0
            heartrate[i] = round(_clamp(hr, 90.0, 198.0), 1)
        if cadence:
            cad = cadence[i] + profile.cadence_shift + (profile.speed_scale - 1.0) * 8.0
            cadence[i] = round(_clamp(cad, 154.0, 196.0), 1)
        if grade:
            grade[i] = round(_clamp(grade[i], -10.0, 10.0), 2)

    if not altitude:
        altitude = [95.0] * duration_s
    if not grade:
        grade = [0.0] * duration_s

    return {
        "time": list(range(duration_s)),
        "velocity_smooth": velocity,
        "heartrate": heartrate if heartrate else [],
        "cadence": cadence if cadence else [],
        "altitude": altitude,
        "grade_smooth": grade,
        "distance": distance,
        "moving": moving,
    }


def _build_schedule(days: int, runs_per_week: int) -> List[datetime]:
    days = int(_clamp(days, 7, 120))
    runs_per_week = int(_clamp(runs_per_week, 2, 7))
    total_runs = max(8, int(round(days * runs_per_week / 7.0)))
    start = datetime.now(timezone.utc) - timedelta(days=days)
    step_days = days / total_runs
    out: List[datetime] = []
    for i in range(total_runs):
        run_day = start + timedelta(days=step_days * i)
        out.append(run_day.replace(hour=6 + (i % 3), minute=10 + (i * 7) % 40, second=0, microsecond=0))
    return out


def _profile_for_index(idx: int, rng: random.Random) -> RunProfile:
    slot = idx % 6
    if slot == 5:
        return RunProfile(
            run_type="long",
            duration_s=int(rng.uniform(5200, 7600)),
            speed_scale=rng.uniform(0.88, 0.98),
            hr_shift=rng.uniform(-3.0, 2.0),
            cadence_shift=rng.uniform(-2.0, 1.0),
            name="Long Run",
        )
    if slot in (2, 4):
        return RunProfile(
            run_type="easy",
            duration_s=int(rng.uniform(2300, 3900)),
            speed_scale=rng.uniform(0.90, 1.02),
            hr_shift=rng.uniform(-6.0, 2.0),
            cadence_shift=rng.uniform(-2.5, 1.0),
            name="Easy Run",
        )
    if slot == 3:
        return RunProfile(
            run_type="progression",
            duration_s=int(rng.uniform(2600, 4400)),
            speed_scale=rng.uniform(0.98, 1.10),
            hr_shift=rng.uniform(-1.0, 5.0),
            cadence_shift=rng.uniform(-1.0, 2.5),
            name="Progression Run",
        )
    return RunProfile(
        run_type="steady",
        duration_s=int(rng.uniform(2500, 4100)),
        speed_scale=rng.uniform(0.94, 1.08),
        hr_shift=rng.uniform(-3.0, 4.0),
        cadence_shift=rng.uniform(-2.0, 2.0),
        name="Morning Run",
    )


def _compute_elevation_gain(altitude: Sequence[float]) -> float:
    if len(altitude) < 2:
        return 0.0
    gain = 0.0
    for i in range(1, len(altitude)):
        delta = float(altitude[i]) - float(altitude[i - 1])
        if delta > 0:
            gain += delta
    return round(gain, 1)


def _insert_splits(
    db: Session,
    activity_id: UUID,
    stream: Dict[str, List],
    split_size_m: float = 1000.0,
) -> int:
    distance = stream.get("distance") or []
    time = stream.get("time") or []
    hr = stream.get("heartrate") or []
    cadence = stream.get("cadence") or []
    if not distance or not time or len(distance) != len(time):
        return 0

    total_m = float(distance[-1])
    if total_m < split_size_m:
        return 0

    split_count = int(total_m // split_size_m)
    created = 0
    prev_idx = 0
    prev_dist = 0.0
    prev_elapsed = int(time[0])
    for n in range(1, split_count + 1):
        target = n * split_size_m
        end_idx = next((i for i, d in enumerate(distance) if float(d) >= target), None)
        if end_idx is None or end_idx <= prev_idx:
            continue

        elapsed = int(time[end_idx]) - prev_elapsed
        seg_dist = float(distance[end_idx]) - prev_dist
        if elapsed <= 0 or seg_dist <= 0:
            prev_idx = end_idx
            prev_dist = float(distance[end_idx])
            prev_elapsed = int(time[end_idx])
            continue

        hr_slice = [float(x) for x in hr[prev_idx:end_idx + 1]] if hr else []
        cad_slice = [float(x) for x in cadence[prev_idx:end_idx + 1]] if cadence else []
        avg_hr = int(round(_mean(hr_slice))) if hr_slice else None
        max_hr = int(round(max(hr_slice))) if hr_slice else None
        avg_cad = round(_mean(cad_slice), 1) if cad_slice else None
        pace_sec_per_mile = (elapsed / seg_dist) * 1609.344

        split = ActivitySplit(
            activity_id=activity_id,
            split_number=n,
            distance=round(seg_dist, 1),
            elapsed_time=elapsed,
            moving_time=elapsed,
            average_heartrate=avg_hr,
            max_heartrate=max_hr,
            average_cadence=avg_cad,
            gap_seconds_per_mile=round(pace_sec_per_mile, 1),
        )
        db.add(split)
        created += 1
        prev_idx = end_idx
        prev_dist = float(distance[end_idx])
        prev_elapsed = int(time[end_idx])
    return created


def _wipe_demo_activity_data(db: Session, athlete_id: UUID) -> Tuple[int, int]:
    activity_ids = [
        row[0]
        for row in db.query(Activity.id).filter(Activity.athlete_id == athlete_id).all()
    ]
    if not activity_ids:
        return 0, 0

    db.query(ActivityReflection).filter(
        ActivityReflection.activity_id.in_(activity_ids)
    ).delete(synchronize_session=False)
    db.query(CachedStreamAnalysis).filter(
        CachedStreamAnalysis.activity_id.in_(activity_ids)
    ).delete(synchronize_session=False)
    split_count = db.query(ActivitySplit).filter(
        ActivitySplit.activity_id.in_(activity_ids)
    ).delete(synchronize_session=False)
    stream_count = db.query(ActivityStream).filter(
        ActivityStream.activity_id.in_(activity_ids)
    ).delete(synchronize_session=False)
    db.query(Activity).filter(Activity.id.in_(activity_ids)).delete(synchronize_session=False)
    return int(stream_count), int(split_count)


def _get_or_create_demo_athlete(
    db: Session,
    email: str,
    display_name: str,
    password: str,
    subscription_tier: str,
) -> Tuple[Athlete, bool]:
    athlete = db.query(Athlete).filter(Athlete.email == email).first()
    created = False
    if athlete is None:
        athlete = Athlete(
            email=email,
            password_hash=get_password_hash(password),
            role="athlete",
            display_name=display_name,
            subscription_tier=subscription_tier,
            preferred_units="imperial",
            onboarding_completed=True,
            max_hr=180,
            resting_hr=50,
            threshold_hr=165,
            timezone="America/New_York",
        )
        db.add(athlete)
        db.flush()
        created = True
    else:
        athlete.password_hash = get_password_hash(password)
        athlete.display_name = display_name
        athlete.subscription_tier = subscription_tier
        athlete.onboarding_completed = True
        if athlete.max_hr is None:
            athlete.max_hr = 180
        if athlete.resting_hr is None:
            athlete.resting_hr = 50
        if athlete.threshold_hr is None:
            athlete.threshold_hr = 165
        if not athlete.timezone:
            athlete.timezone = "America/New_York"
    return athlete, created


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--email",
        default=os.environ.get(DEFAULT_EMAIL_ENV),
        help="demo athlete email (or set STRIDEIQ_DEMO_EMAIL env var)",
    )
    parser.add_argument("--display-name", default="Demo Athlete", help="demo display name")
    parser.add_argument(
        "--password-env",
        default=DEFAULT_PASSWORD_ENV,
        help=f"env var containing demo password (default: {DEFAULT_PASSWORD_ENV})",
    )
    parser.add_argument("--days", type=int, default=30, help="history window (days)")
    parser.add_argument("--runs-per-week", type=int, default=5, help="target runs per week")
    parser.add_argument("--seed", type=int, default=20260213, help="deterministic RNG seed")
    parser.add_argument(
        "--subscription-tier",
        default="elite",
        help="subscription tier to assign (default: elite)",
    )
    parser.add_argument(
        "--source-email",
        default=None,
        help="optional source athlete email used to shape stream patterns",
    )
    parser.add_argument(
        "--template-activity-id",
        default=None,
        help="optional specific activity UUID to use as template stream",
    )
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        default=False,
        help="wipe existing demo athlete activities before generating new month data",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="persist changes; default is dry-run",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    password = os.getenv(args.password_env)
    if not password:
        print(f"ERROR: missing env var {args.password_env}")
        return 2

    template_activity_id = UUID(args.template_activity_id) if args.template_activity_id else None
    rng = random.Random(args.seed)
    dry_run = not args.commit

    db = SessionLocal()
    try:
        athlete, created = _get_or_create_demo_athlete(
            db=db,
            email=args.email.strip().lower(),
            display_name=args.display_name.strip(),
            password=password,
            subscription_tier=args.subscription_tier.strip().lower(),
        )

        print(f"DEMO athlete: {athlete.email} ({athlete.id})")
        print(f"  created: {created}")
        print(f"  tier: {athlete.subscription_tier}")

        removed_streams = 0
        removed_splits = 0
        if args.replace_existing:
            removed_streams, removed_splits = _wipe_demo_activity_data(db, athlete.id)
            print(f"  wiped existing demo data: streams={removed_streams}, splits={removed_splits}")

        template_stream = _extract_template_stream(db, args.source_email, template_activity_id)
        if template_stream:
            print("  template stream: found (demo runs will mirror real shape with variation)")
        else:
            print("  template stream: none found (using synthetic generator)")

        run_times = _build_schedule(args.days, args.runs_per_week)
        print(f"  planned runs: {len(run_times)} over {args.days} days")

        if dry_run:
            print("DRY_RUN: no rows written. Re-run with --commit.")
            db.rollback()
            return 0

        created_activities = 0
        created_splits = 0
        for idx, run_start in enumerate(run_times):
            profile = _profile_for_index(idx, rng)
            if template_stream:
                stream_data = _shape_from_template(template_stream, profile, rng)
            else:
                stream_data = _make_base_synthetic_stream(profile.duration_s, rng)

            duration_s = len(stream_data["time"])
            distance_m = int(stream_data["distance"][-1]) if stream_data["distance"] else 0
            avg_speed = float(distance_m) / duration_s if duration_s > 0 else None

            hr_series = [float(x) for x in (stream_data.get("heartrate") or [])]
            avg_hr = int(round(_mean(hr_series))) if hr_series else None
            max_hr = int(round(max(hr_series))) if hr_series else None

            activity = Activity(
                athlete_id=athlete.id,
                name=profile.name,
                start_time=run_start,
                sport="run",
                source="demo",
                provider="demo",
                external_activity_id=f"demo-{uuid4().hex}",
                duration_s=duration_s,
                distance_m=distance_m,
                avg_hr=avg_hr,
                max_hr=max_hr,
                total_elevation_gain=_compute_elevation_gain(stream_data.get("altitude") or []),
                average_speed=avg_speed,
                stream_fetch_status="success",
                stream_fetch_attempted_at=datetime.now(timezone.utc),
                stream_fetch_retry_count=0,
            )
            db.add(activity)
            db.flush()

            stream = ActivityStream(
                activity_id=activity.id,
                stream_data=stream_data,
                channels_available=list(stream_data.keys()),
                point_count=duration_s,
                source="demo",
            )
            db.add(stream)
            db.flush()

            created_splits += _insert_splits(db, activity.id, stream_data)

            ctx = AthleteContext(
                max_hr=athlete.max_hr,
                resting_hr=athlete.resting_hr,
                threshold_hr=athlete.threshold_hr,
                threshold_pace_per_km=athlete.threshold_pace_per_km,
            )
            get_or_compute_analysis(
                activity_id=activity.id,
                stream_row=stream,
                athlete_ctx=ctx,
                db=db,
                force_recompute=True,
                gemini_client=None,
            )
            created_activities += 1

        db.commit()
        print("OK: demo provisioning complete")
        print(f"  activities created: {created_activities}")
        print(f"  splits created: {created_splits}")
        print(f"  login email: {athlete.email}")
        print("  password: (from env var, not printed)")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"ERROR: provisioning failed: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
