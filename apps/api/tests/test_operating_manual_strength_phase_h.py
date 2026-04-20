"""Phase H — Operating Manual strength domain + narration suppression.

The Operating Manual reports patterns the engine has confirmed about
THIS athlete. Strength is a new observation domain (StrideIQ never
prescribes a routine, never tells the athlete what to do at the gym —
see docs/specs/STRENGTH_V1_SCOPE.md §10).

These tests pin three things:

  1. The strength domain exists in the public taxonomy
     (DOMAIN_ORDER / DOMAIN_LABELS / DOMAIN_DESCRIPTIONS) so the
     /v1/intelligence/manual response carries a strength block.
  2. _classify_domain routes the canonical engine input names to
     "strength" instead of bucketing them into training_pattern.
     Includes negative cases so unrelated inputs don't bleed in.
  3. Narration purity: when _rewrite_headline runs against a
     strength finding, the produced sentence is observational and
     contains zero prescriptive vocabulary. Strength domain
     descriptions and translations are likewise observation-only.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


# ---------------------------------------------------------------------
# 1. Domain taxonomy
# ---------------------------------------------------------------------


class TestStrengthDomainTaxonomy:
    def test_strength_in_domain_order(self):
        from services.operating_manual import DOMAIN_ORDER

        assert "strength" in DOMAIN_ORDER

    def test_strength_in_domain_labels(self):
        from services.operating_manual import DOMAIN_LABELS

        assert DOMAIN_LABELS["strength"] == "Strength"

    def test_strength_has_observation_description(self):
        """Description must read as observation, not prescription."""
        from services.operating_manual import DOMAIN_DESCRIPTIONS

        desc = DOMAIN_DESCRIPTIONS["strength"].lower()
        assert desc, "Strength domain must have a description"

        forbidden = [
            "should ", "must ", "recommended", "we recommend",
            "you need", "prescribe", "do this", "perform ",
        ]
        for term in forbidden:
            assert term not in desc, (
                f"Strength domain description contains prescriptive "
                f"language: {term!r} -> {desc!r}"
            )


# ---------------------------------------------------------------------
# 2. Domain classification
# ---------------------------------------------------------------------


class TestStrengthDomainClassification:
    @pytest.mark.parametrize(
        "input_name",
        [
            "ct_strength_sessions_7d",
            "ct_strength_duration_min",
            "ct_strength_tss_7d",
            "ct_total_sets",
            "ct_lower_body_sets",
            "ct_upper_body_sets",
            "ct_heavy_sets",
            "ct_hours_since_strength",
            "estimated_1rm",
            "lift_days_per_week",
            "lifts_currently",
            "lift_experience_bucket",
        ],
    )
    def test_strength_inputs_classify_as_strength(self, input_name):
        from services.operating_manual import _classify_domain

        # Output side intentionally generic so the rule must match the input.
        assert _classify_domain(input_name, "pace_easy") == "strength"

    @pytest.mark.parametrize(
        "input_name,expected_domain",
        [
            ("garmin_hrv_5min_high", "sleep"),
            ("ctl", "training_load"),
            ("dew_point_f", "environmental"),
            ("readiness_1_5", "subjective"),
        ],
    )
    def test_unrelated_inputs_do_not_bleed_into_strength(
        self, input_name, expected_domain
    ):
        from services.operating_manual import _classify_domain

        assert _classify_domain(input_name, "pace_easy") == expected_domain


# ---------------------------------------------------------------------
# 3. Narration purity
# ---------------------------------------------------------------------


_FORBIDDEN_PRESCRIPTIVE_TOKENS = (
    "you should ",
    "you must ",
    "we recommend",
    "we suggest",
    "try ",
    "perform ",
    "do this",
    "prescribe",
    "your plan",
    "increase your ",
    "decrease your ",
)


def _make_finding(
    input_name: str,
    output_metric: str,
    direction: str = "positive",
    r: float = 0.45,
    lag: int = 0,
):
    return SimpleNamespace(
        input_name=input_name,
        output_metric=output_metric,
        direction=direction,
        correlation_coefficient=r,
        time_lag_days=lag,
    )


class TestStrengthNarrationPurity:
    @pytest.mark.parametrize(
        "input_name,output_metric",
        [
            ("ct_strength_sessions_7d", "pace_easy"),
            ("ct_lower_body_sets", "efficiency_threshold"),
            ("ct_heavy_sets", "vo2_estimate"),
            ("ct_hours_since_strength", "pace_threshold"),
            ("estimated_1rm", "pace_easy"),
        ],
    )
    def test_headline_is_observational_not_prescriptive(
        self, input_name, output_metric
    ):
        from services.operating_manual import _rewrite_headline

        finding = _make_finding(input_name, output_metric)
        headline = _rewrite_headline(finding).lower()

        for token in _FORBIDDEN_PRESCRIPTIVE_TOKENS:
            assert token not in headline, (
                f"Strength headline {headline!r} contains forbidden "
                f"prescriptive token {token!r}"
            )

        assert headline.startswith("when "), (
            "Strength headlines must lead with an observation clause "
            "('When ...'), not a directive."
        )

    def test_strength_input_translations_are_descriptive(self):
        """Translations for strength inputs read as labels, not commands."""
        from services.fingerprint_context import COACHING_LANGUAGE

        for key in [
            "ct_strength_sessions_7d",
            "ct_total_sets",
            "ct_lower_body_sets",
            "ct_heavy_sets",
            "ct_hours_since_strength",
            "lifts_currently",
            "lift_days_per_week",
            "lift_experience_bucket",
            "estimated_1rm",
        ]:
            assert key in COACHING_LANGUAGE, (
                f"Strength engine input {key!r} missing from "
                f"COACHING_LANGUAGE — Manual will fall back to raw "
                f"snake_case."
            )
            label = COACHING_LANGUAGE[key].lower()
            for token in _FORBIDDEN_PRESCRIPTIVE_TOKENS:
                assert token not in label, (
                    f"Translation for {key!r} contains prescriptive "
                    f"token {token!r}: {label!r}"
                )

    def test_strength_inputs_are_not_suppressed_for_athlete(self):
        """Strength inputs must surface — they're how the athlete sees
        what their lifting actually does for them. Suppressing them
        would defeat the purpose of the research instrument."""
        from services.fingerprint_context import _is_suppressed_for_athlete

        for key in [
            "ct_strength_sessions_7d",
            "ct_total_sets",
            "ct_lower_body_sets",
            "ct_heavy_sets",
            "estimated_1rm",
        ]:
            assert not _is_suppressed_for_athlete(key), (
                f"{key!r} is suppressed but Phase H requires it on "
                f"athlete-facing surfaces."
            )
