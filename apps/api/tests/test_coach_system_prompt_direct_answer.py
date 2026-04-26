"""Coach system prompt contract: direct questions come before pattern preambles.

Background
----------
In Jim Rusch's chat sessions the coach repeatedly opened with a
template hook ("Before I answer, I noticed a pattern...") even when Jim
asked a direct question. The cause was an EMERGING PATTERNS rule in
``_build_coach_system_prompt`` that required the coach to ask the
emerging question before discussing any other data — including before
answering whatever the athlete had just typed.

This file pins the corrected contract. The prompt must contain an
explicit direct-answer-first rule, and the EMERGING PATTERNS rule must
be conditioned on the athlete's message being open-ended.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from services.coaching._context import ContextMixin


def _build_prompt() -> str:
    """Construct the high-stakes coach system prompt without DB access."""
    mixin = ContextMixin()
    mixin.db = MagicMock()
    mixin._get_fresh_athlete_facts = MagicMock(return_value=[])  # type: ignore[attr-defined]
    return mixin._build_coach_system_prompt(uuid4())


def test_prompt_contains_direct_answer_rule():
    prompt = _build_prompt()
    assert "DIRECT QUESTIONS COME FIRST" in prompt
    assert "answer it directly before anything else" in prompt


def test_prompt_bans_pattern_preamble_when_question_on_the_table():
    prompt = _build_prompt()
    assert "Do NOT open with a pattern-discovery preamble" in prompt
    assert "Before I answer, I noticed a pattern" in prompt, (
        "The exact phrase the coach was using as a template hook in "
        "production must be quoted in the rule so the LLM recognizes "
        "and avoids it."
    )


def test_prompt_conditions_emerging_question_on_open_ended_message():
    prompt = _build_prompt()
    assert "open-ended (no direct question)" in prompt
    assert "answer the question first" in prompt


def test_prompt_does_not_force_emerging_question_unconditionally():
    """The previous wording forced the emerging question first, full stop.

    That wording is what produced the template-preamble regression.
    """
    prompt = _build_prompt()
    assert "you MUST ask that question before discussing any other data" not in prompt
