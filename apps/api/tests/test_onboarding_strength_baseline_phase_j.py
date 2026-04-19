"""Phase J — onboarding strength_baseline stage.

Adds a new intake stage so athletes can declare their lifting
baseline (currently lifting?, days/week, experience bucket) at
onboarding. Responses are stored in IntakeQuestionnaire AND mirrored
to denormalized Athlete columns (lifts_currently,
lift_days_per_week, lift_experience_bucket) for fast read paths.

Tests:

  1. Source contract: stage is registered in the allowlist; the
     persistor function exists and validates input strictly enough
     that a typo cannot poison the population-level analysis.
  2. Pure-helper unit tests for the persistor — no DB needed beyond
     a stub Athlete object.
  3. End-to-end: post to /v1/onboarding/intake with the new stage,
     read the Athlete row back (skipped locally, runs in CI).
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest


# ---------------------------------------------------------------------
# Source contract
# ---------------------------------------------------------------------


class TestSourceContract:
    def test_strength_baseline_stage_is_in_allowlist(self):
        from routers.onboarding import _ALLOWED_INTAKE_STAGES

        assert "strength_baseline" in _ALLOWED_INTAKE_STAGES

    def test_persistor_helper_exists(self):
        from routers.onboarding import _persist_strength_baseline_to_athlete

        assert callable(_persist_strength_baseline_to_athlete)


# ---------------------------------------------------------------------
# Pure-helper unit tests
# ---------------------------------------------------------------------


def _new_athlete_stub():
    return SimpleNamespace(
        lifts_currently=None,
        lift_days_per_week=None,
        lift_experience_bucket=None,
    )


class TestStrengthBaselinePersistor:
    def test_valid_responses_mirror_onto_athlete_columns(self):
        from routers.onboarding import _persist_strength_baseline_to_athlete

        athlete = _new_athlete_stub()
        _persist_strength_baseline_to_athlete(
            db=None,
            athlete=athlete,
            responses={
                "lifts_currently": "yes",
                "lift_days_per_week": 3,
                "lift_experience_bucket": "established",
            },
        )
        assert athlete.lifts_currently == "yes"
        assert athlete.lift_days_per_week == 3.0
        assert athlete.lift_experience_bucket == "established"

    def test_case_and_whitespace_are_normalized(self):
        from routers.onboarding import _persist_strength_baseline_to_athlete

        athlete = _new_athlete_stub()
        _persist_strength_baseline_to_athlete(
            db=None,
            athlete=athlete,
            responses={
                "lifts_currently": "  YES  ",
                "lift_experience_bucket": "Returning",
            },
        )
        assert athlete.lifts_currently == "yes"
        assert athlete.lift_experience_bucket == "returning"

    def test_invalid_enum_values_are_silently_dropped(self):
        """Athletes can skip; bad values shouldn't poison the column."""
        from routers.onboarding import _persist_strength_baseline_to_athlete

        athlete = _new_athlete_stub()
        _persist_strength_baseline_to_athlete(
            db=None,
            athlete=athlete,
            responses={
                "lifts_currently": "maybe",  # not in enum
                "lift_experience_bucket": "guru",  # not in enum
            },
        )
        assert athlete.lifts_currently is None
        assert athlete.lift_experience_bucket is None

    def test_out_of_range_days_per_week_dropped(self):
        from routers.onboarding import _persist_strength_baseline_to_athlete

        athlete = _new_athlete_stub()
        _persist_strength_baseline_to_athlete(
            db=None,
            athlete=athlete,
            responses={"lift_days_per_week": 99},
        )
        assert athlete.lift_days_per_week is None

    def test_non_dict_response_is_safe(self):
        from routers.onboarding import _persist_strength_baseline_to_athlete

        athlete = _new_athlete_stub()
        _persist_strength_baseline_to_athlete(
            db=None, athlete=athlete, responses=None  # type: ignore[arg-type]
        )
        assert athlete.lifts_currently is None

    def test_partial_responses_only_set_present_fields(self):
        from routers.onboarding import _persist_strength_baseline_to_athlete

        athlete = _new_athlete_stub()
        athlete.lift_days_per_week = 5.0  # already set from a prior intake
        _persist_strength_baseline_to_athlete(
            db=None,
            athlete=athlete,
            responses={"lifts_currently": "no"},
        )
        assert athlete.lifts_currently == "no"
        # Existing value preserved when the field isn't in this payload.
        assert athlete.lift_days_per_week == 5.0


# ---------------------------------------------------------------------
# End-to-end (real Postgres). Local: skipped. CI: runs.
# ---------------------------------------------------------------------


_E2E_REASON = (
    "Onboarding strength_baseline e2e tests require a real Postgres "
    "database. Set RUN_STRENGTH_E2E=1 to enable locally; CI runs them."
)


@pytest.mark.skipif(
    os.environ.get("RUN_STRENGTH_E2E", "0") != "1", reason=_E2E_REASON
)
class TestStrengthBaselineE2E:
    def test_post_intake_persists_to_athlete_and_questionnaire(
        self, db_session, authenticated_client
    ):
        client, athlete = authenticated_client
        r = client.post(
            "/v1/onboarding/intake",
            json={
                "stage": "strength_baseline",
                "responses": {
                    "lifts_currently": "yes",
                    "lift_days_per_week": 3,
                    "lift_experience_bucket": "established",
                },
                "completed": True,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["stage"] == "strength_baseline"

        db_session.refresh(athlete)
        assert athlete.lifts_currently == "yes"
        assert float(athlete.lift_days_per_week) == 3.0
        assert athlete.lift_experience_bucket == "established"
