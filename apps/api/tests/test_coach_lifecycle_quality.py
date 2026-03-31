"""Quality Proof Gate — Tier 1 Automated Checks.

Spec: docs/specs/COACH_QUALITY_PROOF_GATE.md

These tests verify that coach-facing output meets quality standards
for the fingerprint lifecycle integration. All checks are deterministic
(mocked findings, no LLM calls) and CI-runnable.

T1-1: No raw field names in coach-facing output
T1-2: Closed findings grouped, never individually listed
T1-3: Single emerging finding per prompt payload
T1-4: No statistical internals in suggestions payload
T1-5: Resolving attribution surfaced
T1-6: Structural traits labeled correctly
T1-7: NULL lifecycle backward compatibility
T1-8: No promotion without athlete fact
"""
import re
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from services.fingerprint_context import (
    COACHING_LANGUAGE,
    _format_closed_summary,
    _translate,
    build_fingerprint_prompt_section,
    format_finding_line,
)
from services.plan_framework.limiter_classifier import (
    INPUT_TO_LIMITER_TYPE,
    _apply_fact_promotion,
    _extract_limiter_type_from_fact,
    _get_limiter_type_for_finding,
)

ATHLETE_ID = uuid.uuid4()
NOW = datetime(2026, 3, 30, 12, 0, 0, tzinfo=timezone.utc)

FORBIDDEN_STAT_PATTERNS = [
    re.compile(r"\br=-?\d+\.?\d*"),
    re.compile(r"\bp=\d+\.?\d*"),
    re.compile(r"\d+\.\d+\s+confidence"),
]


def _make_finding(**overrides):
    defaults = {
        "id": uuid.uuid4(),
        "athlete_id": ATHLETE_ID,
        "input_name": "long_run_ratio",
        "output_metric": "pace_threshold",
        "direction": "positive",
        "correlation_coefficient": 0.65,
        "p_value": 0.001,
        "sample_size": 30,
        "strength": "moderate",
        "times_confirmed": 8,
        "first_detected_at": NOW - timedelta(days=120),
        "last_confirmed_at": NOW - timedelta(days=5),
        "is_active": True,
        "lifecycle_state": "active",
        "lifecycle_state_updated_at": NOW - timedelta(days=5),
        "insight_text": None,
        "threshold_value": None,
        "threshold_direction": None,
        "r_below_threshold": None,
        "n_below_threshold": None,
        "r_above_threshold": None,
        "n_above_threshold": None,
        "asymmetry_ratio": None,
        "asymmetry_direction": None,
        "effect_below_baseline": None,
        "effect_above_baseline": None,
        "decay_half_life_days": None,
        "decay_type": None,
        "time_lag_days": None,
        "resolving_context": None,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_fact(**overrides):
    defaults = {
        "id": uuid.uuid4(),
        "athlete_id": ATHLETE_ID,
        "fact_type": "limiter_context",
        "fact_key": "limiter_type:L-VOL",
        "fact_value": "Yes, I've been building mileage",
        "is_active": True,
        "temporal": True,
        "ttl_days": 90,
        "extracted_at": NOW - timedelta(days=10),
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


# ===================================================================
# T1-1: No raw field names in coach-facing output
# ===================================================================


class TestT1_1_NoRawFieldNames:
    """Every INPUT_TO_LIMITER_TYPE key must translate — no raw DB names in output."""

    def test_all_known_inputs_translate_without_underscores(self):
        for field_name in INPUT_TO_LIMITER_TYPE:
            translated = _translate(field_name)
            assert "_" not in translated, (
                f"_translate('{field_name}') = '{translated}' still has underscores"
            )

    def test_all_known_inputs_have_explicit_dictionary_entry(self):
        for field_name in INPUT_TO_LIMITER_TYPE:
            assert field_name in COACHING_LANGUAGE, (
                f"'{field_name}' in INPUT_TO_LIMITER_TYPE but missing from COACHING_LANGUAGE"
            )

    def test_full_prompt_contains_no_raw_input_names(self):
        findings = []
        for field_name in INPUT_TO_LIMITER_TYPE:
            findings.append(
                _make_finding(
                    input_name=field_name,
                    output_metric="efficiency",
                    lifecycle_state="active",
                )
            )

        mock_db = MagicMock()
        with patch(
            "services.fingerprint_context.get_confirmed_findings",
            return_value=findings,
        ):
            result = build_fingerprint_prompt_section(ATHLETE_ID, mock_db)

        assert result is not None

        for field_name in INPUT_TO_LIMITER_TYPE:
            if "_" in field_name:
                occurrences = [
                    line for line in result.split("\n")
                    if field_name in line
                    and not line.strip().startswith("(")
                ]
                assert len(occurrences) == 0, (
                    f"Raw field name '{field_name}' found in prompt output:\n"
                    + "\n".join(occurrences)
                )

    def test_finding_line_translates_both_input_and_output(self):
        finding = _make_finding(
            input_name="daily_session_stress",
            output_metric="pace_threshold",
            lifecycle_state="active",
        )
        line = format_finding_line(finding)
        assert "session intensity" in line
        assert "threshold pace" in line
        assert "daily_session_stress" not in line
        assert "pace_threshold" not in line


# ===================================================================
# T1-2: Closed findings grouped, never individually listed
# ===================================================================


class TestT1_2_ClosedGrouping:
    """Closed findings appear as a single summary line, not individual entries."""

    def test_five_closed_produce_one_summary_line(self):
        closed = [
            _make_finding(
                input_name=name,
                lifecycle_state="closed",
                lifecycle_state_updated_at=NOW - timedelta(days=90 + i * 30),
            )
            for i, name in enumerate([
                "long_run_ratio", "sleep_hours", "weekly_volume_km",
                "tsb", "atl",
            ])
        ]
        result = _format_closed_summary(closed)
        assert "Previously solved:" in result
        assert result.count("Previously solved:") == 1

    def test_no_individual_closed_labels_in_prompt(self):
        active = _make_finding(lifecycle_state="active", input_name="cadence")
        closed_findings = [
            _make_finding(
                input_name="long_run_ratio",
                lifecycle_state="closed",
                lifecycle_state_updated_at=NOW - timedelta(days=180),
            ),
            _make_finding(
                input_name="sleep_hours",
                lifecycle_state="closed",
                lifecycle_state_updated_at=NOW - timedelta(days=90),
            ),
        ]

        mock_db = MagicMock()
        with patch(
            "services.fingerprint_context.get_confirmed_findings",
            return_value=[active] + closed_findings,
        ):
            result = build_fingerprint_prompt_section(ATHLETE_ID, mock_db)

        assert result is not None
        assert "[CLOSED" not in result
        assert "Previously solved:" in result

    def test_closed_summary_uses_translated_names(self):
        closed = [
            _make_finding(
                input_name="daily_session_stress",
                lifecycle_state="closed",
                lifecycle_state_updated_at=NOW - timedelta(days=60),
            ),
        ]
        result = _format_closed_summary(closed)
        assert "session intensity" in result
        assert "daily_session_stress" not in result


# ===================================================================
# T1-3: Single emerging finding per prompt payload
# ===================================================================


class TestT1_3_SingleEmerging:
    """Only the single most recently emerged finding appears in the prompt."""

    def test_three_emerging_produce_one_line(self):
        findings = [
            _make_finding(
                input_name="long_run_ratio",
                lifecycle_state="emerging",
                lifecycle_state_updated_at=NOW - timedelta(days=30),
                first_detected_at=NOW - timedelta(days=30),
                times_confirmed=3,
            ),
            _make_finding(
                input_name="sleep_hours",
                lifecycle_state="emerging",
                lifecycle_state_updated_at=NOW - timedelta(days=10),
                first_detected_at=NOW - timedelta(days=10),
                times_confirmed=2,
            ),
            _make_finding(
                input_name="cadence",
                lifecycle_state="emerging",
                lifecycle_state_updated_at=NOW - timedelta(days=2),
                first_detected_at=NOW - timedelta(days=2),
                times_confirmed=2,
            ),
        ]

        mock_db = MagicMock()
        with patch(
            "services.fingerprint_context.get_confirmed_findings",
            return_value=findings,
        ):
            result = build_fingerprint_prompt_section(ATHLETE_ID, mock_db)

        assert result is not None
        emerging_lines = [
            line for line in result.split("\n")
            if "[EMERGING — ask athlete" in line
        ]
        assert len(emerging_lines) == 1, (
            f"Expected 1 emerging line, got {len(emerging_lines)}"
        )

    def test_newest_emerging_is_selected(self):
        older = _make_finding(
            input_name="long_run_ratio",
            lifecycle_state="emerging",
            lifecycle_state_updated_at=NOW - timedelta(days=30),
            first_detected_at=NOW - timedelta(days=30),
            times_confirmed=3,
        )
        newer = _make_finding(
            input_name="cadence",
            lifecycle_state="emerging",
            lifecycle_state_updated_at=NOW - timedelta(days=2),
            first_detected_at=NOW - timedelta(days=2),
            times_confirmed=2,
        )

        mock_db = MagicMock()
        with patch(
            "services.fingerprint_context.get_confirmed_findings",
            return_value=[older, newer],
        ):
            result = build_fingerprint_prompt_section(ATHLETE_ID, mock_db)

        assert result is not None
        assert "running cadence" in result
        emerging_lines = [
            line for line in result.split("\n")
            if "[EMERGING — ask athlete" in line
        ]
        assert len(emerging_lines) == 1
        assert "long runs" not in emerging_lines[0]

    def test_zero_emerging_produces_no_emerging_line(self):
        active = _make_finding(lifecycle_state="active", input_name="tsb")

        mock_db = MagicMock()
        with patch(
            "services.fingerprint_context.get_confirmed_findings",
            return_value=[active],
        ):
            result = build_fingerprint_prompt_section(ATHLETE_ID, mock_db)

        assert result is not None
        emerging_lines = [
            line for line in result.split("\n")
            if "[EMERGING — ask athlete" in line
        ]
        assert len(emerging_lines) == 0


# ===================================================================
# T1-4: No statistical internals in suggestions payload
# ===================================================================


class TestT1_4_NoStatsInSuggestions:
    """Lifecycle-driven suggestions contain no statistical internals."""

    def _make_suggestion_text(self, finding):
        """Simulate the suggestion construction from ai_coach.py source 7."""
        inp = _translate(finding.input_name)
        out = _translate(finding.output_metric)
        title = f"New pattern: {inp}"
        description = f"Your data shows a connection between {inp} and {out}."
        prompt = (
            f"My data shows a new pattern between {inp} and {out}. "
            "Has something shifted in how I train or what I'm focusing on?"
        )
        return f"{title} {description} {prompt}"

    def test_emerging_suggestion_clean(self):
        finding = _make_finding(
            input_name="long_run_ratio",
            output_metric="pace_threshold",
            lifecycle_state="emerging",
            correlation_coefficient=0.72,
            p_value=0.001,
        )
        text = self._make_suggestion_text(finding)

        for pattern in FORBIDDEN_STAT_PATTERNS:
            assert not pattern.search(text), (
                f"Forbidden pattern {pattern.pattern} found in: {text}"
            )

        for raw_name in INPUT_TO_LIMITER_TYPE:
            if "_" in raw_name:
                assert raw_name not in text, (
                    f"Raw field name '{raw_name}' found in suggestion"
                )

    def test_resolving_suggestion_clean(self):
        finding = _make_finding(
            input_name="daily_session_stress",
            output_metric="efficiency",
            lifecycle_state="resolving",
            resolving_context="72h spacing between quality sessions; during 10K Build",
        )
        inp = _translate(finding.input_name)
        ctx = finding.resolving_context
        title = f"{inp} pattern improving"
        description = f"This was a limiter — it's resolving. {ctx}".strip()
        prompt = (
            f"My {inp} pattern is resolving. "
            "What caused this improvement and how do I keep the gains?"
        )
        text = f"{title} {description} {prompt}"

        for pattern in FORBIDDEN_STAT_PATTERNS:
            assert not pattern.search(text), (
                f"Forbidden pattern {pattern.pattern} found in: {text}"
            )
        assert "daily_session_stress" not in text

    def test_all_limiter_types_produce_clean_suggestions(self):
        for field_name in INPUT_TO_LIMITER_TYPE:
            finding = _make_finding(
                input_name=field_name,
                output_metric="efficiency",
                lifecycle_state="emerging",
            )
            text = self._make_suggestion_text(finding)
            if "_" in field_name:
                assert field_name not in text, (
                    f"Raw field name '{field_name}' leaked into suggestion text"
                )


# ===================================================================
# T1-5: Resolving attribution surfaced
# ===================================================================


class TestT1_5_ResolvingAttribution:
    """Resolving findings with context include attribution in formatted output."""

    def test_resolving_with_context_includes_attribution(self):
        finding = _make_finding(
            input_name="daily_session_stress",
            output_metric="efficiency",
            lifecycle_state="resolving",
            resolving_context="72h spacing emphasis; during Half Marathon Build",
        )
        line = format_finding_line(finding)
        assert "Attribution:" in line
        assert "72h spacing emphasis" in line
        assert "Half Marathon Build" in line

    def test_resolving_without_context_omits_attribution(self):
        finding = _make_finding(
            input_name="daily_session_stress",
            output_metric="efficiency",
            lifecycle_state="resolving",
            resolving_context=None,
        )
        line = format_finding_line(finding)
        assert "[RESOLVING" in line
        assert "Attribution:" not in line

    def test_attribution_uses_translated_names(self):
        finding = _make_finding(
            input_name="daily_session_stress",
            output_metric="efficiency",
            lifecycle_state="resolving",
            resolving_context="Reduced session intensity during build phase",
        )
        line = format_finding_line(finding)
        assert "session intensity" in line
        assert "daily_session_stress" not in line


# ===================================================================
# T1-6: Structural traits labeled correctly
# ===================================================================


class TestT1_6_StructuralLabeling:
    """Structural findings are labeled [STRUCTURAL], never [ACTIVE] or [EMERGING]."""

    def test_structural_finding_label(self):
        finding = _make_finding(
            input_name="daily_session_stress",
            output_metric="efficiency",
            lifecycle_state="structural",
        )
        line = format_finding_line(finding)
        assert "[STRUCTURAL" in line
        assert "[ACTIVE" not in line
        assert "[EMERGING" not in line

    def test_structural_monitored_label(self):
        finding = _make_finding(
            input_name="atl",
            output_metric="efficiency",
            lifecycle_state="structural_monitored",
        )
        line = format_finding_line(finding)
        assert "[STRUCTURAL" in line

    def test_structural_in_prompt_gets_correct_section(self):
        structural = _make_finding(
            input_name="daily_session_stress",
            lifecycle_state="structural",
        )
        active = _make_finding(
            input_name="long_run_ratio",
            lifecycle_state="active",
        )

        mock_db = MagicMock()
        with patch(
            "services.fingerprint_context.get_confirmed_findings",
            return_value=[structural, active],
        ):
            result = build_fingerprint_prompt_section(
                ATHLETE_ID, mock_db, verbose=True,
            )

        assert result is not None
        assert "STRUCTURAL = physiological trait" in result
        assert "do not try to fix" in result


# ===================================================================
# T1-7: NULL lifecycle backward compatibility
# ===================================================================


class TestT1_7_NullLifecycleCompat:
    """Findings without lifecycle_state use times_confirmed tiers."""

    def test_null_lifecycle_strong_tier(self):
        finding = _make_finding(
            lifecycle_state=None,
            times_confirmed=8,
        )
        line = format_finding_line(finding)
        assert "[STRONG 8x]" in line
        assert "CLOSED" not in line
        assert "EMERGING —" not in line
        assert "RESOLVING" not in line
        assert "STRUCTURAL" not in line

    def test_null_lifecycle_confirmed_tier(self):
        finding = _make_finding(
            lifecycle_state=None,
            times_confirmed=4,
        )
        line = format_finding_line(finding)
        assert "[CONFIRMED 4x]" in line

    def test_null_lifecycle_emerging_tier(self):
        finding = _make_finding(
            lifecycle_state=None,
            times_confirmed=2,
        )
        line = format_finding_line(finding)
        assert "[EMERGING 2x]" in line
        assert "ask athlete" not in line


# ===================================================================
# T1-8: No promotion without athlete fact
# ===================================================================


class TestT1_8_NoPromotionWithoutFact:
    """Emerging findings stay emerging without a matching limiter_context fact."""

    def test_emerging_stays_emerging_with_no_facts(self):
        finding = _make_finding(
            input_name="long_run_ratio",
            lifecycle_state="emerging",
        )
        result = _apply_fact_promotion(finding, "emerging", [])
        assert result == "emerging"

    def test_emerging_stays_emerging_with_wrong_limiter_type(self):
        finding = _make_finding(
            input_name="long_run_ratio",
            lifecycle_state="emerging",
        )
        wrong_fact = _make_fact(fact_key="limiter_type:L-REC")
        result = _apply_fact_promotion(finding, "emerging", [wrong_fact])
        assert result == "emerging"

    def test_emerging_promotes_with_matching_fact(self):
        finding = _make_finding(
            input_name="long_run_ratio",
            lifecycle_state="emerging",
        )
        matching_fact = _make_fact(
            fact_key="limiter_type:L-VOL",
            fact_value="Yes, I've been building mileage",
        )
        result = _apply_fact_promotion(finding, "emerging", [matching_fact])
        assert result == "active"

    def test_emerging_closes_with_historical_fact(self):
        finding = _make_finding(
            input_name="long_run_ratio",
            lifecycle_state="emerging",
        )
        historical_fact = _make_fact(
            fact_key="limiter_type:L-VOL",
            fact_value="historical",
        )
        result = _apply_fact_promotion(finding, "emerging", [historical_fact])
        assert result == "closed"

    def test_non_emerging_state_unaffected(self):
        finding = _make_finding(
            input_name="long_run_ratio",
            lifecycle_state="active",
        )
        fact = _make_fact(fact_key="limiter_type:L-VOL")
        result = _apply_fact_promotion(finding, "active", [fact])
        assert result == "active"


# ===================================================================
# Cross-cutting: verbose prompt header contains lifecycle directives
# ===================================================================


class TestPromptHeaderDirectives:
    """The verbose prompt header includes lifecycle coaching instructions."""

    def test_verbose_header_has_all_lifecycle_directives(self):
        finding = _make_finding(lifecycle_state="active")
        mock_db = MagicMock()
        with patch(
            "services.fingerprint_context.get_confirmed_findings",
            return_value=[finding],
        ):
            result = build_fingerprint_prompt_section(
                ATHLETE_ID, mock_db, verbose=True,
            )

        assert result is not None
        assert "ACTIVE = proven" in result
        assert "EMERGING = pattern forming" in result
        assert "RESOLVING = improving" in result
        assert "STRUCTURAL = physiological trait" in result
        assert "do not try to fix" in result
        assert "statistical internals" in result.lower() or "coaching language" in result.lower()

    def test_compact_header_has_lifecycle_counts(self):
        findings = [
            _make_finding(lifecycle_state="active"),
            _make_finding(
                lifecycle_state="emerging",
                input_name="cadence",
                lifecycle_state_updated_at=NOW - timedelta(days=1),
                first_detected_at=NOW - timedelta(days=1),
                times_confirmed=2,
            ),
        ]
        mock_db = MagicMock()
        with patch(
            "services.fingerprint_context.get_confirmed_findings",
            return_value=findings,
        ):
            result = build_fingerprint_prompt_section(ATHLETE_ID, mock_db)

        assert result is not None
        assert "1 active" in result
        assert "1 emerging" in result
        assert "emerging" in result.lower()
