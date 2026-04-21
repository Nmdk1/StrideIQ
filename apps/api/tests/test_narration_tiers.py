"""Tests for ``services.intelligence.narration_tiers``.

These tests pin down the language tiers the founder authorized after Jim
Rusch's coach logs surfaced ``Confirmed N times`` strings against
findings with as few as three observations.
"""

from __future__ import annotations

import pytest

from services.intelligence.narration_tiers import (
    CONFIRMED_THRESHOLD,
    EMERGING_THRESHOLD,
    REPEATED_THRESHOLD,
    evidence_phrase,
    headline_qualifier,
    tier_for,
)


@pytest.mark.parametrize("n", [3, 4, 5])
def test_emerging_tier_for_low_counts(n: int):
    assert tier_for(n) == "EMERGING"


@pytest.mark.parametrize("n", [6, 7, 8, 9])
def test_repeated_tier_for_mid_counts(n: int):
    assert tier_for(n) == "REPEATED"


@pytest.mark.parametrize("n", [10, 15, 50])
def test_confirmed_tier_for_high_counts(n: int):
    assert tier_for(n) == "CONFIRMED"


def test_thresholds_are_monotonic():
    assert EMERGING_THRESHOLD < REPEATED_THRESHOLD < CONFIRMED_THRESHOLD


@pytest.mark.parametrize(
    "n,expected",
    [
        (3, "observed 3 times so far"),
        (5, "observed 5 times so far"),
        (6, "repeated across 6 of your runs"),
        (9, "repeated across 9 of your runs"),
        (10, "confirmed across 10 of your runs"),
        (25, "confirmed across 25 of your runs"),
    ],
)
def test_evidence_phrase_uses_tier_language(n: int, expected: str):
    assert evidence_phrase(n) == expected


def test_evidence_phrase_never_says_confirmed_below_threshold():
    """The trust rupture this module exists to prevent."""
    for n in range(1, CONFIRMED_THRESHOLD):
        phrase = evidence_phrase(n)
        assert "confirmed" not in phrase.lower(), (
            f"evidence_phrase({n}) returned {phrase!r}; only counts >= "
            f"{CONFIRMED_THRESHOLD} are allowed to use 'confirmed' language."
        )


@pytest.mark.parametrize(
    "n,expected",
    [
        (3, "an emerging pattern:"),
        (6, "a repeated pattern:"),
        (10, "a confirmed pattern:"),
    ],
)
def test_headline_qualifier_matches_tier(n: int, expected: str):
    assert headline_qualifier(n) == expected
