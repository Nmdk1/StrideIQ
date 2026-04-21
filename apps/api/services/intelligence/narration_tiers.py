"""
Narration language tiers — mapping ``times_confirmed`` to athlete-facing wording.

The ``CorrelationFinding`` model stores a confirmation count
(``times_confirmed``). Surfacing a row at ``times_confirmed=3`` as
"confirmed" overstates what three observations support. The narration
layer is where this discipline lives — the underlying engine semantics
are unchanged.

Tiers
-----
- 3-5: ``EMERGING`` — the language must signal that the system is still
  watching the pattern. Examples: "observed 3 times so far", "an emerging
  pattern", "early signal".
- 6-9: ``REPEATED`` — the pattern has shown up enough that the system
  treats it as worth noting, but the language still respects the modest
  sample size. Examples: "repeated across 7 of your runs", "consistent
  observation".
- 10+: ``CONFIRMED`` — the sample size is large enough that confident
  language is honest. Examples: "confirmed across 12 of your runs", "a
  confirmed pattern".

Below ``EMERGING_THRESHOLD`` (currently 3) the finding is not eligible
for surfacing at all — see ``finding_eligibility.select_eligible_findings``.

Why these thresholds
--------------------
The athlete has to be able to read a narration and know how much weight
to put on it. "Confirmed" and "emerging" are different epistemic
commitments. Three observations is enough to notice a pattern, not
enough to call it confirmed in physiology where confounders are
plentiful (taper effects, illness, weather, life stress, sleep noise).
The 10+ threshold is conservative on purpose — for behavioral patterns
in N=1 data, asking for double-digit replications before promising the
athlete the pattern is real is the discipline the founder asked for.
"""

from __future__ import annotations

from typing import Literal

# Threshold for surfacing at all — anything below this is not eligible.
EMERGING_THRESHOLD = 3

# Boundary between EMERGING and REPEATED tiers.
REPEATED_THRESHOLD = 6

# Boundary between REPEATED and CONFIRMED tiers.
CONFIRMED_THRESHOLD = 10


Tier = Literal["EMERGING", "REPEATED", "CONFIRMED"]


def tier_for(times_confirmed: int) -> Tier:
    """Return the tier label for a given confirmation count.

    Returns "EMERGING" for counts at or below the EMERGING/REPEATED
    boundary, even when ``times_confirmed`` is below 3 — surfaces that
    care about the no-surface case should consult
    ``finding_eligibility.select_eligible_findings`` first.
    """
    if times_confirmed >= CONFIRMED_THRESHOLD:
        return "CONFIRMED"
    if times_confirmed >= REPEATED_THRESHOLD:
        return "REPEATED"
    return "EMERGING"


def evidence_phrase(times_confirmed: int) -> str:
    """Return a short athlete-facing phrase describing the sample weight.

    Examples
    --------
    >>> evidence_phrase(3)
    'observed 3 times so far'
    >>> evidence_phrase(7)
    'repeated across 7 of your runs'
    >>> evidence_phrase(12)
    'confirmed across 12 of your runs'
    """
    n = max(int(times_confirmed or 0), 0)
    tier = tier_for(n)
    if tier == "CONFIRMED":
        return f"confirmed across {n} of your runs"
    if tier == "REPEATED":
        return f"repeated across {n} of your runs"
    return f"observed {n} times so far"


def headline_qualifier(times_confirmed: int) -> str:
    """Return a short qualifier suitable for prefixing a finding headline.

    Examples
    --------
    >>> headline_qualifier(3)
    'an emerging pattern:'
    >>> headline_qualifier(7)
    'a repeated pattern:'
    >>> headline_qualifier(12)
    'a confirmed pattern:'
    """
    tier = tier_for(times_confirmed)
    if tier == "CONFIRMED":
        return "a confirmed pattern:"
    if tier == "REPEATED":
        return "a repeated pattern:"
    return "an emerging pattern:"
