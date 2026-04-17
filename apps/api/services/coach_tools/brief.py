from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)

from models import Activity, TrainingPlan, PlannedWorkout, Athlete
from core.date_utils import calculate_age
from services.coach_tools._utils import (
    _iso, _mi_from_m, _pace_str_mi, _pace_str, _relative_date,
    _preferred_units, _fmt_mmss, _format_run_context, _M_PER_MI,
)


def build_athlete_brief(db: Session, athlete_id: UUID) -> str:  # noqa: C901
    """
    ADR-16: Build a comprehensive pre-computed athlete brief.

    This is the coach's preparation — everything they should know before
    the conversation starts. Pre-computed facts, not raw data. The LLM
    reads this and coaches from it.

    Returns a human-readable multi-section string (~3000-4000 tokens).
    Cached in Redis for 15 minutes. Invalidated on activity write.
    """
    from core.cache import get_cache, set_cache
    from services.timezone_utils import get_athlete_timezone_from_db, athlete_local_today
    import services.coach_tools as ct
    _tz = get_athlete_timezone_from_db(db, athlete_id)
    units = _preferred_units(db, athlete_id)
    is_metric = units == "metric"
    dist_unit = "km" if is_metric else "mi"
    pace_unit = "/km" if is_metric else "/mi"
    _cache_key = f"athlete_brief:{athlete_id}:{units}"
    _cached = get_cache(_cache_key)
    if _cached is not None:
        return _cached

    today = athlete_local_today(_tz)
    sections: List[str] = [
        f"## Date Context\nToday is {today.isoformat()} ({today.strftime('%A')}). All dates below include pre-computed relative labels like '(2 days ago)' or '(yesterday)'. USE those labels verbatim — do NOT compute your own relative time. NEVER say 'X days ago' unless that exact label appears in the data."
    ]

    # ── 1. IDENTITY ──────────────────────────────────────────────────
    try:
        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if athlete:
            lines = [f"Name: {athlete.display_name or 'Athlete'}"]
            if athlete.birthdate:
                age = calculate_age(athlete.birthdate, today)
                lines.append(f"Age: {age}")
            if athlete.sex:
                lines.append(f"Sex: {athlete.sex}")
            lines.append(f"Units: {athlete.preferred_units or 'metric'}")
            sections.append("## Identity\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: identity failed: {e}")

    # ── 1b. ATHLETE EXPERIENCE CALIBRATION ──────────────────────────
    try:
        from services.fitness_bank import FitnessBankCalculator
        from models import PerformanceEvent, CorrelationFinding

        bank = FitnessBankCalculator(db).calculate(athlete_id)
        if bank:
            exp_lines = [f"Experience level: {bank.experience_level.value}"]

            def _vol(mi: float, decimals: int = 0) -> str:
                if is_metric:
                    return f"{(mi * 1.609344):.{decimals}f} {dist_unit}"
                return f"{mi:.{decimals}f} {dist_unit}"

            if bank.peak_weekly_miles:
                exp_lines.append(f"Peak proven weekly volume: {_vol(bank.peak_weekly_miles, 0)}")
            if bank.current_weekly_miles:
                exp_lines.append(f"Current weekly volume: {_vol(bank.current_weekly_miles, 0)}")
            if bank.current_long_run_miles:
                exp_lines.append(f"Recent long run: {_vol(bank.current_long_run_miles, 1)}")
            if bank.is_returning_from_break:
                exp_lines.append("Status: returning from break")
            else:
                exp_lines.append("Status: active training (not returning from break)")

            race_events = (
                db.query(PerformanceEvent)
                .filter(
                    PerformanceEvent.athlete_id == athlete_id,
                    PerformanceEvent.event_type == "race",
                )
                .count()
            )
            if race_events:
                exp_lines.append(f"Races on record: {race_events}")

            self_reg = (
                db.query(CorrelationFinding)
                .filter(
                    CorrelationFinding.athlete_id == athlete_id,
                    CorrelationFinding.is_active == True,  # noqa: E712
                    CorrelationFinding.times_confirmed >= 3,
                )
                .count()
            )
            if self_reg:
                exp_lines.append(f"Confirmed personal patterns: {self_reg}")

            sections.append("## Athlete Experience Calibration\n" + "\n".join(exp_lines))
    except Exception as e:
        logger.debug(f"Brief: experience calibration failed: {e}")

    # ── 2. GOAL RACE ─────────────────────────────────────────────────
    try:
        plan = (
            db.query(TrainingPlan)
            .filter(TrainingPlan.athlete_id == athlete_id, TrainingPlan.status == "active")
            .first()
        )
        if plan:
            lines = [f"Race: {plan.goal_race_name or plan.name}"]
            if plan.goal_race_date:
                days_until = (plan.goal_race_date - today).days
                lines.append(f"Date: {plan.goal_race_date.isoformat()} ({days_until} days away)")
            if plan.goal_race_distance_m:
                if is_metric:
                    dist_km = plan.goal_race_distance_m / 1000.0
                    lines.append(f"Distance: {dist_km:.1f} km ({plan.goal_race_distance_m}m)")
                else:
                    dist_mi = plan.goal_race_distance_m / _M_PER_MI
                    lines.append(f"Distance: {dist_mi:.1f} miles ({plan.goal_race_distance_m}m)")
            if plan.goal_time_seconds:
                h = plan.goal_time_seconds // 3600
                m = (plan.goal_time_seconds % 3600) // 60
                s = plan.goal_time_seconds % 60
                lines.append(f"Target time: {h}:{m:02d}:{s:02d}")
                if plan.goal_race_distance_m and plan.goal_race_distance_m > 0:
                    if is_metric:
                        goal_pace_sec = plan.goal_time_seconds / (plan.goal_race_distance_m / 1000.0)
                    else:
                        goal_pace_sec = plan.goal_time_seconds / (plan.goal_race_distance_m / _M_PER_MI)
                    gp_m = int(goal_pace_sec // 60)
                    gp_s = int(round(goal_pace_sec % 60))
                    lines.append(f"Target pace: {gp_m}:{gp_s:02d}{pace_unit}")
            sections.append("## Goal Race\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: goal race failed: {e}")

    # ── 3. TRAINING STATE ────────────────────────────────────────────
    try:
        load_data = ct.get_training_load(db, athlete_id)
        if load_data.get("ok"):
            d = load_data["data"]
            ctl = d.get("ctl", "N/A")
            atl = d.get("atl", "N/A")
            tsb = d.get("tsb", "N/A")
            zone = d.get("tsb_zone", {})
            zone_label = zone.get("label", "")
            phase = d.get("training_phase", "")
            rec = d.get("recommendation", "")
            lines = [
                "(INTERNAL — use to reason about their state but NEVER quote these numbers to the athlete. Translate into plain coaching language.)",
                f"Chronic load (CTL): {ctl}",
                f"Acute load (ATL): {atl}",
                f"Balance (TSB): {tsb} — {zone_label}",
            ]
            if phase:
                lines.append(f"Phase: {phase}")
            if rec:
                lines.append(f"Recommendation: {rec}")
            sections.append("## Training State\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: training state failed: {e}")

    # ── 4. RECOVERY & DURABILITY ─────────────────────────────────────
    try:
        recovery = ct.get_recovery_status(db, athlete_id)
        if recovery.get("ok"):
            d = recovery["data"]
            lines = [
                "(INTERNAL — reason from these but translate into coaching language for the athlete.)",
                f"Recovery status: {d.get('status', 'unknown')}",
                f"Injury risk score: {d.get('injury_risk_score', 'N/A')}",
            ]
            if d.get("durability_index") is not None:
                lines.append(f"Durability index: {d['durability_index']}")
            if d.get("recovery_half_life_hours") is not None:
                lines.append(f"Recovery half-life: {d['recovery_half_life_hours']:.1f}h")
            sections.append("## Recovery & Durability\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: recovery failed: {e}")

    # ── 5. VOLUME TRAJECTORY ─────────────────────────────────────────
    try:
        weekly = ct.get_weekly_volume(db, athlete_id, weeks=8)
        if weekly.get("ok"):
            weeks_data = weekly.get("data", {}).get("weeks_data", weekly.get("data", {}).get("weeks", []))
            if weeks_data:
                lines = []
                completed_weeks = []
                current_week_info = None
                _dist_key = "total_distance_km" if is_metric else "total_distance_mi"
                for w in weeks_data:
                    dist = w.get(_dist_key, 0)
                    runs = w.get("run_count", 0)
                    if w.get("is_current_week"):
                        elapsed = w.get("days_elapsed", "?")
                        remaining = w.get("days_remaining", "?")
                        current_week_info = f"Current week: {dist:.1f}{dist_unit} through {elapsed} of 7 days ({runs} runs, {remaining} days remaining)"
                    else:
                        completed_weeks.append((w.get("week_start", ""), dist, runs))

                # Show trajectory
                if completed_weeks:
                    recent = completed_weeks[-4:]  # last 4 completed weeks
                    trajectory = " → ".join(f"{d:.0f}" for _, d, _ in recent)
                    lines.append(f"Recent completed weeks ({dist_unit}): {trajectory}")
                    if len(recent) >= 2:
                        first_val = recent[0][1]
                        last_val = recent[-1][1]
                        if first_val > 0:
                            pct_change = ((last_val - first_val) / first_val) * 100
                            direction = "up" if pct_change > 0 else "down"
                            lines.append(f"Trend: {direction} {abs(pct_change):.0f}% over {len(recent)} weeks")
                    # Peak volume
                    peak = max(completed_weeks, key=lambda x: x[1])
                    try:
                        _peak_rel = _relative_date(date.fromisoformat(peak[0]), today)
                    except (ValueError, TypeError):
                        _peak_rel = ""
                    lines.append(f"Peak week: {peak[1]:.1f}{dist_unit} (week of {peak[0]}) {_peak_rel}")
                    if last_val > 0 and peak[1] > 0:
                        pct_of_peak = (last_val / peak[1]) * 100
                        lines.append(f"Current vs peak: {pct_of_peak:.0f}%")

                if current_week_info:
                    lines.append(current_week_info)

                sections.append("## Volume Trajectory\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: volume trajectory failed: {e}")

    # ── 6. RECENT RUNS (grouped by date for multi-activity days) ────
    try:
        recent = ct.get_recent_runs(db, athlete_id, days=14)
        if recent.get("ok"):
            runs = recent.get("data", {}).get("runs", [])
            if runs:
                from collections import OrderedDict
                by_date: OrderedDict[str, list] = OrderedDict()
                for run in runs[:10]:
                    run_date = (run.get("start_time") or "")[:10]
                    by_date.setdefault(run_date, []).append(run)

                lines = [f"Last {len(runs)} runs (14 days):"]
                _run_dist_key = "distance_km" if is_metric else "distance_mi"
                _run_pace_key = "pace_per_km" if is_metric else "pace_per_mile"
                for run_date, day_runs in by_date.items():
                    try:
                        _day_rel = " " + _relative_date(date.fromisoformat(run_date), today)
                    except (ValueError, TypeError):
                        _day_rel = ""

                    if len(day_runs) > 1:
                        day_dist = sum(r.get(_run_dist_key, 0) or 0 for r in day_runs)
                        has_race = any(r.get("is_race") for r in day_runs)
                        label = "Race day" if has_race else f"{len(day_runs)} activities"
                        lines.append(f"  {run_date}{_day_rel} — {label} ({day_dist:.1f}{dist_unit} total):")
                        for run in day_runs:
                            name = run.get("shape_sentence") or run.get("name", "Run")
                            dist = run.get(_run_dist_key, 0) or 0
                            pace = run.get(_run_pace_key, "N/A")
                            hr = run.get("avg_hr", "")
                            hr_str = f" | HR {hr}" if hr else ""
                            tag = " [race]" if run.get("is_race") else ""
                            ctx = _format_run_context(run, units=units)
                            lines.append(f"    • {name} — {dist:.1f}{dist_unit} @ {pace}{hr_str}{ctx}{tag}")
                    else:
                        run = day_runs[0]
                        name = run.get("name", "Run")
                        dist = run.get(_run_dist_key, 0) or 0
                        pace = run.get(_run_pace_key, "N/A")
                        hr = run.get("avg_hr", "")
                        hr_str = f" | HR {hr}" if hr else ""
                        ctx = _format_run_context(run, units=units)
                        lines.append(f"  {run_date}{_day_rel}: {name} — {dist:.1f}{dist_unit} @ {pace}{hr_str}{ctx}")

                sections.append("## Recent Runs\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: recent runs failed: {e}")

    # ── 7. RACE PREDICTIONS ──────────────────────────────────────────
    try:
        preds = ct.get_race_predictions(db, athlete_id)
        if preds.get("ok"):
            pred_data = preds.get("data", {}).get("predictions", {})
            if pred_data:
                lines = []
                for dist_name in ["5K", "10K", "Half Marathon", "Marathon"]:
                    p = pred_data.get(dist_name, {})
                    pred_info = p.get("prediction", {})
                    time_fmt = pred_info.get("time_formatted")
                    confidence = pred_info.get("confidence", "")
                    if time_fmt:
                        lines.append(f"  {dist_name}: {time_fmt} ({confidence} confidence)")
                if lines:
                    sections.append("## Race Predictions\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: race predictions failed: {e}")

    # ── 8. TRAINING PACES ────────────────────────────────────────────
    try:
        paces = ct.get_training_paces(db, athlete_id)
        if paces.get("ok"):
            d = paces["data"]
            pace_data = d.get("paces", {})
            rpi = d.get("rpi", "N/A")
            lines = [
                f"RPI (Running Performance Index): {rpi}",
                "(Paces from RPI — the ONLY authoritative source. NEVER prescribe HR zones.)",
            ]
            easy_val = pace_data.get("easy", "N/A")
            lines.append(f"  Easy: {easy_val} (CEILING — athlete should not run faster than this on easy days)")
            for zone_name in ["marathon", "threshold", "interval", "repetition"]:
                val = pace_data.get(zone_name, "N/A")
                lines.append(f"  {zone_name.capitalize()}: {val}")
            sections.append("## Training Paces\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: training paces failed: {e}")

    # ── 9. KEY PERSONAL BESTS ────────────────────────────────────────
    try:
        pbs = ct.get_pb_patterns(db, athlete_id)
        if pbs.get("ok"):
            pb_list = pbs.get("data", {}).get("pbs", [])
            if pb_list:
                lines = []
                for pb in pb_list[:5]:
                    cat = pb.get("category", pb.get("distance_category", ""))
                    dist_km = pb.get("distance_km", "")
                    time_min = pb.get("time_min", "")
                    pb_date = (pb.get("date") or "")[:10]
                    try:
                        _pb_rel = _relative_date(date.fromisoformat(pb_date), today)
                    except (ValueError, TypeError):
                        _pb_rel = ""
                    if dist_km and time_min:
                        lines.append(f"  {cat}: {time_min:.1f}min / {dist_km:.1f}km ({pb_date} {_pb_rel})")
                if lines:
                    sections.append("## Personal Bests\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: personal bests failed: {e}")

    # ── 10. PERSONAL FINGERPRINT (confirmed patterns with layer intelligence) ──
    try:
        from services.fingerprint_context import build_fingerprint_prompt_section
        fp_section = build_fingerprint_prompt_section(athlete_id, db, verbose=False, max_findings=10)
        if fp_section:
            sections.append("## Personal Fingerprint\n" + fp_section)
        else:
            corr = ct.get_correlations(db, athlete_id, days=90)
            if corr.get("ok"):
                corr_data = corr.get("data", {})
                correlations = corr_data.get("correlations", []) if isinstance(corr_data, dict) else []
                if isinstance(correlations, list) and correlations:
                    lines = []
                    for c in correlations[:5]:
                        input_name = c.get("input_name", "?")
                        output_name = c.get("output_name", "?")
                        r = c.get("correlation_coefficient", 0)
                        n = c.get("sample_size", 0)
                        direction = "positively" if r > 0 else "inversely"
                        lines.append(
                            f"  {input_name} {direction} correlates with {output_name} "
                            f"(r={r:.2f}, n={n})"
                        )
                    if lines:
                        sections.append("## N-of-1 Insights (Correlations)\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: personal fingerprint failed: {e}")

    # ── 10b. INVESTIGATION FINDINGS (race input analysis) ──
    try:
        from services.finding_persistence import get_active_findings
        stored = get_active_findings(athlete_id, db)
        if stored:
            lines = [
                "(Investigation findings — what the system discovered about this athlete's training patterns.)"
            ]
            for f in stored[:8]:
                conf_label = f"confidence: {f.confidence}" if f.confidence else ""
                lines.append(f"  [{f.investigation_name}] {f.sentence} ({conf_label})")
            sections.append("## Training Discoveries\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: investigation findings failed: {e}")

    # ── 11. EFFICIENCY TREND ─────────────────────────────────────────
    try:
        eff = ct.get_efficiency_trend(db, athlete_id, days=60)
        if eff.get("ok"):
            d = eff.get("data", {})
            if d:
                lines = []
                trend = d.get("trend_direction", "")
                avg_ef = d.get("average_ef")
                best_ef = d.get("best_ef")
                if trend:
                    lines.append(f"Trend: {trend}")
                if avg_ef:
                    lines.append(f"Average EF (60 days): {avg_ef}")
                if best_ef:
                    lines.append(f"Best recent EF: {best_ef}")
                if lines:
                    sections.append("## Efficiency Trend\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: efficiency trend failed: {e}")

    # ── 11b. NUTRITION SNAPSHOT ───────────────────────────────────────
    try:
        from models import NutritionEntry
        _n_today = today
        _n_week_ago = today - timedelta(days=7)

        today_entries = (
            db.query(NutritionEntry)
            .filter(
                NutritionEntry.athlete_id == athlete_id,
                NutritionEntry.date == _n_today,
            )
            .all()
        )
        week_entries = (
            db.query(NutritionEntry)
            .filter(
                NutritionEntry.athlete_id == athlete_id,
                NutritionEntry.date >= _n_week_ago,
            )
            .all()
        )

        if today_entries or week_entries:
            n_lines = [
                "(INTERNAL — use to reason about fueling but do NOT recite raw numbers unprompted. "
                "Only discuss nutrition specifics when the athlete asks. Use get_nutrition_log tool for detail.)"
            ]

            if today_entries:
                t_cal = sum(float(e.calories or 0) for e in today_entries)
                t_p = sum(float(e.protein_g or 0) for e in today_entries)
                t_c = sum(float(e.carbs_g or 0) for e in today_entries)
                t_f = sum(float(e.fat_g or 0) for e in today_entries)
                t_caf = sum(float(e.caffeine_mg or 0) for e in today_entries)
                n_lines.append(f"Today: {round(t_cal)} cal, {round(t_p)}g P / {round(t_c)}g C / {round(t_f)}g F ({len(today_entries)} entries)")
                if t_caf > 0:
                    n_lines.append(f"Today caffeine: {round(t_caf)}mg")
            else:
                n_lines.append("Today: no entries logged yet")

            if week_entries:
                by_day: Dict[str, list] = {}
                for e in week_entries:
                    d_str = e.date.isoformat() if e.date else ""
                    by_day.setdefault(d_str, []).append(e)
                days_logged = len(by_day)
                avg_cal = sum(sum(float(x.calories or 0) for x in day) for day in by_day.values()) / max(days_logged, 1)
                avg_p = sum(sum(float(x.protein_g or 0) for x in day) for day in by_day.values()) / max(days_logged, 1)
                avg_c = sum(sum(float(x.carbs_g or 0) for x in day) for day in by_day.values()) / max(days_logged, 1)
                avg_f = sum(sum(float(x.fat_g or 0) for x in day) for day in by_day.values()) / max(days_logged, 1)
                n_lines.append(f"7-day avg: {round(avg_cal)} cal/day ({round(avg_p)}P / {round(avg_c)}C / {round(avg_f)}F) — logged {days_logged}/7 days")

                pre_run = [e for e in week_entries if e.entry_type == "pre_activity"]
                if pre_run:
                    pr_carbs = sum(float(e.carbs_g or 0) for e in pre_run) / len(pre_run)
                    pr_caf = sum(float(e.caffeine_mg or 0) for e in pre_run) / len(pre_run)
                    n_lines.append(f"Pre-run pattern: {len(pre_run)} entries, avg {round(pr_carbs)}g carbs, {round(pr_caf)}mg caffeine")

            try:
                from services.nutrition_targets import compute_daily_targets
                targets = compute_daily_targets(db, athlete_id, today)
                if targets:
                    tier_labels = {"rest": "Rest day", "easy": "Easy day", "moderate": "Moderate day", "hard": "Hard day", "long": "Long run day"}
                    tier_label = tier_labels.get(targets["day_tier"], targets["day_tier"])
                    n_lines.append(
                        f"Goal: {targets['goal_type']} — {tier_label} ({targets['multiplier']}x) — "
                        f"target {targets['calorie_target']} cal, {targets['protein_g']}g P / "
                        f"{targets['carbs_g']}g C / {targets['fat_g']}g F"
                    )
            except Exception:
                pass

            sections.append("## Nutrition Snapshot\n" + "\n".join(n_lines))
    except Exception as e:
        logger.debug(f"Brief: nutrition snapshot failed: {e}")

    # ── 12. INTENT & CHECK-IN ────────────────────────────────────────
    try:
        intent = ct.get_coach_intent_snapshot(db, athlete_id)
        if intent.get("ok"):
            d = intent.get("data", {})
            lines = []
            if d.get("training_intent"):
                lines.append(f"Training intent: {d['training_intent']}")
            if d.get("pain_flag") and d["pain_flag"] != "none":
                lines.append(f"Pain flag: {d['pain_flag']}")
            if d.get("weekly_mileage_target"):
                _wmt = d["weekly_mileage_target"]
                try:
                    _wmt_num = float(_wmt)
                    if is_metric:
                        lines.append(f"Weekly volume target: {_wmt_num * 1.609344:.0f} {dist_unit}")
                    else:
                        lines.append(f"Weekly volume target: {_wmt_num:.0f} {dist_unit}")
                except (TypeError, ValueError):
                    lines.append(f"Weekly volume target: {_wmt}")
            if d.get("next_event_date"):
                try:
                    _evt_rel = _relative_date(date.fromisoformat(str(d['next_event_date'])[:10]), today)
                except (ValueError, TypeError):
                    _evt_rel = ""
                lines.append(f"Next event: {d['next_event_date']} {_evt_rel} ({d.get('next_event_type', '')})")
            if lines:
                sections.append("## Athlete Intent\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: intent failed: {e}")

    try:
        from models import DailyCheckin
        checkin = (
            db.query(DailyCheckin)
            .filter(DailyCheckin.athlete_id == athlete_id)
            .order_by(DailyCheckin.date.desc())
            .first()
        )
        if checkin:
            try:
                _ci_date = checkin.date if isinstance(checkin.date, date) else date.fromisoformat(str(checkin.date)[:10])
                _ci_rel = _relative_date(_ci_date, today)
            except (ValueError, TypeError):
                _ci_rel = ""
            lines = [f"Date: {checkin.date} {_ci_rel}"]
            if checkin.sleep_h is not None:
                lines.append(f"Sleep: {checkin.sleep_h}h")
            if checkin.readiness_1_5 is not None:
                readiness_map = {5: 'High', 4: 'Good', 3: 'Neutral', 2: 'Low', 1: 'Poor'}
                lines.append(f"Readiness: {readiness_map.get(checkin.readiness_1_5, checkin.readiness_1_5)}")
            if checkin.soreness_1_5 is not None:
                soreness_map = {1: 'None', 2: 'Mild', 4: 'Yes'}
                lines.append(f"Soreness: {soreness_map.get(checkin.soreness_1_5, checkin.soreness_1_5)}/5")
            if checkin.stress_1_5 is not None:
                lines.append(f"Stress: {checkin.stress_1_5}/5")
            if checkin.notes:
                lines.append(f"Notes: {checkin.notes[:150]}")
            sections.append("## Latest Check-in\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: checkin failed: {e}")

    if not sections:
        return "(No athlete data available)"

    brief = "\n\n".join(sections)
    set_cache(_cache_key, brief, ttl=900)  # 15 min
    return brief



def compute_running_math(
    db: Session,
    athlete_id: UUID,
    pace_per_mile: str = "",
    pace_per_km: str = "",
    distance_miles: float = 0.0,
    distance_km: float = 0.0,
    time_seconds: int = 0,
    operation: str = "pace_to_finish",
) -> Dict[str, Any]:
    """
    General-purpose running math calculator. The LLM calls this instead of
    doing arithmetic.

    Operations:
      pace_to_finish  — given pace + distance, compute finish time
      finish_to_pace  — given finish time + distance, compute required pace
      split_calc      — given two split paces + half distance each, compute total

    Accepts either imperial (miles) or metric (km). Returns both.
    """
    now = datetime.utcnow()

    def _parse_pace(pace_str: str) -> Optional[float]:
        """Parse 'M:SS' or 'M:SS/mi' or 'M:SS/km' into seconds."""
        if not pace_str:
            return None
        cleaned = re.sub(r"/(mi|km|mile|k)\s*$", "", pace_str.strip())
        parts = cleaned.split(":")
        try:
            if len(parts) == 2:
                return int(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 1:
                return float(parts[0])
        except (ValueError, TypeError):
            return None
        return None

    def _fmt_time(total_seconds: float) -> str:
        """Format seconds as H:MM:SS or M:SS."""
        total_seconds = round(total_seconds)
        h = int(total_seconds // 3600)
        m = int((total_seconds % 3600) // 60)
        s = int(total_seconds % 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    def _fmt_pace(seconds_per_unit: float) -> str:
        m = int(seconds_per_unit // 60)
        s = int(round(seconds_per_unit % 60))
        return f"{m}:{s:02d}"

    try:
        # Normalize distance to miles and km
        dist_mi = distance_miles or (distance_km / 1.60934 if distance_km else 0.0)
        dist_km = distance_km or (distance_miles * 1.60934 if distance_miles else 0.0)

        result: Dict[str, Any] = {"operation": operation}

        if operation == "pace_to_finish":
            pace_sec = _parse_pace(pace_per_mile)
            unit = "mi"
            dist = dist_mi
            if not pace_sec and pace_per_km:
                pace_sec = _parse_pace(pace_per_km)
                unit = "km"
                dist = dist_km
            if not pace_sec or dist <= 0:
                return {"ok": False, "tool": "compute_running_math",
                        "error": "Need a pace and distance to compute finish time."}
            if unit == "km":
                finish_sec = pace_sec * dist_km
                pace_per_mi_sec = pace_sec * 1.60934
            else:
                finish_sec = pace_sec * dist_mi
                pace_per_mi_sec = pace_sec
            pace_per_km_sec = pace_per_mi_sec / 1.60934
            result.update({
                "finish_time": _fmt_time(finish_sec),
                "finish_time_seconds": round(finish_sec),
                "pace_per_mile": _fmt_pace(pace_per_mi_sec) + "/mi",
                "pace_per_km": _fmt_pace(pace_per_km_sec) + "/km",
                "distance_miles": round(dist_mi, 2),
                "distance_km": round(dist_km, 2),
            })

        elif operation == "finish_to_pace":
            if not time_seconds or (dist_mi <= 0 and dist_km <= 0):
                return {"ok": False, "tool": "compute_running_math",
                        "error": "Need a finish time and distance to compute pace."}
            pace_mi = time_seconds / dist_mi if dist_mi > 0 else 0
            pace_km = time_seconds / dist_km if dist_km > 0 else 0
            result.update({
                "finish_time": _fmt_time(time_seconds),
                "pace_per_mile": _fmt_pace(pace_mi) + "/mi",
                "pace_per_km": _fmt_pace(pace_km) + "/km",
                "distance_miles": round(dist_mi, 2),
                "distance_km": round(dist_km, 2),
            })

        elif operation == "split_calc":
            # For split calculations, pace_per_mile = first half pace, pace_per_km = second half pace
            # (repurposing fields) or pass as "7:30,7:00" in pace_per_mile
            paces = pace_per_mile.split(",") if "," in pace_per_mile else [pace_per_mile, pace_per_km]
            p1 = _parse_pace(paces[0].strip() if len(paces) > 0 else "")
            p2 = _parse_pace(paces[1].strip() if len(paces) > 1 else "")
            if not p1 or not p2 or dist_mi <= 0:
                return {"ok": False, "tool": "compute_running_math",
                        "error": "Need two split paces and total distance."}
            half_dist = dist_mi / 2.0
            total_sec = (p1 * half_dist) + (p2 * half_dist)
            avg_pace = total_sec / dist_mi
            result.update({
                "first_half_pace": _fmt_pace(p1) + "/mi",
                "second_half_pace": _fmt_pace(p2) + "/mi",
                "average_pace": _fmt_pace(avg_pace) + "/mi",
                "finish_time": _fmt_time(total_sec),
                "finish_time_seconds": round(total_sec),
                "distance_miles": round(dist_mi, 2),
                "negative_split_seconds": round(p1 * half_dist - p2 * half_dist),
            })
        else:
            return {"ok": False, "tool": "compute_running_math",
                    "error": f"Unknown operation: {operation}. Use pace_to_finish, finish_to_pace, or split_calc."}

        # --- Narrative ---
        if operation == "pace_to_finish":
            math_narr = (
                f"At {result.get('pace_per_mile', '?')} pace over {result.get('distance_miles', '?')} miles: "
                f"finish time is {result.get('finish_time', '?')}."
            )
        elif operation == "finish_to_pace":
            math_narr = (
                f"To finish {result.get('distance_miles', '?')} miles in {result.get('finish_time', '?')}: "
                f"required pace is {result.get('pace_per_mile', '?')}."
            )
        elif operation == "split_calc":
            math_narr = (
                f"Split calculation over {result.get('distance_miles', '?')} miles: "
                f"first half at {result.get('first_half_pace', '?')}, "
                f"second half at {result.get('second_half_pace', '?')}, "
                f"finish time {result.get('finish_time', '?')}."
            )
        else:
            math_narr = f"Running math result: {result}"

        return {
            "ok": True,
            "tool": "compute_running_math",
            "generated_at": _iso(now),
            "narrative": math_narr,
            "data": result,
            "evidence": [{
                "type": "derived",
                "id": f"running_math:{operation}",
                "date": _iso(now)[:10],
                "value": f"{operation}: {result.get('finish_time', result.get('pace_per_mile', 'computed'))}",
            }],
        }
    except Exception as e:
        return {"ok": False, "tool": "compute_running_math", "error": str(e)}


# ---------------------------------------------------------------------------
# GET MILE/KM SPLITS — coach tool
# ---------------------------------------------------------------------------



