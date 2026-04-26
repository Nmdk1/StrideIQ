from types import SimpleNamespace
from uuid import uuid4

from services.coaching._context import ContextMixin


def _fact(fact_type, fact_key, fact_value, source_excerpt="athlete said it"):
    return SimpleNamespace(
        fact_type=fact_type,
        fact_key=fact_key,
        fact_value=fact_value,
        source_excerpt=source_excerpt,
    )


def test_coaching_memory_facts_render_as_constraints():
    mixin = ContextMixin()
    text = mixin._format_known_athlete_facts(
        [
            _fact(
                "stress_boundary",
                "life_stress_boundary",
                "Running is my escape; do not discuss the life stress.",
            ),
            _fact(
                "invalid_race_anchor",
                "coke_10k_2025_invalid_anchor",
                "Ran with a fractured femur; do not use as fitness anchor.",
            ),
            _fact("strength_pr", "deadlift_1rm_lbs", "315"),
        ]
    )

    assert "COACHING MEMORY" in text
    assert "Stress boundary" in text
    assert "Invalid race anchor" in text
    assert "do not discuss the life stress" in text
    assert "do not use as fitness anchor" in text
    assert "KNOWN ATHLETE FACTS" in text
    assert "deadlift_1rm_lbs: 315" in text


def test_system_prompt_includes_coaching_memory_context(monkeypatch):
    mixin = ContextMixin()
    mixin.db = object()
    athlete_id = uuid4()

    monkeypatch.setattr(
        "services.coach_tools.build_athlete_brief",
        lambda _db, _athlete_id: "brief",
    )
    mixin._get_fresh_athlete_facts = lambda athlete_id, max_facts=15: [
        _fact(
            "race_psychology",
            "race_style",
            "I race controlled chaos and can close harder than workouts suggest.",
        )
    ]

    prompt = mixin._build_coach_system_prompt(athlete_id)

    assert "COACHING MEMORY" in prompt
    assert "Race psychology" in prompt
    assert "controlled chaos" in prompt
    assert "Use these as coaching constraints" in prompt


def test_extraction_prompt_contains_coaching_memory_types():
    from tasks.fact_extraction_task import EXTRACTION_PROMPT

    for fact_type in [
        "race_psychology",
        "injury_context",
        "invalid_race_anchor",
        "training_intent",
        "fatigue_strategy",
        "sleep_baseline",
        "stress_boundary",
        "coaching_preference",
        "strength_training_context",
    ]:
        assert fact_type in EXTRACTION_PROMPT

    assert "Running is my escape" in EXTRACTION_PROMPT
    assert "fractured femur" in EXTRACTION_PROMPT


def test_temporal_coaching_memory_ttls_are_declared():
    from tasks.fact_extraction_task import FACT_TTL_CATEGORIES

    assert FACT_TTL_CATEGORIES["training_intent"] == 45
    assert FACT_TTL_CATEGORIES["fatigue_strategy"] == 45
    assert FACT_TTL_CATEGORIES["strength_training_context"] == 90
