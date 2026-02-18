"""
Daily Intelligence Tasks (Phase 2D + 3A)

Celery Beat runs `run_morning_intelligence` every 15 minutes.
The task checks which athletes are at their 5 AM local window
and runs the intelligence pipeline for each one.

Phase 3A addition: after intelligence rules fire, each insight is
narrated by the AdaptationNarrator (Gemini Flash). Narrations are
scored against engine ground truth, and low-quality narrations are
suppressed (silence > bad narrative).

Design:
    - Global task runs every 15 minutes (not once per athlete).
    - Filters athletes whose local time is in the [05:00, 05:14] window.
    - For each qualifying athlete: readiness → intelligence → narrate → persist.
    - One athlete's failure does NOT block others.
    - No insight = no notification (silence is fine).
    - FLAG-level insights get marked for prominent display.
    - Results stored in InsightLog + NarrationLog.

Sources:
    docs/TRAINING_PLAN_REBUILD_PLAN.md (Phase 2D, 3A)
"""

from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from celery import Task
from sqlalchemy.orm import Session

from tasks import celery_app
from core.database import get_db_sync
import logging

logger = logging.getLogger(__name__)

# Window size in minutes — must match the beat schedule interval.
# If beat runs every 15 minutes, the window is 15 minutes.
WINDOW_MINUTES = 15
TARGET_HOUR = 5   # 5 AM local time
TARGET_MINUTE = 0


def _athletes_in_morning_window(db: Session, utc_now: datetime) -> List:
    """
    Find athletes whose local time is in the [05:00, 05:14] window right now.

    Logic:
        For each athlete with a timezone, compute their local time.
        If local_time.hour == TARGET_HOUR and local_time.minute < WINDOW_MINUTES,
        this athlete is in the window.

    Athletes without a timezone are skipped (we don't know when their morning is).
    """
    from models import Athlete, TrainingPlan

    try:
        import zoneinfo
    except ImportError:
        import backports.zoneinfo as zoneinfo  # type: ignore

    # Get athletes with active plans and a timezone set
    athletes = (
        db.query(Athlete)
        .join(TrainingPlan, TrainingPlan.athlete_id == Athlete.id)
        .filter(
            Athlete.timezone.isnot(None),
            TrainingPlan.status == "active",
        )
        .distinct()
        .all()
    )

    qualifying = []
    for athlete in athletes:
        try:
            tz = zoneinfo.ZoneInfo(athlete.timezone)
            local_now = utc_now.astimezone(tz)
            if local_now.hour == TARGET_HOUR and local_now.minute < WINDOW_MINUTES:
                qualifying.append(athlete)
        except (KeyError, ValueError) as e:
            logger.debug(f"Invalid timezone '{athlete.timezone}' for athlete {athlete.id}: {e}")
            continue

    return qualifying


def _run_intelligence_for_athlete(
    athlete_id: UUID,
    target_date: date,
    db: Session,
) -> Dict:
    """
    Run the full intelligence pipeline for one athlete on one date.

    Pipeline:
        1. Compute readiness score
        2. Run intelligence rules
        3. Generate narrations for each insight (Phase 3A)
        4. Score narrations against engine ground truth
        5. Persist insights + narrations (InsightLog + NarrationLog)
        6. Return summary for monitoring

    Returns:
        Dict with status, insight count, highest mode, narration stats, etc.
    """
    from services.readiness_score import ReadinessScoreCalculator
    from services.daily_intelligence import DailyIntelligenceEngine

    # Step 1: Readiness
    readiness_calc = ReadinessScoreCalculator()
    readiness_result = readiness_calc.compute(
        athlete_id=athlete_id,
        target_date=target_date,
        db=db,
    )

    # Step 2: Intelligence
    engine = DailyIntelligenceEngine()
    intel_result = engine.evaluate(
        athlete_id=athlete_id,
        target_date=target_date,
        db=db,
        readiness_score=readiness_result.score,
    )

    # Step 3: Narrate insights (Phase 3A)
    narration_stats = _narrate_insights(
        athlete_id=athlete_id,
        target_date=target_date,
        intel_result=intel_result,
        readiness_result=readiness_result,
        db=db,
    )

    # Step 4: Commit insights + narrations
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    # ADR-065: trigger home briefing refresh after intelligence write
    try:
        from tasks.home_briefing_tasks import enqueue_briefing_refresh
        enqueue_briefing_refresh(str(athlete_id))
    except Exception:
        pass

    # Summary for monitoring
    highest = intel_result.highest_mode
    return {
        "athlete_id": str(athlete_id),
        "date": str(target_date),
        "readiness_score": round(readiness_result.score, 1) if readiness_result.score else None,
        "readiness_confidence": round(readiness_result.confidence, 2),
        "insight_count": len(intel_result.insights),
        "highest_mode": highest.value if highest else None,
        "self_regulation_logged": intel_result.self_regulation_logged,
        "rules_fired": [i.rule_id for i in intel_result.insights],
        **narration_stats,
    }


def _narrate_insights(
    athlete_id: UUID,
    target_date: date,
    intel_result,
    readiness_result,
    db: Session,
) -> Dict:
    """
    Generate and score narrations for each insight (Phase 3A).

    Narrations that fail scoring are suppressed — silence > bad narrative.
    Results are persisted in NarrationLog and attached to InsightLog rows.

    Returns dict with narration statistics for monitoring.
    """
    from services.adaptation_narrator import AdaptationNarrator
    from services.daily_intelligence import InsightMode

    stats = {
        "narrations_generated": 0,
        "narrations_suppressed": 0,
        "narrations_passed": 0,
        "narration_avg_score": 0.0,
    }

    if not intel_result.insights:
        return stats

    # Build ground truth from engine result
    ground_truth = {
        "highest_mode": intel_result.highest_mode.value if intel_result.highest_mode else None,
        "insights": [
            {
                "rule_id": i.rule_id,
                "mode": i.mode.value if hasattr(i.mode, "value") else i.mode,
                "data_cited": i.data_cited,
            }
            for i in intel_result.insights
        ],
    }

    # Initialize narrator — try to get Gemini client
    gemini_client = _get_gemini_client()
    if gemini_client is None:
        logger.info("Gemini client not available — skipping narration generation")
        return stats

    narrator = AdaptationNarrator(gemini_client=gemini_client)

    # Build readiness context
    readiness_components = None
    if hasattr(readiness_result, "components") and readiness_result.components:
        readiness_components = readiness_result.components

    insight_rule_ids = [i.rule_id for i in intel_result.insights]
    scores = []

    for insight in intel_result.insights:
        # Skip LOG mode — internal tracking only
        if insight.mode == InsightMode.LOG:
            continue

        try:
            result = narrator.narrate(
                rule_id=insight.rule_id,
                mode=insight.mode.value if hasattr(insight.mode, "value") else insight.mode,
                data_cited=insight.data_cited,
                ground_truth=ground_truth,
                insight_rule_ids=insight_rule_ids,
                readiness_score=readiness_result.score,
                readiness_components=readiness_components,
            )

            stats["narrations_generated"] += 1

            if result.suppressed:
                stats["narrations_suppressed"] += 1
            else:
                stats["narrations_passed"] += 1

            if result.score_result:
                scores.append(result.score_result.score)

            # Persist narration log
            _persist_narration(
                athlete_id=athlete_id,
                target_date=target_date,
                insight=insight,
                narration_result=result,
                ground_truth=ground_truth,
                db=db,
            )

        except Exception as e:
            logger.error(
                f"Narration failed for {insight.rule_id} athlete {athlete_id}: {e}",
                exc_info=True,
            )

    if scores:
        stats["narration_avg_score"] = round(sum(scores) / len(scores), 3)

    return stats


def _persist_narration(
    athlete_id: UUID,
    target_date: date,
    insight,
    narration_result,
    ground_truth: Dict,
    db: Session,
) -> None:
    """Persist a narration result to NarrationLog and update InsightLog."""
    from models import NarrationLog, InsightLog
    import uuid

    # Create NarrationLog entry
    narration_log = NarrationLog(
        id=uuid.uuid4(),
        athlete_id=athlete_id,
        trigger_date=target_date,
        rule_id=insight.rule_id,
        narration_text=narration_result.raw_response,
        prompt_used=narration_result.prompt_used,
        ground_truth=ground_truth,
        model_used=narration_result.model_used,
        input_tokens=narration_result.input_tokens,
        output_tokens=narration_result.output_tokens,
        latency_ms=narration_result.latency_ms,
        suppressed=narration_result.suppressed,
        suppression_reason=narration_result.suppression_reason,
    )

    # Fill in scoring fields
    if narration_result.score_result:
        sr = narration_result.score_result
        narration_log.factually_correct = sr.factually_correct
        narration_log.no_raw_metrics = sr.no_raw_metrics
        narration_log.actionable_language = sr.actionable_language
        narration_log.criteria_passed = sr.criteria_passed
        narration_log.score = sr.score
        narration_log.contradicts_engine = sr.contradicts_engine
        narration_log.contradiction_detail = sr.contradiction_detail

    db.add(narration_log)

    # Update InsightLog with narration (find the matching row)
    try:
        insight_row = (
            db.query(InsightLog)
            .filter(
                InsightLog.athlete_id == athlete_id,
                InsightLog.trigger_date == target_date,
                InsightLog.rule_id == insight.rule_id,
            )
            .order_by(InsightLog.created_at.desc())
            .first()
        )
        if insight_row:
            if not narration_result.suppressed and narration_result.narration:
                insight_row.narrative = narration_result.narration
            if narration_result.score_result:
                insight_row.narrative_score = narration_result.score_result.score
                insight_row.narrative_contradicts = narration_result.score_result.contradicts_engine
    except Exception as e:
        logger.warning(f"Could not update InsightLog with narration: {e}")


def _get_gemini_client():
    """Get a Gemini client instance, or None if unavailable."""
    import os
    google_key = os.environ.get("GOOGLE_API_KEY")
    if not google_key:
        return None
    try:
        from google import genai
        return genai.Client(api_key=google_key)
    except Exception as e:
        logger.warning(f"Could not initialize Gemini client: {e}")
        return None


@celery_app.task(
    name="tasks.run_morning_intelligence",
    bind=True,
    max_retries=0,      # Don't retry the batch — individual athletes are isolated
    soft_time_limit=600, # 10 minutes soft limit
    time_limit=720,      # 12 minutes hard limit
)
def run_morning_intelligence(self: Task, force_athlete_id: Optional[str] = None) -> Dict:
    """
    Morning intelligence task — runs every 15 minutes via Celery Beat.

    Finds athletes in their 5 AM local window and runs the intelligence
    pipeline for each. Each athlete is processed independently — one
    failure doesn't block others.

    Args:
        force_athlete_id: If set, run for this athlete regardless of timezone.
                         Used for manual triggering / testing.

    Returns:
        Summary dict with processed athletes and any errors.
    """
    db: Session = next(get_db_sync())
    utc_now = datetime.now(timezone.utc)
    today = utc_now.date()

    try:
        if force_athlete_id:
            # Manual trigger — process specific athlete
            from models import Athlete
            athlete = db.query(Athlete).filter(
                Athlete.id == force_athlete_id
            ).first()

            if not athlete:
                return {"status": "error", "message": f"Athlete {force_athlete_id} not found"}

            athletes = [athlete]
            logger.info(f"Morning intelligence: forced run for athlete {force_athlete_id}")
        else:
            athletes = _athletes_in_morning_window(db, utc_now)
            logger.info(
                f"Morning intelligence: {len(athletes)} athletes in 5 AM window "
                f"at {utc_now.strftime('%H:%M UTC')}"
            )

        if not athletes:
            return {
                "status": "ok",
                "utc_time": utc_now.isoformat(),
                "athletes_processed": 0,
                "message": "No athletes in morning window",
            }

        results = []
        errors = []

        for athlete in athletes:
            try:
                # Determine target date in athlete's local timezone
                try:
                    import zoneinfo
                except ImportError:
                    import backports.zoneinfo as zoneinfo  # type: ignore

                if athlete.timezone:
                    tz = zoneinfo.ZoneInfo(athlete.timezone)
                    local_date = utc_now.astimezone(tz).date()
                else:
                    local_date = today

                result = _run_intelligence_for_athlete(
                    athlete_id=athlete.id,
                    target_date=local_date,
                    db=db,
                )
                results.append(result)

                # Log summary
                if result["insight_count"] > 0:
                    logger.info(
                        f"Intelligence for {athlete.id}: "
                        f"{result['insight_count']} insights, "
                        f"highest={result['highest_mode']}, "
                        f"readiness={result['readiness_score']}"
                    )
            except Exception as e:
                error_msg = f"Failed for athlete {athlete.id}: {type(e).__name__}: {e}"
                logger.error(error_msg, exc_info=True)
                errors.append({"athlete_id": str(athlete.id), "error": str(e)})

        return {
            "status": "ok",
            "utc_time": utc_now.isoformat(),
            "athletes_processed": len(results),
            "athletes_errored": len(errors),
            "total_insights": sum(r["insight_count"] for r in results),
            "flag_count": sum(1 for r in results if r["highest_mode"] == "flag"),
            "results": results,
            "errors": errors if errors else None,
        }

    except Exception as e:
        logger.error(f"Morning intelligence task failed: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(
    name="tasks.run_intelligence_for_athlete",
    bind=True,
    max_retries=1,
    soft_time_limit=60,
    time_limit=90,
)
def run_intelligence_for_athlete_task(
    self: Task, athlete_id: str, target_date: Optional[str] = None,
) -> Dict:
    """
    Run intelligence for a single athlete. Can be called:
    - Manually by admin
    - After a Strava sync (to update self-regulation data)
    - From the morning intelligence batch

    Args:
        athlete_id: UUID string
        target_date: ISO date string (defaults to today UTC)
    """
    db: Session = next(get_db_sync())

    try:
        from uuid import UUID as UUID_type
        aid = UUID_type(athlete_id)
        td = date.fromisoformat(target_date) if target_date else date.today()

        result = _run_intelligence_for_athlete(aid, td, db)
        return result

    except Exception as e:
        logger.error(f"Intelligence task failed for {athlete_id}: {e}", exc_info=True)
        return {"status": "error", "athlete_id": athlete_id, "message": str(e)}
    finally:
        db.close()
