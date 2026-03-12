"""
Regression tests: friendly signal name rendering.

Prevents:
  1. Raw signal names (e.g. 'readiness_1_5') from appearing in athlete-facing text.
  2. Router files from using naive .replace('_', ' ') instead of friendly_signal_name().
  3. Known problem signals from reverting to broken display.
  4. New correlation engine inputs from being added without a FRIENDLY_NAMES entry.
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ---------------------------------------------------------------------------
# Test 1: Every correlation input key has a FRIENDLY_NAMES entry
# ---------------------------------------------------------------------------

def test_all_correlation_inputs_have_friendly_names():
    """Every signal the engine aggregates must have a human-readable name."""
    from services.n1_insight_generator import FRIENDLY_NAMES

    src = (Path(__file__).resolve().parents[1] / "services" / "correlation_engine.py").read_text()

    # Extract all keys assigned into the inputs dict in the engine.
    required_signals = set(
        re.findall(r'inputs\["([a-z0-9_]+)"\]\s*=', src)
        + re.findall(r"inputs\['([a-z0-9_]+)'\]\s*=", src)
    )
    assert required_signals, "No input keys extracted from correlation_engine.py — pattern may have drifted"

    missing = sorted(s for s in required_signals if s not in FRIENDLY_NAMES)
    assert not missing, (
        f"Signals missing from FRIENDLY_NAMES in n1_insight_generator.py:\n"
        + "\n".join(f"  {s!r}" for s in missing)
    )


# ---------------------------------------------------------------------------
# Test 2: No router file uses naive .replace('_', ' ') on input_name/output_metric
# ---------------------------------------------------------------------------

_ROUTER_FILES = [
    "routers/home.py",
    "routers/activities.py",
    "routers/progress.py",
    "routers/insights.py",
    "routers/correlations.py",
]

@pytest.mark.parametrize("rel_path", _ROUTER_FILES)
def test_no_naive_replacement_in_router(rel_path):
    """Athlete-facing routers must route all signal labels through friendly_signal_name()."""
    fpath = Path(__file__).resolve().parents[1] / rel_path
    if not fpath.exists():
        pytest.skip(f"{rel_path} not found")
    content = fpath.read_text(encoding="utf-8", errors="replace")

    for pattern in (
        'input_name.replace("_", " ")',
        "input_name.replace('_', ' ')",
        'output_metric.replace("_", " ")',
        "output_metric.replace('_', ' ')",
    ):
        assert pattern not in content, (
            f"{rel_path}: naive replacement found — use friendly_signal_name() instead:\n"
            f"  {pattern!r}"
        )


@pytest.mark.parametrize("rel_path", _ROUTER_FILES)
def test_no_raw_output_metric_in_athlete_facing_string(rel_path):
    """Athlete-facing fallback strings must not embed f.output_metric directly."""
    fpath = Path(__file__).resolve().parents[1] / rel_path
    if not fpath.exists():
        pytest.skip(f"{rel_path} not found")
    content = fpath.read_text(encoding="utf-8", errors="replace")

    # Detect the specific pattern: affects your {f.output_metric}" without friendly_signal_name
    bad_pattern = r'affects your \{f\.output_metric\}'
    matches = re.findall(bad_pattern, content)
    assert not matches, (
        f"{rel_path}: raw output_metric in fallback string — "
        f"use friendly_signal_name(f.output_metric) instead"
    )


# ---------------------------------------------------------------------------
# Test 3: Known problem signals render correctly
# ---------------------------------------------------------------------------

def test_readiness_signal_renders_friendly():
    from services.n1_insight_generator import friendly_signal_name

    assert friendly_signal_name("readiness_1_5") == "self-rated readiness"
    assert "1 5" not in friendly_signal_name("readiness_1_5")
    assert "1_5" not in friendly_signal_name("readiness_1_5")


def test_known_missing_signals_now_render():
    from services.n1_insight_generator import friendly_signal_name

    cases = {
        "stress_1_5": "stress level",
        "soreness_1_5": "soreness",
        "enjoyment_1_5": "run enjoyment",
        "confidence_1_5": "confidence",
        "rpe_1_10": "perceived effort",
        "readiness_1_5": "self-rated readiness",
    }
    for raw, expected in cases.items():
        result = friendly_signal_name(raw)
        assert result == expected, f"friendly_signal_name({raw!r}) = {result!r}, expected {expected!r}"
        # None of these should produce a raw underscore or digit pattern
        assert "_" not in result, f"Underscore leaked in friendly name for {raw!r}: {result!r}"


def test_output_metrics_render_friendly():
    from services.n1_insight_generator import FRIENDLY_NAMES, friendly_signal_name

    # Output metrics must be in FRIENDLY_NAMES so they use the dict, not raw replace fallback
    for metric in ("efficiency", "pace_easy", "pace_threshold", "completion"):
        assert metric in FRIENDLY_NAMES, f"Output metric {metric!r} missing from FRIENDLY_NAMES"
        # The mapped name must differ from the raw fallback (replace('_', ' '))
        raw_fallback = metric.replace("_", " ")
        mapped = friendly_signal_name(metric)
        assert mapped != raw_fallback, (
            f"friendly_signal_name({metric!r}) returns the naive fallback {raw_fallback!r} — "
            f"add a real entry to FRIENDLY_NAMES"
        )


def test_unknown_signal_falls_back_gracefully():
    """An unknown signal name falls back to replace('_', ' ') — no crash."""
    from services.n1_insight_generator import friendly_signal_name

    result = friendly_signal_name("some_unknown_metric_xyz")
    assert result == "some unknown metric xyz"
    assert "_" not in result
