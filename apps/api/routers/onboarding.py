"""
Onboarding ("Latency Bridge") router (Phase 3).

Purpose:
- Provide deterministic progress + bootstrap ingestion without long-running requests.
- Keep external provider sync queued and observable.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import get_current_user
from models import (
    Athlete,
    Activity,
    IntakeQuestionnaire,
    CoachIntentSnapshot,
    AthleteRaceResultAnchor,
    AthleteTrainingPaceProfile,
)


router = APIRouter(prefix="/v1/onboarding", tags=["onboarding"])

# "baseline" is a thin-history fallback intake for production beta.
_ALLOWED_INTAKE_STAGES = {
    "initial",
    "basic_profile",
    "goals",
    "baseline",
    "connect_strava",
    "nutrition_setup",
    "work_setup",
}


def _run_history_snapshot(db: Session, athlete_id) -> dict:
    """
    Best-effort "thin history" detector used to decide whether we need baseline questions.

    We do NOT try to infer performance here; we only detect whether we have enough recent
    data to ground coach guidance without guessing.
    """
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    cutoff_28d = now - timedelta(days=28)
    cutoff_14d = now - timedelta(days=14)

    q = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.sport.ilike("run"),
            Activity.start_time >= cutoff_28d,
        )
        .order_by(Activity.start_time.desc())
    )
    runs = q.all()
    run_count_28d = len(runs)
    total_distance_m_28d = sum(int(r.distance_m or 0) for r in runs if r.distance_m)
    last_run_at = runs[0].start_time if runs else None

    # Conservative: treat as thin unless we have a minimal recent baseline.
    # (Thresholds are not "population paces"; they're just enough-data checks.)
    reasons: list[str] = []
    if run_count_28d < 6:
        reasons.append("low_run_count_28d")
    if total_distance_m_28d < int(1609.344 * 10):  # < ~10 miles in 28 days
        reasons.append("low_volume_28d")
    if (last_run_at is None) or (last_run_at < cutoff_14d):
        reasons.append("no_recent_run_14d")

    is_thin = bool(reasons)
    return {
        "is_thin": is_thin,
        "reasons": reasons,
        "run_count_28d": int(run_count_28d),
        "total_distance_m_28d": int(total_distance_m_28d),
        "last_run_at": last_run_at.isoformat() if last_run_at else None,
    }


class IntakeUpsertRequest(BaseModel):
    stage: str
    responses: dict
    completed: bool | None = None


def _normalize_stage(stage: str) -> str:
    s = (stage or "").strip()
    if not s:
        raise HTTPException(status_code=400, detail="stage required")
    if s not in _ALLOWED_INTAKE_STAGES:
        raise HTTPException(status_code=400, detail=f"invalid stage: {s}")
    return s


def _upsert_intake_row(db: Session, athlete_id, stage: str, responses: dict, completed: bool | None):
    """
    Upsert by (athlete_id, stage) in a schema-safe way.

    The DB schema does not currently enforce uniqueness. To keep behavior deterministic and
    avoid duplicates over time, we:
    - update the newest row if one exists
    - delete any older duplicates
    """
    from datetime import datetime

    rows = (
        db.query(IntakeQuestionnaire)
        .filter(IntakeQuestionnaire.athlete_id == athlete_id, IntakeQuestionnaire.stage == stage)
        .order_by(IntakeQuestionnaire.created_at.desc())
        .all()
    )
    row = rows[0] if rows else None
    if not row:
        row = IntakeQuestionnaire(athlete_id=athlete_id, stage=stage, responses=responses or {})
        db.add(row)
    else:
        row.responses = responses or {}

    # If caller marks completed, set completed_at; otherwise leave untouched.
    if completed is True:
        row.completed_at = datetime.utcnow()

    # Clean up any older duplicates (best-effort).
    if len(rows) > 1:
        for extra in rows[1:]:
            try:
                db.delete(extra)
            except Exception:
                pass

    return row


def _maybe_seed_intent_snapshot_from_goals(db: Session, athlete_id, responses: dict):
    """
    Intake answers are not "settings", but they are athlete-led priors. We seed the
    CoachIntentSnapshot with a few high-leverage fields so the coach can collaborate
    immediately without re-asking basics.
    """
    if not isinstance(responses, dict):
        return

    next_event_date = responses.get("goal_event_date")
    next_event_type = responses.get("goal_event_type")  # e.g., "5k" / "marathon" / "none"
    pain_flag = responses.get("pain_flag")  # "none" | "niggle" | "pain"
    time_available_min = responses.get("time_available_min")
    weekly_mileage_target = responses.get("weekly_mileage_target")
    what_feels_off = responses.get("limiter_primary")
    policy = responses.get("policy_stance")
    output_priorities = responses.get("output_metric_priorities")

    snap = db.query(CoachIntentSnapshot).filter(CoachIntentSnapshot.athlete_id == athlete_id).first()
    if not snap:
        snap = CoachIntentSnapshot(athlete_id=athlete_id)
        db.add(snap)

    def _norm_pain(v):
        vv = (v or "").strip().lower()
        return vv if vv in ("none", "niggle", "pain") else None

    try:
        from datetime import date as _date

        if next_event_date:
            snap.next_event_date = _date.fromisoformat(next_event_date)
    except Exception:
        pass

    if next_event_type is not None:
        snap.next_event_type = (str(next_event_type).strip() or None)
    if pain_flag is not None:
        snap.pain_flag = _norm_pain(pain_flag)
    if time_available_min is not None:
        try:
            snap.time_available_min = int(time_available_min)
        except Exception:
            pass
    if weekly_mileage_target is not None:
        try:
            snap.weekly_mileage_target = float(weekly_mileage_target)
        except Exception:
            pass
    if what_feels_off is not None:
        snap.what_feels_off = (str(what_feels_off).strip() or None)

    extra = snap.extra or {}
    if policy is not None:
        extra["policy_stance"] = policy
    if output_priorities is not None:
        extra["output_metric_priorities"] = output_priorities

    # Optional: race anchor (used for pace calibration) — store as a prior, not as settings.
    # This keeps Coach context aligned without claiming prescriptive validity if missing.
    try:
        rr_dist = responses.get("recent_race_distance")
        rr_time = responses.get("recent_race_time")
        rr_m = responses.get("recent_race_distance_m")
        rr_date = responses.get("recent_race_date")
        if rr_dist or rr_time:
            extra["recent_race_anchor"] = {
                "distance": rr_dist,
                "time": rr_time,
                "distance_meters": rr_m,
                "date": rr_date,
            }
    except Exception:
        pass
    snap.extra = extra


def _maybe_compute_and_persist_training_paces_from_goals(
    db: Session, *, athlete: Athlete, responses: dict
) -> dict | None:
    """
    Compute and persist a Training Pace Profile from Goals-stage race anchor, if present.

    Trust contract:
    - Race/time-trial result only (no inference from training data).
    - Does NOT mutate Athlete.rpi/threshold pace columns (safety).
    - Best-effort: failures should not block onboarding progression.
    """
    if not isinstance(responses, dict):
        return None

    # Feature gate: if flag missing/disabled, behave as if unsupported.
    try:
        from services.plan_framework.feature_flags import FeatureFlagService

        if not FeatureFlagService(db).is_enabled("onboarding.pace_calibration_v1", athlete.id):
            return None
    except Exception:
        return None

    dist_key = responses.get("recent_race_distance")
    time_str = responses.get("recent_race_time")
    dist_m = responses.get("recent_race_distance_m")
    race_date_str = responses.get("recent_race_date")

    if not dist_key or not time_str:
        return None

    from services.training_pace_profile import (
        RaceAnchor,
        parse_race_time_to_seconds,
        compute_training_pace_profile,
    )
    from datetime import date as _date

    time_seconds = parse_race_time_to_seconds(str(dist_key), str(time_str))
    if not time_seconds:
        return {"status": "invalid_anchor", "error": "invalid_time_format"}

    rd = None
    if race_date_str:
        try:
            rd = _date.fromisoformat(str(race_date_str))
        except Exception:
            rd = None

    anchor = RaceAnchor(
        distance_key=str(dist_key),
        time_seconds=int(time_seconds),
        distance_meters=int(dist_m) if dist_m is not None else None,
        race_date=rd,
    )

    payload, err = compute_training_pace_profile(anchor)
    if err or not payload:
        return {"status": "invalid_anchor", "error": err or "calc_failed"}

    # Upsert anchor (one per athlete).
    a = db.query(AthleteRaceResultAnchor).filter(AthleteRaceResultAnchor.athlete_id == athlete.id).first()
    if not a:
        a = AthleteRaceResultAnchor(athlete_id=athlete.id)
        db.add(a)

    a.distance_key = str(payload.get("anchor", {}).get("distance_key") or dist_key)
    a.distance_meters = int(payload.get("anchor", {}).get("distance_meters") or 0) or None
    a.time_seconds = int(payload.get("anchor", {}).get("time_seconds") or time_seconds)
    a.race_date = rd
    a.source = "user"

    db.flush()  # ensure a.id exists

    # Upsert pace profile (one per athlete).
    p = db.query(AthleteTrainingPaceProfile).filter(AthleteTrainingPaceProfile.athlete_id == athlete.id).first()
    if not p:
        p = AthleteTrainingPaceProfile(athlete_id=athlete.id, race_anchor_id=a.id)
        db.add(p)
    else:
        p.race_anchor_id = a.id

    p.fitness_score = float(payload.get("fitness_score")) if payload.get("fitness_score") is not None else None
    p.paces = payload

    return {"status": "computed", "pace_profile": payload}


@router.get("/intake")
def get_intake(
    stage: str | None = None,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Fetch saved intake interview responses for the current user.

    - If stage is provided: returns that stage's responses (or null).
    - If stage is omitted: returns a dict of stage -> responses.
    """
    if stage:
        st = _normalize_stage(stage)
        row = (
            db.query(IntakeQuestionnaire)
            .filter(IntakeQuestionnaire.athlete_id == current_user.id, IntakeQuestionnaire.stage == st)
            .order_by(IntakeQuestionnaire.created_at.desc())
            .first()
        )
        return {"stage": st, "responses": (row.responses if row else None), "completed_at": row.completed_at if row else None}

    out = {}
    rows = (
        db.query(IntakeQuestionnaire)
        .filter(IntakeQuestionnaire.athlete_id == current_user.id)
        .order_by(IntakeQuestionnaire.created_at.desc())
        .all()
    )
    for r in rows:
        if r.stage not in out:
            out[r.stage] = {"responses": r.responses, "completed_at": r.completed_at}
    return {"stages": out}


@router.post("/intake")
def upsert_intake(
    payload: IntakeUpsertRequest,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Save intake interview responses for the current user.

    This writes to IntakeQuestionnaire only (does not mutate plan settings).
    We may seed the CoachIntentSnapshot with a minimal subset of athlete-led priors.
    """
    st = _normalize_stage(payload.stage)
    if not isinstance(payload.responses, dict):
        raise HTTPException(status_code=400, detail="responses must be an object")

    row = _upsert_intake_row(db, current_user.id, st, payload.responses, payload.completed)
    pace_result = None
    pace_flag_enabled = False
    if st == "goals":
        _maybe_seed_intent_snapshot_from_goals(db, current_user.id, payload.responses)
        try:
            from services.plan_framework.feature_flags import FeatureFlagService

            pace_flag_enabled = FeatureFlagService(db).is_enabled("onboarding.pace_calibration_v1", current_user.id)
        except Exception:
            pace_flag_enabled = False
        pace_result = _maybe_compute_and_persist_training_paces_from_goals(db, athlete=current_user, responses=payload.responses)

    db.commit()
    db.refresh(row)
    out = {"ok": True, "stage": st, "saved_at": row.created_at, "completed_at": row.completed_at}
    if pace_result:
        out.update(pace_result)
    else:
        # Explicitly tell clients this surface is locked until a race result exists,
        # so we don't "appease" with low-quality inference.
        if st == "goals" and pace_flag_enabled:
            out["status"] = "missing_anchor"
    return out


@router.get("/status")
def get_onboarding_status(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return Strava connection + ingestion status snapshot for the current user.
    """
    from services.ingestion_state import get_ingestion_state_snapshot

    snapshot = get_ingestion_state_snapshot(db, current_user.id, provider="strava")
    history = _run_history_snapshot(db, current_user.id)

    baseline_row = (
        db.query(IntakeQuestionnaire)
        .filter(IntakeQuestionnaire.athlete_id == current_user.id, IntakeQuestionnaire.stage == "baseline")
        .order_by(IntakeQuestionnaire.created_at.desc())
        .first()
    )
    baseline_completed = bool(baseline_row and baseline_row.completed_at)
    return {
        "strava_connected": bool(current_user.strava_access_token),
        "last_sync": current_user.last_strava_sync.isoformat() if current_user.last_strava_sync else None,
        "ingestion_state": snapshot.to_dict() if snapshot else None,
        "history": history,
        "baseline": {
            "completed": bool(baseline_completed),
            "needed": bool(history.get("is_thin") and (not baseline_completed)),
        },
    }


@router.post("/bootstrap")
def bootstrap_ingestion(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Queue the minimal ingestion tasks that make the dashboard populate deterministically.

    - Index backfill is queued immediately (cheap, creates Activity rows quickly).
    - Full sync is queued (heavier, details/splits/pbs).
    """
    if not current_user.strava_access_token:
        raise HTTPException(status_code=400, detail="Strava not connected")

    from tasks.strava_tasks import backfill_strava_activity_index_task, sync_strava_activities_task
    from services.ingestion_state import get_ingestion_state_snapshot
    from datetime import datetime, timezone, timedelta

    # Best-effort idempotency: if an index backfill started recently, don't spam queue.
    snapshot = get_ingestion_state_snapshot(db, current_user.id, provider="strava")
    if snapshot and snapshot.last_index_started_at:
        try:
            started = snapshot.last_index_started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - started < timedelta(minutes=5) and snapshot.last_index_task_id:
                return {
                    "queued": False,
                    "index_task_id": snapshot.last_index_task_id,
                    "sync_task_id": None,
                    "message": "Index backfill already started recently",
                }
        except Exception:
            pass

    index_task = backfill_strava_activity_index_task.delay(str(current_user.id), pages=5)
    sync_task = sync_strava_activities_task.delay(str(current_user.id))
    return {
        "queued": True,
        "index_task_id": index_task.id,
        "sync_task_id": sync_task.id,
        "message": "Bootstrap ingestion queued",
    }

