from datetime import date, timedelta

from celery.schedules import crontab


def _create_plan(db_session, athlete_id, *, status: str, goal_race_date: date):
    from models import TrainingPlan

    plan = TrainingPlan(
        athlete_id=athlete_id,
        name=f"{status} plan",
        status=status,
        goal_race_date=goal_race_date,
        goal_race_distance_m=42195,
        plan_start_date=goal_race_date - timedelta(weeks=16),
        plan_end_date=goal_race_date,
        total_weeks=16,
        plan_type="marathon",
        generation_method="ai",
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan


def test_complete_expired_plans_transitions_past_race_date(db_session, test_athlete):
    from tasks.plan_lifecycle_tasks import _complete_expired_plans_in_db

    stale = _create_plan(
        db_session,
        test_athlete.id,
        status="active",
        goal_race_date=date.today() - timedelta(days=1),
    )

    updated_count = _complete_expired_plans_in_db(db_session)
    db_session.refresh(stale)

    assert updated_count >= 1
    assert stale.status == "completed"


def test_complete_expired_plans_ignores_future_race(db_session, test_athlete):
    from tasks.plan_lifecycle_tasks import _complete_expired_plans_in_db

    future = _create_plan(
        db_session,
        test_athlete.id,
        status="active",
        goal_race_date=date.today() + timedelta(days=7),
    )

    updated_count = _complete_expired_plans_in_db(db_session)
    db_session.refresh(future)

    assert updated_count == 0
    assert future.status == "active"


def test_complete_expired_plans_ignores_non_active_statuses(db_session, test_athlete):
    from tasks.plan_lifecycle_tasks import _complete_expired_plans_in_db

    completed = _create_plan(
        db_session,
        test_athlete.id,
        status="completed",
        goal_race_date=date.today() - timedelta(days=10),
    )
    cancelled = _create_plan(
        db_session,
        test_athlete.id,
        status="cancelled",
        goal_race_date=date.today() - timedelta(days=10),
    )

    updated_count = _complete_expired_plans_in_db(db_session)
    db_session.refresh(completed)
    db_session.refresh(cancelled)

    assert updated_count == 0
    assert completed.status == "completed"
    assert cancelled.status == "cancelled"


def test_complete_expired_plans_idempotent(db_session, test_athlete):
    from tasks.plan_lifecycle_tasks import _complete_expired_plans_in_db

    stale = _create_plan(
        db_session,
        test_athlete.id,
        status="active",
        goal_race_date=date.today() - timedelta(days=2),
    )

    first = _complete_expired_plans_in_db(db_session)
    second = _complete_expired_plans_in_db(db_session)
    db_session.refresh(stale)

    assert first >= 1
    assert second == 0
    assert stale.status == "completed"


def test_complete_expired_plans_is_wired_in_beat_schedule():
    from celerybeat_schedule import beat_schedule

    entry = beat_schedule.get("complete-expired-plans")
    assert entry is not None
    assert entry["task"] == "tasks.complete_expired_plans"

    schedule = entry["schedule"]
    assert isinstance(schedule, crontab)
    assert schedule._orig_hour == 2
    assert schedule._orig_minute == 0
