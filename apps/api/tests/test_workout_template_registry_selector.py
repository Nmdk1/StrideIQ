from __future__ import annotations

from uuid import uuid4
from datetime import date

import pytest


def _mk_template(
    *,
    template_id: str,
    phases: list[str],
    intensity_tier: str,
    steps: list[dict],
    variance_tags: list[str] | None = None,
    constraints: dict | None = None,
    dont_follow: list[str] | None = None,
):
    from models import WorkoutTemplate

    return WorkoutTemplate(
        id=template_id,
        name=template_id.replace("_", " ").title(),
        intensity_tier=intensity_tier,
        phase_compatibility=phases,
        progression_logic={"type": "steps", "steps": steps},
        variance_tags=variance_tags or [],
        constraints=constraints or {},
        dont_follow=dont_follow or [],
    )


def _clear_registry(db_session):
    # The migration seeds a minimal template set. For unit tests, isolate by clearing it.
    from models import WorkoutTemplate

    db_session.query(WorkoutTemplate).delete()
    db_session.commit()


class TestWorkoutTemplateRegistrySelectorInvariants:
    """
    Unit tests for the DB-backed 3D selector invariants.

    These are intentionally deterministic (no random explore/exploit).
    """

    def test_no_wrong_phase_template_selected(self, db_session):
        from services.workout_template_selector import select_quality_template

        _clear_registry(db_session)

        # One base, one build. Ask for BUILD => must never return BASE.
        db_session.add(
            _mk_template(
                template_id="base_a",
                phases=["base"],
                intensity_tier="AEROBIC",
                steps=[{"key": "s1", "structure": "strides", "description_template": "strides"}],
            )
        )
        db_session.add(
            _mk_template(
                template_id="build_a",
                phases=["build"],
                intensity_tier="THRESHOLD",
                steps=[{"key": "s1", "structure": "2x10", "description_template": "2x10 @ {t_pace}"}],
            )
        )
        db_session.commit()

        res = select_quality_template(
            db=db_session,
            athlete_id=uuid4(),
            phase="build",
            week_in_phase=1,
            total_phase_weeks=8,
            recent_template_ids=[],
            constraints={"time_available_min": 60, "facilities": []},
        )
        assert res["selected"]["template_id"] == "build_a"

    def test_dont_follow_is_respected(self, db_session):
        from services.workout_template_selector import select_quality_template

        _clear_registry(db_session)

        db_session.add(
            _mk_template(
                template_id="build_threshold",
                phases=["build"],
                intensity_tier="THRESHOLD",
                steps=[{"key": "s1", "structure": "2x10", "description_template": "2x10"}],
            )
        )
        db_session.add(
            _mk_template(
                template_id="build_vo2",
                phases=["build"],
                intensity_tier="VO2MAX",
                steps=[{"key": "s1", "structure": "6x400", "description_template": "6x400"}],
                dont_follow=["build_threshold"],
            )
        )
        db_session.commit()

        res = select_quality_template(
            db=db_session,
            athlete_id=uuid4(),
            phase="build",
            week_in_phase=2,
            total_phase_weeks=8,
            recent_template_ids=["build_threshold"],
            constraints={"time_available_min": 60, "facilities": []},
        )
        assert res["selected"]["template_id"] == "build_threshold"
        assert "dont_follow" in (res["filters_applied"] or {})

    def test_min_time_constraint_excludes_template(self, db_session):
        from services.workout_template_selector import select_quality_template

        _clear_registry(db_session)

        db_session.add(
            _mk_template(
                template_id="build_long_threshold",
                phases=["build"],
                intensity_tier="THRESHOLD",
                steps=[{"key": "s1", "structure": "3x10", "description_template": "3x10"}],
                constraints={"min_time_min": 60},
            )
        )
        db_session.add(
            _mk_template(
                template_id="build_short_vo2",
                phases=["build"],
                intensity_tier="VO2MAX",
                steps=[{"key": "s1", "structure": "5x400", "description_template": "5x400"}],
                constraints={"min_time_min": 35},
            )
        )
        db_session.commit()

        res = select_quality_template(
            db=db_session,
            athlete_id=uuid4(),
            phase="build",
            week_in_phase=3,
            total_phase_weeks=8,
            recent_template_ids=[],
            constraints={"time_available_min": 40, "facilities": []},
        )
        assert res["selected"]["template_id"] == "build_short_vo2"
        assert "min_time_min" in (res["filters_applied"] or {})

    def test_progression_step_is_deterministic(self, db_session):
        from services.workout_template_selector import select_quality_template

        _clear_registry(db_session)

        db_session.add(
            _mk_template(
                template_id="build_threshold_steps",
                phases=["build"],
                intensity_tier="THRESHOLD",
                steps=[
                    {"key": "s1", "structure": "2x10", "description_template": "2x10 @ {t_pace}"},
                    {"key": "s2", "structure": "3x10", "description_template": "3x10 @ {t_pace}"},
                ],
            )
        )
        db_session.commit()

        early = select_quality_template(
            db=db_session,
            athlete_id=uuid4(),
            phase="build",
            week_in_phase=1,
            total_phase_weeks=8,
            recent_template_ids=[],
            constraints={"time_available_min": 60, "facilities": []},
        )
        late = select_quality_template(
            db=db_session,
            athlete_id=uuid4(),
            phase="build",
            week_in_phase=8,
            total_phase_weeks=8,
            recent_template_ids=[],
            constraints={"time_available_min": 60, "facilities": []},
        )

        assert early["selected"]["progression_step"]["key"] == "s1"
        assert late["selected"]["progression_step"]["key"] == "s2"

    def test_determinism_same_inputs_same_output(self, db_session):
        from services.workout_template_selector import select_quality_template

        _clear_registry(db_session)

        db_session.add(
            _mk_template(
                template_id="build_a",
                phases=["build"],
                intensity_tier="THRESHOLD",
                steps=[{"key": "s1", "structure": "2x10", "description_template": "2x10"}],
            )
        )
        db_session.add(
            _mk_template(
                template_id="build_b",
                phases=["build"],
                intensity_tier="VO2MAX",
                steps=[{"key": "s1", "structure": "6x400", "description_template": "6x400"}],
            )
        )
        db_session.commit()

        athlete_id = uuid4()
        args = dict(
            db=db_session,
            athlete_id=athlete_id,
            phase="build",
            week_in_phase=4,
            total_phase_weeks=8,
            recent_template_ids=["build_a"],
            constraints={"time_available_min": 60, "facilities": []},
        )
        r1 = select_quality_template(**args)
        r2 = select_quality_template(**args)
        assert r1["selected"]["template_id"] == r2["selected"]["template_id"]
        assert r1["selected"]["progression_step"]["key"] == r2["selected"]["progression_step"]["key"]

    def test_type_is_selected_from_phase_allowlist_and_logged(self, db_session):
        """
        Invariant: the selector chooses a "type" (intensity_tier) from a phase-specific allowlist,
        and emits the allowlist + chosen type in audit payload.
        """
        from services.workout_template_selector import select_quality_template, PHASE_INTENSITY_TIER_ALLOWLIST

        _clear_registry(db_session)

        # Two build templates with different tiers.
        db_session.add(
            _mk_template(
                template_id="build_threshold_a",
                phases=["build"],
                intensity_tier="THRESHOLD",
                steps=[{"key": "s1", "structure": "2x10", "description_template": "2x10"}],
            )
        )
        db_session.add(
            _mk_template(
                template_id="build_vo2_a",
                phases=["build"],
                intensity_tier="VO2MAX",
                steps=[{"key": "s1", "structure": "6x400", "description_template": "6x400"}],
            )
        )
        db_session.commit()

        res = select_quality_template(
            db=db_session,
            athlete_id=uuid4(),
            phase="build",
            week_in_phase=2,
            total_phase_weeks=8,
            recent_template_ids=[],
            constraints={"time_available_min": 60, "facilities": []},
        )
        audit = res.get("audit") or {}
        assert audit.get("type_allowlist") == PHASE_INTENSITY_TIER_ALLOWLIST["build"]
        assert audit.get("type_selected") in set(PHASE_INTENSITY_TIER_ALLOWLIST["build"])
        assert res["selected"]["intensity_tier"].upper() == audit.get("type_selected")

    def test_type_selection_avoids_immediate_previous_type_when_possible(self, db_session):
        """
        Invariant: if multiple types are available, avoid repeating the immediate prior type.
        """
        from services.workout_template_selector import select_quality_template

        _clear_registry(db_session)

        db_session.add(
            _mk_template(
                template_id="build_threshold_a",
                phases=["build"],
                intensity_tier="THRESHOLD",
                steps=[{"key": "s1", "structure": "2x10", "description_template": "2x10"}],
            )
        )
        db_session.add(
            _mk_template(
                template_id="build_vo2_a",
                phases=["build"],
                intensity_tier="VO2MAX",
                steps=[{"key": "s1", "structure": "6x400", "description_template": "6x400"}],
            )
        )
        db_session.commit()

        # Previous template is THRESHOLD; expect VO2MAX to be selected if available.
        res = select_quality_template(
            db=db_session,
            athlete_id=uuid4(),
            phase="build",
            week_in_phase=3,
            total_phase_weeks=8,
            recent_template_ids=["build_threshold_a"],
            constraints={"time_available_min": 60, "facilities": []},
        )
        assert res["selected"]["intensity_tier"].upper() == "VO2MAX"

    def test_dont_repeat_window_excludes_recent_templates_when_possible(self, db_session):
        """
        Invariant: templates used within the recent dont-repeat window are excluded if possible.
        """
        from services.workout_template_selector import select_quality_template

        _clear_registry(db_session)

        # Two threshold templates so we can avoid repeating a specific recent template without forcing a type switch.
        db_session.add(
            _mk_template(
                template_id="build_threshold_a",
                phases=["build"],
                intensity_tier="THRESHOLD",
                steps=[{"key": "s1", "structure": "2x10", "description_template": "2x10"}],
            )
        )
        db_session.add(
            _mk_template(
                template_id="build_threshold_b",
                phases=["build"],
                intensity_tier="THRESHOLD",
                steps=[{"key": "s1", "structure": "3x8", "description_template": "3x8"}],
            )
        )
        db_session.commit()

        res = select_quality_template(
            db=db_session,
            athlete_id=uuid4(),
            phase="build",
            week_in_phase=4,
            total_phase_weeks=8,
            recent_template_ids=["build_threshold_a"],
            constraints={"time_available_min": 60, "facilities": []},
        )
        assert res["selected"]["template_id"] == "build_threshold_b"
        audit = res.get("audit") or {}
        assert audit.get("dont_repeat_window_relaxed") is False
        assert int(audit.get("dont_repeat_excluded_count") or 0) >= 1

    def test_dont_repeat_window_relaxes_when_all_candidates_are_recent(self, db_session):
        """
        Invariant: if dont-repeat would exclude all candidates, we relax deterministically
        (but still keep selection deterministic and safe).
        """
        from services.workout_template_selector import select_quality_template

        _clear_registry(db_session)

        # Only one valid template exists; it's also in the recent window.
        db_session.add(
            _mk_template(
                template_id="build_only_threshold",
                phases=["build"],
                intensity_tier="THRESHOLD",
                steps=[{"key": "s1", "structure": "2x10", "description_template": "2x10"}],
            )
        )
        db_session.commit()

        res = select_quality_template(
            db=db_session,
            athlete_id=uuid4(),
            phase="build",
            week_in_phase=5,
            total_phase_weeks=8,
            recent_template_ids=["build_only_threshold", "build_only_threshold", "build_only_threshold"],
            constraints={"time_available_min": 60, "facilities": []},
        )
        assert res["selected"]["template_id"] == "build_only_threshold"
        audit = res.get("audit") or {}
        assert audit.get("dont_repeat_window_relaxed") is True

