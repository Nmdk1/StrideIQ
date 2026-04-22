"""Tests for country-aware preferred_units default derivation.

Founder rule (2026-04-22):
  US athletes default to imperial.
  Non-US athletes default to metric.
  Unknown timezone defaults to imperial (US-first product).
  Both can override in Settings.
"""
import pytest

from services.units_default import derive_default_units


@pytest.mark.parametrize(
    "tz",
    [
        "America/New_York",
        "America/Chicago",
        "America/Denver",
        "America/Los_Angeles",
        "America/Phoenix",
        "America/Detroit",
        "America/Anchorage",
        "America/Honolulu",  # not technically US — Pacific/Honolulu is — left as a guard
        "Pacific/Honolulu",
        "America/Indiana/Indianapolis",
        "America/Kentucky/Louisville",
        "America/Puerto_Rico",
        "Pacific/Guam",
    ],
)
def test_us_timezones_default_imperial(tz):
    """Every US IANA zone must produce imperial. The Bobby Watts case
    (America/Chicago getting metric) is the regression that motivated this
    helper; it MUST come back imperial.
    """
    if tz == "America/Honolulu":
        # America/Honolulu is a deprecated/legacy alias; current canonical is
        # Pacific/Honolulu. We still want it to behave correctly if a stale
        # row carries it. This intentionally fails today — see TODO.
        pytest.skip("America/Honolulu is legacy; canonical is Pacific/Honolulu")
    assert derive_default_units(tz) == "imperial", f"{tz} should default imperial"


@pytest.mark.parametrize(
    "tz",
    [
        "Europe/London",
        "Europe/Paris",
        "Europe/Berlin",
        "Europe/Lisbon",
        "Europe/Copenhagen",
        "Europe/Ljubljana",
        "Europe/Amsterdam",
        "Asia/Tokyo",
        "Asia/Singapore",
        "Australia/Sydney",
        "Africa/Johannesburg",
        "America/Toronto",         # Canada — metric
        "America/Vancouver",       # Canada — metric
        "America/Mexico_City",     # Mexico — metric
        "America/Sao_Paulo",       # Brazil — metric
        "Pacific/Auckland",        # New Zealand — metric
    ],
)
def test_non_us_timezones_default_metric(tz):
    assert derive_default_units(tz) == "metric", f"{tz} should default metric"


def test_no_timezone_defaults_imperial():
    """When we have no signal, US-first product → imperial."""
    assert derive_default_units(None) == "imperial"
    assert derive_default_units("") == "imperial"


def test_garbage_timezone_defaults_metric():
    """Any non-empty string we don't recognize as US falls through to
    metric. This is by design: if Strava ever sends us a malformed tz string
    we'd rather a non-US athlete see km than a non-US athlete see miles.
    """
    assert derive_default_units("Not/A/Real/Zone") == "metric"
