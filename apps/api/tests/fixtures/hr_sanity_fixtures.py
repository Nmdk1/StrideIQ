"""Synthetic stream fixtures for HR sanity check tests (A2).

Each fixture produces a stream_data dict where HR is intentionally unreliable
in a specific way, paired with velocity that tells the true effort story.

Deterministic — no randomness.
"""
from typing import Dict, List


def make_inverted_hr_stream(
    duration_s: int = 5400,  # 90 min
    warmup_s: int = 600,
    finish_kick_s: int = 600,
) -> Dict[str, List]:
    """HR inversely correlated with pace — classic wrist sensor glitch.

    Pace profile: slow warmup → steady moderate → fast finish (5:50/mi).
    HR profile: INVERTED — high at rest, drops as pace increases.
    This simulates a wrist sensor that loses contact during hard effort
    (low skin contact, sweat evaporation, etc.).

    Expected: hr_reliable = False, because pace-HR correlation is negative.
    """
    time = list(range(duration_s))
    heartrate = []
    velocity = []
    cadence = []
    distance = []
    altitude = []
    grade = []
    cum_dist = 0.0

    steady_s = duration_s - warmup_s - finish_kick_s

    for t in time:
        # Velocity: warmup (2.0 m/s) → steady (3.0 m/s) → fast finish (4.5 m/s)
        if t < warmup_s:
            frac = t / warmup_s
            v = 2.0 + frac * 1.0  # 2.0 → 3.0
        elif t < warmup_s + steady_s:
            v = 3.0
        else:
            frac = (t - warmup_s - steady_s) / finish_kick_s
            v = 3.0 + frac * 1.5  # 3.0 → 4.5

        # HR: INVERTED — high when slow, low when fast (sensor glitch)
        if t < warmup_s:
            frac = t / warmup_s
            hr = 120.0 - frac * 20.0  # 120 → 100 (dropping as pace increases)
        elif t < warmup_s + steady_s:
            hr = 95.0  # suspiciously low for 6:40/mi
        else:
            frac = (t - warmup_s - steady_s) / finish_kick_s
            hr = 95.0 - frac * 20.0  # 95 → 75 (drops MORE as runner sprints)

        cum_dist += v
        velocity.append(round(v, 3))
        heartrate.append(round(hr, 1))
        cadence.append(175)
        distance.append(round(cum_dist, 1))
        altitude.append(100.0)
        grade.append(0.0)

    return {
        "time": time,
        "heartrate": heartrate,
        "velocity_smooth": velocity,
        "cadence": cadence,
        "distance": distance,
        "altitude": altitude,
        "grade_smooth": grade,
    }


def make_flatline_hr_stream(
    duration_s: int = 3600,
) -> Dict[str, List]:
    """HR flatlined near resting during a hard run — sensor stuck.

    Pace varies normally (progressive run) but HR is locked at ~65 bpm
    with tiny noise. Std dev of HR is unreasonably low for a run.

    Expected: hr_reliable = False.
    """
    time = list(range(duration_s))
    heartrate = []
    velocity = []
    cadence = []
    distance = []
    altitude = []
    grade = []
    cum_dist = 0.0

    for t in time:
        # Progressive pace: 2.5 → 4.0 m/s over the run
        frac = t / duration_s
        v = 2.5 + frac * 1.5

        # HR: flatlined near 65 with ±1 noise
        hr = 65.0 + (t % 3 - 1) * 0.5  # 64.5, 65.0, 65.5 repeating

        cum_dist += v
        velocity.append(round(v, 3))
        heartrate.append(round(hr, 1))
        cadence.append(170)
        distance.append(round(cum_dist, 1))
        altitude.append(100.0)
        grade.append(0.0)

    return {
        "time": time,
        "heartrate": heartrate,
        "velocity_smooth": velocity,
        "cadence": cadence,
        "distance": distance,
        "altitude": altitude,
        "grade_smooth": grade,
    }


def make_dropout_hr_stream(
    duration_s: int = 3600,
    dropout_start_s: int = 1200,
    dropout_end_s: int = 2400,
) -> Dict[str, List]:
    """HR drops to 0 for a sustained period mid-run.

    Normal HR for first and last thirds, zero/near-zero for middle third.

    Expected: hr_reliable = False.
    """
    time = list(range(duration_s))
    heartrate = []
    velocity = []
    cadence = []
    distance = []
    altitude = []
    grade = []
    cum_dist = 0.0

    for t in time:
        v = 3.0  # steady pace throughout

        if t < dropout_start_s:
            hr = 145.0  # normal running HR
        elif t < dropout_end_s:
            hr = 0.0  # sensor dropout
        else:
            hr = 148.0  # normal running HR

        cum_dist += v
        velocity.append(round(v, 3))
        heartrate.append(round(hr, 1))
        cadence.append(172)
        distance.append(round(cum_dist, 1))
        altitude.append(100.0)
        grade.append(0.0)

    return {
        "time": time,
        "heartrate": heartrate,
        "velocity_smooth": velocity,
        "cadence": cadence,
        "distance": distance,
        "altitude": altitude,
        "grade_smooth": grade,
    }


def make_normal_hr_stream(
    duration_s: int = 3600,
) -> Dict[str, List]:
    """Normal, reliable HR data — control fixture.

    HR positively correlated with pace. Should NOT trigger sanity check.

    Expected: hr_reliable = True.
    """
    time = list(range(duration_s))
    heartrate = []
    velocity = []
    cadence = []
    distance = []
    altitude = []
    grade = []
    cum_dist = 0.0

    for t in time:
        # Easy run: warmup then steady
        if t < 600:
            frac = t / 600
            v = 2.0 + frac * 0.8
            hr = 100.0 + frac * 40.0  # 100 → 140
        else:
            v = 2.8
            elapsed = t - 600
            hr = 140.0 + (elapsed / 3600.0) * 8.0  # slow drift

        cum_dist += v
        velocity.append(round(v, 3))
        heartrate.append(round(hr, 1))
        cadence.append(172)
        distance.append(round(cum_dist, 1))
        altitude.append(100.0)
        grade.append(0.0)

    return {
        "time": time,
        "heartrate": heartrate,
        "velocity_smooth": velocity,
        "cadence": cadence,
        "distance": distance,
        "altitude": altitude,
        "grade_smooth": grade,
    }
