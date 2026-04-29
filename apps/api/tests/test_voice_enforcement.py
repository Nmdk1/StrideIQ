from __future__ import annotations

import pytest

from services.coaching._eval import (
    build_tier3_judge_payload,
    evaluate_tier3_judge_scores,
)
from services.coaching.voice_enforcement import (
    TEMPLATE_PHRASE_BLOCKLIST,
    VoiceContractViolation,
    check_response,
    enforce_voice,
)


def test_each_blocklist_phrase_detected():
    for phrase in TEMPLATE_PHRASE_BLOCKLIST:
        result = check_response(f"This contains {phrase}.")
        assert result["ok"] is False
        assert phrase in result["hits"]


def test_visible_internal_packet_language_is_detected():
    result = check_response(
        "The packet has no nutrition_context, but calendar_context says you walked."
    )

    assert result["ok"] is False
    assert "packet" in result["hits"]
    assert "nutrition_context" in result["hits"]
    assert "calendar_context" in result["hits"]


@pytest.mark.asyncio
async def test_enforce_voice_retries_until_rewritten_response_succeeds():
    calls = []

    async def retry(instruction: str) -> str:
        calls.append(instruction)
        return "Run easy today. Keep the decision boring and specific."

    result = await enforce_voice("Great question. You might want to rest.", retry)

    assert (
        result["response"] == "Run easy today. Keep the decision boring and specific."
    )
    assert result["template_phrase_count"] == 2
    assert result["retried"] is True
    assert calls and "great question" in calls[0].lower()
    assert "athlete-facing coaching prose" in calls[0]
    assert "translate internal field names" in calls[0]


@pytest.mark.asyncio
async def test_enforce_voice_cleans_visible_system_labels_without_llm_retry():
    calls = []

    async def retry(instruction: str) -> str:
        calls.append(instruction)
        return "Should not be called."

    result = await enforce_voice(
        "The unasked: the packet says threshold is 6:31/mi.\n"
        "Consider keeping it controlled.",
        retry,
    )

    assert result["response"] == (
        "the data here says threshold is 6:31/mi.\nkeeping it controlled."
    )
    assert result["retried"] is True
    assert calls == []


@pytest.mark.asyncio
async def test_enforce_voice_cleans_decision_for_today_label_without_llm_retry():
    calls = []

    async def retry(instruction: str) -> str:
        calls.append(instruction)
        return "Should not be called."

    result = await enforce_voice(
        "Decision for today: Run 20-30 minutes easy tomorrow.",
        retry,
    )

    assert result["response"] == "Run 20-30 minutes easy tomorrow."
    assert result["template_phrase_hits"] == ["decision for today:"]
    assert calls == []


@pytest.mark.asyncio
async def test_enforce_voice_cleans_internal_block_names_without_llm_retry():
    result = await enforce_voice(
        "Looking at your recent_activities and recent_threads, you should run easy.",
        lambda instruction: "Should not be called.",
    )

    assert result["response"] == (
        "Looking at your training data and our recent conversation, you should run easy."
    )
    assert result["template_phrase_hits"] == ["recent_activities", "recent_threads"]


@pytest.mark.asyncio
async def test_enforce_voice_raises_after_max_retry_hits():
    async def retry(instruction: str) -> str:
        return "You've got this. Trust the process."

    with pytest.raises(VoiceContractViolation) as exc:
        await enforce_voice("Great question.", retry, max_retries=1)

    assert "great question" in exc.value.hits


@pytest.mark.asyncio
async def test_enforce_voice_uses_all_retries_before_failing():
    calls = []
    responses = iter(
        [
            "Great question. The unasked: this still mentions the packet.",
            "Run easy today. Keep it boring.",
        ]
    )

    async def retry(instruction: str) -> str:
        calls.append(instruction)
        return next(responses)

    result = await enforce_voice("Great question.", retry, max_retries=2)

    assert result["response"] == "Run easy today. Keep it boring."
    assert len(calls) == 2
    assert "great question" in calls[1].lower()


def test_tier3_payload_and_scores_penalize_template_hits():
    case = {
        "id": "artifact7-case",
        "domain": "race_day",
        "eval_schema_version": "artifact7.v1",
        "baseline_voice": "direct",
        "baseline_citation": "docs/references/example.md",
    }

    payload = build_tier3_judge_payload(
        case,
        assistant_text="Great question. You should race by feel.",
    )
    result = evaluate_tier3_judge_scores(
        case,
        {
            "tactical_correctness": 5,
            "baseline_utility": 5,
            "outcome_served": 5,
            "evidence_usefulness": 5,
            "voice_alignment": 5,
            "template_phrase_hits": payload["template_phrase_hits"],
        },
    )

    assert payload["template_phrase_hits"] == ["great question"]
    assert result.passed is False
    assert any(
        "voice_alignment_blocklist_hit" in failure for failure in result.failures
    )
