"""
Regression: Garmin proprietary model outputs must not be discovered as
correlation signals.

Founder rule: real measured metrics only. Garmin's Body Battery, Training
Effect, and Stress Score are model outputs (not measurements) and should
never appear in the correlation engine, fingerprint context units map, or
n1 insight friendly-name registry — that would create the appearance that
those scores are doing real causal work.

This test enforces the contract by source inspection. If you intentionally
re-introduce one of these fields, this test will fail and force a doc /
review trail.
"""

import inspect
from pathlib import Path

import pytest

from services import fingerprint_context
from services.intelligence import correlation_engine, n1_insight_generator


_BANNED_PROPRIETARY_KEYS = (
    "garmin_aerobic_te",
    "garmin_anaerobic_te",
    "garmin_body_battery_impact",
    "garmin_body_battery_end",
    "garmin_avg_stress",
    "garmin_max_stress",
)


def _signal_keys_in_correlation_engine() -> set[str]:
    """Return every (key, attr) tuple key registered in _ACTIVITY_SIGNALS."""
    src = inspect.getsource(correlation_engine)
    # The list lives inside a function; we grep its tuples literally.
    keys: set[str] = set()
    in_list = False
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("_ACTIVITY_SIGNALS"):
            in_list = True
            continue
        if in_list:
            if stripped.startswith("]"):
                break
            if stripped.startswith('("'):
                # ('key', 'attr')
                key = stripped.split('"', 2)[1]
                keys.add(key)
    return keys


def _keys_in_units_map() -> set[str]:
    """Return every key in fingerprint_context.UNITS_BY_KEY (or equivalent)."""
    # The units dict is a module-level literal; grab keys via getattr.
    candidates = []
    for attr_name in dir(fingerprint_context):
        attr = getattr(fingerprint_context, attr_name)
        if isinstance(attr, dict) and attr_name.isupper():
            # The biggest UPPER dict is the units map.
            candidates.append((attr_name, attr))
    if not candidates:
        return set()
    biggest = max(candidates, key=lambda kv: len(kv[1]))
    return set(biggest[1].keys())


def _keys_in_n1_friendly_map() -> set[str]:
    """Return every key in n1_insight_generator's friendly-label dict(s)."""
    keys: set[str] = set()
    for attr_name in dir(n1_insight_generator):
        attr = getattr(n1_insight_generator, attr_name)
        if isinstance(attr, dict) and attr_name.isupper():
            keys.update(attr.keys())
    return keys


@pytest.mark.parametrize("banned_key", _BANNED_PROPRIETARY_KEYS)
def test_correlation_engine_does_not_register_proprietary_field(banned_key):
    keys = _signal_keys_in_correlation_engine()
    assert keys, "expected to find _ACTIVITY_SIGNALS in correlation_engine source"
    assert banned_key not in keys, (
        f"{banned_key} is a Garmin proprietary model output and must not be "
        f"registered as a correlation signal. Founder rule: real measured "
        f"metrics only. If you intentionally re-introduce it, update both "
        f"this test and docs/wiki/garmin-integration.md with rationale."
    )


@pytest.mark.parametrize("banned_key", _BANNED_PROPRIETARY_KEYS)
def test_fingerprint_context_does_not_register_proprietary_field(banned_key):
    keys = _keys_in_units_map()
    if not keys:
        pytest.skip("no UPPER-case dict found in fingerprint_context to inspect")
    assert banned_key not in keys, (
        f"{banned_key} is a Garmin proprietary model output and must not be "
        f"registered in fingerprint_context units map. Founder rule: real "
        f"measured metrics only."
    )


@pytest.mark.parametrize("banned_key", _BANNED_PROPRIETARY_KEYS)
def test_n1_insight_generator_does_not_register_proprietary_field(banned_key):
    keys = _keys_in_n1_friendly_map()
    if not keys:
        pytest.skip("no UPPER-case dict found in n1_insight_generator to inspect")
    assert banned_key not in keys, (
        f"{banned_key} is a Garmin proprietary model output and must not be "
        f"registered in n1_insight_generator friendly-name map. Founder rule: "
        f"real measured metrics only."
    )
