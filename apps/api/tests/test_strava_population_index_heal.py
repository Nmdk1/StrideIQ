"""
Population-wide Strava index heal orchestrator.

Locks down the eligibility filter (data-derived, idempotent) and the throttling
behavior (per-athlete enqueue + countdown spacing) for
`tasks.strava_tasks.heal_strava_indexes_population_task`.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from models import Activity, Athlete
from tasks.strava_tasks import (
    _select_athletes_needing_strava_index_backfill,
    heal_strava_indexes_population_task,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_athlete(
    db,
    *,
    has_strava_token: bool = True,
    last_strava_sync: datetime | None = None,
) -> Athlete:
    athlete = Athlete(
        email=f"pop_heal_{uuid4()}@example.com",
        display_name="Population Heal Athlete",
        subscription_tier="free",
        birthdate=date(1990, 1, 1),
        sex="M",
        strava_access_token="token-xyz" if has_strava_token else None,
        last_strava_sync=last_strava_sync,
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    return athlete


def _add_activity(db, athlete: Athlete, *, sport: str, provider: str = "strava") -> None:
    db.add(
        Activity(
            athlete_id=athlete.id,
            external_activity_id=f"ext-{uuid4()}",
            provider=provider,
            source=provider,
            sport=sport,
            start_time=datetime.now(timezone.utc),
            distance_m=5000,
            duration_s=1800,
        )
    )
    db.commit()


# ---------------------------------------------------------------------------
# Eligibility filter (the "fingerprint" of the dropped-data bug)
# ---------------------------------------------------------------------------


def test_eligibility_includes_athlete_with_only_runs_from_strava(db_session):
    """
    Classic bug fingerprint: athlete synced before the fix → has runs from Strava but
    nothing else. Must be selected for healing.
    """
    last_sync = datetime.now(timezone.utc) - timedelta(days=10)
    athlete = _make_athlete(db_session, last_strava_sync=last_sync)
    _add_activity(db_session, athlete, sport="run", provider="strava")

    selected = _select_athletes_needing_strava_index_backfill(db_session, limit=50)
    assert str(athlete.id) in selected


def test_eligibility_excludes_athlete_with_strava_cycling_already_present(db_session):
    """
    Once an athlete has been healed (any non-run Strava row exists), they fall out of
    the eligible set. This is what makes re-running the orchestrator a safe no-op.
    """
    last_sync = datetime.now(timezone.utc) - timedelta(days=10)
    athlete = _make_athlete(db_session, last_strava_sync=last_sync)
    _add_activity(db_session, athlete, sport="run", provider="strava")
    _add_activity(db_session, athlete, sport="cycling", provider="strava")

    selected = _select_athletes_needing_strava_index_backfill(db_session, limit=50)
    assert str(athlete.id) not in selected


@pytest.mark.parametrize("non_run_sport", ["cycling", "walking", "hiking", "strength", "flexibility"])
def test_eligibility_excludes_when_any_canonical_non_run_sport_present(db_session, non_run_sport):
    """
    All five canonical non-run sports must satisfy the "already healed" check —
    otherwise we'd enqueue redundant backfills for athletes who only happen to be
    missing one specific sport.
    """
    last_sync = datetime.now(timezone.utc) - timedelta(days=10)
    athlete = _make_athlete(db_session, last_strava_sync=last_sync)
    _add_activity(db_session, athlete, sport=non_run_sport, provider="strava")

    selected = _select_athletes_needing_strava_index_backfill(db_session, limit=50)
    assert str(athlete.id) not in selected


def test_eligibility_excludes_athlete_without_strava_token(db_session):
    """
    Can't backfill someone we have no token for. Garmin-only athletes must not be
    selected.
    """
    athlete = _make_athlete(
        db_session,
        has_strava_token=False,
        last_strava_sync=None,
    )
    _add_activity(db_session, athlete, sport="run", provider="garmin")

    selected = _select_athletes_needing_strava_index_backfill(db_session, limit=50)
    assert str(athlete.id) not in selected


def test_eligibility_excludes_athlete_who_has_never_synced_strava(db_session):
    """
    `last_strava_sync IS NULL` means the buggy old code never touched them; they get
    correct multi-sport ingest from their first sync. No heal needed.
    """
    athlete = _make_athlete(db_session, has_strava_token=True, last_strava_sync=None)
    selected = _select_athletes_needing_strava_index_backfill(db_session, limit=50)
    assert str(athlete.id) not in selected


def test_eligibility_excludes_garmin_only_non_run_activities(db_session):
    """
    A garmin-sourced cycling row does NOT prove the Strava history is healed —
    Strava might still be missing rides the athlete actually did. Only Strava-
    provider non-runs satisfy the heal-already-done check.
    """
    last_sync = datetime.now(timezone.utc) - timedelta(days=10)
    athlete = _make_athlete(db_session, last_strava_sync=last_sync)
    _add_activity(db_session, athlete, sport="run", provider="strava")
    _add_activity(db_session, athlete, sport="cycling", provider="garmin")

    selected = _select_athletes_needing_strava_index_backfill(db_session, limit=50)
    assert str(athlete.id) in selected


def test_eligibility_orders_oldest_synced_first(db_session):
    """
    Athletes who have been waiting longest get healed first. Important so a
    bounded `max_athletes` batch doesn't keep re-picking the same recently-synced
    athletes while older ones starve.
    """
    now = datetime.now(timezone.utc)
    a_old = _make_athlete(db_session, last_strava_sync=now - timedelta(days=60))
    a_mid = _make_athlete(db_session, last_strava_sync=now - timedelta(days=30))
    a_new = _make_athlete(db_session, last_strava_sync=now - timedelta(days=1))

    for a in (a_old, a_mid, a_new):
        _add_activity(db_session, a, sport="run", provider="strava")

    selected = _select_athletes_needing_strava_index_backfill(db_session, limit=10)
    ids = [str(a_old.id), str(a_mid.id), str(a_new.id)]
    selected_for_test = [s for s in selected if s in ids]
    assert selected_for_test == ids  # oldest → newest


def test_eligibility_respects_limit(db_session):
    """
    `max_athletes` bounds the batch so a single invocation can never blast the queue.
    """
    now = datetime.now(timezone.utc)
    athletes = []
    for _ in range(5):
        a = _make_athlete(db_session, last_strava_sync=now - timedelta(days=10))
        _add_activity(db_session, a, sport="run", provider="strava")
        athletes.append(a)

    selected = _select_athletes_needing_strava_index_backfill(db_session, limit=3)
    assert len(selected) == 3


# ---------------------------------------------------------------------------
# Orchestrator behavior (enqueue + throttling)
# ---------------------------------------------------------------------------


def _patch_session_close_noop(session):
    """
    Orchestrator owns its DB session and closes it in `finally`. In tests we share
    the transactional fixture session and must not let it be closed. Returns a tuple
    of (patched_session_proxy, original_close_method) so the test can restore.
    """
    original_close = session.close
    session.close = lambda: None  # type: ignore[assignment]
    return original_close


def test_orchestrator_enqueues_one_apply_async_per_eligible_athlete(db_session):
    """
    Per-athlete tasks must be enqueued (not run inline) so they distribute across
    workers. The orchestrator returns quickly regardless of how many athletes are
    healed.
    """
    now = datetime.now(timezone.utc)
    athlete_ids = []
    for _ in range(3):
        a = _make_athlete(db_session, last_strava_sync=now - timedelta(days=10))
        _add_activity(db_session, a, sport="run", provider="strava")
        athlete_ids.append(str(a.id))

    original_close = _patch_session_close_noop(db_session)
    try:
        with patch(
            "tasks.strava_tasks.backfill_strava_activity_index_task.apply_async"
        ) as mock_apply, patch(
            "tasks.strava_tasks.get_db_sync", return_value=db_session
        ):
            result = heal_strava_indexes_population_task.run(
                max_athletes=10, pages_per_athlete=15, spacing_seconds=60
            )
    finally:
        db_session.close = original_close  # type: ignore[assignment]

    assert result["status"] == "success"
    enqueued_ids = {call.kwargs["args"][0] for call in mock_apply.call_args_list}
    assert set(athlete_ids).issubset(enqueued_ids)
    assert result["enqueued"] >= 3


def test_orchestrator_spaces_enqueues_with_increasing_countdown(db_session):
    """
    Throttling is implemented via Celery countdown spacing so combined Strava read
    traffic stays under the 200 req / 15 min per-app limit. Each successive
    enqueue must have a larger countdown than the previous.
    """
    now = datetime.now(timezone.utc)
    target_ids = []
    for _ in range(4):
        a = _make_athlete(db_session, last_strava_sync=now - timedelta(days=10))
        _add_activity(db_session, a, sport="run", provider="strava")
        target_ids.append(str(a.id))

    original_close = _patch_session_close_noop(db_session)
    try:
        with patch(
            "tasks.strava_tasks.backfill_strava_activity_index_task.apply_async"
        ) as mock_apply, patch(
            "tasks.strava_tasks.get_db_sync", return_value=db_session
        ):
            heal_strava_indexes_population_task.run(
                max_athletes=10, pages_per_athlete=15, spacing_seconds=60
            )
    finally:
        db_session.close = original_close  # type: ignore[assignment]

    # Filter to only the calls for athletes we created in this test so other
    # eligible fixture-leftover athletes don't pollute the spacing assertion.
    countdowns = [
        call.kwargs["countdown"]
        for call in mock_apply.call_args_list
        if call.kwargs["args"][0] in target_ids
    ]
    assert len(countdowns) == 4
    # Within our four enqueues the deltas should be 60s apart, in enqueue order.
    countdowns_sorted = sorted(countdowns)
    assert countdowns_sorted == countdowns
    assert all(b - a == 60 for a, b in zip(countdowns_sorted, countdowns_sorted[1:]))


def test_orchestrator_passes_pages_per_athlete_to_per_athlete_task(db_session):
    """
    The pages_per_athlete budget must be propagated to each enqueued backfill so
    callers (or a beat schedule entry) can tune the cost/depth tradeoff in one place.
    """
    now = datetime.now(timezone.utc)
    a = _make_athlete(db_session, last_strava_sync=now - timedelta(days=10))
    _add_activity(db_session, a, sport="run", provider="strava")
    target_id = str(a.id)

    original_close = _patch_session_close_noop(db_session)
    try:
        with patch(
            "tasks.strava_tasks.backfill_strava_activity_index_task.apply_async"
        ) as mock_apply, patch(
            "tasks.strava_tasks.get_db_sync", return_value=db_session
        ):
            heal_strava_indexes_population_task.run(
                max_athletes=10, pages_per_athlete=25, spacing_seconds=30
            )
    finally:
        db_session.close = original_close  # type: ignore[assignment]

    matching = [
        call for call in mock_apply.call_args_list if call.kwargs["args"][0] == target_id
    ]
    assert matching, "expected our test athlete to be enqueued"
    assert matching[0].kwargs["args"][1] == 25  # pages


def test_orchestrator_is_a_noop_when_athlete_is_already_healed(db_session):
    """
    Healthy steady state: every connected athlete has at least one non-run Strava
    row. Re-running the orchestrator must NOT re-enqueue them.
    """
    now = datetime.now(timezone.utc)
    a = _make_athlete(db_session, last_strava_sync=now - timedelta(days=10))
    _add_activity(db_session, a, sport="run", provider="strava")
    _add_activity(db_session, a, sport="cycling", provider="strava")
    target_id = str(a.id)

    original_close = _patch_session_close_noop(db_session)
    try:
        with patch(
            "tasks.strava_tasks.backfill_strava_activity_index_task.apply_async"
        ) as mock_apply, patch(
            "tasks.strava_tasks.get_db_sync", return_value=db_session
        ):
            result = heal_strava_indexes_population_task.run(max_athletes=10)
    finally:
        db_session.close = original_close  # type: ignore[assignment]

    enqueued_ids = {call.kwargs["args"][0] for call in mock_apply.call_args_list}
    assert target_id not in enqueued_ids
    assert result["status"] == "success"


def test_orchestrator_reports_eligible_total_and_batch_size_separately(db_session):
    """
    Operators need to see "you healed 50 of 1200 — re-run me 23 more times" not
    just "I healed 50". eligible_total must reflect the full population, enqueued
    only the bounded batch.
    """
    now = datetime.now(timezone.utc)
    for _ in range(4):
        a = _make_athlete(db_session, last_strava_sync=now - timedelta(days=10))
        _add_activity(db_session, a, sport="run", provider="strava")

    original_close = _patch_session_close_noop(db_session)
    try:
        with patch(
            "tasks.strava_tasks.backfill_strava_activity_index_task.apply_async"
        ), patch(
            "tasks.strava_tasks.get_db_sync", return_value=db_session
        ):
            result = heal_strava_indexes_population_task.run(
                max_athletes=2, pages_per_athlete=15, spacing_seconds=60
            )
    finally:
        db_session.close = original_close  # type: ignore[assignment]

    assert result["enqueued"] == 2
    assert result["eligible_total"] >= 4  # at least the 4 we just created
