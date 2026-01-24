from __future__ import annotations

from uuid import uuid4
from datetime import date

from models import Athlete, WorkoutSelectionAuditEvent, WorkoutTemplate
from services.workout_audit_logger import record_workout_selection_event


def test_workout_selection_audit_event_persists(db_session):
    athlete = Athlete(
        email=f"audit_{uuid4()}@example.com",
        display_name="Audit Tester",
        subscription_tier="free",
        role="athlete",
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)

    # Ensure at least one template exists for FK integrity (if referenced).
    t = WorkoutTemplate(
        id="audit_template",
        name="Audit Template",
        intensity_tier="THRESHOLD",
        phase_compatibility=["build"],
        progression_logic={"type": "steps", "steps": [{"key": "s1", "structure": "2x10", "description_template": "2x10"}]},
        variance_tags=[],
        constraints={},
        dont_follow=[],
    )
    db_session.add(t)
    db_session.commit()

    payload = {
        "phase": "build",
        "week_in_phase": 2,
        "selected_template_id": "audit_template",
        "filters_applied": {"phase": 0},
    }

    record_workout_selection_event(
        db=db_session,
        athlete_id=athlete.id,
        trigger="plan_gen",
        payload=payload,
        plan_generation_id="pg-1",
        target_date=date.today().isoformat(),
        phase="build",
        phase_week=2,
        selected_template_id="audit_template",
        selection_mode="on",
    )
    db_session.commit()

    ev = (
        db_session.query(WorkoutSelectionAuditEvent)
        .filter(WorkoutSelectionAuditEvent.athlete_id == athlete.id)
        .order_by(WorkoutSelectionAuditEvent.created_at.desc())
        .first()
    )
    assert ev is not None
    assert ev.trigger == "plan_gen"
    assert ev.plan_generation_id == "pg-1"
    assert ev.phase == "build"
    assert ev.phase_week == 2
    assert ev.selected_template_id == "audit_template"
    assert isinstance(ev.payload, dict)
