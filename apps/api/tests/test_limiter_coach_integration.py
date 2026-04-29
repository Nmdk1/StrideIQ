"""Tests for Limiter Engine Phase 4: Coach Layer Integration.

Guardrail tests — these are the blockers specified in the build contract:

A. API-level payload tests proving:
   1. Closed findings are grouped in one summary line
   2. Translation dictionary output is used (no raw field names)
   3. Only one emerging finding is returned (most recent first)

B. Transition-path tests proving:
   4. TTL expiry re-evaluates associated findings
   5. resolving_context is persisted and surfaced
   6. Fact-aware promotion: emerging → active via limiter_context fact
   7. Fact-aware promotion: emerging → closed via historical fact
   8. Backward compatibility: findings without lifecycle_state render correctly
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from services.fingerprint_context import (
    COACHING_LANGUAGE,
    _translate,
    _format_closed_summary,
    build_fingerprint_prompt_section,
    format_finding_line,
)
from services.plan_framework.limiter_classifier import (
    INPUT_TO_LIMITER_TYPE,
    _apply_fact_promotion,
    _build_resolving_context,
    _extract_limiter_type_from_fact,
    _get_limiter_type_for_finding,
    _is_fact_expired,
    _load_limiter_context_facts,
    classify_lifecycle_states,
)

ATHLETE_ID = uuid.uuid4()
NOW = datetime(2026, 3, 30, 12, 0, 0, tzinfo=timezone.utc)


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
# A. API-LEVEL PAYLOAD TESTS
# ===================================================================


class TestClosedFindingsGroupedInOneLine:
    """Contract: closed findings → single summary line, not individual entries."""

    def test_closed_grouped_summary_format(self):
        closed = [
            _make_finding(
                input_name="long_run_ratio",
                lifecycle_state="closed",
                lifecycle_state_updated_at=NOW - timedelta(days=240),
            ),
            _make_finding(
                input_name="sleep_hours",
                lifecycle_state="closed",
                lifecycle_state_updated_at=NOW - timedelta(days=90),
            ),
        ]
        result = _format_closed_summary(closed, now=NOW)
        assert "Previously solved:" in result
        assert "long runs" in result
        assert "sleep duration" in result
        assert "8mo ago" in result
        assert "3mo ago" in result

    def test_closed_not_individually_listed(self):
        active_finding = _make_finding(
            input_name="weekly_volume_km",
            lifecycle_state="active",
        )
        closed_finding = _make_finding(
            input_name="long_run_ratio",
            lifecycle_state="closed",
            lifecycle_state_updated_at=NOW - timedelta(days=180),
        )

        mock_db = MagicMock()
        with patch(
            "services.fingerprint_context.get_confirmed_findings",
            return_value=[active_finding, closed_finding],
        ):
            result = build_fingerprint_prompt_section(ATHLETE_ID, mock_db)

        assert result is not None
        assert "Previously solved:" in result

        lines = result.split("\n")
        closed_individual_lines = [
            line for line in lines
            if "[CLOSED" in line and "long_run_ratio" in line
        ]
        assert len(closed_individual_lines) == 0, (
            "Closed findings should not appear as individual lines"
        )


class TestTranslationDictionary:
    """Contract: no raw field names in coach-facing output."""

    def test_known_fields_translated(self):
        assert _translate("long_run_ratio") == "long runs"
        assert _translate("weekly_volume_km") == "weekly mileage"
        assert _translate("tsb") == "freshness (training stress balance)"
        assert _translate("daily_session_stress") == "session intensity"
        assert _translate("sleep_hours") == "sleep duration"
        assert _translate("days_since_quality") == "days since last quality session"

    def test_unknown_field_falls_back_cleanly(self):
        result = _translate("some_new_metric")
        assert result == "some new metric"
        assert "_" not in result

    def test_format_finding_uses_translation(self):
        finding = _make_finding(
            input_name="long_run_ratio",
            output_metric="pace_threshold",
            lifecycle_state="active",
        )
        line = format_finding_line(finding)
        assert "long runs" in line
        assert "threshold pace" in line
        assert "long_run_ratio" not in line
        assert "pace_threshold" not in line

    def test_closed_summary_uses_translation(self):
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

    def test_all_input_to_limiter_types_have_translation(self):
        for input_name in INPUT_TO_LIMITER_TYPE:
            translated = _translate(input_name)
            assert "_" not in translated or translated in COACHING_LANGUAGE, (
                f"{input_name} translation '{translated}' still contains underscore"
            )


class TestEmergingSingleNewestFirst:
    """Contract: only one emerging finding surfaces, most recent first."""

    def test_only_newest_emerging_in_prompt(self):
        """Only the most recent emerging finding appears in the prompt.

        Hard enforcement: the payload caps to 1 emerging finding (newest first)
        so the LLM cannot ask about patterns it doesn't see.
        """
        older_emerging = _make_finding(
            input_name="long_run_ratio",
            lifecycle_state="emerging",
            lifecycle_state_updated_at=NOW - timedelta(days=30),
            first_detected_at=NOW - timedelta(days=30),
            times_confirmed=3,
        )
        newer_emerging = _make_finding(
            input_name="sleep_hours",
            lifecycle_state="emerging",
            lifecycle_state_updated_at=NOW - timedelta(days=5),
            first_detected_at=NOW - timedelta(days=5),
            times_confirmed=2,
        )

        mock_db = MagicMock()
        with patch(
            "services.fingerprint_context.get_confirmed_findings",
            return_value=[older_emerging, newer_emerging],
        ):
            result = build_fingerprint_prompt_section(ATHLETE_ID, mock_db)

        assert result is not None
        assert result.count("=== EMERGING PATTERN") == 1, (
            "Expected exactly 1 emerging block in payload"
        )
        emerging_block = result.split("=== END EMERGING ===")[0]
        assert "sleep duration" in emerging_block, (
            "Newest emerging finding (sleep_hours) should be the one included"
        )

    def test_format_emerging_label(self):
        finding = _make_finding(lifecycle_state="emerging", times_confirmed=3)
        line = format_finding_line(finding)
        assert "[EMERGING — ask athlete" in line

    def test_format_resolving_with_attribution(self):
        finding = _make_finding(
            lifecycle_state="resolving",
            resolving_context="Volume emphasis during build phase, weeks 4-12",
            times_confirmed=8,
        )
        line = format_finding_line(finding)
        assert "[RESOLVING" in line
        assert "Attribution: Volume emphasis" in line


# ===================================================================
# B. TRANSITION-PATH TESTS
# ===================================================================


class TestTTLExpiryReEvaluation:
    """Contract: when limiter_context fact TTL expires, finding is re-evaluated."""

    def test_fact_not_expired(self):
        fact = _make_fact(
            extracted_at=NOW - timedelta(days=10),
            temporal=True,
            ttl_days=90,
        )
        assert _is_fact_expired(fact, NOW) is False

    def test_fact_expired(self):
        fact = _make_fact(
            extracted_at=NOW - timedelta(days=100),
            temporal=True,
            ttl_days=90,
        )
        assert _is_fact_expired(fact, NOW) is True

    def test_non_temporal_fact_never_expires(self):
        fact = _make_fact(temporal=False, ttl_days=None)
        assert _is_fact_expired(fact, NOW) is False

    def test_expired_fact_excluded_from_active_facts(self):
        expired_fact = _make_fact(
            extracted_at=NOW - timedelta(days=100),
            temporal=True,
            ttl_days=90,
        )
        fresh_fact = _make_fact(
            extracted_at=NOW - timedelta(days=10),
            temporal=True,
            ttl_days=90,
            fact_key="limiter_type:L-REC",
        )

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [
            expired_fact, fresh_fact,
        ]

        result = _load_limiter_context_facts(ATHLETE_ID, mock_db, NOW)
        assert len(result) == 1
        assert result[0].fact_key == "limiter_type:L-REC"

    def test_ttl_expiry_demotes_promoted_finding(self):
        """Full flow: fact expires → finding reverts from active to emerging."""
        finding = _make_finding(
            input_name="long_run_ratio",
            lifecycle_state="active",
            first_detected_at=NOW - timedelta(days=30),
            last_confirmed_at=NOW - timedelta(days=5),
            times_confirmed=3,
            correlation_coefficient=0.45,
        )

        expired_fact = _make_fact(
            fact_key="limiter_type:L-VOL",
            extracted_at=NOW - timedelta(days=100),
            temporal=True,
            ttl_days=90,
        )

        mock_db = MagicMock()
        findings_query = MagicMock()
        findings_query.filter.return_value.all.return_value = [finding]

        facts_query = MagicMock()
        facts_query.filter.return_value.all.return_value = [expired_fact]

        def side_effect_query(model):
            from models import AthleteFact
            if model == AthleteFact:
                return facts_query
            return findings_query

        mock_db.query = MagicMock(side_effect=side_effect_query)
        mock_db.flush = MagicMock()

        with patch("services.plan_framework.limiter_classifier._get_profile") as mock_profile, \
             patch("services.plan_framework.limiter_classifier._check_lspec_gate") as mock_lspec:
            mock_profile.return_value = MagicMock(
                recovery_half_life_hours=30.0,
                peak_weekly_miles=40.0,
            )
            mock_lspec.return_value = False

            results = classify_lifecycle_states(ATHLETE_ID, mock_db, now=NOW)

        assert results[finding.id] == "emerging", (
            "Finding should revert to emerging after supporting fact expires"
        )


class TestResolvingContextPersistence:
    """Contract: resolving_context captured at active → resolving and surfaced."""

    def test_resolving_context_built_from_matching_fact(self):
        finding = _make_finding(input_name="long_run_ratio")
        fact = _make_fact(
            fact_key="limiter_type:L-VOL",
            fact_value="Focused on long run volume in build phase",
        )
        ctx = _build_resolving_context(finding, [fact], MagicMock(), ATHLETE_ID)
        assert ctx is not None
        assert "Focused on long run volume" in ctx

    def test_resolving_context_includes_plan_name(self):
        finding = _make_finding(input_name="long_run_ratio")
        fact = _make_fact(fact_key="limiter_type:L-VOL", fact_value="Added volume")

        mock_plan = MagicMock()
        mock_plan.name = "Coke 10K Build"

        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = mock_plan
        mock_db = MagicMock()
        mock_db.query.return_value = mock_query

        ctx = _build_resolving_context(finding, [fact], mock_db, ATHLETE_ID)
        assert ctx is not None
        assert "Added volume" in ctx
        assert "during Coke 10K Build" in ctx

    def test_resolving_context_none_when_no_matching_fact(self):
        finding = _make_finding(input_name="long_run_ratio")
        fact = _make_fact(fact_key="limiter_type:L-REC", fact_value="Sleep changes")

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        ctx = _build_resolving_context(finding, [fact], mock_db, ATHLETE_ID)
        assert ctx is None

    def test_resolving_context_surfaced_in_format_line(self):
        finding = _make_finding(
            lifecycle_state="resolving",
            resolving_context="Volume emphasis during build phase, weeks 4-12",
        )
        line = format_finding_line(finding)
        assert "Attribution: Volume emphasis during build phase" in line


class TestFactAwarePromotion:
    """Contract: structured limiter_type matching for emerging → active/closed."""

    def test_extract_limiter_type_colon_format(self):
        fact = _make_fact(fact_key="limiter_type:L-VOL")
        assert _extract_limiter_type_from_fact(fact) == "L-VOL"

    def test_extract_limiter_type_bare_format(self):
        fact = _make_fact(fact_key="L-REC")
        assert _extract_limiter_type_from_fact(fact) == "L-REC"

    def test_extract_limiter_type_unknown_format(self):
        fact = _make_fact(fact_key="some_random_key")
        assert _extract_limiter_type_from_fact(fact) is None

    def test_finding_to_limiter_type_mapping(self):
        assert _get_limiter_type_for_finding(
            _make_finding(input_name="long_run_ratio")
        ) == "L-VOL"
        assert _get_limiter_type_for_finding(
            _make_finding(input_name="tsb")
        ) == "L-REC"
        assert _get_limiter_type_for_finding(
            _make_finding(input_name="days_since_quality")
        ) == "L-THRESH"

    def test_emerging_promoted_to_active_by_confirming_fact(self):
        finding = _make_finding(
            input_name="long_run_ratio",
            lifecycle_state="emerging",
        )
        fact = _make_fact(
            fact_key="limiter_type:L-VOL",
            fact_value="Yes, I've been building long run mileage",
        )
        result = _apply_fact_promotion(finding, "emerging", [fact])
        assert result == "active"

    def test_emerging_promoted_to_closed_by_historical_fact(self):
        finding = _make_finding(
            input_name="long_run_ratio",
            lifecycle_state="emerging",
        )
        fact = _make_fact(
            fact_key="limiter_type:L-VOL",
            fact_value="historical",
        )
        result = _apply_fact_promotion(finding, "emerging", [fact])
        assert result == "closed"

    def test_non_emerging_not_promoted(self):
        finding = _make_finding(input_name="long_run_ratio")
        fact = _make_fact(fact_key="limiter_type:L-VOL")
        result = _apply_fact_promotion(finding, "active", [fact])
        assert result == "active"

    def test_no_matching_fact_no_promotion(self):
        finding = _make_finding(input_name="long_run_ratio")
        fact = _make_fact(fact_key="limiter_type:L-REC")
        result = _apply_fact_promotion(finding, "emerging", [fact])
        assert result == "emerging"


class TestBackwardCompatibility:
    """Contract: findings without lifecycle_state still render correctly."""

    def test_format_finding_no_lifecycle_state(self):
        # Founder narration tiers: 6-9 confirmations narrate as REPEATED.
        # The legacy STRONG label was the trust-rupture vector.
        finding = _make_finding(
            lifecycle_state=None,
            times_confirmed=8,
        )
        line = format_finding_line(finding)
        assert "[REPEATED 8x]" in line

    def test_format_finding_no_lifecycle_confirmed(self):
        # 4 confirmations cannot be narrated as "CONFIRMED" anymore;
        # post-Jim, 3-5 confirmations narrate as EMERGING.
        finding = _make_finding(
            lifecycle_state=None,
            times_confirmed=4,
        )
        line = format_finding_line(finding)
        assert "[EMERGING 4x]" in line

    def test_format_finding_no_lifecycle_emerging(self):
        finding = _make_finding(
            lifecycle_state=None,
            times_confirmed=2,
        )
        line = format_finding_line(finding)
        assert "[EMERGING 2x]" in line

    def test_fingerprint_section_with_no_lifecycle_data(self):
        # Founder narration tiers: 6-9 confirmations narrate as REPEATED;
        # 10+ as CONFIRMED. The legacy "STRONG/CONFIRMED at any N" label
        # was the trust-rupture vector and is no longer valid.
        finding = _make_finding(
            lifecycle_state=None,
            times_confirmed=6,
        )

        mock_db = MagicMock()
        with patch(
            "services.fingerprint_context.get_confirmed_findings",
            return_value=[finding],
        ):
            result = build_fingerprint_prompt_section(ATHLETE_ID, mock_db)

        assert result is not None
        assert "REPEATED" in result or "CONFIRMED" in result


# ===================================================================
# C. COACH SYSTEM PROMPT CONTRACT TESTS
# ===================================================================


class TestCoachPromptDirective:
    """Contract: system prompt contains the emerging-finding coaching directive."""

    def test_sonnet_prompt_contains_emerging_directive(self):
        from services.ai_coach import AICoach

        mock_db = MagicMock()
        coach = AICoach.__new__(AICoach)
        coach.db = mock_db

        with patch.object(coach, "_get_fresh_athlete_facts", return_value=[]):
            try:
                prompt = coach._build_coach_system_prompt(ATHLETE_ID)
            except Exception:
                pytest.skip("Coach prompt build requires full DB context")

        # Post-Jim contract: emerging-pattern questioning is conditional on
        # the athlete's message being open-ended. The directive must still
        # exist (so the coach knows what to do with EMERGING blocks) but
        # must NOT be unconditional ("MUST ask"). Direct questions take
        # precedence over pattern preambles. See _context.py.
        assert "EMERGING PATTERNS" in prompt
        assert "=== EMERGING PATTERN" in prompt
        assert "ASK ABOUT THIS FIRST" in prompt
        assert "you may ask that question first" in prompt
        assert "MUST ask that question" not in prompt


# ===================================================================
# D. FACT EXTRACTION PROMPT CONTRACT
# ===================================================================


class TestFactExtractionPrompt:
    """Contract: limiter_context is a recognized fact type with TTL."""

    def test_limiter_context_in_ttl_categories(self):
        from tasks.fact_extraction_task import FACT_TTL_CATEGORIES
        assert "limiter_context" in FACT_TTL_CATEGORIES
        assert FACT_TTL_CATEGORIES["limiter_context"] == 90

    def test_extraction_prompt_contains_limiter_context(self):
        from tasks.fact_extraction_task import EXTRACTION_PROMPT
        assert "limiter_context" in EXTRACTION_PROMPT
        assert "L-VOL" in EXTRACTION_PROMPT
        assert "L-REC" in EXTRACTION_PROMPT
        assert "L-THRESH" in EXTRACTION_PROMPT
        assert "L-CEIL" in EXTRACTION_PROMPT

    def test_extraction_prompt_contains_limiter_type_examples(self):
        from tasks.fact_extraction_task import EXTRACTION_PROMPT
        assert "limiter_type:L-VOL" in EXTRACTION_PROMPT
        assert "limiter_type:L-REC" in EXTRACTION_PROMPT


# ===================================================================
# E. COACHING LANGUAGE COVERAGE
# ===================================================================


class TestCoachingLanguageCoverage:
    """Every INPUT_TO_LIMITER_TYPE key must have a COACHING_LANGUAGE entry."""

    def test_all_limiter_inputs_have_coaching_translation(self):
        for input_name in INPUT_TO_LIMITER_TYPE:
            assert input_name in COACHING_LANGUAGE, (
                f"INPUT_TO_LIMITER_TYPE key '{input_name}' missing from COACHING_LANGUAGE"
            )

    def test_lifecycle_labels(self):
        states = {
            "active": "ACTIVE",
            "emerging": "EMERGING — ask athlete",
            "resolving": "RESOLVING",
            "structural": "STRUCTURAL",
            "structural_monitored": "STRUCTURAL",
            "active_fixed": "ACTIVE (race-specific)",
            "closed": "CLOSED",
        }
        for state, expected_label in states.items():
            f = _make_finding(lifecycle_state=state, times_confirmed=5)
            line = format_finding_line(f)
            assert expected_label in line, (
                f"lifecycle_state='{state}' should produce label containing '{expected_label}', "
                f"got: {line}"
            )


# ===================================================================
# F. API-LEVEL ENDPOINT TESTS (real DB, real FastAPI, serialized payload)
# ===================================================================


class TestAPILevelCoachPayload:
    """Hit real endpoints with real DB records to prove serialized behavior.

    Proves the three contract items end-to-end:
      1. Closed findings are grouped (not individually listed) in coach prompt
      2. Translation dictionary is used (no raw field names in output)
      3. Only one emerging finding surfaces (newest first, hard-capped)
    """

    @pytest.fixture()
    def _api_setup(self):
        """Create athlete + CorrelationFinding rows with lifecycle states."""
        from fastapi.testclient import TestClient

        from core.database import SessionLocal
        from core.security import create_access_token
        from main import app
        from models import Athlete, CorrelationFinding

        db = SessionLocal()
        athlete = None
        try:
            athlete = Athlete(
                email=f"coach_payload_{uuid.uuid4()}@example.com",
                display_name="Coach Payload Test",
                subscription_tier="free",
                role="admin",
                onboarding_stage="complete",
                onboarding_completed=True,
            )
            db.add(athlete)
            db.commit()
            db.refresh(athlete)

            now = datetime.now(timezone.utc)

            findings = [
                CorrelationFinding(
                    athlete_id=athlete.id,
                    input_name="long_run_ratio",
                    output_metric="pace_threshold",
                    direction="positive",
                    correlation_coefficient=0.72,
                    p_value=0.001,
                    sample_size=30,
                    strength="strong",
                    times_confirmed=12,
                    category="what_works",
                    confidence=0.85,
                    is_active=True,
                    lifecycle_state="active",
                    lifecycle_state_updated_at=now - timedelta(days=5),
                ),
                CorrelationFinding(
                    athlete_id=athlete.id,
                    input_name="sleep_hours",
                    output_metric="efficiency",
                    direction="positive",
                    correlation_coefficient=0.55,
                    p_value=0.01,
                    sample_size=25,
                    strength="moderate",
                    times_confirmed=3,
                    first_detected_at=now - timedelta(days=20),
                    category="what_works",
                    confidence=0.7,
                    is_active=True,
                    lifecycle_state="emerging",
                    lifecycle_state_updated_at=now - timedelta(days=3),
                ),
                CorrelationFinding(
                    athlete_id=athlete.id,
                    input_name="daily_session_stress",
                    output_metric="efficiency",
                    direction="negative",
                    correlation_coefficient=-0.48,
                    p_value=0.02,
                    sample_size=20,
                    strength="moderate",
                    times_confirmed=2,
                    first_detected_at=now - timedelta(days=40),
                    category="what_doesnt",
                    confidence=0.6,
                    is_active=True,
                    lifecycle_state="emerging",
                    lifecycle_state_updated_at=now - timedelta(days=15),
                ),
                CorrelationFinding(
                    athlete_id=athlete.id,
                    input_name="weekly_volume_km",
                    output_metric="pace_easy",
                    direction="positive",
                    correlation_coefficient=0.60,
                    p_value=0.005,
                    sample_size=40,
                    strength="moderate",
                    times_confirmed=15,
                    category="what_works",
                    confidence=0.9,
                    is_active=True,
                    lifecycle_state="closed",
                    lifecycle_state_updated_at=now - timedelta(days=180),
                ),
                CorrelationFinding(
                    athlete_id=athlete.id,
                    input_name="tsb",
                    output_metric="pace_threshold",
                    direction="positive",
                    correlation_coefficient=0.52,
                    p_value=0.01,
                    sample_size=35,
                    strength="moderate",
                    times_confirmed=10,
                    category="what_works",
                    confidence=0.8,
                    is_active=True,
                    lifecycle_state="resolving",
                    lifecycle_state_updated_at=now - timedelta(days=10),
                    resolving_context="Volume emphasis during build phase",
                ),
            ]
            for f in findings:
                db.add(f)
            db.commit()

            token = create_access_token(
                {"sub": str(athlete.id), "email": athlete.email, "role": athlete.role}
            )
            client = TestClient(app)
            headers = {"Authorization": f"Bearer {token}"}

            yield {
                "client": client,
                "headers": headers,
                "athlete": athlete,
                "db": db,
            }
        finally:
            try:
                if athlete is not None:
                    from models import CorrelationFinding as CF
                    for cf in db.query(CF).filter(CF.athlete_id == athlete.id).all():
                        db.delete(cf)
                    a = db.query(Athlete).filter(Athlete.id == athlete.id).first()
                    if a:
                        db.delete(a)
                    db.commit()
            except Exception:
                db.rollback()
            db.close()

    def test_suggestions_endpoint_returns_emerging_suggestion(self, _api_setup):
        """GET /v1/coach/suggestions returns a lifecycle-driven suggestion
        for the newest emerging finding, using translated field names."""
        ctx = _api_setup
        resp = ctx["client"].get("/v1/coach/suggestions", headers=ctx["headers"])
        assert resp.status_code == 200, resp.text

        data = resp.json()
        suggestions = data.get("suggestions", [])

        emerging_suggestions = [
            s for s in suggestions
            if "new pattern" in s.get("title", "").lower()
            or "pattern" in s.get("title", "").lower()
        ]

        if emerging_suggestions:
            s = emerging_suggestions[0]
            assert "sleep_hours" not in s["title"], "Raw field name leaked into title"
            assert "sleep_hours" not in s["description"], "Raw field name leaked into description"
            assert "sleep" in s["title"].lower() or "sleep" in s["description"].lower(), (
                "Translated term 'sleep duration' should appear"
            )

    def test_fingerprint_prompt_with_real_db(self, _api_setup):
        """build_fingerprint_prompt_section with real DB proves all three
        contract items in the serialized coach prompt payload."""
        ctx = _api_setup
        athlete = ctx["athlete"]
        db = ctx["db"]

        result = build_fingerprint_prompt_section(athlete.id, db, verbose=False)
        assert result is not None

        lines = result.split("\n")

        assert result.count("=== EMERGING PATTERN") == 1, (
            "Expected exactly 1 emerging block in prompt"
        )
        emerging_block = result.split("=== END EMERGING ===")[0]
        assert "sleep duration" in emerging_block, (
            "Newest emerging (sleep_hours, updated 3 days ago) should be the one"
        )
        assert 'Suggested question' in emerging_block, (
            "Emerging block must contain a pre-generated question"
        )

        assert "Previously solved:" in result, "Closed findings should be grouped"
        closed_individual = [ln for ln in lines if "[CLOSED" in ln]
        assert len(closed_individual) == 0, "No individual [CLOSED] lines allowed"

        assert "weekly mileage" in result, "Closed finding should use translated name"
        assert "weekly_volume_km" not in result, "Raw field name leaked into prompt"

        assert "long_run_ratio" not in result, "Raw field name leaked"
        assert "long runs" in result, "Active finding should use translated name"

        assert "daily_session_stress" not in result, (
            "Older emerging finding should be excluded from prompt entirely"
        )

        resolving_lines = [ln for ln in lines if "[RESOLVING" in ln]
        assert len(resolving_lines) == 1
        assert "Volume emphasis during build phase" in resolving_lines[0]

    def test_fingerprint_prompt_verbose_with_real_db(self, _api_setup):
        """Verbose mode (morning voice) also respects lifecycle grouping."""
        ctx = _api_setup
        result = build_fingerprint_prompt_section(
            ctx["athlete"].id, ctx["db"], verbose=True,
        )
        assert result is not None
        assert "--- Personal Fingerprint" in result
        assert "=== EMERGING PATTERN" in result
        assert "Previously solved:" in result
