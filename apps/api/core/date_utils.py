"""Date helper utilities shared across coach paths."""

from datetime import date


def calculate_age(birthdate: date, as_of: date) -> int:
    """Return age in years as of ``as_of`` using month/day boundary logic."""
    return as_of.year - birthdate.year - ((as_of.month, as_of.day) < (birthdate.month, birthdate.day))

