"""
D1: Data Model Changes — Tests

Covers:
  D1.1 — Athlete OAuth token fields (garmin_001 migration scope)
  D1.2 — Activity running dynamics + Garmin columns (garmin_002 migration scope)
  D1.3 — GarminDay model (garmin_003 migration scope)

All tests are model-level (SQLAlchemy inspection + runtime DB ops).
Migration SQL is validated by the Alembic upgrade/downgrade smoke test
in CI (not duplicated here — that test runs against a live DB).

AC reference: PHASE2_GARMIN_INTEGRATION_AC.md §D1
"""

import inspect
import uuid
from datetime import date, datetime, timezone

import pytest


# ---------------------------------------------------------------------------
# D1.1 — Athlete OAuth token fields
# ---------------------------------------------------------------------------

class TestAthleteOAuthFields:
    """Athlete model must expose OAuth token fields; credential fields must be gone."""

    def test_has_garmin_oauth_access_token(self):
        from models import Athlete
        assert hasattr(Athlete, "garmin_oauth_access_token")

    def test_has_garmin_oauth_refresh_token(self):
        from models import Athlete
        assert hasattr(Athlete, "garmin_oauth_refresh_token")

    def test_has_garmin_oauth_token_expires_at(self):
        from models import Athlete
        assert hasattr(Athlete, "garmin_oauth_token_expires_at")

    def test_has_garmin_user_id(self):
        from models import Athlete
        assert hasattr(Athlete, "garmin_user_id")

    def test_no_garmin_username_column(self):
        from models import Athlete
        col_names = [c.key for c in Athlete.__table__.columns]
        assert "garmin_username" not in col_names

    def test_no_garmin_password_encrypted_column(self):
        from models import Athlete
        col_names = [c.key for c in Athlete.__table__.columns]
        assert "garmin_password_encrypted" not in col_names

    def test_existing_garmin_fields_still_present(self):
        from models import Athlete
        assert hasattr(Athlete, "garmin_connected")
        assert hasattr(Athlete, "last_garmin_sync")
        assert hasattr(Athlete, "garmin_sync_enabled")

    def test_athlete_can_store_oauth_fields(self, db_session, test_athlete):
        """Runtime: OAuth token fields persist and round-trip through the DB."""
        expires = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        test_athlete.garmin_oauth_access_token = "encrypted_access_token_placeholder"
        test_athlete.garmin_oauth_refresh_token = "encrypted_refresh_token_placeholder"
        test_athlete.garmin_oauth_token_expires_at = expires
        test_athlete.garmin_user_id = "garmin_uid_12345"
        test_athlete.garmin_connected = True
        db_session.commit()
        db_session.expire(test_athlete)

        reloaded = db_session.get(type(test_athlete), test_athlete.id)
        assert reloaded.garmin_oauth_access_token == "encrypted_access_token_placeholder"
        assert reloaded.garmin_oauth_refresh_token == "encrypted_refresh_token_placeholder"
        assert reloaded.garmin_user_id == "garmin_uid_12345"
        assert reloaded.garmin_connected is True


# ---------------------------------------------------------------------------
# D1.2 — Activity new columns (source inspection + runtime)
# ---------------------------------------------------------------------------

class TestActivityGarminColumns:
    """Activity model must expose all new Garmin-specific columns."""

    REQUIRED_COLUMNS = [
        # Running dynamics
        "avg_cadence", "max_cadence", "avg_stride_length_m",
        "avg_ground_contact_ms", "avg_ground_contact_balance_pct",
        "avg_vertical_oscillation_cm", "avg_vertical_ratio_pct",
        # Power
        "avg_power_w", "max_power_w",
        # Effort / grade
        "avg_gap_min_per_mile", "total_descent_m",
        # Training Effect
        "garmin_aerobic_te", "garmin_anaerobic_te", "garmin_te_label",
        # Self-evaluation
        "garmin_feel", "garmin_perceived_effort",
        # Wellness crossover
        "garmin_body_battery_impact",
        # Timing / energy
        "moving_time_s", "max_speed", "active_kcal",
    ]

    def test_all_new_columns_present(self):
        from models import Activity
        col_names = {c.key for c in Activity.__table__.columns}
        missing = [c for c in self.REQUIRED_COLUMNS if c not in col_names]
        assert not missing, f"Missing Activity columns: {missing}"

    def test_all_new_columns_nullable(self):
        from models import Activity
        col_map = {c.key: c for c in Activity.__table__.columns}
        non_nullable = [
            c for c in self.REQUIRED_COLUMNS
            if not col_map[c].nullable
        ]
        assert not non_nullable, f"Expected nullable, got non-nullable: {non_nullable}"

    def test_training_effect_annotation_in_model_source(self):
        """[L2] INFORMATIONAL ONLY annotation must be present in models.py source."""
        from models.activity import Activity
        src = inspect.getsource(Activity)
        assert "INFORMATIONAL ONLY" in src, (
            "garmin_aerobic_te / _anaerobic_te / _te_label must be annotated "
            "'INFORMATIONAL ONLY' in models.py"
        )

    def test_garmin_feel_annotation_in_model_source(self):
        """[L3] Self-evaluation caveat annotation must be present in models.py source."""
        from models.activity import Activity
        src = inspect.getsource(Activity)
        assert "low-fidelity" in src.lower() or "low fidelity" in src.lower(), (
            "garmin_feel / garmin_perceived_effort must have low-fidelity caveat in models.py"
        )

    def test_training_effect_absent_from_load_readiness(self):
        """[L2] Training Effect columns must not appear in load/readiness services.

        TE is allowed in n1_insight_generator FRIENDLY_NAMES (correlation
        discovery display labels) but blocked from daily_intelligence
        (load/readiness calculations). garmin_te_label (categorical) is
        blocked everywhere.
        """
        import os

        load_services = ["services/daily_intelligence.py"]
        te_columns = ["garmin_aerobic_te", "garmin_anaerobic_te", "garmin_te_label"]
        for service in load_services:
            path = os.path.join(os.path.dirname(__file__), "..", service)
            if not os.path.exists(path):
                continue
            with open(path) as f:
                content = f.read()
            for col in te_columns:
                assert col not in content, (
                    f"{col} (Training Effect) found in {service}. "
                    "Must not be used in load or readiness calculations."
                )

        insight_path = os.path.join(
            os.path.dirname(__file__), "..", "services/n1_insight_generator.py"
        )
        if os.path.exists(insight_path):
            with open(insight_path) as f:
                content = f.read()
            assert "garmin_te_label" not in content, (
                "garmin_te_label (categorical) must not appear in insight generator."
            )

    def test_new_garmin_activity_columns_round_trip(self, db_session, test_athlete):
        """Runtime: new columns persist correctly for a Garmin activity."""
        from models import Activity
        act = Activity(
            athlete_id=test_athlete.id,
            start_time=datetime(2026, 2, 21, 8, 0, 0, tzinfo=timezone.utc),
            sport="run",
            source="garmin",
            provider="garmin",
            external_activity_id=f"g_d1_test_{uuid.uuid4().hex[:8]}",
            duration_s=3600,
            distance_m=16093,
            avg_cadence=168,
            max_cadence=185,
            avg_stride_length_m=1.21,
            avg_ground_contact_ms=248.0,
            avg_ground_contact_balance_pct=49.8,
            avg_vertical_oscillation_cm=9.3,
            avg_vertical_ratio_pct=7.7,
            avg_power_w=285,
            max_power_w=420,
            avg_gap_min_per_mile=9.2,
            total_descent_m=80.0,
            garmin_aerobic_te=4.5,
            garmin_anaerobic_te=0.3,
            garmin_te_label="Maintaining",
            garmin_feel="GOOD",
            garmin_perceived_effort=3,
            garmin_body_battery_impact=-22,
            moving_time_s=3540,
            max_speed=4.2,
            active_kcal=820,
        )
        db_session.add(act)
        db_session.commit()
        db_session.expire(act)

        reloaded = db_session.get(Activity, act.id)
        assert reloaded.avg_cadence == 168
        assert reloaded.avg_stride_length_m == pytest.approx(1.21)
        assert reloaded.garmin_aerobic_te == pytest.approx(4.5)
        assert reloaded.garmin_feel == "GOOD"
        assert reloaded.active_kcal == 820


# ---------------------------------------------------------------------------
# D1.3 — GarminDay model
# ---------------------------------------------------------------------------

class TestGarminDayModel:
    """GarminDay model: schema, constraints, and runtime ops."""

    def test_garmin_day_importable(self):
        from models import GarminDay
        assert GarminDay.__tablename__ == "garmin_day"

    def test_garmin_day_has_required_columns(self):
        from models import GarminDay
        required = [
            "id", "athlete_id", "calendar_date",
            "resting_hr", "avg_stress", "max_stress", "stress_qualifier",
            "steps", "active_time_s", "active_kcal",
            "moderate_intensity_s", "vigorous_intensity_s",
            "min_hr", "max_hr",
            "sleep_total_s", "sleep_deep_s", "sleep_light_s",
            "sleep_rem_s", "sleep_awake_s",
            "sleep_score", "sleep_score_qualifier", "sleep_validation",
            "hrv_overnight_avg", "hrv_5min_high",
            "vo2max",
            "body_battery_end",
            "stress_samples", "body_battery_samples",
            "garmin_daily_summary_id", "garmin_sleep_summary_id", "garmin_hrv_summary_id",
            "inserted_at", "updated_at",
        ]
        col_names = {c.key for c in GarminDay.__table__.columns}
        missing = [c for c in required if c not in col_names]
        assert not missing, f"Missing GarminDay columns: {missing}"

    def test_garmin_day_unique_constraint_exists(self):
        from models import GarminDay
        constraints = {c.name for c in GarminDay.__table__.constraints}
        assert "uq_garmin_day_athlete_date" in constraints

    def test_no_garmin_sleep_model(self):
        import models as mod
        assert not hasattr(mod, "GarminSleep"), (
            "GarminSleep must not exist as a separate model — use GarminDay"
        )

    def test_no_garmin_hrv_model(self):
        import models as mod
        assert not hasattr(mod, "GarminHRV"), (
            "GarminHRV must not exist as a separate model — use GarminDay"
        )

    def test_garmin_day_create_and_read(self, db_session, test_athlete):
        """Runtime: GarminDay row persists and reads back correctly."""
        from models import GarminDay
        day = GarminDay(
            athlete_id=test_athlete.id,
            calendar_date=date(2026, 2, 21),
            resting_hr=48,
            sleep_total_s=27000,
            sleep_score=82,
            sleep_score_qualifier="GOOD",
            hrv_overnight_avg=58,
            hrv_5min_high=72,
            steps=12500,
            body_battery_end=45,
        )
        db_session.add(day)
        db_session.commit()
        db_session.expire(day)

        reloaded = db_session.get(GarminDay, day.id)
        assert reloaded.resting_hr == 48
        assert reloaded.sleep_total_s == 27000
        assert reloaded.sleep_score == 82
        assert reloaded.sleep_score_qualifier == "GOOD"
        assert reloaded.hrv_overnight_avg == 58
        assert reloaded.steps == 12500
        assert reloaded.calendar_date == date(2026, 2, 21)

    def test_garmin_day_upsert_pattern(self, db_session, test_athlete):
        """Runtime: upsert (INSERT ... ON CONFLICT DO UPDATE) works correctly."""
        from models import GarminDay
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        values = {
            "id": uuid.uuid4(),
            "athlete_id": test_athlete.id,
            "calendar_date": date(2026, 2, 22),
            "resting_hr": 50,
            "sleep_score": 75,
        }
        stmt = pg_insert(GarminDay).values(**values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_garmin_day_athlete_date",
            set_={"resting_hr": 52, "sleep_score": 80},
        )
        db_session.execute(stmt)
        db_session.commit()

        # Upsert again — should update, not insert duplicate
        stmt2 = pg_insert(GarminDay).values(**{**values, "id": uuid.uuid4()})
        stmt2 = stmt2.on_conflict_do_update(
            constraint="uq_garmin_day_athlete_date",
            set_={"resting_hr": 52, "sleep_score": 80},
        )
        db_session.execute(stmt2)
        db_session.commit()

        rows = (
            db_session.query(GarminDay)
            .filter(
                GarminDay.athlete_id == test_athlete.id,
                GarminDay.calendar_date == date(2026, 2, 22),
            )
            .all()
        )
        assert len(rows) == 1, "Upsert must produce exactly one row per (athlete, date)"

    def test_garmin_day_unique_constraint_enforced(self, db_session, test_athlete):
        """Runtime: inserting a duplicate (athlete_id, calendar_date) raises."""
        from models import GarminDay
        from sqlalchemy.exc import IntegrityError

        day1 = GarminDay(athlete_id=test_athlete.id, calendar_date=date(2026, 2, 20))
        day2 = GarminDay(athlete_id=test_athlete.id, calendar_date=date(2026, 2, 20))
        db_session.add(day1)
        db_session.commit()
        db_session.add(day2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_calendar_date_is_wakeup_day_not_prior_night(self):
        """
        L1 rule documentation test: calendar_date must represent the wakeup
        morning. The docstring in GarminDay must state this.
        """
        from models import GarminDay
        doc = GarminDay.__doc__ or ""
        assert "wakeup" in doc.lower() or "wake" in doc.lower(), (
            "GarminDay docstring must document that calendar_date is the wakeup day"
        )

    def test_athlete_garmin_days_relationship(self, db_session, test_athlete):
        """Runtime: athlete.garmin_days relationship returns GarminDay rows."""
        from models import GarminDay
        db_session.add(GarminDay(athlete_id=test_athlete.id, calendar_date=date(2026, 2, 21)))
        db_session.add(GarminDay(athlete_id=test_athlete.id, calendar_date=date(2026, 2, 22)))
        db_session.commit()

        count = test_athlete.garmin_days.count()
        assert count == 2
