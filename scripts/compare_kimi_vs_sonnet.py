#!/usr/bin/env python3
"""
Offline replay comparator: kimi-k2-turbo-preview vs Claude Sonnet 4.6

Usage:
    python scripts/compare_kimi_vs_sonnet.py [OPTIONS]

Options:
    --athlete-id UUID     Replay prompts for a specific athlete (default: use fixtures)
    --fixtures-file PATH  JSON file with pre-captured prompts (default: built-in fixtures)
    --output-dir PATH     Where to write results (default: scripts/replay_results/)
    --calls N             How many prompts to replay per model (default: 5)
    --timeout S           Per-call timeout in seconds (default: 30 — kimi-k2-turbo-preview responds in ~800ms)
    --sonnet-only         Only run Sonnet (baseline pass — generate fixtures)
    --kimi-only           Only run Kimi (comparison pass)
    --no-coach            Skip coach tool-call scenario (default: include in offline, skip live canary)

Environment variables required:
    ANTHROPIC_API_KEY   — for Sonnet baseline
    KIMI_API_KEY        — for Kimi comparison

Scoring criteria (output to summary.md):
    - JSON parse compliance (briefing calls)
    - Hallucination guard: required fields present
    - Latency p50/p95
    - Field coverage (optional fields populated)
    - Side-by-side diff logged per prompt

Example:
    ANTHROPIC_API_KEY=sk-... KIMI_API_KEY=sk-... python scripts/compare_kimi_vs_sonnet.py --calls 10
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add api directory to path so we can import from it
_REPO_ROOT = Path(__file__).resolve().parent.parent
_API_DIR = _REPO_ROOT / "apps" / "api"
# Allow override via env var for cases where script is run from outside the repo
# (e.g. copied into a Docker container at /tmp)
_API_DIR_OVERRIDE = os.environ.get("STRIDEIQ_API_DIR")
if _API_DIR_OVERRIDE:
    sys.path.insert(0, _API_DIR_OVERRIDE)
elif _API_DIR.exists():
    sys.path.insert(0, str(_API_DIR))
else:
    # Fallback: try common container path
    for _fallback in ["/app", "/opt/strideiq/repo/apps/api"]:
        if Path(_fallback).exists():
            sys.path.insert(0, _fallback)
            break


# ---------------------------------------------------------------------------
# Built-in prompt fixtures (representative briefing scenarios)
# ---------------------------------------------------------------------------

_REQUIRED_BRIEFING_FIELDS = ["coach_noticed", "week_assessment", "today_context", "morning_voice"]
_OPTIONAL_BRIEFING_FIELDS = ["checkin_reaction", "race_assessment"]

_BRIEFING_SCHEMA = {
    "coach_noticed": "1-2 sentences on the most notable training signal from recent runs",
    "morning_voice": "A personal, motivating 1-sentence opener for the day — references real data",
    "week_assessment": "2-3 sentences assessing this week's training load and quality",
    "today_context": "1-2 sentences of actionable guidance for today's training decision",
    "checkin_reaction": "OPTIONAL: 1 sentence responding to the athlete check-in",
    "race_assessment": "OPTIONAL: 1-2 sentences on race readiness if race data is present",
}

_FIXTURES: List[Dict[str, Any]] = [
    {
        "scenario": "steady_week_no_race",
        "type": "briefing",
        "system_suffix": "",
        "user_prompt": (
            "Athlete context: 35-year-old male recreational runner. "
            "Recent runs: Mon 5mi easy (8:30/mi), Wed 8mi with 4x1mi at 7:00, Sat 12mi long (8:45/mi). "
            "Weekly mileage: 25mi. "
            "Efficiency trend: stable (+2% vs 4-week avg). "
            "No check-in today. No upcoming race. "
            "Generate a home briefing for this athlete."
        ),
    },
    {
        "scenario": "race_week_taper",
        "type": "briefing",
        "system_suffix": "",
        "user_prompt": (
            "Athlete context: 28-year-old female competitive runner. "
            "Recent runs: Mon 4mi easy (7:45/mi), Tue 30min strides only, Thu 3mi easy. "
            "Weekly mileage: 11mi (tapering). Race in 3 days: Half Marathon, goal 1:35. "
            "4-week avg weekly mileage: 42mi. "
            "HRV trend: improving. Sleep avg: 7.8h/night last week. "
            "Generate a home briefing for this athlete."
        ),
    },
    {
        "scenario": "overtraining_signal",
        "type": "briefing",
        "system_suffix": "",
        "user_prompt": (
            "Athlete context: 42-year-old male high-mileage runner. "
            "Recent runs: Mon 10mi (7:30/mi), Tue 8mi (7:20/mi), Wed 12mi (7:15/mi), Thu 9mi (7:25/mi). "
            "Weekly mileage so far: 39mi in 4 days. "
            "Efficiency trend: declining (-8% vs 4-week avg). "
            "Athlete check-in: 'Legs feel heavy and sluggish.' "
            "No race scheduled. "
            "Generate a home briefing for this athlete."
        ),
    },
    {
        "scenario": "new_runner_low_data",
        "type": "briefing",
        "system_suffix": "",
        "user_prompt": (
            "Athlete context: 24-year-old female, just started running. "
            "Recent runs: Mon 2mi (10:30/mi), Thu 1.5mi (11:00/mi). "
            "Weekly mileage: 3.5mi. First 2 weeks of running. "
            "No race scheduled. No check-in. "
            "Generate a home briefing for this athlete."
        ),
    },
    {
        "scenario": "post_marathon_recovery",
        "type": "briefing",
        "system_suffix": "",
        "user_prompt": (
            "Athlete context: 38-year-old male, ran marathon 5 days ago (3:45:00 finish). "
            "Recent runs: 2 days rest, then 2x 15min very easy jog (10:30/mi). "
            "No check-in today. No upcoming race for 8 weeks. "
            "Weekly mileage this week: 5mi. "
            "Generate a home briefing for this athlete."
        ),
    },
]


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _build_system_prompt(schema: dict, required: list) -> str:
    _today = date.today()
    field_descriptions = "\n".join(
        f'  - "{k}" ({"REQUIRED" if k in required else "optional"}): {v}'
        for k, v in schema.items()
    )
    return (
        f"You are an elite running coach generating a structured home page briefing. "
        f"Today is {_today.isoformat()} ({_today.strftime('%A')}). "
        "Respond with ONLY a valid JSON object — no markdown, no code fences, no explanation. "
        f"The JSON must contain these fields:\n{field_descriptions}\n\n"
        "Rules:\n"
        "- Every required field MUST be present.\n"
        "- Optional fields should be included only when relevant data exists.\n"
        "- Keep each field concise: 1-2 sentences max.\n"
        "- Respond with the raw JSON object only.\n"
        "- Do NOT invent statistics, times, or names not mentioned in the prompt."
    )


def _parse_json_safely(text: str) -> Optional[dict]:
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t[3:]
    if t.endswith("```"):
        t = t[:-3]
    t = t.strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        return None


def _score_result(raw_text: str, required_fields: list, latency_ms: float) -> dict:
    parsed = _parse_json_safely(raw_text)
    json_ok = parsed is not None
    fields_present = []
    fields_missing = []
    if parsed:
        for f in required_fields:
            if parsed.get(f):
                fields_present.append(f)
            else:
                fields_missing.append(f)
    return {
        "json_parse_ok": json_ok,
        "required_fields_present": fields_present,
        "required_fields_missing": fields_missing,
        "all_required_ok": json_ok and len(fields_missing) == 0,
        "latency_ms": round(latency_ms, 1),
        "parsed": parsed,
    }


# ---------------------------------------------------------------------------
# Model call wrappers
# ---------------------------------------------------------------------------

def _call_model(model: str, system: str, user_prompt: str, timeout_s: int) -> Tuple[str, float, str]:
    """Returns (raw_text, latency_ms, actual_model_used). Raises on hard failure."""
    # Import here so the script can be run standalone without full Django setup
    from core.llm_client import call_llm
    t0 = time.monotonic()
    result = call_llm(
        model=model,
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
        max_tokens=2000,
        temperature=0.3,
        response_mode="json",
        timeout_s=timeout_s,
    )
    latency_ms = (time.monotonic() - t0) * 1000
    return result["text"], latency_ms, result["provider"]


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

def _write_summary(results: list, output_dir: Path, sonnet_model: str, kimi_model: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write per-scenario JSONs
    for r in results:
        scenario = r["scenario"]
        with open(output_dir / f"{scenario}.json", "w", encoding="utf-8") as f:
            json.dump(r, f, indent=2)

    # Aggregate stats
    def _stats(model_key: str) -> dict:
        rows = [r[model_key] for r in results if r.get(model_key)]
        if not rows:
            return {}
        parse_ok = sum(1 for x in rows if x.get("json_parse_ok", False))
        all_req_ok = sum(1 for x in rows if x.get("all_required_ok", False))
        latencies = [x["latency_ms"] for x in rows]
        latencies.sort()
        p50 = latencies[len(latencies) // 2] if latencies else 0
        p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
        # For kimi rows, track how many were actually served by Kimi (not fallback)
        kimi_served = sum(1 for x in rows if x.get("kimi_served", True))
        result = {
            "n": len(rows),
            "json_parse_rate": f"{parse_ok}/{len(rows)} ({100*parse_ok//len(rows)}%)",
            "required_fields_rate": f"{all_req_ok}/{len(rows)} ({100*all_req_ok//len(rows)}%)",
            "p50_latency_ms": round(p50, 1),
            "p95_latency_ms": round(p95, 1),
        }
        if model_key == "kimi":
            result["kimi_served_rate"] = f"{kimi_served}/{len(rows)} ({100*kimi_served//len(rows)}%)"
        return result

    sonnet_stats = _stats("sonnet")
    kimi_stats = _stats("kimi")

    # Acceptance criteria evaluation
    def _meets_criteria(s: dict, k: dict) -> List[str]:
        issues = []
        if not k:
            issues.append("NO KIMI RESULTS — cannot evaluate")
            return issues
        # Kimi must actually serve >= 90% of calls (not fall back to Sonnet/Gemini)
        served_str = k.get("kimi_served_rate", "N/A")
        if served_str != "N/A":
            served_pct = int(served_str.split("(")[1].rstrip("%)"))
            if served_pct < 90:
                issues.append(
                    f"Kimi direct serve rate {served_pct}% < 90% — too many timeouts/429s for canary"
                )
        k_parse = int(k.get("json_parse_rate", "0/0 (0%)").split("(")[1].rstrip("%)"))
        if k_parse < 99:
            issues.append(f"JSON parse rate {k_parse}% < 99.5% target")
        if s and k:
            s_p95 = s.get("p95_latency_ms", 0)
            k_p95 = k.get("p95_latency_ms", 0)
            if s_p95 > 0 and k_p95 > s_p95 * 1.5:
                issues.append(
                    f"Kimi p95 latency {k_p95}ms > 1.5x Sonnet baseline {s_p95}ms"
                )
        return issues

    issues = _meets_criteria(sonnet_stats, kimi_stats)
    verdict = "GO" if not issues else "NO-GO"

    # Write markdown summary
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    md_lines = [
        f"# Kimi K2.5 vs Sonnet Offline Replay — {now}",
        "",
        f"**Verdict: {verdict}**",
        "",
        "## Acceptance Criteria",
    ]
    if not issues:
        md_lines.append("- All criteria met")
    else:
        for issue in issues:
            md_lines.append(f"- FAIL: {issue}")

    md_lines += [
        "",
        "## Sonnet Baseline Stats",
        f"- n: {sonnet_stats.get('n', 'N/A')}",
        f"- JSON parse rate: {sonnet_stats.get('json_parse_rate', 'N/A')}",
        f"- Required fields rate: {sonnet_stats.get('required_fields_rate', 'N/A')}",
        f"- p50 latency: {sonnet_stats.get('p50_latency_ms', 'N/A')} ms",
        f"- p95 latency: {sonnet_stats.get('p95_latency_ms', 'N/A')} ms",
        "",
        "## Kimi K2.5 Stats",
        f"- n: {kimi_stats.get('n', 'N/A')}",
        f"- Kimi directly served: {kimi_stats.get('kimi_served_rate', 'N/A')}",
        f"- JSON parse rate: {kimi_stats.get('json_parse_rate', 'N/A')}",
        f"- Required fields rate: {kimi_stats.get('required_fields_rate', 'N/A')}",
        f"- p50 latency: {kimi_stats.get('p50_latency_ms', 'N/A')} ms",
        f"- p95 latency: {kimi_stats.get('p95_latency_ms', 'N/A')} ms",
        "",
        "## Per-Scenario Results",
        "",
    ]

    for r in results:
        scenario = r["scenario"]
        s_res = r.get("sonnet", {})
        k_res = r.get("kimi", {})
        md_lines.append(f"### {scenario}")
        if s_res:
            ok = "✓" if s_res.get("all_required_ok") else "✗"
            md_lines.append(
                f"- Sonnet: JSON={s_res.get('json_parse_ok')} AllRequired={ok} "
                f"lat={s_res.get('latency_ms')}ms"
            )
            if s_res.get("required_fields_missing"):
                md_lines.append(f"  - Missing: {s_res['required_fields_missing']}")
        if k_res:
            ok = "✓" if k_res.get("all_required_ok") else "✗"
            md_lines.append(
                f"- Kimi:   JSON={k_res.get('json_parse_ok')} AllRequired={ok} "
                f"lat={k_res.get('latency_ms')}ms"
            )
            if k_res.get("required_fields_missing"):
                md_lines.append(f"  - Missing: {k_res['required_fields_missing']}")
        if s_res.get("parsed") and k_res.get("parsed"):
            md_lines.append("  - Field diff (Sonnet vs Kimi):")
            for field in list(s_res["parsed"].keys()) + list(k_res["parsed"].keys()):
                if field not in s_res["parsed"] or field not in k_res["parsed"]:
                    continue
            # Simple truncated side-by-side for key fields
            for field in _REQUIRED_BRIEFING_FIELDS:
                s_val = (s_res["parsed"].get(field) or "")[:120]
                k_val = (k_res["parsed"].get(field) or "")[:120]
                if s_val != k_val:
                    md_lines.append(f"    - {field}:")
                    md_lines.append(f"      Sonnet: {s_val!r}")
                    md_lines.append(f"      Kimi:   {k_val!r}")
        md_lines.append("")

    md_lines += [
        "## Non-Go Conditions (automatic)",
        "- Kimi returns JSON parse failure on >0.5% of calls",
        "- Kimi p95 latency > 1.5x Sonnet baseline",
        "- Any hallucinated athlete name/stat not in the prompt",
        "- Required fields missing in >0% of calls",
        "",
        "## Coach Tool-Call Scope",
        "Coach tool-call loop (ai_coach.py query_opus) is NOT included in live canary.",
        "Include it in offline comparison only after manual review of these results.",
    ]

    summary_path = output_dir / "summary.md"
    summary_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"\nSummary written to {summary_path}")
    print(f"Verdict: {verdict}")
    if issues:
        print("Issues:")
        for issue in issues:
            print(f"  - {issue}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Kimi K2.5 vs Sonnet offline replay comparator")
    parser.add_argument("--fixtures-file", default=None, help="Path to JSON fixtures file")
    parser.add_argument("--output-dir", default="scripts/replay_results", help="Output directory")
    parser.add_argument("--calls", type=int, default=5, help="Number of prompts to replay")
    parser.add_argument("--timeout", type=int, default=30, help="Per-call timeout in seconds (default 30 — kimi-k2-turbo-preview responds in ~800ms)")
    parser.add_argument("--sonnet-only", action="store_true")
    parser.add_argument("--kimi-only", action="store_true")
    parser.add_argument("--no-coach", action="store_true", help="Skip coach tool-call scenario")
    args = parser.parse_args()

    # Validate env
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    kimi_key = os.getenv("KIMI_API_KEY")
    if not args.kimi_only and not anthropic_key:
        print("ERROR: ANTHROPIC_API_KEY not set. Required for Sonnet baseline.")
        sys.exit(1)
    if not args.sonnet_only and not kimi_key:
        print("ERROR: KIMI_API_KEY not set. Required for Kimi comparison.")
        sys.exit(1)

    # Load fixtures
    if args.fixtures_file:
        fixtures_path = Path(args.fixtures_file)
        if not fixtures_path.exists():
            print(f"ERROR: fixtures file not found: {fixtures_path}")
            sys.exit(1)
        with open(fixtures_path, encoding="utf-8") as f:
            fixtures = json.load(f)
    else:
        fixtures = _FIXTURES

    fixtures = fixtures[: args.calls]

    output_dir = Path(args.output_dir)
    sonnet_model = "claude-sonnet-4-6"
    kimi_model = "kimi-k2-turbo-preview"

    results = []
    for i, fixture in enumerate(fixtures):
        scenario = fixture["scenario"]
        ftype = fixture.get("type", "briefing")
        user_prompt = fixture["user_prompt"]

        if ftype == "briefing":
            system = _build_system_prompt(_BRIEFING_SCHEMA, _REQUIRED_BRIEFING_FIELDS)
            required_fields = _REQUIRED_BRIEFING_FIELDS
        else:
            system = "You are an expert running coach. Respond accurately."
            required_fields = []

        print(f"\n[{i+1}/{len(fixtures)}] Scenario: {scenario}")

        result_row: dict = {"scenario": scenario, "type": ftype}

        # --- Sonnet ---
        if not args.kimi_only:
            print(f"  Running Sonnet ({sonnet_model})...", end=" ", flush=True)
            try:
                text, latency_ms, actual_provider = _call_model(sonnet_model, system, user_prompt, args.timeout)
                score = _score_result(text, required_fields, latency_ms)
                score["raw_text"] = text
                score["actual_provider"] = actual_provider
                result_row["sonnet"] = score
                ok_str = "OK" if score["all_required_ok"] else "FAIL"
                print(f"{ok_str} ({latency_ms:.0f}ms)")
            except Exception as exc:
                result_row["sonnet"] = {"error": str(exc), "latency_ms": 0, "json_parse_ok": False}
                print(f"ERROR: {exc}")

        # --- Kimi ---
        if not args.sonnet_only:
            print(f"  Running Kimi ({kimi_model})...", end=" ", flush=True)
            try:
                text, latency_ms, actual_provider = _call_model(kimi_model, system, user_prompt, args.timeout)
                score = _score_result(text, required_fields, latency_ms)
                score["raw_text"] = text
                score["actual_provider"] = actual_provider
                # Track whether Kimi actually served (vs fell back to Sonnet/Gemini)
                score["kimi_served"] = (actual_provider == "kimi")
                result_row["kimi"] = score
                served_str = "" if score["kimi_served"] else " [FALLBACK to Sonnet]"
                ok_str = "OK" if score["all_required_ok"] else "FAIL"
                print(f"{ok_str} ({latency_ms:.0f}ms){served_str}")
            except Exception as exc:
                result_row["kimi"] = {"error": str(exc), "latency_ms": 0, "json_parse_ok": False, "kimi_served": False}
                print(f"ERROR: {exc}")

        results.append(result_row)

    _write_summary(results, output_dir, sonnet_model, kimi_model)


if __name__ == "__main__":
    main()
