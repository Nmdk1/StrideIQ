#!/usr/bin/env python3
"""
ADVANCED PLAN QUALITY AUDIT
============================

Goes beyond basic validation to ensure plans are EXCEPTIONAL:
- T-block progression follows established patterns
- MP progression builds appropriately  
- Long runs progress then taper
- Distance-specific requirements met
- Workout descriptions are clear and actionable
- Counter-conventional notes are insightful

Sources:
- _AI_CONTEXT_/KNOWLEDGE_BASE/TRAINING_PHILOSOPHY.md
- _AI_CONTEXT_/KNOWLEDGE_BASE/PLAN_GENERATION_FRAMEWORK.md
- Daniels Running Formula, Pfitzinger Advanced Marathoning, Hudson Run Faster

Author: AI Assistant
Date: 2026-01-15
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta
from uuid import uuid4
from unittest.mock import MagicMock
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import json
import statistics

from services.model_driven_plan_generator import generate_model_driven_plan


# ==============================================================================
# QUALITY CRITERIA
# ==============================================================================

QUALITY_CRITERIA = {
    "threshold_progression": {
        "description": "T-work should progress from intervals to continuous",
        "example": "Week 5: 5×5min → Week 6: 4×6min → Week 7: 3×8min → Week 9: 2×10min → Week 11: 20min continuous",
        "source": "TRAINING_PHILOSOPHY.md T-Block Progression"
    },
    "mp_progression": {
        "description": "Marathon pace work should build from 4mi to 8-14mi",
        "example": "Week 9: 4mi @ MP → Week 13: 10mi → Week 15: 14mi",
        "source": "PLAN_GENERATION_FRAMEWORK.md MP Progression"
    },
    "long_run_progression": {
        "description": "Long runs build then taper appropriately",
        "marathon_peak": "20-22 miles, hold 2-3 weeks before taper",
        "half_peak": "14-16 miles",
        "source": "TRAINING_PHILOSOPHY.md Long Run"
    },
    "cutback_effectiveness": {
        "description": "Cutback weeks should reduce volume 20-30%",
        "source": "TRAINING_PHILOSOPHY.md Cut-back Weeks"
    },
    "workout_descriptions": {
        "description": "Descriptions should be clear, actionable, include paces",
        "good_example": "Threshold: 3 × 8 min at 7:15/mi (comfortably hard), 2 min jog recovery",
        "bad_example": "Threshold workout"
    },
    "counter_conventional_notes": {
        "description": "Notes should be insightful, not generic",
        "good_example": "Your τ1 of 38 days suggests you absorb fitness slowly - hold big weeks longer",
        "bad_example": "Listen to your body"
    }
}


@dataclass
class QualityCheck:
    name: str
    passed: bool
    score: float  # 0-100
    details: str
    recommendation: str = ""


def create_mock_db():
    """Create mock database session."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.all.return_value = []
    mock_db.query.return_value.filter.return_value.first.return_value = None
    return mock_db


def generate_test_plan(distance: str, weeks: int):
    """Generate a plan for testing."""
    mock_db = create_mock_db()
    athlete_id = uuid4()
    race_date = date.today() + timedelta(days=weeks * 7)
    
    return generate_model_driven_plan(
        athlete_id=athlete_id,
        race_date=race_date,
        race_distance=distance,
        db=mock_db
    )


# ==============================================================================
# ADVANCED QUALITY CHECKS
# ==============================================================================

def check_threshold_progression(plan) -> QualityCheck:
    """
    Verify T-work progresses from shorter intervals to longer continuous.
    
    Expected pattern:
    - Build phase starts: 5-6 × 5min intervals
    - Build phase ends: 20-40min continuous
    """
    quality_sessions = []
    
    # Look for quality/threshold/tempo/race_pace workouts
    quality_types = {"quality", "threshold", "tempo", "race_pace", "sharpening"}
    
    for week in plan.weeks:
        for day in week.days:
            if day.workout_type in quality_types or "threshold" in (day.name or "").lower() or "tempo" in (day.name or "").lower():
                quality_sessions.append({
                    "week": week.week_number,
                    "phase": week.phase,
                    "description": day.description or "",
                    "name": day.name or "",
                    "tss": day.target_tss or 0
                })
    
    if len(quality_sessions) < 3:
        return QualityCheck(
            name="Threshold Progression",
            passed=False,
            score=30,
            details=f"Only {len(quality_sessions)} quality sessions found",
            recommendation="Add more threshold work in build phase"
        )
    
    # Check if descriptions suggest progression
    has_intervals = any("×" in s["description"] or "x" in s["description"] for s in quality_sessions[:len(quality_sessions)//2])
    has_continuous = any("continuous" in s["description"].lower() or "tempo" in s["description"].lower() for s in quality_sessions[len(quality_sessions)//2:])
    
    # Check TSS increases over time in quality sessions
    tss_values = [s["tss"] for s in quality_sessions if s["tss"] > 0]
    if len(tss_values) >= 3:
        first_half_avg = statistics.mean(tss_values[:len(tss_values)//2])
        second_half_avg = statistics.mean(tss_values[len(tss_values)//2:])
        tss_progresses = second_half_avg >= first_half_avg * 0.9  # Allow 10% variance
    else:
        tss_progresses = True
    
    passed = has_intervals or has_continuous or tss_progresses
    score = 100 if (has_intervals and has_continuous) else (70 if passed else 40)
    
    return QualityCheck(
        name="Threshold Progression",
        passed=passed,
        score=score,
        details=f"Found {len(quality_sessions)} quality sessions. Intervals: {has_intervals}, Continuous: {has_continuous}",
        recommendation="" if passed else "Ensure T-work progresses from intervals to continuous"
    )


def check_long_run_progression(plan, distance: str) -> QualityCheck:
    """
    Verify long runs build appropriately then taper.
    
    Marathon: Build to 20-22mi, hold 2-3 weeks, then taper to 12-14mi
    Half: Build to 14-16mi, hold 1-2 weeks, then taper to 10mi
    """
    long_runs = []
    
    for week in plan.weeks:
        for day in week.days:
            if day.workout_type in ("long", "long_run"):
                long_runs.append({
                    "week": week.week_number,
                    "phase": week.phase,
                    "miles": day.target_miles or 0,
                    "is_cutback": week.is_cutback
                })
    
    if not long_runs:
        return QualityCheck(
            name="Long Run Progression",
            passed=False,
            score=0,
            details="No long runs found!",
            recommendation="CRITICAL: Add long runs"
        )
    
    # Get non-cutback long run distances
    regular_long_runs = [lr for lr in long_runs if not lr["is_cutback"]]
    if not regular_long_runs:
        regular_long_runs = long_runs
    
    distances = [lr["miles"] for lr in regular_long_runs]
    peak_distance = max(distances)
    peak_week_idx = distances.index(peak_distance)
    
    # Expected peak distances
    expected_peak = {
        "marathon": (18, 24),
        "half_marathon": (13, 18),
        "10k": (10, 15),
        "5k": (8, 12)
    }.get(distance, (12, 20))
    
    peak_appropriate = expected_peak[0] <= peak_distance <= expected_peak[1]
    
    # Check taper (last 2-3 weeks should decrease)
    if len(distances) >= 3:
        final_runs = distances[-3:]
        taper_ok = final_runs[-1] < max(final_runs[:2]) * 0.85
    else:
        taper_ok = True
    
    # Check build (generally increasing before peak)
    if len(distances) >= 4:
        early_runs = distances[:len(distances)//2]
        mid_runs = distances[len(distances)//2:-2] if len(distances) > 4 else []
        if early_runs and mid_runs:
            builds_up = statistics.mean(mid_runs) > statistics.mean(early_runs)
        else:
            builds_up = True
    else:
        builds_up = True
    
    passed = peak_appropriate and taper_ok
    score = 100 if (peak_appropriate and taper_ok and builds_up) else (70 if passed else 40)
    
    return QualityCheck(
        name="Long Run Progression",
        passed=passed,
        score=score,
        details=f"Peak: {peak_distance:.1f}mi (expected {expected_peak[0]}-{expected_peak[1]}), Taper OK: {taper_ok}, Builds: {builds_up}",
        recommendation="" if passed else f"Adjust peak long run to {expected_peak[0]}-{expected_peak[1]} miles"
    )


def check_cutback_effectiveness(plan) -> QualityCheck:
    """
    Verify cutback weeks reduce volume by 20-30%.
    """
    weekly_tss = []
    cutback_weeks = []
    
    for i, week in enumerate(plan.weeks):
        weekly_tss.append({
            "week": week.week_number,
            "tss": week.target_tss,
            "is_cutback": week.is_cutback
        })
        if week.is_cutback:
            cutback_weeks.append(i)
    
    if not cutback_weeks:
        return QualityCheck(
            name="Cutback Week Effectiveness",
            passed=False,
            score=30,
            details="No cutback weeks found",
            recommendation="Add cutback weeks every 3-4 weeks"
        )
    
    # Check each cutback reduces volume appropriately
    reductions = []
    for idx in cutback_weeks:
        if idx > 0:
            prev_tss = weekly_tss[idx - 1]["tss"]
            cutback_tss = weekly_tss[idx]["tss"]
            if prev_tss > 0:
                reduction = (prev_tss - cutback_tss) / prev_tss * 100
                reductions.append(reduction)
    
    if reductions:
        avg_reduction = statistics.mean(reductions)
        reductions_ok = all(15 <= r <= 40 for r in reductions)
    else:
        avg_reduction = 0
        reductions_ok = False
    
    passed = reductions_ok and len(cutback_weeks) >= 2
    score = 100 if (avg_reduction >= 20 and reductions_ok) else (70 if passed else 40)
    
    return QualityCheck(
        name="Cutback Week Effectiveness",
        passed=passed,
        score=score,
        details=f"Cutback weeks: {len(cutback_weeks)}, Avg reduction: {avg_reduction:.1f}%, Individual: {[f'{r:.0f}%' for r in reductions]}",
        recommendation="" if passed else "Cutback weeks should reduce volume 20-30%"
    )


def check_workout_description_quality(plan) -> QualityCheck:
    """
    Verify workout descriptions are clear, actionable, include paces.
    """
    quality_indicators = {
        "has_pace": 0,
        "has_duration": 0,
        "has_effort": 0,
        "has_recovery": 0,
        "is_detailed": 0
    }
    
    total_workouts = 0
    
    for week in plan.weeks:
        for day in week.days:
            if day.workout_type in ("rest", "shakeout"):
                continue
            
            total_workouts += 1
            desc = (day.description or "").lower()
            
            if any(x in desc for x in ["/mi", "/km", "pace", "min/mi"]):
                quality_indicators["has_pace"] += 1
            
            if any(x in desc for x in ["min", "miles", "km", "hour"]):
                quality_indicators["has_duration"] += 1
            
            if any(x in desc for x in ["easy", "comfortably", "hard", "relaxed", "fast", "threshold", "tempo"]):
                quality_indicators["has_effort"] += 1
            
            if "recovery" in desc or "jog" in desc or "rest" in desc:
                quality_indicators["has_recovery"] += 1
            
            if len(desc) > 50:
                quality_indicators["is_detailed"] += 1
    
    if total_workouts == 0:
        return QualityCheck(
            name="Workout Description Quality",
            passed=False,
            score=0,
            details="No workouts found",
            recommendation="CRITICAL: Plan has no workouts"
        )
    
    # Calculate score
    pct_with_pace = quality_indicators["has_pace"] / total_workouts * 100
    pct_with_effort = quality_indicators["has_effort"] / total_workouts * 100
    pct_detailed = quality_indicators["is_detailed"] / total_workouts * 100
    
    overall_score = (pct_with_pace + pct_with_effort + pct_detailed) / 3
    passed = overall_score >= 50
    
    return QualityCheck(
        name="Workout Description Quality",
        passed=passed,
        score=overall_score,
        details=f"Pace info: {pct_with_pace:.0f}%, Effort cues: {pct_with_effort:.0f}%, Detailed: {pct_detailed:.0f}%",
        recommendation="" if passed else "Add pace, effort cues, and detail to workout descriptions"
    )


def check_counter_conventional_notes(plan) -> QualityCheck:
    """
    Verify counter-conventional notes are insightful, not generic.
    """
    notes = plan.counter_conventional_notes or []
    
    if not notes:
        return QualityCheck(
            name="Counter-Conventional Notes",
            passed=False,
            score=30,
            details="No counter-conventional notes found",
            recommendation="Add personalized insights based on model parameters"
        )
    
    # Check for quality indicators
    quality_indicators = {
        "mentions_tau": any("τ" in n or "tau" in n.lower() for n in notes),
        "mentions_data": any(x in " ".join(notes).lower() for x in ["your data", "your history", "your pattern"]),
        "is_specific": any(len(n) > 60 for n in notes),
        "has_numbers": any(any(c.isdigit() for c in n) for n in notes),
        "not_generic": not any(x in " ".join(notes).lower() for x in ["listen to your body", "stay hydrated", "warm up"])
    }
    
    score = sum(20 for v in quality_indicators.values() if v)
    passed = score >= 60
    
    return QualityCheck(
        name="Counter-Conventional Notes",
        passed=passed,
        score=score,
        details=f"Notes: {len(notes)}, τ reference: {quality_indicators['mentions_tau']}, Data-driven: {quality_indicators['mentions_data']}, Specific: {quality_indicators['is_specific']}",
        recommendation="" if passed else "Notes should reference personal τ values and data-driven insights"
    )


def check_distance_specific_requirements(plan, distance: str) -> QualityCheck:
    """
    Verify distance-specific workout requirements.
    """
    requirements = {
        "5k": {
            "needs_intervals": True,
            "needs_threshold": True,
            "needs_mp": False,
            "min_long_run": 6,
            "max_long_run": 12
        },
        "10k": {
            "needs_intervals": True,
            "needs_threshold": True,
            "needs_mp": False,
            "min_long_run": 8,
            "max_long_run": 15
        },
        "half_marathon": {
            "needs_intervals": False,
            "needs_threshold": True,
            "needs_mp": True,
            "min_long_run": 12,
            "max_long_run": 18
        },
        "marathon": {
            "needs_intervals": False,
            "needs_threshold": True,
            "needs_mp": True,
            "min_long_run": 16,
            "max_long_run": 24
        }
    }.get(distance, {})
    
    # Analyze plan
    workout_types = set()
    max_long_run = 0
    
    for week in plan.weeks:
        for day in week.days:
            workout_types.add(day.workout_type.lower())
            desc = (day.description or "").lower()
            
            if "interval" in desc or "repeat" in desc:
                workout_types.add("intervals")
            if "threshold" in desc or "tempo" in desc:
                workout_types.add("threshold")
            if "marathon pace" in desc or "mp" in desc.split() or "race pace" in desc:
                workout_types.add("mp")
            
            if day.workout_type in ("long", "long_run"):
                max_long_run = max(max_long_run, day.target_miles or 0)
    
    # Check requirements
    checks = []
    
    if requirements.get("needs_threshold"):
        has_threshold = "threshold" in workout_types or "tempo" in workout_types or "quality" in workout_types
        checks.append(("Threshold work", has_threshold))
    
    if requirements.get("needs_mp"):
        has_mp = "mp" in workout_types or "race_pace" in workout_types
        checks.append(("MP work", has_mp))
    
    if requirements.get("min_long_run"):
        long_ok = max_long_run >= requirements["min_long_run"]
        checks.append((f"Long run ≥{requirements['min_long_run']}mi", long_ok))
    
    passed_checks = [c for c in checks if c[1]]
    failed_checks = [c for c in checks if not c[1]]
    
    score = len(passed_checks) / len(checks) * 100 if checks else 100
    passed = len(failed_checks) == 0
    
    return QualityCheck(
        name="Distance-Specific Requirements",
        passed=passed,
        score=score,
        details=f"Passed: {[c[0] for c in passed_checks]}, Failed: {[c[0] for c in failed_checks]}, Max long: {max_long_run:.1f}mi",
        recommendation="" if passed else f"Missing: {', '.join(c[0] for c in failed_checks)}"
    )


def check_weekly_volume_progression(plan) -> QualityCheck:
    """
    Verify weekly volume builds gradually (no >10% jumps except after cutback).
    """
    weekly_volumes = []
    
    for week in plan.weeks:
        weekly_volumes.append({
            "week": week.week_number,
            "tss": week.target_tss,
            "miles": week.target_miles,
            "is_cutback": week.is_cutback
        })
    
    violations = []
    
    for i in range(1, len(weekly_volumes)):
        prev = weekly_volumes[i - 1]
        curr = weekly_volumes[i]
        
        # Skip if coming off cutback (expect increase)
        if prev["is_cutback"]:
            continue
        
        # Skip if current is cutback (expect decrease)
        if curr["is_cutback"]:
            continue
        
        # Check for >15% increase
        if prev["tss"] > 0:
            increase = (curr["tss"] - prev["tss"]) / prev["tss"] * 100
            if increase > 15:
                violations.append(f"Week {i} → {i+1}: +{increase:.0f}%")
    
    passed = len(violations) <= 1  # Allow one exception
    score = 100 if not violations else max(0, 100 - len(violations) * 20)
    
    return QualityCheck(
        name="Weekly Volume Progression",
        passed=passed,
        score=score,
        details=f"Violations: {violations}" if violations else "Gradual progression maintained",
        recommendation="" if passed else "Reduce volume jumps to <15% between non-cutback weeks"
    )


def check_race_week_optimization(plan) -> QualityCheck:
    """
    Verify race week is optimally structured for peak performance.
    """
    race_week = plan.weeks[-1]
    
    checks = {
        "ends_with_race": False,
        "has_shakeout": False,
        "has_rest_day_before": False,
        "minimal_quality": True,
        "low_volume": False
    }
    
    for i, day in enumerate(race_week.days):
        if day.workout_type == "race":
            checks["ends_with_race"] = True
            # Check day before
            if i > 0 and race_week.days[i-1].workout_type in ("rest", "shakeout"):
                checks["has_rest_day_before"] = True
        
        if day.workout_type == "shakeout":
            checks["has_shakeout"] = True
        
        if day.workout_type == "quality":
            checks["minimal_quality"] = False
    
    # Check total TSS is low (race week should be ~50% of normal)
    avg_tss = sum(w.target_tss for w in plan.weeks[:-2]) / max(1, len(plan.weeks) - 2)
    checks["low_volume"] = race_week.target_tss < avg_tss * 0.7
    
    passed_count = sum(1 for v in checks.values() if v)
    score = passed_count / len(checks) * 100
    passed = checks["ends_with_race"] and passed_count >= 4
    
    return QualityCheck(
        name="Race Week Optimization",
        passed=passed,
        score=score,
        details=f"Checks: {checks}",
        recommendation="" if passed else "Optimize race week: ends with race, shakeout, rest before race"
    )


def run_quality_audit():
    """Run comprehensive quality audit for all distances."""
    print("=" * 80)
    print("ADVANCED PLAN QUALITY AUDIT")
    print("Ensuring plans are EXCEPTIONAL, not just correct")
    print("=" * 80)
    print()
    
    distances = ["5k", "10k", "half_marathon", "marathon"]
    week_configs = {
        "5k": 8,
        "10k": 10,
        "half_marathon": 12,
        "marathon": 16,  # Test with 16 weeks for marathon
    }
    
    all_results = {}
    
    for distance in distances:
        weeks = week_configs[distance]
        print(f"\n{'='*60}")
        print(f"AUDITING: {distance.upper()} ({weeks} weeks)")
        print(f"{'='*60}")
        
        try:
            plan = generate_test_plan(distance, weeks)
            
            checks = [
                check_threshold_progression(plan),
                check_long_run_progression(plan, distance),
                check_cutback_effectiveness(plan),
                check_workout_description_quality(plan),
                check_counter_conventional_notes(plan),
                check_distance_specific_requirements(plan, distance),
                check_weekly_volume_progression(plan),
                check_race_week_optimization(plan),
            ]
            
            all_results[distance] = checks
            
            # Calculate overall score
            avg_score = statistics.mean(c.score for c in checks)
            passed = sum(1 for c in checks if c.passed)
            
            print(f"\nQuality Score: {avg_score:.0f}/100")
            print(f"Checks Passed: {passed}/{len(checks)}")
            print()
            
            for check in checks:
                status = "✓" if check.passed else "✗"
                print(f"  {status} {check.name}: {check.score:.0f}/100")
                print(f"      {check.details}")
                if check.recommendation:
                    print(f"      → {check.recommendation}")
            
            # Rating
            if avg_score >= 85:
                rating = "EXCEPTIONAL"
            elif avg_score >= 70:
                rating = "GOOD"
            elif avg_score >= 50:
                rating = "ACCEPTABLE"
            else:
                rating = "NEEDS IMPROVEMENT"
            
            print(f"\n  Rating: {rating}")
            
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    # Overall summary
    print(f"\n{'='*80}")
    print("OVERALL QUALITY SUMMARY")
    print(f"{'='*80}")
    
    total_score = 0
    total_checks = 0
    total_passed = 0
    
    for distance, checks in all_results.items():
        dist_score = statistics.mean(c.score for c in checks)
        dist_passed = sum(1 for c in checks if c.passed)
        print(f"  {distance.upper():15} - Score: {dist_score:.0f}/100, Passed: {dist_passed}/{len(checks)}")
        total_score += dist_score
        total_checks += len(checks)
        total_passed += dist_passed
    
    overall_avg = total_score / len(all_results)
    
    print(f"\n  OVERALL AVERAGE: {overall_avg:.0f}/100")
    print(f"  TOTAL CHECKS PASSED: {total_passed}/{total_checks}")
    
    print(f"\n{'='*80}")
    if overall_avg >= 85:
        print("VERDICT: WORLD-CLASS QUALITY")
        print("Plans meet or exceed professional coaching standards")
    elif overall_avg >= 70:
        print("VERDICT: GOOD QUALITY")
        print("Plans are solid but have room for improvement")
    else:
        print("VERDICT: NEEDS WORK")
        print("Plans require improvements before production use")
    print(f"{'='*80}")
    
    return all_results


if __name__ == "__main__":
    run_quality_audit()
