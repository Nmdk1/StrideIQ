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

from sqlalchemy.orm import Session

from models import Activity, ActivitySplit, CachedStreamAnalysis, CalendarNote
from services.timezone_utils import get_athlete_timezone_from_db, to_athlete_local_date

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
- Never state the obvious (distance, duration, avg pace) — the athlete sees those.
- Focus on what THIS run reveals: pacing execution, cardiac response, \
rep quality, drift, fade, efficiency trends, conditions impact.
- Reference specific data: rep numbers, pace values, HR numbers, percentages.
- If reps were busted/incomplete, say which ones and what it means for the session.
- If historical comparison data exists, USE it — that's the insight the athlete can't see.
- If pre-state data exists (sleep, HRV, resting HR), connect it to the run \
outcome ONLY if there's a plausible link. Don't force it.
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


def _is_interval_workout(activity: Activity) -> bool:
    wt = getattr(activity, "workout_type", None)
    if not wt:
        return False
    return wt.lower() in {"interval", "intervals", "track", "track_workout"}


# ── Data gathering ─────────────────────────────────────────────────────


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

    if len(work_splits) < 2:
        return None

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
        })

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

    return {
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
    }


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
            "prev_date": to_athlete_local_date(prev.start_time, get_athlete_timezone_from_db(db, activity.athlete_id)).isoformat(),
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
    run_date = to_athlete_local_date(activity.start_time, get_athlete_timezone_from_db(db, activity.athlete_id))
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

    elev = getattr(activity, "total_elevation_gain", None)
    if elev and float(elev) > 30:
        ctx["elevation_gain_ft"] = int(float(elev) * 3.28084)

    is_race = getattr(activity, "is_race_candidate", False) or (
        activity.workout_type and activity.workout_type.lower() == "race"
    )
    if is_race:
        ctx["is_race"] = True

    temp = getattr(activity, "temperature_f", None)
    if temp:
        ctx["temperature_f"] = round(float(temp))
    humidity = getattr(activity, "humidity_pct", None)
    if humidity:
        ctx["humidity_pct"] = round(float(humidity))
    heat_adj = getattr(activity, "heat_adjustment_pct", None)
    if heat_adj and float(heat_adj) > 2:
        ctx["heat_adjustment_pct"] = round(float(heat_adj), 1)

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
