"""
Behavioral contract: a Settings toggle pins
`Athlete.preferred_units_set_explicitly = True`, which prevents subsequent
country-aware derivation (e.g. Strava OAuth writing a new timezone) from
overwriting the deliberate choice.

This is the protection the founder asked for on 2026-04-22:
  "US athletes should default to imperial - non US athletes should default
   to metric - both should be able to select either."

The ability to "select either" only works if the system stops trying to
re-derive every time a new signal lands.
"""
from sqlalchemy.orm import Session

from models import Athlete
from routers.preferences import UpdatePreferencesRequest, update_preferences
from services.units_default import derive_default_units


async def _run_update(athlete: Athlete, db: Session, units: str) -> None:
    await update_preferences(
        request=UpdatePreferencesRequest(preferred_units=units),
        athlete=athlete,
        db=db,
    )


def test_default_explicit_flag_is_false_on_new_athlete(db_session, test_athlete):
    """A freshly created athlete has not chosen anything yet."""
    db_session.refresh(test_athlete)
    assert test_athlete.preferred_units_set_explicitly is False


async def test_settings_toggle_pins_explicit_flag_to_true(db_session, test_athlete):
    """Toggling units in Settings is a deliberate choice and must stick."""
    assert test_athlete.preferred_units_set_explicitly is False

    await _run_update(test_athlete, db_session, "metric")

    db_session.refresh(test_athlete)
    assert test_athlete.preferred_units == "metric"
    assert test_athlete.preferred_units_set_explicitly is True


async def test_settings_toggle_to_same_value_still_marks_explicit(db_session, test_athlete):
    """Even if the athlete picks the same value as the current default,
    the act of picking is itself a commitment we honor going forward.
    """
    assert test_athlete.preferred_units == "imperial"
    assert test_athlete.preferred_units_set_explicitly is False

    await _run_update(test_athlete, db_session, "imperial")

    db_session.refresh(test_athlete)
    assert test_athlete.preferred_units == "imperial"
    assert test_athlete.preferred_units_set_explicitly is True


def test_country_default_changes_with_timezone_when_not_explicit():
    """If the athlete has never toggled, deriving the default from a US
    timezone yields imperial; from a European timezone, metric. This is
    the contract the Strava OAuth callback relies on.
    """
    assert derive_default_units("America/Chicago") == "imperial"  # Bobby
    assert derive_default_units("Europe/Ljubljana") == "metric"   # Dejan
    assert derive_default_units(None) == "imperial"               # unknown → US-first


async def test_explicit_choice_survives_a_re_derivation_pass(db_session, test_athlete):
    """Simulate the production sequence: athlete picks metric in Settings,
    then later Strava OAuth writes a US timezone. The explicit choice must
    win — we do NOT flip them back to imperial.
    """
    await _run_update(test_athlete, db_session, "metric")
    db_session.refresh(test_athlete)
    assert test_athlete.preferred_units == "metric"
    assert test_athlete.preferred_units_set_explicitly is True

    # Now simulate the Strava-OAuth derivation block (mirrors the guard in
    # routers/strava.py). It must short-circuit on the explicit flag.
    if not test_athlete.preferred_units_set_explicitly:
        test_athlete.preferred_units = derive_default_units("America/Chicago")
    db_session.commit()
    db_session.refresh(test_athlete)

    assert test_athlete.preferred_units == "metric", (
        "Explicit choice was overwritten by country derivation — this is "
        "the bug the explicit flag exists to prevent."
    )
