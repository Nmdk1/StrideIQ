"""
Generate realistic synthetic athletes and run histories.

Safety contract:
- Writes are ALLOWED ONLY for emails ending with @strideiq.test and starting with synth_real_.
- Default mode is dry-run. Use --execute to write.

Usage (in api container with PYTHONPATH=/app):
  python /app/scripts/generate_realistic_synthetic_population.py --dry-run
  python /app/scripts/generate_realistic_synthetic_population.py --execute --emit-tokens
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from core.database import SessionLocal
from core.security import create_access_token
from models import Activity, Athlete

SYNTH_SOURCE = "synthetic_realistic_v1"
SYNTH_EMAIL_SUFFIX = "@strideiq.test"
SYNTH_EMAIL_PREFIX = "synth_real_"
FOUNDER_EMAIL = "mbshaf@gmail.com"

DISTANCES: List[Tuple[str, int]] = [
    ("5k", 5000),
    ("10k", 10000),
    ("half_marathon", 21097),
    ("marathon", 42195),
]
LEVELS = ["novice", "developing", "intermediate", "advanced", "elite"]

WEEKLY_BY_DISTANCE_LEVEL: Dict[str, Dict[str, float]] = {
    "5k": {"novice": 18, "developing": 28, "intermediate": 42, "advanced": 58, "elite": 76},
    "10k": {"novice": 22, "developing": 34, "intermediate": 50, "advanced": 66, "elite": 84},
    "half_marathon": {"novice": 28, "developing": 40, "intermediate": 56, "advanced": 74, "elite": 94},
    "marathon": {"novice": 34, "developing": 48, "intermediate": 64, "advanced": 82, "elite": 104},
}


@dataclass
class FounderSlice:
    weekly_miles_p50: float
    weekly_miles_p75: float
    easy_pace_sec_mi_p50: int
    easy_pace_sec_mi_p75: int
    long_run_miles_p75: float


def ensure_synthetic_email(email: str) -> None:
    e = (email or "").lower().strip()
    if not e.endswith(SYNTH_EMAIL_SUFFIX) or not e.startswith(SYNTH_EMAIL_PREFIX):
        raise RuntimeError(f"Refusing non-synthetic email write: {email}")


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    x = sorted(values)
    idx = max(0, min(len(x) - 1, int(round((len(x) - 1) * p))))
    return float(x[idx])


def extract_founder_slice(db) -> FounderSlice:
    start = datetime(2025, 5, 1, tzinfo=timezone.utc)
    end = datetime(2025, 11, 30, 23, 59, 59, tzinfo=timezone.utc)
    founder = db.query(Athlete).filter(Athlete.email == FOUNDER_EMAIL).first()
    if founder is None:
        return FounderSlice(42.0, 58.0, 500, 460, 16.0)

    rows = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == founder.id,
            Activity.sport.ilike("run"),
            Activity.start_time >= start,
            Activity.start_time <= end,
        )
        .all()
    )
    if not rows:
        return FounderSlice(42.0, 58.0, 500, 460, 16.0)

    weekly: Dict[date, float] = {}
    easy_paces: List[float] = []
    longs: List[float] = []
    for a in rows:
        miles = float((a.distance_m or 0) / 1609.344)
        wk = (a.start_time.date() - timedelta(days=a.start_time.weekday()))
        weekly[wk] = weekly.get(wk, 0.0) + miles

        wt = (a.workout_type or "").lower()
        if miles >= 3.0 and (a.duration_s or 0) > 0:
            sec_mi = float(a.duration_s) / max(0.1, miles)
            if wt in ("easy_run", "recovery_run", "", "none", None):
                easy_paces.append(sec_mi)
        if miles >= 8.0:
            longs.append(miles)

    weekly_vals = list(weekly.values()) or [42.0, 58.0]
    easy_vals = easy_paces or [500.0, 460.0]
    long_vals = longs or [16.0]
    return FounderSlice(
        weekly_miles_p50=percentile(weekly_vals, 0.50),
        weekly_miles_p75=percentile(weekly_vals, 0.75),
        easy_pace_sec_mi_p50=int(percentile(easy_vals, 0.50)),
        easy_pace_sec_mi_p75=int(percentile(easy_vals, 0.75)),
        long_run_miles_p75=percentile(long_vals, 0.75),
    )


def fmt_pace(sec_mi: float) -> str:
    sec = int(max(1, round(sec_mi)))
    return f"{sec // 60}:{sec % 60:02d}/mi"


def build_archetypes(founder: FounderSlice) -> List[Dict]:
    archetypes: List[Dict] = []

    for distance_key, _ in DISTANCES:
        for level in LEVELS:
            weekly = WEEKLY_BY_DISTANCE_LEVEL[distance_key][level]
            pace_adjust = {
                "novice": +85,
                "developing": +45,
                "intermediate": +5,
                "advanced": -25,
                "elite": -55,
            }[level]
            easy_sec = max(290, founder.easy_pace_sec_mi_p50 + pace_adjust)
            long_base = {
                "5k": min(18.0, max(8.0, weekly * 0.26)),
                "10k": min(20.0, max(9.0, weekly * 0.27)),
                "half_marathon": min(21.0, max(10.0, weekly * 0.29)),
                "marathon": min(24.0, max(12.0, weekly * 0.31)),
            }[distance_key]
            founder_shape_boost = min(4.0, max(0.0, founder.long_run_miles_p75 - 12.0)) * 0.30
            long_miles = round(long_base + founder_shape_boost, 1)

            archetypes.append(
                {
                    "cohort": "founder_shape",
                    "distance": distance_key,
                    "level": level,
                    "weekly_miles": weekly,
                    "easy_sec_mi": easy_sec,
                    "long_miles": long_miles,
                }
            )

    # Non-founder populations: build consistency + volatility + comeback.
    for style in ("consistent", "volatile", "comeback"):
        for distance_key, _ in DISTANCES:
            for level in ("novice", "intermediate", "advanced"):
                weekly = WEEKLY_BY_DISTANCE_LEVEL[distance_key][level]
                if style == "volatile":
                    weekly *= 0.95
                elif style == "comeback":
                    weekly *= 0.90
                easy_sec = {
                    "novice": 620,
                    "intermediate": 485,
                    "advanced": 430,
                }[level]
                if style == "volatile":
                    easy_sec += 18
                archetypes.append(
                    {
                        "cohort": style,
                        "distance": distance_key,
                        "level": level,
                        "weekly_miles": round(weekly, 1),
                        "easy_sec_mi": easy_sec,
                        "long_miles": round(max(7.0, weekly * (0.24 if distance_key in ("5k", "10k") else 0.28)), 1),
                    }
                )
    return archetypes


def add_activity(db, athlete_id, when, miles, sec_mi, workout_type, name, is_race=False):
    duration = int(max(420, miles * sec_mi))
    db.add(
        Activity(
            athlete_id=athlete_id,
            name=name,
            start_time=when,
            sport="run",
            source=SYNTH_SOURCE,
            duration_s=duration,
            distance_m=int(miles * 1609.344),
            workout_type=workout_type,
            is_race_candidate=bool(is_race),
            race_confidence=0.95 if is_race else 0.05,
            user_verified_race=bool(is_race),
        )
    )


def populate_history(db, athlete, cfg, seed: int) -> None:
    rng = random.Random(seed)
    now = datetime.now(timezone.utc)
    distance_key = cfg["distance"]
    weekly_target = float(cfg["weekly_miles"])
    easy_sec = float(cfg["easy_sec_mi"])
    long_miles_target = float(cfg["long_miles"])
    level = cfg["level"]
    cohort = cfg["cohort"]

    # Clear prior synthetic history for this athlete/source.
    db.query(Activity).filter(
        Activity.athlete_id == athlete.id,
        Activity.source == SYNTH_SOURCE,
    ).delete(synchronize_session=False)

    weeks = 30
    quality_days = 1 if level == "novice" else (2 if level in ("developing", "intermediate") else 3)

    for w in range(weeks):
        week_start = now - timedelta(days=(weeks - w) * 7)

        if cohort == "volatile":
            weekly = weekly_target * (0.80 + 0.35 * rng.random())
        elif cohort == "comeback":
            # Recover toward target over first 10 weeks.
            ramp = min(1.0, (w + 1) / 10.0)
            weekly = weekly_target * (0.55 + 0.45 * ramp) * (0.95 + 0.10 * rng.random())
        else:
            weekly = weekly_target * (0.92 + 0.16 * rng.random())

        long_miles = min(long_miles_target * (0.90 + 0.18 * rng.random()), weekly * 0.38)
        long_miles = max(6.0, long_miles)
        quality_miles_each = max(2.0, weekly * (0.07 if quality_days == 1 else 0.09))
        easy_miles_remaining = max(4.0, weekly - long_miles - (quality_days * quality_miles_each))
        easy_days = max(2, 6 - quality_days)
        easy_miles_each = easy_miles_remaining / easy_days

        # Monday recovery / rest
        add_activity(
            db,
            athlete.id,
            week_start + timedelta(days=0),
            miles=max(0.0, easy_miles_each * 0.5),
            sec_mi=easy_sec + 25,
            workout_type="recovery_run",
            name=f"{athlete.display_name} recovery",
            is_race=False,
        )

        # Quality days (Tue/Thu[/Sat])
        q_day_slots = [1, 3, 5][:quality_days]
        for d_idx, d in enumerate(q_day_slots):
            wt = "threshold" if d_idx % 2 == 0 else "intervals"
            add_activity(
                db,
                athlete.id,
                week_start + timedelta(days=d),
                miles=quality_miles_each,
                sec_mi=max(280, easy_sec - (65 if wt == "intervals" else 45)),
                workout_type=wt,
                name=f"{athlete.display_name} {wt}",
                is_race=False,
            )

        # Easy fillers
        filler_days = [2, 4, 6]
        for d in filler_days:
            add_activity(
                db,
                athlete.id,
                week_start + timedelta(days=d),
                miles=easy_miles_each,
                sec_mi=easy_sec + rng.uniform(-12, 16),
                workout_type="easy_run",
                name=f"{athlete.display_name} easy",
                is_race=False,
            )

        # Long run on Sunday override
        add_activity(
            db,
            athlete.id,
            week_start + timedelta(days=6),
            miles=long_miles,
            sec_mi=easy_sec + 5,
            workout_type="long_run",
            name=f"{athlete.display_name} long",
            is_race=False,
        )

    # Final anchor race (9 days ago)
    distance_m = dict(DISTANCES)[distance_key]
    race_miles = distance_m / 1609.344
    race_sec_mi = max(240, easy_sec - 90)
    add_activity(
        db,
        athlete.id,
        now - timedelta(days=9),
        miles=race_miles,
        sec_mi=race_sec_mi,
        workout_type="race",
        name=f"{athlete.display_name} benchmark race",
        is_race=True,
    )


def upsert_athlete(db, cfg) -> Athlete:
    email = f"{SYNTH_EMAIL_PREFIX}{cfg['cohort']}_{cfg['distance']}_{cfg['level']}{SYNTH_EMAIL_SUFFIX}"
    ensure_synthetic_email(email)
    display = f"SynthReal {cfg['cohort']} {cfg['distance']} {cfg['level']}"
    athlete = db.query(Athlete).filter(Athlete.email == email).first()
    if athlete is None:
        athlete = Athlete(
            email=email,
            role="owner",
            display_name=display,
            subscription_tier="subscriber",
            onboarding_completed=True,
            ai_consent=True,
            is_demo=True,
        )
        db.add(athlete)
        db.flush()
    else:
        athlete.role = "owner"
        athlete.display_name = display
        athlete.subscription_tier = "subscriber"
        athlete.onboarding_completed = True
        athlete.ai_consent = True
        athlete.is_demo = True
    return athlete


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--execute", action="store_true", help="Persist to DB")
    p.add_argument("--dry-run", action="store_true", help="Preview only (default)")
    p.add_argument("--emit-tokens", action="store_true", help="Include auth tokens in output")
    p.add_argument("--limit", type=int, default=0, help="Optional cap on number of athletes")
    p.add_argument("--seed", type=int, default=1703)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    execute = bool(args.execute and not args.dry_run)

    db = SessionLocal()
    try:
        founder = extract_founder_slice(db)
        archetypes = build_archetypes(founder)
        if args.limit and args.limit > 0:
            archetypes = archetypes[: args.limit]

        out = []
        for i, cfg in enumerate(archetypes):
            email = f"{SYNTH_EMAIL_PREFIX}{cfg['cohort']}_{cfg['distance']}_{cfg['level']}{SYNTH_EMAIL_SUFFIX}"
            ensure_synthetic_email(email)
            row = {
                "email": email,
                "cohort": cfg["cohort"],
                "distance": cfg["distance"],
                "level": cfg["level"],
                "weekly_miles_target": cfg["weekly_miles"],
                "easy_pace": fmt_pace(cfg["easy_sec_mi"]),
                "long_run_target": cfg["long_miles"],
            }
            if execute:
                athlete = upsert_athlete(db, cfg)
                populate_history(db, athlete, cfg, seed=args.seed + i * 101)
                row["athlete_id"] = str(athlete.id)
                if args.emit_tokens:
                    row["token"] = create_access_token(
                        data={"sub": str(athlete.id), "email": athlete.email, "role": athlete.role}
                    )
            out.append(row)

        if execute:
            db.commit()

        print(
            json.dumps(
                {
                    "mode": "execute" if execute else "dry-run",
                    "count": len(out),
                    "founder_slice": {
                        "weekly_miles_p50": founder.weekly_miles_p50,
                        "weekly_miles_p75": founder.weekly_miles_p75,
                        "easy_pace_p50": fmt_pace(founder.easy_pace_sec_mi_p50),
                        "easy_pace_p75": fmt_pace(founder.easy_pace_sec_mi_p75),
                        "long_run_p75": round(founder.long_run_miles_p75, 1),
                    },
                    "athletes": out,
                },
                indent=2,
            )
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
