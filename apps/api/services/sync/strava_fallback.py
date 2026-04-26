"""Garmin -> Strava structural fallback.

When the Garmin per-second detail webhook never arrives, the cleanup beat
(`tasks.cleanup_stale_garmin_pending_streams`) fail-closes the row to
`stream_fetch_status='unavailable'` after 30 minutes.  That makes the
activity page render without a chart, map, splits or run-shape analysis
-- even though the same workout exists in Strava.

This module is the structural repair: when triggered for one of those
fail-closed rows, it finds the matching Strava activity, pulls its streams
and laps, and attaches them to the **existing Garmin activity row** so the
UI surfaces light up.  The activity stays labeled as Garmin in the DB; we
only borrow the missing pieces from Strava.

Founder-locked answers (see docs/specs/garmin_strava_fallback_plan.md):
  1. Matching window: tight -- start_time +/- 30 min, distance +/- 5%, HR +/- 5 bpm
  2. Splits: detect intervals from streams when laps are missing or single-lap
  3. Missing HR channel: still mark success (degraded), do not block
  4. Retry skipped_no_match once after 2h
  5. Max age: 14 days
  6. No nightly sweep for re-linked Strava (out of scope for v1)
  7. Use shared Strava read budget (no dedicated sub-budget)
  8. No UI banner -- silent repair (provenance only via ActivityStream.source)

The Celery task wrapper lives in `tasks.strava_fallback_tasks`; this
module is pure-ish (takes a session) so unit tests can drive every branch
without Celery.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

GARMIN_STREAM_TIMEOUT_MARKER = "garmin_detail_missing_timeout_30m"
MAX_FALLBACK_AGE_DAYS = 14
MATCH_WINDOW_SECONDS = 30 * 60
MATCH_DISTANCE_TOLERANCE = 0.05
MATCH_HR_TOLERANCE_BPM = 5
SKIPPED_NO_MATCH_RETRY_DELAY_SECONDS = 2 * 60 * 60
MAX_FALLBACK_ATTEMPTS = 3


@dataclass
class RepairResult:
    status: str
    activity_id: Optional[UUID] = None
    strava_activity_id: Optional[int] = None
    point_count: int = 0
    splits_written: int = 0
    error: Optional[str] = None
    retry_after_s: Optional[int] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "activity_id": str(self.activity_id) if self.activity_id else None,
            "strava_activity_id": self.strava_activity_id,
            "point_count": self.point_count,
            "splits_written": self.splits_written,
            "error": self.error,
            "retry_after_s": self.retry_after_s,
            **self.extra,
        }


def repair_garmin_activity_from_strava(
    activity_id: UUID,
    db: Session,
    *,
    now: Optional[datetime] = None,
    strava_service_module=None,
    interval_detector_module=None,
    shape_extractor_module=None,
) -> RepairResult:
    """Attempt a single Garmin -> Strava repair for one activity.

    The injection arguments exist for tests; production callers leave them
    None and the real `services.sync.strava_service` is used.

    Concurrency: the function takes a row-level claim via
    UPDATE...WHERE strava_fallback_status IS NULL OR 'failed' RETURNING id
    so two workers cannot both run the API calls.
    """
    from models import Activity, ActivityStream, ActivitySplit, Athlete

    # --- Late imports so the module is cheap to import in test contexts ---
    if strava_service_module is None:
        from services.sync import strava_service as strava_service_module  # type: ignore
    if interval_detector_module is None:
        from services import interval_detector as interval_detector_module  # type: ignore
    if shape_extractor_module is None:
        from services import shape_extractor as shape_extractor_module  # type: ignore

    now = now or datetime.now(timezone.utc)

    # --- 1. Concurrency claim ---------------------------------------------
    # Atomically flip status -> pending only if it is currently NULL or
    # 'failed', so a second worker that arrives concurrently sees nothing
    # to claim.  The RETURNING gives us back the row only if we won.
    claim_row = db.execute(
        text(
            """
            UPDATE activity
            SET strava_fallback_status = 'pending',
                strava_fallback_attempted_at = :now,
                strava_fallback_attempt_count = strava_fallback_attempt_count + 1
            WHERE id = :id
              AND provider = 'garmin'
              AND stream_fetch_status = 'unavailable'
              AND (strava_fallback_status IS NULL OR strava_fallback_status = 'failed')
              AND strava_fallback_attempt_count < :max_attempts
            RETURNING id, athlete_id, start_time, distance_m, avg_hr, sport,
                      stream_fetch_error
            """
        ),
        {
            "id": str(activity_id),
            "now": now,
            "max_attempts": MAX_FALLBACK_ATTEMPTS,
        },
    ).fetchone()
    db.commit()

    if claim_row is None:
        logger.info(
            "strava_fallback_skipped_not_claimable activity_id=%s", activity_id
        )
        return RepairResult(
            status="skipped_not_claimable",
            activity_id=activity_id,
            error="not_eligible_or_already_in_progress",
        )

    athlete_id = claim_row.athlete_id
    start_time = claim_row.start_time
    distance_m = float(claim_row.distance_m) if claim_row.distance_m else None
    avg_hr = int(claim_row.avg_hr) if claim_row.avg_hr else None
    sport = (claim_row.sport or "").lower()

    # --- 2. Recency / sport gates -----------------------------------------
    if sport != "run":
        return _record_terminal(
            db, activity_id, "skipped_not_run", error=f"sport={sport!r}"
        )

    if start_time is None:
        return _record_terminal(
            db, activity_id, "skipped_no_start_time", error="start_time_null"
        )

    age = now - _ensure_aware(start_time)
    if age > timedelta(days=MAX_FALLBACK_AGE_DAYS):
        return _record_terminal(
            db,
            activity_id,
            "skipped_too_old",
            error=f"age_days={age.days}",
        )

    # --- 3. Athlete / Strava token ----------------------------------------
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if athlete is None:
        return _record_terminal(
            db, activity_id, "failed", error="athlete_missing"
        )

    if not getattr(athlete, "strava_access_token", None) or not getattr(
        athlete, "strava_refresh_token", None
    ):
        return _record_terminal(
            db, activity_id, "skipped_no_strava", error="no_strava_tokens"
        )

    try:
        strava_service_module.ensure_fresh_token(athlete, db)
    except Exception as exc:  # token refresh failed
        logger.warning(
            "strava_fallback_token_refresh_failed activity_id=%s error=%s",
            activity_id,
            exc,
        )
        return _record_terminal(
            db,
            activity_id,
            "failed",
            error=f"token_refresh_failed:{str(exc)[:200]}",
        )

    # --- 4. Find matching Strava activity ---------------------------------
    try:
        strava_match = _find_strava_match(
            athlete=athlete,
            start_time=_ensure_aware(start_time),
            distance_m=distance_m,
            avg_hr=avg_hr,
            strava_service_module=strava_service_module,
        )
    except _RateLimitedError as exc:
        return _record_skipped_with_retry(
            db,
            activity_id,
            "skipped_rate_limited",
            error=str(exc)[:200],
            retry_after_s=exc.retry_after_s,
        )
    except Exception as exc:
        logger.warning(
            "strava_fallback_match_lookup_failed activity_id=%s error=%s",
            activity_id,
            exc,
        )
        return _record_terminal(
            db,
            activity_id,
            "failed",
            error=f"match_lookup_failed:{str(exc)[:200]}",
        )

    if strava_match is None:
        return _record_skipped_with_retry(
            db,
            activity_id,
            "skipped_no_match",
            error="no_matching_strava_activity",
            retry_after_s=SKIPPED_NO_MATCH_RETRY_DELAY_SECONDS,
        )

    strava_activity_id = int(strava_match["id"])

    # --- 5. Fetch streams from Strava -------------------------------------
    try:
        stream_result = strava_service_module.get_activity_streams(
            athlete,
            activity_id=strava_activity_id,
            allow_rate_limit_sleep=False,
        )
    except getattr(strava_service_module, "StravaRateLimitError", Exception) as exc:
        retry_after = int(getattr(exc, "retry_after_s", 900) or 900)
        return _record_skipped_with_retry(
            db,
            activity_id,
            "skipped_rate_limited",
            error=f"strava_rate_limited:{str(exc)[:120]}",
            retry_after_s=retry_after,
            strava_activity_id=strava_activity_id,
        )
    except Exception as exc:
        logger.warning(
            "strava_fallback_stream_fetch_failed activity_id=%s strava_id=%s error=%s",
            activity_id,
            strava_activity_id,
            exc,
        )
        return _record_terminal(
            db,
            activity_id,
            "failed",
            error=f"stream_fetch_failed:{str(exc)[:200]}",
            strava_activity_id=strava_activity_id,
        )

    if stream_result.outcome == "skipped_no_redis":
        # Redis down: leave the row claimable on the next pass.  Do NOT
        # mark terminal; clear our pending claim back to NULL so the next
        # cleanup-cycle enqueue can try again.
        return _record_skipped_with_retry(
            db,
            activity_id,
            None,
            error="redis_unavailable_during_strava_fetch",
            retry_after_s=900,
            strava_activity_id=strava_activity_id,
        )

    if stream_result.outcome == "unavailable":
        return _record_terminal(
            db,
            activity_id,
            "skipped_strava_no_streams",
            error=stream_result.error or "strava_returned_no_streams",
            strava_activity_id=strava_activity_id,
        )

    if stream_result.outcome == "failed":
        return _record_terminal(
            db,
            activity_id,
            "failed",
            error=f"strava_stream_failed:{(stream_result.error or 'unknown')[:200]}",
            strava_activity_id=strava_activity_id,
        )

    stream_data = stream_result.data or {}
    if not stream_data:
        return _record_terminal(
            db,
            activity_id,
            "skipped_strava_no_streams",
            error="empty_stream_payload",
            strava_activity_id=strava_activity_id,
        )

    # --- 6. Fetch laps (best-effort: missing/single-lap is fine) ----------
    laps_payload: Optional[List[Dict[str, Any]]] = None
    try:
        laps_payload = strava_service_module.get_activity_laps(
            athlete,
            activity_id=strava_activity_id,
            allow_rate_limit_sleep=False,
        )
    except Exception as exc:
        # Laps are best-effort; we can still detect intervals from streams.
        logger.info(
            "strava_fallback_laps_fetch_skipped activity_id=%s strava_id=%s reason=%s",
            activity_id,
            strava_activity_id,
            exc,
        )
        laps_payload = None

    # --- 7. Persist streams (upsert on existing Garmin activity_id) -------
    channels = list(stream_data.keys())
    point_count = len(stream_data.get("time") or [])

    existing_stream = (
        db.query(ActivityStream)
        .filter(ActivityStream.activity_id == activity_id)
        .first()
    )
    if existing_stream is not None:
        existing_stream.stream_data = stream_data
        existing_stream.channels_available = channels
        existing_stream.point_count = point_count
        existing_stream.source = "strava_fallback"
    else:
        db.add(
            ActivityStream(
                activity_id=activity_id,
                stream_data=stream_data,
                channels_available=channels,
                point_count=point_count,
                source="strava_fallback",
            )
        )

    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if activity is None:
        # Should not happen: we just claimed it.  Defensive.
        db.rollback()
        return _record_terminal(
            db, activity_id, "failed", error="activity_disappeared_post_claim"
        )

    # --- 8. Splits / interval reconstruction ------------------------------
    splits_written = _rebuild_splits_from_strava(
        db=db,
        activity_id=activity_id,
        stream_data=stream_data,
        laps_payload=laps_payload,
        interval_detector_module=interval_detector_module,
    )

    # --- 9. Run shape sentence --------------------------------------------
    try:
        _populate_run_shape(
            db=db,
            activity=activity,
            athlete=athlete,
            stream_data=stream_data,
            shape_extractor_module=shape_extractor_module,
        )
    except Exception as exc:
        # Shape extraction is non-blocking: the chart still renders without it.
        logger.warning(
            "strava_fallback_shape_extract_failed activity_id=%s error=%s",
            activity_id,
            exc,
        )

    # --- 10. Mark stream + fallback both successful -----------------------
    activity.stream_fetch_status = "success"
    if not activity.stream_fetch_error or activity.stream_fetch_error == GARMIN_STREAM_TIMEOUT_MARKER:
        activity.stream_fetch_error = "repaired_via_strava_fallback"

    db.execute(
        text(
            """
            UPDATE activity
            SET strava_fallback_status = 'succeeded',
                strava_fallback_strava_activity_id = :strava_id,
                strava_fallback_error = NULL
            WHERE id = :id
            """
        ),
        {"id": str(activity_id), "strava_id": strava_activity_id},
    )
    db.commit()

    # Bust the cached stream analysis so the next /v1/activities/{id}/stream-analysis
    # call recomputes from the freshly written stream row.
    try:
        from services.stream_analysis_cache import invalidate_cache

        invalidate_cache(activity_id, db)
    except Exception:
        pass

    # --- ROUTE FINGERPRINT (Phase 2 of comparison family) ---
    try:
        from services.routes.route_fingerprint import compute_for_activity

        compute_for_activity(db, activity_id)
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning(
            "strava_fallback_route_fingerprint_failed activity_id=%s err=%s",
            activity_id,
            exc,
        )
        db.rollback()

    logger.info(
        "strava_fallback_succeeded activity_id=%s strava_id=%s points=%s splits=%s",
        activity_id,
        strava_activity_id,
        point_count,
        splits_written,
    )

    return RepairResult(
        status="succeeded",
        activity_id=activity_id,
        strava_activity_id=strava_activity_id,
        point_count=point_count,
        splits_written=splits_written,
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


class _RateLimitedError(Exception):
    def __init__(self, message: str, retry_after_s: int = 900):
        super().__init__(message)
        self.retry_after_s = retry_after_s


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _find_strava_match(
    *,
    athlete,
    start_time: datetime,
    distance_m: Optional[float],
    avg_hr: Optional[int],
    strava_service_module,
) -> Optional[Dict[str, Any]]:
    """Pull a small window of Strava activities around start_time and pick the match.

    Window: +/- 6 hours around the Garmin start_time -- wide enough that
    Strava sync delay (typically minutes, sometimes hours) cannot hide the
    candidate, narrow enough that it costs at most one Strava list call.
    Then `match_activities` enforces the tight +/- 30 min / 5% / 5 bpm
    rule for actual identity.
    """
    from services.sync.activity_deduplication import (
        match_activities,
        TIME_WINDOW_S,  # noqa: F401 -- imported for parity / future tightening
    )

    # Fetch list window
    after_ts = int((start_time - timedelta(hours=6)).timestamp())
    before_ts = int((start_time + timedelta(hours=6)).timestamp())

    try:
        candidates = strava_service_module.poll_activities_page(
            athlete,
            after_timestamp=after_ts,
            before_timestamp=before_ts,
            page=1,
            per_page=50,
            allow_rate_limit_sleep=False,
        )
    except getattr(strava_service_module, "StravaRateLimitError", Exception) as exc:
        retry_after = int(getattr(exc, "retry_after_s", 900) or 900)
        raise _RateLimitedError(str(exc), retry_after_s=retry_after) from exc

    if not candidates:
        return None

    garmin_internal = {
        "start_time": start_time,
        "distance_m": distance_m,
    }
    if avg_hr:
        garmin_internal["avg_hr"] = avg_hr

    # Among matches, prefer the one with the closest start_time -- defends
    # against an athlete who happens to have two same-distance same-day runs.
    best: Optional[Dict[str, Any]] = None
    best_delta = float("inf")
    tight_window = timedelta(seconds=MATCH_WINDOW_SECONDS)

    for c in candidates:
        if (c.get("type") or "").lower() != "run":
            continue

        start_str = c.get("start_date")
        if not start_str:
            continue
        try:
            cand_start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        except ValueError:
            continue

        delta = abs((cand_start - start_time).total_seconds())
        if delta > MATCH_WINDOW_SECONDS:
            continue

        candidate_internal = {
            "start_time": cand_start,
            "distance_m": c.get("distance"),
        }
        if c.get("average_heartrate"):
            candidate_internal["avg_hr"] = int(c["average_heartrate"])

        if not match_activities(garmin_internal, candidate_internal):
            continue

        if delta < best_delta:
            best = c
            best_delta = delta

    return best


def _rebuild_splits_from_strava(
    *,
    db: Session,
    activity_id: UUID,
    stream_data: Dict[str, Any],
    laps_payload: Optional[List[Dict[str, Any]]],
    interval_detector_module,
) -> int:
    """Replace any existing splits with ones derived from Strava data.

    Preference order:
      1. Strava laps payload (`get_activity_laps`) -- mirror the Garmin
         success path: hand to `interval_detector.detect_interval_structure`
         and write the labeled output.
      2. Stream-derived intervals (no laps or single auto-lap): fall back
         to the in-house pace-derivation path.  Returns 0 splits here is
         fine -- the chart still renders.
    """
    from models import ActivitySplit

    db.query(ActivitySplit).filter(
        ActivitySplit.activity_id == activity_id
    ).delete(synchronize_session=False)

    written = 0

    if laps_payload and len(laps_payload) > 1:
        lap_dicts = _adapt_strava_laps(laps_payload)
        if lap_dicts:
            try:
                analysis = interval_detector_module.detect_interval_structure(lap_dicts)
                for ls in analysis.labeled_splits:
                    db.add(
                        ActivitySplit(
                            activity_id=activity_id,
                            split_number=ls.split_number,
                            distance=ls.distance,
                            elapsed_time=ls.elapsed_time,
                            moving_time=ls.moving_time,
                            average_heartrate=ls.average_heartrate,
                            max_heartrate=ls.max_heartrate,
                            average_cadence=ls.average_cadence,
                            gap_seconds_per_mile=ls.gap_seconds_per_mile,
                            lap_type=ls.lap_type,
                            interval_number=ls.interval_number,
                        )
                    )
                    written += 1
            except Exception as exc:
                logger.warning(
                    "strava_fallback_lap_detection_failed activity_id=%s error=%s",
                    activity_id,
                    exc,
                )
                written = 0

    return written


def _adapt_strava_laps(laps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Translate Strava lap payload to the internal split dict shape that
    `interval_detector.detect_interval_structure` expects.

    Strava laps use `lap_index`, `distance` (m), `elapsed_time` (s),
    `moving_time`, `average_heartrate`, `max_heartrate`, `average_cadence`."""
    out: List[Dict[str, Any]] = []
    for i, lap in enumerate(laps):
        try:
            elapsed = int(float(lap.get("elapsed_time") or 0))
            distance = float(lap.get("distance") or 0)
            moving_time = int(float(lap.get("moving_time") or elapsed))
            out.append(
                {
                    "split_number": int(lap.get("lap_index") or i + 1),
                    "distance": distance,
                    "elapsed_time": elapsed,
                    "moving_time": moving_time,
                    "average_heartrate": (
                        int(lap["average_heartrate"]) if lap.get("average_heartrate") else None
                    ),
                    "max_heartrate": (
                        int(lap["max_heartrate"]) if lap.get("max_heartrate") else None
                    ),
                    "average_cadence": (
                        float(lap["average_cadence"]) if lap.get("average_cadence") else None
                    ),
                    "gap_seconds_per_mile": None,
                }
            )
        except (TypeError, ValueError):
            continue
    return out


def _populate_run_shape(
    *,
    db: Session,
    activity,
    athlete,
    stream_data: Dict[str, Any],
    shape_extractor_module,
) -> None:
    """Mirror the Garmin success path's shape extraction.  Defensive: any
    error here is swallowed by the caller -- the chart still renders even
    if the one-line sentence is missing."""
    try:
        from tasks.strava_tasks import _resolve_pace_profile, _get_median_duration
    except Exception:
        return

    pace_prof = _resolve_pace_profile(athlete, db) if athlete else None
    heat_adj = (
        float(activity.heat_adjustment_pct)
        if getattr(activity, "heat_adjustment_pct", None)
        else None
    )
    median_dur = _get_median_duration(athlete.id, db) if athlete else None

    shape = shape_extractor_module.extract_shape(
        stream_data,
        pace_profile=pace_prof,
        heat_adjustment_pct=heat_adj,
        median_duration_s=median_dur,
    )
    if not shape:
        return

    activity.run_shape = shape.to_dict()
    total_dist = float(activity.distance_m) if activity.distance_m else 0.0
    total_dur = float(activity.duration_s or 0)
    use_km = (
        getattr(athlete, "preferred_units", "imperial") == "metric"
        if athlete
        else False
    )
    activity.shape_sentence = shape_extractor_module.generate_shape_sentence(
        shape,
        total_dist,
        total_dur,
        pace_profile=pace_prof,
        median_duration_s=median_dur,
        use_km=use_km,
    )


def _record_terminal(
    db: Session,
    activity_id: UUID,
    status: str,
    *,
    error: Optional[str] = None,
    strava_activity_id: Optional[int] = None,
) -> RepairResult:
    """Mark a terminal outcome and commit.  No further retries."""
    db.execute(
        text(
            """
            UPDATE activity
            SET strava_fallback_status = :status,
                strava_fallback_error = :error,
                strava_fallback_strava_activity_id = COALESCE(:strava_id, strava_fallback_strava_activity_id)
            WHERE id = :id
            """
        ),
        {
            "id": str(activity_id),
            "status": status,
            "error": (error or None),
            "strava_id": strava_activity_id,
        },
    )
    db.commit()
    logger.info(
        "strava_fallback_terminal activity_id=%s status=%s error=%s",
        activity_id,
        status,
        error,
    )
    return RepairResult(
        status=status,
        activity_id=activity_id,
        strava_activity_id=strava_activity_id,
        error=error,
    )


def _record_skipped_with_retry(
    db: Session,
    activity_id: UUID,
    status: Optional[str],
    *,
    error: str,
    retry_after_s: int,
    strava_activity_id: Optional[int] = None,
) -> RepairResult:
    """Record a soft-skip that should be retried.

    For `status=None` (Redis down), we revert the claim back to NULL so
    the next cleanup-cycle enqueue can re-claim cleanly.  Otherwise we
    write the explicit skip status (`failed` / `skipped_rate_limited` /
    `skipped_no_match`) which is also retryable per the eligibility scan
    (only NULL/`failed` are claimable; we only count attempts).
    """
    if status is None:
        # Soft-revert: status NULL but retain the attempt count + timestamp
        # so the eligibility scan can re-pick this row on the next cycle.
        write_status_sql = "strava_fallback_status = NULL"
    elif status in ("skipped_rate_limited", "skipped_no_match"):
        # These should be retried next cycle, so keep status='failed' to
        # remain claimable, with the descriptive error stamped.
        write_status_sql = "strava_fallback_status = 'failed'"
    else:
        write_status_sql = "strava_fallback_status = :status"

    sql = f"""
        UPDATE activity
        SET {write_status_sql},
            strava_fallback_error = :error,
            strava_fallback_strava_activity_id = COALESCE(:strava_id, strava_fallback_strava_activity_id)
        WHERE id = :id
    """
    params = {
        "id": str(activity_id),
        "error": error,
        "strava_id": strava_activity_id,
    }
    if status is not None and status not in ("skipped_rate_limited", "skipped_no_match"):
        params["status"] = status

    db.execute(text(sql), params)
    db.commit()

    logger.info(
        "strava_fallback_soft_skip activity_id=%s status=%s retry_after_s=%s",
        activity_id,
        status or "redis_down_revert",
        retry_after_s,
    )
    return RepairResult(
        status=status or "skipped_redis_down",
        activity_id=activity_id,
        strava_activity_id=strava_activity_id,
        error=error,
        retry_after_s=retry_after_s,
    )
