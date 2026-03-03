"""Tests for GET /v1/progress/knowledge — Phase 1: Ship the Moat."""
import json
import uuid
from datetime import datetime, date, timedelta
from unittest.mock import patch, MagicMock, PropertyMock

import pytest
from fastapi.testclient import TestClient

from main import app
from routers.progress import (
    _assemble_knowledge,
    _confidence_tier,
    _humanize_metric,
    _build_headline,
    _apply_knowledge_llm,
    KnowledgeResponse,
    HeroData,
    HeroStat,
    DataCoverageKnowledge,
)


client = TestClient(app)

ATHLETE_ID = uuid.uuid4()


def _mock_athlete():
    a = MagicMock()
    a.id = ATHLETE_ID
    a.email = "test@strideiq.run"
    a.role = "athlete"
    a.distance_unit = "mi"
    a.is_blocked = False
    return a


def _mock_finding(
    input_name="sleep_hours",
    output_metric="efficiency",
    direction="positive",
    r=0.62,
    times_confirmed=7,
    strength="strong",
    lag=1,
    insight_text="Sleep drives efficiency.",
    confidence=0.85,
    category="what_works",
):
    f = MagicMock()
    f.id = uuid.uuid4()
    f.athlete_id = ATHLETE_ID
    f.input_name = input_name
    f.output_metric = output_metric
    f.direction = direction
    f.correlation_coefficient = r
    f.time_lag_days = lag
    f.times_confirmed = times_confirmed
    f.strength = strength
    f.insight_text = insight_text
    f.confidence = confidence
    f.category = category
    f.is_active = True
    f.p_value = 0.01
    f.sample_size = 30
    return f


def _mock_load_history():
    class DailyLoad:
        def __init__(self, ctl):
            self.ctl = ctl
            self.atl = ctl * 1.1
            self.tsb = -5
            self.date = date.today()
            self.total_tss = 100
            self.workout_count = 1

    return [DailyLoad(9.9)] + [DailyLoad(i) for i in range(10, 43)] + [DailyLoad(42.4)]


def _make_plan(has_race=True):
    plan = MagicMock()
    plan.athlete_id = ATHLETE_ID
    plan.status = "active"
    plan.name = "Marathon Plan"
    if has_race:
        plan.goal_race_name = "Tobacco Road v26"
        plan.goal_race_date = date.today() + timedelta(days=13)
    else:
        plan.goal_race_name = None
        plan.goal_race_date = None
    return plan


# ═══════════════════════════════════════════════════════════════════
# Test 1: Response has all required fields
# ═══════════════════════════════════════════════════════════════════
def test_response_has_all_required_fields():
    db = MagicMock()
    findings = [
        _mock_finding("sleep_hours", "efficiency", "positive", 0.62, 7, "strong", 1),
        _mock_finding("motivation_1_5", "efficiency", "positive", 0.71, 9, "strong", 2),
    ]
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = findings
    db.query.return_value.filter.return_value.first.return_value = _make_plan()
    db.query.return_value.filter.return_value.count.return_value = 24

    with patch("services.training_load.TrainingLoadCalculator") as MockCalc:
        MockCalc.return_value.get_load_history.return_value = _mock_load_history()
        resp = _assemble_knowledge(ATHLETE_ID, db)

    assert resp.hero is not None
    assert resp.hero.date_label
    assert resp.hero.headline
    assert resp.hero.headline_accent
    assert resp.hero.subtext
    assert len(resp.hero.stats) == 3
    assert resp.correlation_web["nodes"]
    assert resp.correlation_web["edges"]
    assert len(resp.proved_facts) > 0
    assert resp.generated_at
    assert resp.data_coverage


# ═══════════════════════════════════════════════════════════════════
# Test 2: Nodes deduplicate input/output names
# ═══════════════════════════════════════════════════════════════════
def test_nodes_deduplicate_correctly():
    db = MagicMock()
    findings = [
        _mock_finding("sleep_hours", "efficiency", "positive", 0.62, 7, "strong", 1),
        _mock_finding("sleep_hours", "pace", "positive", 0.48, 4, "moderate", 2),
        _mock_finding("motivation_1_5", "efficiency", "positive", 0.71, 9, "strong", 2),
    ]
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = findings
    db.query.return_value.filter.return_value.first.return_value = _make_plan()
    db.query.return_value.filter.return_value.count.return_value = 24

    with patch("services.training_load.TrainingLoadCalculator") as MockCalc:
        MockCalc.return_value.get_load_history.return_value = _mock_load_history()
        resp = _assemble_knowledge(ATHLETE_ID, db)

    nodes = resp.correlation_web["nodes"]
    input_nodes = [n for n in nodes if n["group"] == "input"]
    output_nodes = [n for n in nodes if n["group"] == "output"]

    input_ids = [n["id"] for n in input_nodes]
    assert input_ids.count("sleep_hours") == 1
    assert "motivation_1_5" in input_ids

    output_ids = [n["id"] for n in output_nodes]
    assert output_ids.count("efficiency") == 1
    assert "pace" in output_ids


# ═══════════════════════════════════════════════════════════════════
# Test 3: Edges map 1:1 to findings
# ═══════════════════════════════════════════════════════════════════
def test_edges_map_one_to_one():
    db = MagicMock()
    findings = [
        _mock_finding("sleep_hours", "efficiency", "positive", 0.62, 7, "strong", 1),
        _mock_finding("stress_1_5", "completion", "negative", -0.55, 5, "moderate", 0),
    ]
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = findings
    db.query.return_value.filter.return_value.first.return_value = _make_plan()
    db.query.return_value.filter.return_value.count.return_value = 10

    with patch("services.training_load.TrainingLoadCalculator") as MockCalc:
        MockCalc.return_value.get_load_history.return_value = _mock_load_history()
        resp = _assemble_knowledge(ATHLETE_ID, db)

    edges = resp.correlation_web["edges"]
    assert len(edges) == 2
    assert edges[0]["source"] == "sleep_hours"
    assert edges[0]["target"] == "efficiency"
    assert edges[1]["source"] == "stress_1_5"
    assert edges[1]["direction"] == "negative"


# ═══════════════════════════════════════════════════════════════════
# Test 4: Proved facts ordered by times_confirmed descending
# ═══════════════════════════════════════════════════════════════════
def test_proved_facts_ordered_by_times_confirmed():
    db = MagicMock()
    findings = [
        _mock_finding("sleep_hours", "efficiency", "positive", 0.62, 3, "moderate", 1),
        _mock_finding("motivation_1_5", "efficiency", "positive", 0.71, 9, "strong", 2),
        _mock_finding("hrv", "pace", "positive", 0.38, 1, "weak", 1),
    ]
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = findings
    db.query.return_value.filter.return_value.first.return_value = _make_plan()
    db.query.return_value.filter.return_value.count.return_value = 10

    with patch("services.training_load.TrainingLoadCalculator") as MockCalc:
        MockCalc.return_value.get_load_history.return_value = _mock_load_history()
        resp = _assemble_knowledge(ATHLETE_ID, db)

    facts = resp.proved_facts
    assert facts[0].times_confirmed == 9
    assert facts[1].times_confirmed == 3
    assert facts[2].times_confirmed == 1


# ═══════════════════════════════════════════════════════════════════
# Test 5: Confidence tiers assigned correctly
# ═══════════════════════════════════════════════════════════════════
def test_confidence_tiers():
    assert _confidence_tier(1) == "emerging"
    assert _confidence_tier(2) == "emerging"
    assert _confidence_tier(3) == "confirmed"
    assert _confidence_tier(5) == "confirmed"
    assert _confidence_tier(6) == "strong"
    assert _confidence_tier(9) == "strong"
    assert _confidence_tier(100) == "strong"


# ═══════════════════════════════════════════════════════════════════
# Test 6: Empty state — no findings, patterns_forming populated
# ═══════════════════════════════════════════════════════════════════
def test_empty_state_shows_patterns_forming():
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    db.query.return_value.filter.return_value.first.return_value = _make_plan()
    db.query.return_value.filter.return_value.count.return_value = 5

    with patch("services.training_load.TrainingLoadCalculator") as MockCalc:
        MockCalc.return_value.get_load_history.return_value = _mock_load_history()
        resp = _assemble_knowledge(ATHLETE_ID, db)

    assert resp.correlation_web["nodes"] == []
    assert resp.correlation_web["edges"] == []
    assert resp.proved_facts == []
    assert resp.patterns_forming is not None
    assert resp.patterns_forming.checkin_count == 5
    assert resp.patterns_forming.progress_pct > 0


# ═══════════════════════════════════════════════════════════════════
# Test 7: LLM failure still returns full deterministic data
# ═══════════════════════════════════════════════════════════════════
def test_llm_failure_returns_deterministic_data():
    db = MagicMock()
    findings = [_mock_finding()]
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = findings
    db.query.return_value.filter.return_value.first.return_value = _make_plan()
    db.query.return_value.filter.return_value.count.return_value = 10

    with patch("services.training_load.TrainingLoadCalculator") as MockCalc:
        MockCalc.return_value.get_load_history.return_value = _mock_load_history()
        resp = _assemble_knowledge(ATHLETE_ID, db)

    assert resp.hero.headline
    assert resp.hero.headline_accent
    assert resp.hero.subtext
    assert len(resp.correlation_web["nodes"]) > 0
    assert len(resp.correlation_web["edges"]) > 0
    assert len(resp.proved_facts) > 0
    for f in resp.proved_facts:
        assert f.evidence


# ═══════════════════════════════════════════════════════════════════
# Test 8: Cache hit returns cached response
# ═══════════════════════════════════════════════════════════════════
def test_cache_hit():
    cached = KnowledgeResponse(
        hero=HeroData(
            date_label="Mon, Mar 2",
            headline="Cached",
            headline_accent="headline",
            subtext="cached sub",
            stats=[HeroStat(label="CTL", value="42", color="blue")],
        ),
        correlation_web={"nodes": [], "edges": []},
        proved_facts=[],
        patterns_forming=None,
        generated_at="2026-03-02T12:00:00Z",
        data_coverage=DataCoverageKnowledge(
            total_findings=0, confirmed_findings=0, emerging_findings=0, checkin_count=0,
        ),
    )
    from database import get_db
    from routers.auth import get_current_user

    app.dependency_overrides[get_db] = lambda: MagicMock()
    app.dependency_overrides[get_current_user] = lambda: _mock_athlete()

    try:
        with patch("routers.progress.get_cache", return_value=cached.model_dump()):
            resp = client.get("/v1/progress/knowledge")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    assert resp.json()["hero"]["headline"] == "Cached"


# ═══════════════════════════════════════════════════════════════════
# Test 9: Hero stats with race
# ═══════════════════════════════════════════════════════════════════
def test_hero_with_race():
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    plan = _make_plan(has_race=True)
    db.query.return_value.filter.return_value.first.return_value = plan
    db.query.return_value.filter.return_value.count.return_value = 10

    with patch("services.training_load.TrainingLoadCalculator") as MockCalc:
        MockCalc.return_value.get_load_history.return_value = _mock_load_history()
        resp = _assemble_knowledge(ATHLETE_ID, db)

    stats = resp.hero.stats
    labels = [s.label for s in stats]
    assert "Fitness then" in labels
    assert "Fitness now" in labels
    assert "Days out" in labels
    assert "Tobacco Road" in resp.hero.date_label


# ═══════════════════════════════════════════════════════════════════
# Test 10: Hero without race shows weeks tracked
# ═══════════════════════════════════════════════════════════════════
def test_hero_without_race():
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.count.return_value = 0

    with patch("services.training_load.TrainingLoadCalculator") as MockCalc:
        MockCalc.return_value.get_load_history.return_value = _mock_load_history()
        resp = _assemble_knowledge(ATHLETE_ID, db)

    stats = resp.hero.stats
    labels = [s.label for s in stats]
    assert "Patterns found" in labels
    assert "Days out" not in labels


# ═══════════════════════════════════════════════════════════════════
# Test 11: Humanize metric names
# ═══════════════════════════════════════════════════════════════════
def test_humanize_metric():
    assert _humanize_metric("sleep_hours") == "Sleep"
    assert _humanize_metric("motivation_1_5") == "Motivation"
    assert _humanize_metric("efficiency") == "Efficiency"
    assert _humanize_metric("soreness_1_5") == "Soreness"
    assert _humanize_metric("ctl") == "Fitness (CTL)"
    assert _humanize_metric("atl") == "Fatigue (ATL)"
    assert _humanize_metric("tsb") == "Form (TSB)"
    assert _humanize_metric("hrv_rmssd") == "Heart Rate Variability"


# ═══════════════════════════════════════════════════════════════════
# Test 12: Build headline generates correct text
# ═══════════════════════════════════════════════════════════════════
def test_build_headline():
    f = _mock_finding("sleep_hours", "efficiency", "positive", 0.62, 7, "strong", 2)
    headline = _build_headline(f)
    assert "sleep" in headline.lower()
    assert "efficiency" in headline.lower()
    assert "improves" in headline.lower()

    f_neg = _mock_finding("stress_1_5", "completion", "negative", -0.55, 5, "moderate", 0)
    headline_neg = _build_headline(f_neg)
    assert "reduces" in headline_neg.lower()


# ═══════════════════════════════════════════════════════════════════
# Test 13: LLM narrative merge applies correctly
# ═══════════════════════════════════════════════════════════════════
def test_llm_narrative_merge():
    resp = KnowledgeResponse(
        hero=HeroData(
            date_label="Mon, Mar 2",
            headline="Fallback",
            headline_accent="fallback accent",
            subtext="fallback sub",
            stats=[HeroStat(label="CTL", value="42", color="blue")],
        ),
        correlation_web={"nodes": [], "edges": []},
        proved_facts=[],
        patterns_forming=None,
        generated_at="2026-03-02T12:00:00Z",
        data_coverage=DataCoverageKnowledge(
            total_findings=0, confirmed_findings=0, emerging_findings=0, checkin_count=0,
        ),
    )

    llm_output = {
        "headline": "Eight weeks of work.",
        "headline_accent": "Here's what your body became.",
        "subtext": "Discovered from your own data.",
    }
    _apply_knowledge_llm(resp, llm_output)

    assert resp.hero.headline == "Eight weeks of work."
    assert resp.hero.headline_accent == "Here's what your body became."
    assert resp.hero.subtext == "Discovered from your own data."


# ═══════════════════════════════════════════════════════════════════
# Test 14: Confidence gating — emerging patterns reject causal language
# ═══════════════════════════════════════════════════════════════════
def test_confidence_gating_rejects_causal_for_emerging():
    from routers.progress import ProvedFact

    resp = KnowledgeResponse(
        hero=HeroData(
            date_label="Mon, Mar 2",
            headline="test",
            headline_accent="test",
            subtext="test",
            stats=[],
        ),
        correlation_web={"nodes": [], "edges": []},
        proved_facts=[
            ProvedFact(
                input_metric="hrv",
                output_metric="pace",
                headline="HRV → pace",
                evidence="Observed 2 times",
                implication="",
                times_confirmed=2,
                confidence_tier="emerging",
                direction="positive",
                correlation_coefficient=0.38,
                lag_days=1,
            ),
        ],
        patterns_forming=None,
        generated_at="2026-03-02T12:00:00Z",
        data_coverage=DataCoverageKnowledge(
            total_findings=1, confirmed_findings=0, emerging_findings=1, checkin_count=10,
        ),
    )

    llm_output = {
        "implications": {
            "0": "HRV always drives your pace improvement."
        }
    }
    _apply_knowledge_llm(resp, llm_output)

    assert resp.proved_facts[0].implication == ""


# ═══════════════════════════════════════════════════════════════════
# Test 15: Data coverage counts correctly
# ═══════════════════════════════════════════════════════════════════
def test_data_coverage_counts():
    db = MagicMock()
    findings = [
        _mock_finding("a", "b", "positive", 0.5, 6, "strong", 1),
        _mock_finding("c", "d", "positive", 0.4, 3, "moderate", 0),
        _mock_finding("e", "f", "positive", 0.3, 1, "weak", 2),
    ]
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = findings
    db.query.return_value.filter.return_value.first.return_value = _make_plan()
    db.query.return_value.filter.return_value.count.return_value = 45

    with patch("services.training_load.TrainingLoadCalculator") as MockCalc:
        MockCalc.return_value.get_load_history.return_value = _mock_load_history()
        resp = _assemble_knowledge(ATHLETE_ID, db)

    assert resp.data_coverage.total_findings == 3
    assert resp.data_coverage.confirmed_findings == 2
    assert resp.data_coverage.emerging_findings == 1
