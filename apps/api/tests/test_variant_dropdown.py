"""
Variant Dropdown feature tests.

Covers:
- _resolve_variant_for_constraint_workout mapping
- Variant options filtering by stem + build_context_tag
- PATCH validation (invalid variant rejected)
- Endpoint-level PATCH contract test
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest

from services.plan_framework.variant_selector import (
    select_variant,
    _load_registry,
    _STEM_MAP,
    clear_variant_selector_cache,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_variant_selector_cache()
    yield
    clear_variant_selector_cache()


class TestResolveVariantForConstraintWorkout:
    """Mirrors _resolve_variant_for_constraint_workout logic using select_variant directly."""

    _PHASE_TO_TAG = {
        "rebuild": "durability_rebuild",
        "base": "base_building",
        "build": "full_featured_healthy",
        "peak": "peak_fitness",
        "race": "race_specific",
        "taper": "minimal_sharpen",
        "recovery": "durability_rebuild",
    }

    def _resolve(self, workout_type, phase, week=1, total=8, distance="marathon", title=""):
        tag = self._PHASE_TO_TAG.get(phase, "full_featured_healthy")
        return select_variant(
            workout_type=workout_type,
            build_context_tag=tag,
            week_in_phase=week,
            total_phase_weeks=total,
            distance=distance,
            title=title,
        )

    def test_threshold_build_resolves(self):
        vid = self._resolve("threshold", "build")
        assert vid is not None
        assert "threshold" in vid

    def test_intervals_peak_resolves(self):
        vid = self._resolve("intervals", "peak")
        assert vid is not None

    def test_easy_resolves_to_staple(self):
        vid = self._resolve("easy", "base")
        assert vid == "easy_conversational_staple"

    def test_rest_resolves(self):
        vid = self._resolve("rest", "build")
        assert vid == "rest_day_complete"

    def test_long_mp_resolves(self):
        vid = self._resolve("long_mp", "race")
        assert vid is not None
        assert "long_mp" in vid

    def test_unknown_type_returns_none(self):
        vid = self._resolve("cross_training", "build")
        assert vid is None

    def test_recovery_phase_maps_correctly(self):
        vid = self._resolve("easy", "recovery")
        assert vid == "easy_conversational_staple"

    def test_taper_intervals_gets_sharpen_variant(self):
        vid = self._resolve("intervals", "taper")
        assert vid == "vo2_minimal_sharpen_micro_touch"


class TestVariantOptionsFiltering:
    """Test the filtering logic used by the GET endpoint."""

    def test_threshold_build_returns_multiple_options(self):
        registry = _load_registry()
        stem = _STEM_MAP.get("threshold", "")
        build_tag = "full_featured_healthy"
        options = [
            v for v in registry
            if v.get("stem") == stem and build_tag in (v.get("build_context_tags") or [])
        ]
        assert len(options) >= 3, "Build phase threshold should have multiple variant options"

    def test_intervals_injury_return_limited(self):
        registry = _load_registry()
        stem = _STEM_MAP.get("intervals", "")
        options = [
            v for v in registry
            if v.get("stem") == stem and "injury_return" in (v.get("build_context_tags") or [])
        ]
        ids = {v["id"] for v in options}
        assert ids == {"vo2_400m_short_reps_development", "vo2_conservative_low_dose"}

    def test_rest_has_single_option(self):
        registry = _load_registry()
        stem = _STEM_MAP.get("rest", "")
        options = [v for v in registry if v.get("stem") == stem]
        assert len(options) == 1
        assert options[0]["id"] == "rest_day_complete"

    def test_all_options_have_display_name(self):
        registry = _load_registry()
        for v in registry:
            assert v.get("display_name"), f"Missing display_name for {v['id']}"


class TestPhaseLocalProgression:
    """Validate that phase-local inputs produce correct progression variants."""

    _PHASE_TO_TAG = TestResolveVariantForConstraintWorkout._PHASE_TO_TAG

    def _resolve(self, workout_type, phase, week, total, distance="marathon"):
        tag = self._PHASE_TO_TAG.get(phase, "full_featured_healthy")
        return select_variant(
            workout_type=workout_type,
            build_context_tag=tag,
            week_in_phase=week,
            total_phase_weeks=total,
            distance=distance,
        )

    def test_intervals_early_vs_late_phase(self):
        """Early in a 6-week build should pick 400m; late should pick 1000m."""
        early = self._resolve("intervals", "build", week=1, total=6)
        late = self._resolve("intervals", "build", week=6, total=6)
        assert early == "vo2_400m_short_reps_development"
        assert late == "vo2_1000m_reps_classic"

    def test_intervals_global_vs_phase_local_differ(self):
        """Proves the bug: global week 9/12 gives 0.75 progress (1000m),
        but phase-local week 1/4 of peak gives 0.25 progress (400m).
        With global inputs the wrong variant is selected for an early peak week."""
        global_result = select_variant(
            workout_type="intervals",
            build_context_tag="peak_fitness",
            week_in_phase=9,
            total_phase_weeks=12,
        )
        phase_local_result = select_variant(
            workout_type="intervals",
            build_context_tag="peak_fitness",
            week_in_phase=1,
            total_phase_weeks=4,
        )
        assert global_result == "vo2_1000m_reps_classic", "global 9/12=0.75 → late variant"
        assert phase_local_result == "vo2_400m_short_reps_development", "phase-local 1/4=0.25 → early variant"
        assert global_result != phase_local_result

    def test_repetitions_early_vs_late_phase(self):
        """Early in a 4-week build → 200m; late → 300m."""
        early = self._resolve("repetitions", "build", week=1, total=4)
        late = self._resolve("repetitions", "build", week=4, total=4)
        assert early == "reps_200m_neuromuscular_early"
        assert late == "reps_300m_economy_late"

    def test_threshold_intervals_early_vs_late_phase(self):
        """Early → 5-6 min; late → cruise classic."""
        early = self._resolve("threshold_intervals", "build", week=1, total=6)
        late = self._resolve("threshold_intervals", "build", week=6, total=6)
        assert early == "threshold_intervals_5_to_6_min"
        assert late == "cruise_intervals_classic"


class TestVariantPatchValidation:
    """Test that PATCH validation works correctly (stem + build_context_tag)."""

    def test_valid_variant_matches_stem(self):
        registry = _load_registry()
        stem = _STEM_MAP.get("threshold", "")
        valid_ids = {v["id"] for v in registry if v.get("stem") == stem}
        assert "threshold_continuous_progressive" in valid_ids
        assert "vo2_400m_short_reps_development" not in valid_ids

    def test_cross_stem_variant_rejected(self):
        registry = _load_registry()
        stem = _STEM_MAP.get("easy", "")
        valid_ids = {v["id"] for v in registry if v.get("stem") == stem}
        assert "threshold_continuous_progressive" not in valid_ids

    def test_context_ineligible_variant_rejected(self):
        """A same-stem variant that is not eligible for the workout's phase
        should not appear in the valid set."""
        registry = _load_registry()
        stem = _STEM_MAP.get("intervals", "")
        build_tag = "minimal_sharpen"
        valid_ids = {
            v["id"] for v in registry
            if v.get("stem") == stem and build_tag in (v.get("build_context_tags") or [])
        }
        assert "vo2_minimal_sharpen_micro_touch" in valid_ids
        assert "vo2_1000m_reps_classic" not in valid_ids, (
            "1000m classic should not be eligible in taper/sharpen phase"
        )


class TestVariantPatchEndpoint:
    """Endpoint-level tests against PATCH /v1/calendar/workouts/{id}/variant.

    These hit the real FastAPI route to lock the contract end-to-end.
    """

    @pytest.fixture()
    def _endpoint_setup(self):
        from fastapi.testclient import TestClient

        from core.database import SessionLocal
        from core.security import create_access_token
        from main import app
        from models import Athlete, PlannedWorkout, TrainingPlan

        db = SessionLocal()
        athlete = None
        try:
            athlete = Athlete(
                email=f"variant_patch_{uuid4()}@example.com",
                display_name="Variant PATCH Test",
                subscription_tier="free",
                role="athlete",
                onboarding_stage="complete",
                onboarding_completed=True,
            )
            db.add(athlete)
            db.commit()
            db.refresh(athlete)

            plan = TrainingPlan(
                athlete_id=athlete.id,
                name="Test Plan",
                status="active",
                goal_race_date=date.today() + timedelta(weeks=8),
                goal_race_distance_m=42195,
                plan_start_date=date.today(),
                plan_end_date=date.today() + timedelta(weeks=8),
                total_weeks=8,
                plan_type="marathon",
                generation_method="constraint_aware",
            )
            db.add(plan)
            db.commit()
            db.refresh(plan)

            workout = PlannedWorkout(
                plan_id=plan.id,
                athlete_id=athlete.id,
                scheduled_date=date.today() + timedelta(days=3),
                week_number=1,
                day_of_week=3,
                workout_type="intervals",
                title="VO2 Intervals",
                phase="taper",
                workout_variant_id="vo2_minimal_sharpen_micro_touch",
            )
            db.add(workout)
            db.commit()
            db.refresh(workout)

            token = create_access_token(
                {"sub": str(athlete.id), "email": athlete.email, "role": athlete.role}
            )
            client = TestClient(app)
            headers = {"Authorization": f"Bearer {token}"}

            yield {
                "client": client,
                "headers": headers,
                "workout": workout,
                "db": db,
                "athlete": athlete,
                "plan": plan,
            }
        finally:
            try:
                if athlete is not None:
                    for pw in db.query(PlannedWorkout).filter(
                        PlannedWorkout.athlete_id == athlete.id
                    ).all():
                        db.delete(pw)
                    for tp in db.query(TrainingPlan).filter(
                        TrainingPlan.athlete_id == athlete.id
                    ).all():
                        db.delete(tp)
                    a = db.query(Athlete).filter(Athlete.id == athlete.id).first()
                    if a:
                        db.delete(a)
                    db.commit()
            except Exception:
                db.rollback()
            db.close()

    def test_patch_accepts_context_eligible_variant(self, _endpoint_setup):
        ctx = _endpoint_setup
        resp = ctx["client"].patch(
            f"/v1/calendar/workouts/{ctx['workout'].id}/variant",
            json={"variant_id": "vo2_minimal_sharpen_micro_touch"},
            headers=ctx["headers"],
        )
        assert resp.status_code == 200, resp.text

    def test_patch_rejects_context_ineligible_same_stem(self, _endpoint_setup):
        """vo2_1000m_reps_classic has stem 'intervals' but is not tagged
        with 'minimal_sharpen', so PATCH must reject it for a taper workout."""
        ctx = _endpoint_setup
        resp = ctx["client"].patch(
            f"/v1/calendar/workouts/{ctx['workout'].id}/variant",
            json={"variant_id": "vo2_1000m_reps_classic"},
            headers=ctx["headers"],
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "not eligible" in resp.json()["detail"].lower() or "not eligible" in resp.text.lower()

    def test_patch_rejects_cross_stem_variant(self, _endpoint_setup):
        ctx = _endpoint_setup
        resp = ctx["client"].patch(
            f"/v1/calendar/workouts/{ctx['workout'].id}/variant",
            json={"variant_id": "threshold_continuous_progressive"},
            headers=ctx["headers"],
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
