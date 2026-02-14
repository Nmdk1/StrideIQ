"""Synthetic stream data generators for Phase 2 tests.

Each generator produces a dict matching ActivityStream.stream_data format:
    {"time": [...], "heartrate": [...], "velocity_smooth": [...], ...}

All generators are deterministic (no randomness) for AC-4 compliance.
"""
import math
from typing import Dict, List, Optional


def make_easy_run_stream(
    duration_s: int = 3600,
    warmup_s: int = 600,
    cooldown_s: int = 300,
    steady_pace_m_s: float = 2.8,        # ~5:57/km
    warmup_start_pace_m_s: float = 2.0,  # ~8:20/km
    resting_hr: int = 60,
    steady_hr: int = 140,
    drift_hr_per_hour: float = 8.0,      # bpm/hr cardiac drift
    cadence_spm: int = 172,
) -> Dict[str, List]:
    """60-min easy run: warmup ramp → steady with gradual drift → cooldown.

    Segments expected: warmup(0-600), steady(600-3300), cooldown(3300-3600).
    Drift: ~8 bpm/hr cardiac drift during steady portion.
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
        # Velocity profile
        if t < warmup_s:
            frac = t / warmup_s
            v = warmup_start_pace_m_s + frac * (steady_pace_m_s - warmup_start_pace_m_s)
        elif t < duration_s - cooldown_s:
            v = steady_pace_m_s
        else:
            frac = (t - (duration_s - cooldown_s)) / cooldown_s
            v = steady_pace_m_s - frac * (steady_pace_m_s - warmup_start_pace_m_s)

        # HR profile: ramp during warmup, drift during steady, drop during cooldown
        if t < warmup_s:
            frac = t / warmup_s
            hr = resting_hr + frac * (steady_hr - resting_hr)
        elif t < duration_s - cooldown_s:
            elapsed_steady = t - warmup_s
            drift = drift_hr_per_hour * (elapsed_steady / 3600.0)
            hr = steady_hr + drift
        else:
            frac = (t - (duration_s - cooldown_s)) / cooldown_s
            last_steady_hr = steady_hr + drift_hr_per_hour * ((duration_s - cooldown_s - warmup_s) / 3600.0)
            hr = last_steady_hr - frac * (last_steady_hr - resting_hr - 20)

        cum_dist += v
        velocity.append(round(v, 3))
        heartrate.append(round(hr, 1))
        cadence.append(cadence_spm)
        distance.append(round(cum_dist, 1))
        altitude.append(100.0)  # flat
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


def make_interval_stream(
    reps: int = 6,
    warmup_s: int = 600,
    cooldown_s: int = 300,
    work_duration_s: int = 90,
    rest_duration_s: int = 90,
    work_pace_m_s: float = 4.5,          # ~3:42/km
    rest_pace_m_s: float = 2.0,          # ~8:20/km jog
    work_hr: int = 175,
    rest_hr: int = 140,
    warmup_pace_m_s: float = 2.5,
    cadence_work: int = 190,
    cadence_rest: int = 165,
) -> Dict[str, List]:
    """Interval session: warmup → (work+recovery)*N → cooldown.

    Expected segments: warmup, then alternating work/recovery, then cooldown.
    """
    total_s = warmup_s + reps * (work_duration_s + rest_duration_s) + cooldown_s
    time = list(range(total_s))
    heartrate = []
    velocity = []
    cadence = []
    distance = []
    altitude = []
    grade = []
    cum_dist = 0.0

    for t in time:
        if t < warmup_s:
            frac = t / warmup_s
            v = warmup_pace_m_s * 0.8 + frac * (warmup_pace_m_s - warmup_pace_m_s * 0.8)
            hr = 80 + frac * (rest_hr - 80)
            cad = 165
        elif t < warmup_s + reps * (work_duration_s + rest_duration_s):
            interval_t = t - warmup_s
            rep_duration = work_duration_s + rest_duration_s
            within_rep = interval_t % rep_duration

            if within_rep < work_duration_s:
                v = work_pace_m_s
                hr = work_hr
                cad = cadence_work
            else:
                v = rest_pace_m_s
                hr = rest_hr
                cad = cadence_rest
        else:
            frac = (t - (total_s - cooldown_s)) / cooldown_s
            v = warmup_pace_m_s - frac * (warmup_pace_m_s - warmup_pace_m_s * 0.6)
            hr = rest_hr - frac * 30
            cad = 160

        cum_dist += v
        velocity.append(round(v, 3))
        heartrate.append(round(hr, 1))
        cadence.append(cad)
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


def make_progressive_run_stream(
    duration_s: int = 3000,
    warmup_s: int = 600,
    cooldown_s: int = 180,
    start_pace_m_s: float = 2.6,
    end_pace_m_s: float = 3.8,
    start_hr: int = 135,
    end_hr: int = 170,
    cadence_start: int = 170,
    cadence_end: int = 185,
) -> Dict[str, List]:
    """Progressive run: warmup → monotonically increasing pace → cooldown.

    Expected: warmup + single steady/work segment with descending pace + cooldown.
    """
    time = list(range(duration_s))
    heartrate = []
    velocity = []
    cadence = []
    distance = []
    cum_dist = 0.0
    work_duration = duration_s - warmup_s - cooldown_s

    for t in time:
        if t < warmup_s:
            frac = t / warmup_s
            v = start_pace_m_s * 0.75 + frac * (start_pace_m_s - start_pace_m_s * 0.75)
            hr = 80 + frac * (start_hr - 80)
            cad = 165
        elif t < duration_s - cooldown_s:
            frac = (t - warmup_s) / work_duration
            v = start_pace_m_s + frac * (end_pace_m_s - start_pace_m_s)
            hr = start_hr + frac * (end_hr - start_hr)
            cad = cadence_start + int(frac * (cadence_end - cadence_start))
        else:
            frac = (t - (duration_s - cooldown_s)) / cooldown_s
            v = end_pace_m_s - frac * (end_pace_m_s - start_pace_m_s * 0.6)
            hr = end_hr - frac * 40
            cad = 165

        cum_dist += v
        velocity.append(round(v, 3))
        heartrate.append(round(hr, 1))
        cadence.append(cad)
        distance.append(round(cum_dist, 1))

    return {
        "time": time,
        "heartrate": heartrate,
        "velocity_smooth": velocity,
        "cadence": cadence,
        "distance": distance,
        "altitude": [100.0] * duration_s,
        "grade_smooth": [0.0] * duration_s,
    }


def make_long_run_with_drift_stream(
    duration_s: int = 7200,
    warmup_s: int = 600,
    cooldown_s: int = 300,
    steady_pace_m_s: float = 2.7,
    steady_hr_start: int = 138,
    drift_onset_s: int = 4200,        # drift becomes notable at 70 min
    drift_rate_bpm_per_hour: float = 12.0,
    cadence_spm: int = 170,
) -> Dict[str, List]:
    """2-hour long run with clear cardiac drift onset at ~70 min.

    Expected: warmup + long steady segment, cardiac drift onset moment detected.
    """
    time = list(range(duration_s))
    heartrate = []
    velocity = []
    cadence = []
    distance = []
    cum_dist = 0.0

    for t in time:
        if t < warmup_s:
            frac = t / warmup_s
            v = steady_pace_m_s * 0.75 + frac * (steady_pace_m_s - steady_pace_m_s * 0.75)
            hr = 70 + frac * (steady_hr_start - 70)
        elif t < duration_s - cooldown_s:
            v = steady_pace_m_s
            if t < drift_onset_s:
                # Pre-drift: slow/mild rise
                elapsed = t - warmup_s
                hr = steady_hr_start + 2.0 * (elapsed / 3600.0)
            else:
                # Post-drift onset: accelerated HR rise
                pre_drift_hr = steady_hr_start + 2.0 * ((drift_onset_s - warmup_s) / 3600.0)
                elapsed_since_onset = t - drift_onset_s
                hr = pre_drift_hr + drift_rate_bpm_per_hour * (elapsed_since_onset / 3600.0)
        else:
            frac = (t - (duration_s - cooldown_s)) / cooldown_s
            last_hr = steady_hr_start + 2.0 * ((drift_onset_s - warmup_s) / 3600.0) + \
                      drift_rate_bpm_per_hour * ((duration_s - cooldown_s - drift_onset_s) / 3600.0)
            v = steady_pace_m_s - frac * (steady_pace_m_s * 0.3)
            hr = last_hr - frac * 30

        cum_dist += v
        velocity.append(round(v, 3))
        heartrate.append(round(hr, 1))
        cadence.append(cadence_spm)
        distance.append(round(cum_dist, 1))

    return {
        "time": time,
        "heartrate": heartrate,
        "velocity_smooth": velocity,
        "cadence": cadence,
        "distance": distance,
        "altitude": [100.0] * duration_s,
        "grade_smooth": [0.0] * duration_s,
    }


def make_hill_repeat_stream(
    reps: int = 5,
    warmup_s: int = 600,
    cooldown_s: int = 300,
    uphill_s: int = 120,
    downhill_s: int = 120,
    uphill_grade: float = 8.0,
    downhill_grade: float = -8.0,
    uphill_pace_m_s: float = 2.5,
    downhill_pace_m_s: float = 3.5,
    uphill_hr: int = 172,
    downhill_hr: int = 145,
) -> Dict[str, List]:
    """Hill repeats: grade explains pace variation (not fitness).

    Expected: segment detection must account for grade when classifying work/recovery.
    """
    total_s = warmup_s + reps * (uphill_s + downhill_s) + cooldown_s
    time = list(range(total_s))
    heartrate = []
    velocity = []
    cadence = []
    distance = []
    altitude_list = []
    grade_list = []
    cum_dist = 0.0
    alt = 100.0

    for t in time:
        if t < warmup_s:
            frac = t / warmup_s
            v = 2.5 * 0.8 + frac * 0.5
            hr = 80 + frac * 60
            g = 0.0
        elif t < warmup_s + reps * (uphill_s + downhill_s):
            rep_t = t - warmup_s
            within_rep = rep_t % (uphill_s + downhill_s)
            if within_rep < uphill_s:
                v = uphill_pace_m_s
                hr = uphill_hr
                g = uphill_grade
            else:
                v = downhill_pace_m_s
                hr = downhill_hr
                g = downhill_grade
        else:
            frac = (t - (total_s - cooldown_s)) / cooldown_s
            v = 2.5 - frac * 0.8
            hr = 140 - frac * 30
            g = 0.0

        alt += v * math.sin(math.radians(math.atan(g / 100.0) * 180 / math.pi)) if g != 0 else 0
        cum_dist += v
        velocity.append(round(v, 3))
        heartrate.append(round(hr, 1))
        cadence.append(175)
        distance.append(round(cum_dist, 1))
        altitude_list.append(round(alt, 1))
        grade_list.append(g)

    return {
        "time": time,
        "heartrate": heartrate,
        "velocity_smooth": velocity,
        "cadence": cadence,
        "distance": distance,
        "altitude": altitude_list,
        "grade_smooth": grade_list,
    }


def make_partial_stream(channels: List[str], duration_s: int = 1800) -> Dict[str, List]:
    """Stream with only specified channels — for partial-channel testing."""
    time = list(range(duration_s))
    result = {"time": time}

    if "heartrate" in channels:
        result["heartrate"] = [140.0 + 0.002 * t for t in time]
    if "velocity_smooth" in channels:
        result["velocity_smooth"] = [2.8] * duration_s
    if "cadence" in channels:
        result["cadence"] = [172] * duration_s
    if "distance" in channels:
        result["distance"] = [2.8 * t for t in time]
    if "altitude" in channels:
        result["altitude"] = [100.0] * duration_s
    if "grade_smooth" in channels:
        result["grade_smooth"] = [0.0] * duration_s

    return result
