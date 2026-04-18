"""
Run Intelligence Synthesis — LLM-powered coaching summary.

Gathers structured data from stream analysis, attribution, splits,
classification, pre-state, wellness, and historical comparison, then
passes it to Kimi to produce a coaching-quality summary that reads
like a knowledgeable human analyzed the run.

Data in, coaching voice out.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import List, Dict, Optional, Any
import json
import logging
import re

from sqlalchemy.orm import Session

from models import Activity, ActivitySplit, CachedStreamAnalysis, CalendarNote
from services.timezone_utils import get_athlete_timezone_from_db, to_activity_local_date

logger = logging.getLogger(__name__)

INTELLIGENCE_MODEL = "kimi-k2.5"
INTELLIGENCE_MAX_TOKENS = 400
INTELLIGENCE_TIMEOUT_S = 30

SYSTEM_PROMPT = """\
You are the intelligence voice of a running analytics product. You write \
2-4 sentences that a serious runner would find genuinely useful — the kind \
of observation a coach who watched the whole run would make.

Rules:
- ONLY describe what the data shows. Never speculate about what "should have" \
happened, what was "planned," or why data is missing. If there are 4 reps, \
there are 4 reps. Do not infer planned rep counts from workout names or titles.
- If `intervals.derived_from_pace` is true, the rep structure was inferred \
from the pace pattern of the splits because the watch did not tag reps \
explicitly. The reps are real and the paces are accurate, but if there is \
genuine ambiguity about rep boundaries you may say "around N reps". Never \
mention "the algorithm" or "we inferred" -- just describe the workout.
- If `intervals.cooldown` is present, the trailing slow split was a deliberate \
cooldown (HR dropped, pace eased, athlete chose to ease off). Do NOT describe \
it as fading, hitting a wall, or losing form. You may briefly note the cooldown \
when contextually useful, but the run "ended" with the last work rep.
- If `workout_name` is present, treat it as informational only. Do NOT use it \
to infer planned rep counts, distances, or paces. Reps are what the data shows, \
not what the name suggests.
- If `shape_classification` is present, it is the stream analyzer's bucket \
for this run's structural shape (e.g. "intervals", "tempo", "anomaly", \
"long_run"). Use it as a sanity check; don't quote it.
- Never state the obvious (distance, duration, avg pace) — the athlete sees those.
- Focus on what THIS run reveals: pacing execution, cardiac response, \
rep quality, drift, fade, efficiency trends, conditions impact.
- Reference specific data: rep numbers, pace values, HR numbers, percentages.
- If reps were busted/incomplete, say which ones and what it means for the session.
- If historical comparison data exists, USE it — that's the insight the athlete can't see.
- If pre-state data exists (sleep, HRV, resting HR), connect it to the run \
outcome ONLY if there's a plausible link. Don't force it.
- Heat stress for runners is driven by DEW POINT, not temperature alone. \
When dew_point_f is present, lead with it for any heat discussion. \
Runner-meaningful dew-point thresholds (deg F): <50 comfortable, 50-55 ok, \
55-60 noticeable, 60-65 hard, 65-70 very hard, 70+ dangerous. The combined \
value (temp_plus_dew_combined) is the input to the validated heat-adjustment \
model: <120 negligible, 120-140 light, 140-150 moderate, 150-160 significant, \
160-170 hard, 170+ severe. heat_adjustment_pct is the model's estimate of \
how much slower an athlete's normal pace becomes in those conditions -- when \
present, use it to contextualize HR escalation or pace fade.
- Never use generic motivational language. No "great job" or "keep it up".
- Never say "based on the data" or "analysis shows" — just say the thing.
- Never speculate about causes you can't observe (missed lap buttons, \
stumbles, watch malfunctions). Describe what happened, not why.
- If there's nothing meaningful to say, respond with exactly: NO_INSIGHT
- Write in second person ("you", "your").
- Be direct. Every word should carry information.\
"""


@dataclass
class IntelligenceHighlight:
    label: str
    value: str
    color: str = "slate"


@dataclass
class RunIntelligenceResult:
    headline: str
    body: str
    highlights: List[IntelligenceHighlight] = field(default_factory=list)


def _fmt_pace_per_mile(seconds_per_km: float) -> str:
    spm = seconds_per_km * 1.60934
    mins = int(spm // 60)
    secs = int(spm % 60)
    return f"{mins}:{secs:02d}/mi"


def _fmt_duration(seconds: float) -> str:
    s = int(seconds)
    hrs = s // 3600
    mins = (s % 3600) // 60
    secs = s % 60
    if hrs > 0:
        return f"{hrs}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"


def _fmt_distance_mi(meters: float) -> str:
    mi = meters / 1609.34
    return f"{mi:.1f}"


def _workout_label(wt: Optional[str]) -> str:
    if not wt:
        return "run"
    labels = {
        "easy_run": "easy run",
        "recovery": "recovery run",
        "long_run": "long run",
        "long_run_quality": "long run with quality",
        "tempo": "tempo",
        "interval": "interval session",
        "race": "race",
        "moderate": "moderate run",
        "pacing": "pacing effort",
    }
    return labels.get(wt.lower(), wt.lower().replace("_", " "))


# Canonical set of workout types that are structured as discrete reps.
# Source: WORKOUT_TYPE_OPTIONS in routers/activity_workout_type.py.  Anything
# here should be analyzed as reps, not as a continuous run, even if the watch
# did not tag splits with lap_type='work'.  Excludes fartlek (pace pattern too
# irregular) and strides (too short to read as reps).
INTERVAL_WORKOUT_TYPES = frozenset({
    "interval",            # legacy / generic
    "intervals",           # legacy / generic
    "track",               # legacy
    "track_workout",
    "tempo_intervals",
    "cruise_intervals",
    "vo2max_intervals",
    "hill_repetitions",
})


# Values of run_shape.summary.workout_classification (from
# services.shape_extractor._derive_classification) that mean "this run had
# structured work, treat it as intervals downstream".  Easy/long/gray
# classifications are deliberately excluded so we never run pace-pattern
# rep detection on a steady run.
STRUCTURED_SHAPE_CLASSIFICATIONS = frozenset({
    "anomaly",                # shape doesn't fit any clean bucket — usually intervals
    "intervals",
    "track_intervals",
    "threshold_intervals",
    "tempo",
    "over_under",
    "hill_repeats",
    "progression",
    "fartlek",
})


# Pattern matches "N x M unit" rep notation common in Garmin / TrainingPeaks
# workout names.  Examples: "4 x 1 mile", "8x400m", "2 x 2 x mile",
# "3x1k", "10 x 200m".  The unit is required to avoid false positives
# like "Marathon prep x 2" or "Run x easy".
_REP_NOTATION_RE = re.compile(
    r"\b\d+\s*[x×]\s*(?:\d+\s*[x×]\s*)?"
    r"(?:\d+\s*)?"
    r"(?:m|mi|mile|miles|k|km|kilometers|metres|meters|min|minutes|sec|seconds|s)\b",
    re.IGNORECASE,
)

# Unit-less track-distance pattern.  Garmin / Strava names commonly drop
# the unit when the second number is a canonical track distance.  Examples
# that must match: "6x800", "10 x 400", "8x1600".  Won't match "1x2" or
# "training x 4".
_REP_TRACK_DISTANCE_RE = re.compile(
    r"\b\d{1,3}\s*[x×]\s*"
    r"(?:200|300|400|500|600|800|1000|1200|1500|1600|2000|3000|5000|10000)\b",
    re.IGNORECASE,
)

# Standalone keywords that almost always indicate structured work when they
# appear in a workout name.  "tempo" alone is intentionally excluded -- a
# "tempo" workout might be a continuous tempo run, which the existing gate
# handles correctly via _get_split_pacing.  "track" alone is also excluded
# (could be the venue, not the structure).
_STRUCTURED_NAME_KEYWORDS = (
    "interval",
    "intervals",
    "repeat",
    "repeats",
    "repetition",
    "fartlek",
    "hill repeat",
    "hill repeats",
    "mile repeats",
    "track intervals",
    "track repeats",
    "threshold intervals",
    "cruise intervals",
)


def _workout_name_suggests_intervals(name: Optional[str]) -> bool:
    """Pure-string parser. True if the workout name contains either a
    rep-notation pattern (e.g. "4 x 1 mile") or a structured-workout
    keyword (e.g. "intervals", "repeats")."""
    if not name:
        return False
    text = name.lower()
    if _REP_NOTATION_RE.search(name):
        return True
    if _REP_TRACK_DISTANCE_RE.search(name):
        return True
    return any(kw in text for kw in _STRUCTURED_NAME_KEYWORDS)


def _shape_classification(activity: Activity) -> Optional[str]:
    """Pull workout_classification out of Activity.run_shape JSONB safely."""
    rs = getattr(activity, "run_shape", None)
    if not isinstance(rs, dict):
        return None
    summary = rs.get("summary")
    if not isinstance(summary, dict):
        return None
    cls = summary.get("workout_classification")
    return cls if isinstance(cls, str) else None


def _is_interval_workout(activity: Activity) -> bool:
    """Multi-signal gate. True if any of:
    1. Explicit workout_type is in the canonical interval set
    2. run_shape classification says this had structured work
    3. The workout name uses rep notation or a structured-workout keyword

    History (the bug that drove this expansion): the founder's 2026-04-18
    run had workout_type=NULL, run_shape=anomaly, name="Meridian - 2 x 2
    x mile", and split data showing a textbook 4x1mi session.  The old
    workout_type-only gate said "no", so the LLM got pacing-decay context
    and described the planned cooldown mile as "hitting a wall".
    """
    wt = getattr(activity, "workout_type", None)
    if wt and wt.lower() in INTERVAL_WORKOUT_TYPES:
        return True

    cls = _shape_classification(activity)
    if cls and cls in STRUCTURED_SHAPE_CLASSIFICATIONS:
        return True

    name = getattr(activity, "name", None)
    if _workout_name_suggests_intervals(name):
        return True

    return False


# ── Cooldown labeling ──────────────────────────────────────────────────
#
# A trailing split is labeled cooldown ONLY if all four hold:
#   1. Position: comes after the last detected work rep
#   2. Pace:     slower than the avg work-rep pace
#   3. HR drop:  avg HR >= COOLDOWN_HR_DROP_BPM below avg work-rep HR
#   4. Substantial: distance >= COOLDOWN_MIN_DISTANCE_M
#                   OR duration >= COOLDOWN_MIN_DURATION_S
#
# HR drop is the load-bearing signal because cardiac response can't be
# faked -- it only drops when the athlete genuinely eases off.  Pace alone
# doesn't work because cruise-interval floats look identical to true
# cooldowns pace-wise.

COOLDOWN_HR_DROP_BPM = 12
COOLDOWN_MIN_DISTANCE_M = 644   # 0.4 mi
COOLDOWN_MIN_DURATION_S = 180   # 3 min
# Cooldown is jogging, not walking.  Anything slower than 3x the work pace
# is a between-rep recovery walk (e.g. 38:00/mi after a 6:00/mi rep is
# clearly walking, not winding down).
COOLDOWN_MAX_PACE_MULTIPLIER = 3.0


def _label_cooldown(
    reps: List[Dict[str, Any]],
    splits: List[Any],
) -> Optional[Dict[str, Any]]:
    """Find the post-rep cooldown split, if any. Returns a dict with
    split_number, distance_m, elapsed_s, pace_per_mile, pace_s_km, avg_hr.
    Returns None when no trailing split meets all four cooldown gates."""
    if not reps or not splits:
        return None

    work_hrs = [r["avg_hr"] for r in reps if r.get("avg_hr")]
    work_paces = [r["pace_s_km"] for r in reps if r.get("pace_s_km")]
    if not work_hrs or not work_paces:
        return None
    avg_work_hr = sum(work_hrs) / len(work_hrs)
    avg_work_pace = sum(work_paces) / len(work_paces)

    last_rep_split = max(
        (r.get("split_number") for r in reps if r.get("split_number") is not None),
        default=None,
    )
    if last_rep_split is None:
        return None

    # Walk the splits AFTER the last rep and find the LAST one that
    # satisfies all four gates.  A cooldown is by convention the closing
    # wind-down -- when there's a recovery jog AND a cooldown after the
    # last rep (founder's 2026-04-18 case: split 17 = 0.10mi recovery
    # jog, split 18 = 0.99mi cooldown), the cooldown is the trailing
    # piece.  Picking the last qualifying split also naturally filters
    # out tail debris (sub-50m fragments fail the substantial gate).
    candidate = None
    for s in splits:
        sn = getattr(s, "split_number", None)
        if sn is None or sn <= last_rep_split:
            continue
        dist = float(s.distance) if s.distance else 0.0
        elapsed = float(s.elapsed_time) if s.elapsed_time else 0.0
        if dist < 50 or elapsed <= 0:
            continue
        if dist < COOLDOWN_MIN_DISTANCE_M and elapsed < COOLDOWN_MIN_DURATION_S:
            continue

        hr = s.average_heartrate
        if hr is None:
            continue
        if (avg_work_hr - float(hr)) < COOLDOWN_HR_DROP_BPM:
            continue

        pace = elapsed / (dist / 1000)
        if pace <= avg_work_pace:
            # "Cooldown" must be at least as slow as the work pace.
            continue
        if pace > avg_work_pace * COOLDOWN_MAX_PACE_MULTIPLIER:
            # Walking-pace recovery between reps -- not a cooldown.
            continue

        candidate = {
            "split_number": sn,
            "distance_m": round(dist),
            "elapsed_s": round(elapsed, 1),
            "pace_per_mile": _fmt_pace_per_mile(pace),
            "pace_s_km": round(pace, 1),
            "avg_hr": int(hr),
        }

    return candidate


# ── Data gathering ─────────────────────────────────────────────────────


def _derive_reps_from_unmarked_splits(splits) -> Optional[List[Dict[str, Any]]]:
    """
    When the watch did not tag splits with lap_type='work' (the common Garmin
    case for cruise intervals, tempo intervals, and any "fake" interval done
    without a structured workout file), reconstruct the rep structure from the
    pace pattern of the splits.

    Algorithm
    ---------
    1. Compute pace_s_km for every split with usable distance/time.
    2. Find the largest gap in the lower (faster) half of the sorted paces;
       splits faster than that gap are work candidates, the rest are
       warmup/recovery/cooldown.
    3. Group consecutive work-candidate splits into reps (a slow split between
       two fast clusters breaks the rep).
    4. For each rep, sum distance + time, derive pace and time-weighted HR.

    The watch's 1-mile auto-lap habit chops a single ~10-min rep into two
    consecutive fast splits; merging via "consecutive work-candidate" handles
    that natively.

    Returns a list of rep dicts in the same shape as the lap_type='work' path,
    or None if the pattern is too ambiguous to read confidently.
    """
    candidates = []
    for s in splits:
        if not s.distance or not s.elapsed_time:
            continue
        dist = float(s.distance)
        elapsed = float(s.elapsed_time)
        if dist < 100 or elapsed <= 0:
            continue
        pace = elapsed / (dist / 1000)
        candidates.append({
            "split": s,
            "distance_m": dist,
            "elapsed_s": elapsed,
            "pace_s_km": pace,
        })

    if len(candidates) < 4:
        return None

    paces_sorted = sorted(c["pace_s_km"] for c in candidates)
    n = len(paces_sorted)
    gaps = [
        (paces_sorted[i + 1] - paces_sorted[i], paces_sorted[i], paces_sorted[i + 1])
        for i in range(n // 2)
    ]
    if not gaps:
        return None
    best_gap, lo_edge, hi_edge = max(gaps, key=lambda g: g[0])

    fastest = paces_sorted[0]
    if best_gap < max(20.0, fastest * 0.10):
        return None

    work_threshold = lo_edge

    in_rep = False
    rep_splits: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    for c in candidates:
        if c["pace_s_km"] <= work_threshold:
            current.append(c)
            in_rep = True
        else:
            if in_rep and current:
                rep_splits.append(current)
                current = []
            in_rep = False
    if current:
        rep_splits.append(current)

    if len(rep_splits) < 2:
        return None

    reps: List[Dict[str, Any]] = []
    for i, group in enumerate(rep_splits):
        total_dist = sum(g["distance_m"] for g in group)
        total_elapsed = sum(g["elapsed_s"] for g in group)
        pace = total_elapsed / (total_dist / 1000)

        hr_num = 0.0
        hr_den = 0.0
        for g in group:
            sp = g["split"]
            if sp.average_heartrate:
                hr_num += float(sp.average_heartrate) * g["elapsed_s"]
                hr_den += g["elapsed_s"]
        avg_hr = int(round(hr_num / hr_den)) if hr_den > 0 else None

        last_split_num = group[-1]["split"].split_number if group else None

        reps.append({
            "rep": i + 1,
            "distance_m": round(total_dist),
            "elapsed_s": round(total_elapsed, 1),
            "pace_per_mile": _fmt_pace_per_mile(pace),
            "pace_s_km": round(pace, 1),
            "avg_hr": avg_hr,
            "split_number": last_split_num,
        })

    return reps


def _get_interval_analysis(activity: Activity, db: Session) -> Optional[Dict[str, Any]]:
    splits = (
        db.query(ActivitySplit)
        .filter(ActivitySplit.activity_id == activity.id)
        .order_by(ActivitySplit.split_number)
        .all()
    )

    work_splits = [
        s for s in splits
        if s.lap_type == "work"
        and s.distance and float(s.distance) > 0
        and s.elapsed_time and float(s.elapsed_time) > 0
    ]

    derived_from_pace = False
    if len(work_splits) >= 2:
        reps = []
        for i, s in enumerate(work_splits):
            dist = float(s.distance)
            elapsed = float(s.elapsed_time)
            pace_s_km = elapsed / (dist / 1000)
            hr = int(s.average_heartrate) if s.average_heartrate else None
            reps.append({
                "rep": i + 1,
                "distance_m": round(dist),
                "elapsed_s": round(elapsed, 1),
                "pace_per_mile": _fmt_pace_per_mile(pace_s_km),
                "pace_s_km": round(pace_s_km, 1),
                "avg_hr": hr,
                "split_number": getattr(s, "split_number", None),
            })
    else:
        derived = _derive_reps_from_unmarked_splits(splits)
        if not derived:
            return None
        reps = derived
        derived_from_pace = True

    all_paces = [r["pace_s_km"] for r in reps]
    sorted_paces = sorted(all_paces)
    median_pace = sorted_paces[len(sorted_paces) // 2]

    for r in reps:
        r["busted"] = r["pace_s_km"] > median_pace * 1.30

    clean_paces = [r["pace_s_km"] for r in reps if not r["busted"]]
    if not clean_paces:
        clean_paces = all_paces
        for r in reps:
            r["busted"] = False

    avg_pace = sum(clean_paces) / len(clean_paces)
    spreads = [abs((p - avg_pace) / avg_pace * 100) for p in clean_paces]
    max_spread = max(spreads) if spreads else 0

    history = _get_interval_history(activity, reps[0]["distance_m"], db)

    # Cooldown labeling: only the clean (non-busted) reps define what "work"
    # looked like.  Otherwise a busted rep would drag the work-HR baseline
    # down and cause us to under-call cooldowns.
    clean_reps = [r for r in reps if not r["busted"]]
    cooldown = _label_cooldown(clean_reps or reps, splits)

    result = {
        "type": "interval",
        "reps": reps,
        "clean_avg_pace_per_mile": _fmt_pace_per_mile(avg_pace),
        "clean_avg_pace_s_km": avg_pace,
        "max_spread_pct": round(max_spread, 1),
        "total_reps": len(reps),
        "clean_reps": len(clean_paces),
        "busted_reps": [r["rep"] for r in reps if r["busted"]],
        "avg_hr_work": round(sum(r["avg_hr"] for r in reps if r["avg_hr"]) / max(1, sum(1 for r in reps if r["avg_hr"]))) if any(r["avg_hr"] for r in reps) else None,
        "history": history,
        "derived_from_pace": derived_from_pace,
    }
    if cooldown is not None:
        result["cooldown"] = cooldown
    return result


def _get_interval_history(
    activity: Activity, rep_distance_m: float, db: Session
) -> Optional[Dict[str, Any]]:
    end_date = activity.start_time
    start_date = end_date - timedelta(days=120)

    prev_activities = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == activity.athlete_id,
            Activity.id != activity.id,
            Activity.start_time >= start_date,
            Activity.start_time < end_date,
            Activity.workout_type.in_(["interval", "intervals", "track", "track_workout"]),
        )
        .order_by(Activity.start_time.desc())
        .limit(10)
        .all()
    )

    dist_lo = rep_distance_m * 0.80
    dist_hi = rep_distance_m * 1.20

    for prev in prev_activities:
        prev_work = (
            db.query(ActivitySplit)
            .filter(
                ActivitySplit.activity_id == prev.id,
                ActivitySplit.lap_type == "work",
                ActivitySplit.distance.isnot(None),
                ActivitySplit.elapsed_time.isnot(None),
            )
            .all()
        )
        if len(prev_work) < 2:
            continue

        prev_dists = [float(s.distance) for s in prev_work]
        prev_avg_dist = sum(prev_dists) / len(prev_dists)
        if not (dist_lo <= prev_avg_dist <= dist_hi):
            continue

        prev_paces = [
            float(s.elapsed_time) / (float(s.distance) / 1000)
            for s in prev_work
        ]
        sorted_pp = sorted(prev_paces)
        prev_median = sorted_pp[len(sorted_pp) // 2]
        prev_clean = [p for p in prev_paces if p <= prev_median * 1.30]
        if not prev_clean:
            continue

        prev_avg = sum(prev_clean) / len(prev_clean)
        return {
            "prev_avg_pace_per_mile": _fmt_pace_per_mile(prev_avg),
            "prev_avg_pace_s_km": prev_avg,
            "prev_date": to_activity_local_date(prev, get_athlete_timezone_from_db(db, activity.athlete_id)).isoformat(),
            "prev_reps": len(prev_clean),
            "prev_total_reps": len(prev_paces),
        }

    return None


def _get_split_pacing(activity: Activity, db: Session) -> Optional[Dict[str, Any]]:
    if _is_interval_workout(activity):
        return None

    splits = (
        db.query(ActivitySplit)
        .filter(ActivitySplit.activity_id == activity.id)
        .order_by(ActivitySplit.split_number)
        .all()
    )
    valid = [
        s for s in splits
        if s.distance and s.elapsed_time and float(s.elapsed_time) > 0
    ]
    if len(valid) < 3:
        return None

    per_split = []
    for i, s in enumerate(valid):
        dist = float(s.distance)
        elapsed = float(s.elapsed_time)
        pace_s_km = elapsed / (dist / 1000)
        per_split.append({
            "split": i + 1,
            "distance_m": round(dist),
            "pace_per_mile": _fmt_pace_per_mile(pace_s_km),
            "pace_s_km": round(pace_s_km, 1),
        })

    paces = [s["pace_s_km"] for s in per_split]
    mid = len(paces) // 2
    first_avg = sum(paces[:mid]) / mid
    second_avg = sum(paces[mid:]) / (len(paces) - mid)
    decay_pct = ((second_avg - first_avg) / first_avg) * 100 if first_avg > 0 else 0

    return {
        "type": "continuous",
        "splits": per_split,
        "first_half_avg_pace": _fmt_pace_per_mile(first_avg),
        "second_half_avg_pace": _fmt_pace_per_mile(second_avg),
        "decay_pct": round(decay_pct, 1),
    }


def _get_stream_drift(activity_id, db: Session) -> Optional[Dict[str, Any]]:
    from services.stream_analysis_cache import CURRENT_ANALYSIS_VERSION

    row = (
        db.query(CachedStreamAnalysis.result_json)
        .filter(
            CachedStreamAnalysis.activity_id == activity_id,
            CachedStreamAnalysis.analysis_version == CURRENT_ANALYSIS_VERSION,
        )
        .first()
    )
    if not row or not row[0]:
        return None

    result = row[0]
    drift = result.get("drift")
    if not drift:
        return None

    return {
        "cardiac_drift_pct": drift.get("cardiac_pct"),
        "pace_drift_pct": drift.get("pace_pct"),
    }


def _get_efficiency_vs_peers(activity: Activity, db: Session) -> Optional[Dict[str, Any]]:
    if not activity.avg_hr or activity.avg_hr < 100:
        return None
    if not activity.distance_m or not activity.duration_s:
        return None
    if not activity.workout_type:
        return None

    speed_mps = activity.distance_m / activity.duration_s
    this_ef = speed_mps / float(activity.avg_hr)

    end_date = activity.start_time
    start_date = end_date - timedelta(days=90)

    peers = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == activity.athlete_id,
            Activity.id != activity.id,
            Activity.avg_hr.isnot(None),
            Activity.avg_hr > 100,
            Activity.distance_m > 1000,
            Activity.duration_s > 0,
            Activity.start_time >= start_date,
            Activity.start_time < end_date,
            Activity.workout_type == activity.workout_type,
        )
        .all()
    )
    if len(peers) < 2:
        return None

    peer_efs = [
        (p.distance_m / p.duration_s) / float(p.avg_hr) for p in peers
    ]
    avg_ef = sum(peer_efs) / len(peer_efs)
    diff_pct = ((this_ef - avg_ef) / avg_ef) * 100 if avg_ef > 0 else 0

    return {
        "diff_pct": round(diff_pct, 1),
        "sample_size": len(peers),
        "workout_type": activity.workout_type.lower().replace("_", " "),
    }


def _get_drift_history_avg(activity: Activity, db: Session) -> Optional[Dict[str, Any]]:
    from services.run_analysis_engine import CONTROLLED_STEADY_TYPES
    from services.stream_analysis_cache import CURRENT_ANALYSIS_VERSION

    wt = getattr(activity, "workout_type", None)
    if not wt or wt.lower() not in CONTROLLED_STEADY_TYPES:
        return None

    end_date = activity.start_time
    start_date = end_date - timedelta(days=90)

    rows = (
        db.query(CachedStreamAnalysis.result_json)
        .join(Activity, Activity.id == CachedStreamAnalysis.activity_id)
        .filter(
            Activity.athlete_id == activity.athlete_id,
            Activity.id != activity.id,
            Activity.start_time >= start_date,
            Activity.start_time < end_date,
            Activity.workout_type.in_(CONTROLLED_STEADY_TYPES),
            CachedStreamAnalysis.analysis_version == CURRENT_ANALYSIS_VERSION,
        )
        .all()
    )

    drifts = []
    for (rj,) in rows:
        d = rj.get("drift") if rj else None
        cp = d.get("cardiac_pct") if d else None
        if cp is not None:
            drifts.append(cp)

    if len(drifts) < 3:
        return None

    return {
        "avg_cardiac_drift_pct": round(sum(drifts) / len(drifts), 1),
        "count": len(drifts),
    }


def _get_athlete_notes(activity: Activity, db: Session) -> Optional[str]:
    """Fetch athlete's calendar notes for this activity's date."""
    run_date = to_activity_local_date(activity, get_athlete_timezone_from_db(db, activity.athlete_id))
    notes = (
        db.query(CalendarNote)
        .filter(
            CalendarNote.athlete_id == activity.athlete_id,
            CalendarNote.note_date == run_date,
        )
        .all()
    )
    if not notes:
        return None

    parts = []
    for n in notes:
        if n.text_content:
            parts.append(n.text_content)
        if n.voice_memo_transcript:
            parts.append(n.voice_memo_transcript)
        if n.structured_data:
            for k, v in n.structured_data.items():
                if v:
                    parts.append(f"{k}: {v}")
    return " | ".join(parts) if parts else None


def _get_pre_state(activity: Activity) -> Optional[Dict[str, Any]]:
    state = {}
    if activity.pre_sleep_h is not None:
        state["sleep_hours"] = float(activity.pre_sleep_h)
    if activity.pre_sleep_score is not None:
        state["sleep_score"] = int(activity.pre_sleep_score)
    if activity.pre_resting_hr is not None:
        state["resting_hr"] = int(activity.pre_resting_hr)
    if activity.pre_recovery_hrv is not None:
        state["recovery_hrv"] = int(activity.pre_recovery_hrv)
    if activity.pre_overnight_hrv is not None:
        state["overnight_hrv"] = int(activity.pre_overnight_hrv)
    return state if state else None


# ── Assembly & LLM call ────────────────────────────────────────────────


def _build_data_context(activity: Activity, db: Session) -> Dict[str, Any]:
    """Assemble all structured data into a single dict for the LLM prompt."""
    pace_s_km = activity.duration_s / (activity.distance_m / 1000)
    is_interval = _is_interval_workout(activity)

    ctx: Dict[str, Any] = {
        "date": activity.start_time.strftime("%Y-%m-%d"),
        "workout_type": _workout_label(activity.workout_type),
        "distance_miles": round(activity.distance_m / 1609.34, 2),
        "duration": _fmt_duration(activity.duration_s),
        "avg_pace_per_mile": _fmt_pace_per_mile(pace_s_km),
        "avg_hr": int(activity.avg_hr) if activity.avg_hr else None,
        "max_hr": int(activity.max_hr) if activity.max_hr else None,
    }

    # Surface the raw workout name and shape classification.  The LLM uses
    # these for context only -- the SYSTEM_PROMPT forbids inferring planned
    # rep counts from names.  But when our gate misfires, the LLM at least
    # sees the truth in front of it instead of a contradicting summary.
    name = getattr(activity, "name", None)
    if name:
        ctx["workout_name"] = name
    cls = _shape_classification(activity)
    if cls:
        ctx["shape_classification"] = cls

    elev = getattr(activity, "total_elevation_gain", None)
    if elev and float(elev) > 30:
        ctx["elevation_gain_ft"] = int(float(elev) * 3.28084)

    is_race = getattr(activity, "is_race_candidate", False) or (
        activity.workout_type and activity.workout_type.lower() == "race"
    )
    if is_race:
        ctx["is_race"] = True

    # Weather block.  Dew point is the *actual* heat-stress signal runners use
    # (temperature alone is misleading -- 83 F with 30 F dew point feels
    # totally different from 83 F with 65 F dew point).  We also surface the
    # combined value (temp + dew point) used by services/heat_adjustment.py,
    # because that is the validated model behind heat_adjustment_pct.
    temp = getattr(activity, "temperature_f", None)
    if temp:
        ctx["temperature_f"] = round(float(temp))
    humidity = getattr(activity, "humidity_pct", None)
    if humidity:
        ctx["humidity_pct"] = round(float(humidity))
    dew_point = getattr(activity, "dew_point_f", None)
    if dew_point is not None:
        ctx["dew_point_f"] = round(float(dew_point), 1)
        if temp:
            ctx["temp_plus_dew_combined"] = round(float(temp) + float(dew_point), 1)
    # heat_adjustment_pct is stored as a fraction (0.0304 == 3.04% slowdown).
    # Convert to a percent for the LLM, and surface anything >= 1% (which
    # corresponds to a Combined Value >= ~125 -- noticeable for any quality work).
    heat_adj = getattr(activity, "heat_adjustment_pct", None)
    if heat_adj is not None and float(heat_adj) >= 0.01:
        ctx["heat_adjustment_pct"] = round(float(heat_adj) * 100, 1)

    if is_interval:
        interval_data = _get_interval_analysis(activity, db)
        if interval_data:
            ctx["intervals"] = interval_data
    else:
        pacing = _get_split_pacing(activity, db)
        if pacing:
            ctx["pacing"] = pacing

    drift = _get_stream_drift(activity.id, db)
    if drift:
        ctx["cardiac_drift"] = drift

    efficiency = _get_efficiency_vs_peers(activity, db)
    if efficiency:
        ctx["efficiency_vs_recent"] = efficiency

    drift_hist = _get_drift_history_avg(activity, db)
    if drift_hist:
        ctx["drift_history"] = drift_hist

    pre_state = _get_pre_state(activity)
    if pre_state:
        ctx["pre_run_state"] = pre_state

    notes = _get_athlete_notes(activity, db)
    if notes:
        ctx["athlete_notes"] = notes

    cadence = getattr(activity, "avg_cadence", None)
    if cadence:
        ctx["avg_cadence"] = int(cadence)

    return ctx


def _build_headline(activity: Activity, interval_data: Optional[Dict]) -> str:
    pace_s_km = activity.duration_s / (activity.distance_m / 1000)
    pace_str = _fmt_pace_per_mile(pace_s_km)
    dist_str = _fmt_distance_mi(activity.distance_m)
    dist_mi = activity.distance_m / 1609.34
    duration_str = _fmt_duration(activity.duration_s)
    wt_label = _workout_label(activity.workout_type)

    is_race = getattr(activity, "is_race_candidate", False) or (
        activity.workout_type and activity.workout_type.lower() == "race"
    )

    if interval_data:
        clean = interval_data["clean_reps"]
        total = interval_data["total_reps"]
        avg_dist = interval_data["reps"][0]["distance_m"] if interval_data["reps"] else 0
        avg_pace = interval_data["clean_avg_pace_per_mile"]
        if interval_data["busted_reps"]:
            return f"{clean} of {total} reps at {avg_dist}m, {avg_pace} avg — {wt_label}."
        return f"{total}x{avg_dist}m at {avg_pace} avg — {wt_label}."

    if is_race and dist_mi >= 13.0:
        return f"{dist_str} mi in {duration_str} — {wt_label}."
    return f"{dist_str} mi at {pace_str} — {wt_label}."


def _build_highlights(
    activity: Activity,
    drift: Optional[Dict],
    pacing: Optional[Dict],
    efficiency: Optional[Dict],
    interval_data: Optional[Dict] = None,
) -> List[IntelligenceHighlight]:
    hl: List[IntelligenceHighlight] = []

    if interval_data:
        spread = interval_data["max_spread_pct"]
        clean = interval_data["clean_reps"]
        total = interval_data["total_reps"]
        busted = interval_data["busted_reps"]

        if clean >= 2:
            color = "emerald" if spread <= 2 else "green" if spread <= 5 else "yellow" if spread <= 10 else "orange"
            hl.append(IntelligenceHighlight(
                label="Rep Consistency", value=f"{spread:.1f}% spread", color=color
            ))

        rep_label = f"{clean}/{total}" if busted else str(total)
        hl.append(IntelligenceHighlight(label="Reps", value=rep_label))

        if interval_data.get("avg_hr_work"):
            hl.append(IntelligenceHighlight(
                label="Avg HR (work)", value=f"{int(interval_data['avg_hr_work'])} bpm"
            ))
    else:
        if activity.avg_hr:
            hl.append(IntelligenceHighlight(
                label="Avg HR", value=f"{int(activity.avg_hr)} bpm"
            ))

    if drift and drift.get("cardiac_drift_pct") is not None:
        cp = drift["cardiac_drift_pct"]
        color = "emerald" if abs(cp) <= 3 else "yellow" if abs(cp) <= 5 else "orange"
        hl.append(IntelligenceHighlight(
            label="Cardiac Drift", value=f"{cp:+.1f}%", color=color
        ))

    if pacing and pacing.get("decay_pct") is not None:
        d = pacing["decay_pct"]
        color = "emerald" if d < -1 else "green" if d <= 3 else "yellow" if d <= 6 else "orange"
        hl.append(IntelligenceHighlight(
            label="Pacing", value=f"{d:+.1f}%", color=color
        ))

    if efficiency:
        d = efficiency["diff_pct"]
        color = "emerald" if d > 3 else "green" if d > 0 else "yellow" if d > -3 else "orange"
        hl.append(IntelligenceHighlight(
            label="Efficiency", value=f"{d:+.1f}% vs recent", color=color
        ))

    elev = getattr(activity, "total_elevation_gain", None)
    if elev and float(elev) > 30:
        ft = int(float(elev) * 3.28084)
        hl.append(IntelligenceHighlight(
            label="Elevation", value=f"{ft:,}ft"
        ))

    return hl


def _call_intelligence_llm(data_context: Dict[str, Any]) -> Optional[str]:
    """Send structured data to Kimi and get coaching summary back."""
    from core.llm_client import call_llm

    user_prompt = (
        "Here is the structured data for this run. Write a coaching-quality "
        "summary (2-4 sentences). Reference specific numbers. "
        "If reps were busted, explain what happened and what it means. "
        "If there's historical data, compare. If conditions affected the run, say how.\n\n"
        f"{json.dumps(data_context, indent=2, default=str)}"
    )

    try:
        result = call_llm(
            model=INTELLIGENCE_MODEL,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=INTELLIGENCE_MAX_TOKENS,
            temperature=0.4,
            response_mode="text",
            timeout_s=INTELLIGENCE_TIMEOUT_S,
            disable_thinking=True,
        )
        text = (result["text"] or "").strip()
        if not text or text == "NO_INSIGHT":
            return None
        logger.info(
            "Run intelligence LLM: model=%s in=%d out=%d lat=%.0fms",
            result["model"], result["input_tokens"],
            result["output_tokens"], result["latency_ms"],
        )
        return text
    except Exception:
        logger.exception("Run intelligence LLM call failed")
        return None


# ── Public API ─────────────────────────────────────────────────────────


def generate_run_intelligence(
    activity_id: str,
    athlete_id: str,
    db: Session,
) -> Optional[RunIntelligenceResult]:
    """
    Main entry point. Gathers structured data, calls Kimi for the
    coaching summary, and returns headline + body + highlights.
    """
    activity = (
        db.query(Activity)
        .filter(Activity.id == activity_id, Activity.athlete_id == athlete_id)
        .first()
    )
    if not activity:
        return None

    if not activity.distance_m or not activity.duration_s:
        return None

    try:
        data_ctx = _build_data_context(activity, db)

        interval_data = data_ctx.get("intervals")
        pacing = data_ctx.get("pacing")
        drift = data_ctx.get("cardiac_drift")
        efficiency = data_ctx.get("efficiency_vs_recent")

        headline = _build_headline(activity, interval_data)
        highlights = _build_highlights(activity, drift, pacing, efficiency, interval_data)

        body = _call_intelligence_llm(data_ctx)

        if not body and not highlights:
            return None

        return RunIntelligenceResult(
            headline=headline,
            body=body or "",
            highlights=highlights,
        )
    except Exception:
        logger.exception("Failed to generate run intelligence for %s", activity_id)
        return None
