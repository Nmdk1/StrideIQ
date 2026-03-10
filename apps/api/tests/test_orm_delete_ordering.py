"""Regression tests for SQLAlchemy unit-of-work delete ordering.

Background (2026-02-14):
    The Athlete model had no relationship() to Activity. SQLAlchemy's UoW
    determines delete ordering from mapped relationships, not bare ForeignKey
    columns. Without a relationship, the delete order between Athlete and
    Activity was arbitrary — determined by mapper registration tiebreaking.

    Adding ActivityStream (a new mapper with a relationship to Activity)
    changed the mapper graph enough to flip the tiebreak: Athlete started
    deleting before Activity, causing ForeignKeyViolation.

    Fix: added Athlete.activities ↔ Activity.athlete bidirectional relationship.

    These tests encode the exact failure path so that any future mapper
    addition that disrupts UoW ordering is caught immediately.
"""
import pytest
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models import Athlete, Activity, ActivitySplit, ActivityStream


class TestDeleteOrdering:
    """Verify SQLAlchemy deletes children before parents in a single flush.

    These tests reproduce the exact pattern from test_anchor_finder_integration
    and test_run_delivery that broke when ActivityStream was added. If a future
    mapper addition changes the topological sort, these tests catch it.
    """

    def test_delete_activity_then_athlete_single_flush(self, db_session):
        """Core regression: delete Activity + Athlete in one commit.

        This is the exact pattern that broke: session.delete(activity),
        session.delete(athlete), session.commit(). SQLAlchemy must delete
        Activity before Athlete due to the FK dependency.
        """
        athlete = Athlete(
            email=f"delete_order_{uuid4()}@test.com",
            display_name="Delete Order Test",
            subscription_tier="free",
            birthdate=date(1990, 1, 1),
            sex="M",
        )
        db_session.add(athlete)
        db_session.commit()

        activity = Activity(
            athlete_id=athlete.id,
            provider="strava",
            external_activity_id=str(uuid4())[:10],
            sport="run",
            name="Test Run",
            start_time=datetime.now(timezone.utc),
            distance_m=10000,
            duration_s=2700,
            average_speed=Decimal("3.7"),
            avg_hr=165,
            max_hr=175,
        )
        db_session.add(activity)
        db_session.commit()

        # The exact pattern that caused ForeignKeyViolation:
        # delete child and parent in one flush.
        db_session.delete(activity)
        db_session.delete(athlete)
        db_session.commit()  # Must not raise ForeignKeyViolation

    def test_delete_activity_with_splits_and_athlete_single_flush(self, db_session):
        """Three-level cascade: ActivitySplit → Activity → Athlete."""
        athlete = Athlete(
            email=f"delete_3level_{uuid4()}@test.com",
            display_name="Three Level Test",
            subscription_tier="free",
        )
        db_session.add(athlete)
        db_session.commit()

        activity = Activity(
            athlete_id=athlete.id,
            provider="strava",
            external_activity_id=str(uuid4())[:10],
            sport="run",
            name="Splits Run",
            start_time=datetime.now(timezone.utc),
            distance_m=10000,
            duration_s=2700,
        )
        db_session.add(activity)
        db_session.commit()

        split = ActivitySplit(
            activity_id=activity.id,
            split_number=1,
            distance=Decimal("1609"),
            elapsed_time=450,
        )
        db_session.add(split)
        db_session.commit()

        # Delete all three in one flush — must respect FK ordering
        db_session.delete(split)
        db_session.delete(activity)
        db_session.delete(athlete)
        db_session.commit()

    def test_delete_activity_with_stream_and_athlete_single_flush(self, db_session):
        """Three-level cascade: ActivityStream → Activity → Athlete."""
        athlete = Athlete(
            email=f"delete_stream_{uuid4()}@test.com",
            display_name="Stream Delete Test",
            subscription_tier="free",
        )
        db_session.add(athlete)
        db_session.commit()

        activity = Activity(
            athlete_id=athlete.id,
            provider="strava",
            external_activity_id=str(uuid4())[:10],
            sport="run",
            name="Stream Run",
            start_time=datetime.now(timezone.utc),
            distance_m=10000,
            duration_s=3600,
        )
        db_session.add(activity)
        db_session.commit()

        stream = ActivityStream(
            activity_id=activity.id,
            stream_data={"time": [0, 1, 2], "heartrate": [140, 141, 142]},
            channels_available=["time", "heartrate"],
            point_count=3,
            source="strava",
        )
        db_session.add(stream)
        db_session.commit()

        # Delete all three in one flush
        db_session.delete(stream)
        db_session.delete(activity)
        db_session.delete(athlete)
        db_session.commit()

    def test_delete_multiple_activities_and_athlete_single_flush(self, db_session):
        """Multiple children: 5 Activities + 1 Athlete in one flush."""
        athlete = Athlete(
            email=f"delete_multi_{uuid4()}@test.com",
            display_name="Multi Delete Test",
            subscription_tier="free",
        )
        db_session.add(athlete)
        db_session.commit()

        activities = []
        for i in range(5):
            a = Activity(
                athlete_id=athlete.id,
                provider="strava",
                external_activity_id=f"multi_{i}_{uuid4()}",
                sport="run",
                name=f"Run {i}",
                start_time=datetime.now(timezone.utc) - timedelta(days=i),
                distance_m=8000,
                duration_s=2400,
            )
            db_session.add(a)
            activities.append(a)
        db_session.commit()

        # Delete all in one flush — intentionally worst-case order
        # (parent first, then children) to verify SQLAlchemy reorders
        db_session.delete(athlete)
        for a in activities:
            db_session.delete(a)
        db_session.commit()

    def test_delete_full_object_graph_single_flush(self, db_session):
        """Full graph: Athlete → Activity → {Splits, Stream} all in one flush."""
        athlete = Athlete(
            email=f"delete_full_{uuid4()}@test.com",
            display_name="Full Graph Test",
            subscription_tier="free",
        )
        db_session.add(athlete)
        db_session.commit()

        activity = Activity(
            athlete_id=athlete.id,
            provider="strava",
            external_activity_id=str(uuid4())[:10],
            sport="run",
            name="Full Graph Run",
            start_time=datetime.now(timezone.utc),
            distance_m=10000,
            duration_s=3600,
        )
        db_session.add(activity)
        db_session.commit()

        split = ActivitySplit(
            activity_id=activity.id,
            split_number=1,
            distance=Decimal("1609"),
            elapsed_time=450,
        )
        stream = ActivityStream(
            activity_id=activity.id,
            stream_data={"time": [0, 1], "distance": [0.0, 2.8]},
            channels_available=["time", "distance"],
            point_count=2,
            source="strava",
        )
        db_session.add(split)
        db_session.add(stream)
        db_session.commit()

        # Intentionally worst-case order: parent first
        db_session.delete(athlete)
        db_session.delete(activity)
        db_session.delete(split)
        db_session.delete(stream)
        db_session.commit()
