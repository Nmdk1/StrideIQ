from __future__ import annotations

from datetime import date
from uuid import uuid4

from fastapi.testclient import TestClient

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models import Athlete, CoachIntentSnapshot, IntakeQuestionnaire, WorkoutTemplate, WorkoutSelectionAuditEvent


client = TestClient(app)


def test_intake_time_available_min_changes_selected_quality_template():
    """
    Black-box wiring check:
    - Intake POST seeds CoachIntentSnapshot.time_available_min
    - ModelDrivenPlanGenerator quality selection reads that value
    - Selected DB-backed template flips deterministically due to min_time_min constraint
    """
    db = SessionLocal()
    athlete = None
    template_suffix = str(uuid4()).replace("-", "")[:10]
    # Use numeric prefixes so our test templates deterministically sort before any existing build_* seeds.
    long_id = f"build_000_long_{template_suffix}"
    short_id = f"build_001_short_{template_suffix}"
    try:
        # Defensive cleanup: if a previous failed run left behind templates with our test prefixes,
        # delete them so ordering is deterministic for this run.
        try:
            for row in db.query(WorkoutTemplate).filter(WorkoutTemplate.id.like("build_000_long_%")).all():
                db.delete(row)
            for row in db.query(WorkoutTemplate).filter(WorkoutTemplate.id.like("build_001_short_%")).all():
                db.delete(row)
            db.commit()
        except Exception:
            db.rollback()

        athlete = Athlete(
            email=f"wire_{uuid4()}@example.com",
            display_name="Wiring Tester",
            subscription_tier="free",
            role="athlete",
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)

        # Insert 2 build templates that will dominate selection ordering:
        # - Without time constraint: long_id is chosen (sorts before others)
        # - With time_available_min=40: long_id is filtered out, short_id is chosen.
        long_t = WorkoutTemplate(
            id=long_id,
            name="AAA Long Template",
            intensity_tier="THRESHOLD",
            phase_compatibility=["build"],
            progression_logic={
                "type": "steps",
                "steps": [{"key": "s1", "structure": "LONG", "description_template": "AAA LONG 3x10 @ {t_pace}"}],
            },
            variance_tags=[],
            constraints={"min_time_min": 60},
            dont_follow=[],
        )
        short_t = WorkoutTemplate(
            id=short_id,
            name="BBB Short Template",
            intensity_tier="VO2MAX",
            phase_compatibility=["build"],
            progression_logic={
                "type": "steps",
                "steps": [{"key": "s1", "structure": "SHORT", "description_template": "BBB SHORT 6x400 @ {i_pace}"}],
            },
            variance_tags=[],
            constraints={"min_time_min": 30},
            dont_follow=[],
        )
        db.add(long_t)
        db.add(short_t)
        db.commit()

        # --- Before intake: no snapshot, so min_time filter cannot apply -> AAA should be selected ---
        from services.model_driven_plan_generator import ModelDrivenPlanGenerator
        from services.optimal_load_calculator import TrainingPhase

        gen1 = ModelDrivenPlanGenerator(db)
        gen1._current_athlete_id = athlete.id
        gen1._plan_generation_id = "wirecheck-1"
        gen1._recent_quality_ids = []
        gen1._recent_quality_ids_shadow = []

        day1 = gen1._select_quality_workout_3d(
            date=date.today(),
            day_of_week="Thursday",
            target_tss=80,
            miles=10,
            paces={"e_pace": "9:00/mi", "t_pace": "7:15/mi", "m_pace": "8:00/mi", "i_pace": "6:30/mi", "r_pace": "6:00/mi"},
            phase=TrainingPhase.BUILD,
            week_number=4,
            total_weeks=16,
        )
        assert day1.name == "AAA Long Template"
        ev1 = (
            db.query(WorkoutSelectionAuditEvent)
            .filter(WorkoutSelectionAuditEvent.athlete_id == athlete.id, WorkoutSelectionAuditEvent.plan_generation_id == "wirecheck-1")
            .first()
        )
        assert ev1 is not None
        assert ev1.selected_template_id == long_id

        # --- Intake: seed snapshot time_available_min=40 via the real API ---
        token = create_access_token({"sub": str(athlete.id), "email": athlete.email, "role": athlete.role})
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post(
            "/v1/onboarding/intake",
            json={
                "stage": "goals",
                "responses": {"goal_event_type": "5k", "time_available_min": 40},
                "completed": True,
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text

        # Use a new session to ensure we read committed state from the API request.
        db.close()
        db = SessionLocal()

        snap = db.query(CoachIntentSnapshot).filter(CoachIntentSnapshot.athlete_id == athlete.id).first()
        assert snap is not None
        assert snap.time_available_min == 40

        # --- After intake: AAA is filtered (min_time 60), so BBB is selected ---
        gen2 = ModelDrivenPlanGenerator(db)
        gen2._current_athlete_id = athlete.id
        gen2._plan_generation_id = "wirecheck-2"
        gen2._recent_quality_ids = []
        gen2._recent_quality_ids_shadow = []

        day2 = gen2._select_quality_workout_3d(
            date=date.today(),
            day_of_week="Thursday",
            target_tss=80,
            miles=10,
            paces={"e_pace": "9:00/mi", "t_pace": "7:15/mi", "m_pace": "8:00/mi", "i_pace": "6:30/mi", "r_pace": "6:00/mi"},
            phase=TrainingPhase.BUILD,
            week_number=4,
            total_weeks=16,
        )
        assert day2.name == "BBB Short Template"

        # Optional stronger proof: audit row exists with selected_template_id == BBB
        ev2 = (
            db.query(WorkoutSelectionAuditEvent)
            .filter(WorkoutSelectionAuditEvent.athlete_id == athlete.id, WorkoutSelectionAuditEvent.plan_generation_id == "wirecheck-2")
            .first()
        )
        assert ev2 is not None
        assert ev2.selected_template_id == short_id
        assert isinstance(ev2.payload, dict)
    finally:
        try:
            # Release any locks from uncommitted audit rows created during selection.
            try:
                db.rollback()
            except Exception:
                pass

            # Best-effort cleanup for suites that run against a persistent DB.
            db2 = SessionLocal()
            if athlete is not None:
                # Delete audit events
                for row in db2.query(WorkoutSelectionAuditEvent).filter(WorkoutSelectionAuditEvent.athlete_id == athlete.id).all():
                    db2.delete(row)
                # Delete intake rows + snapshot
                for row in db2.query(IntakeQuestionnaire).filter(IntakeQuestionnaire.athlete_id == athlete.id).all():
                    db2.delete(row)
                snap = db2.query(CoachIntentSnapshot).filter(CoachIntentSnapshot.athlete_id == athlete.id).first()
                if snap:
                    db2.delete(snap)
                # Delete any templates created by this wiring test (prefix-based).
                for row in db2.query(WorkoutTemplate).filter(WorkoutTemplate.id.like("build_000_long_%")).all():
                    db2.delete(row)
                for row in db2.query(WorkoutTemplate).filter(WorkoutTemplate.id.like("build_001_short_%")).all():
                    db2.delete(row)
                # Delete athlete
                a = db2.query(Athlete).filter(Athlete.id == athlete.id).first()
                if a:
                    db2.delete(a)
                db2.commit()
            db2.close()
        except Exception:
            try:
                db2.rollback()
                db2.close()
            except Exception:
                pass
        try:
            db.close()
        except Exception:
            pass

