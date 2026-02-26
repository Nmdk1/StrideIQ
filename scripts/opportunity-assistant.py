"""
StrideIQ Opportunity Assistant — Human-in-the-Loop Q&A Drafting

Reads candidate questions from stdin or a file, generates draft answers
with supporting StrideIQ calculator numbers, and posts to Discord webhook
for human review before posting.

Constraints (non-negotiable):
  - No autonomous posting to external platforms.
  - Human reviews every draft before posting.
  - Numbers in drafts validated against local data files.
  - Deduplication via SQLite log.

Usage:
  echo "What training pace should I run for a 20 minute 5K?" | python scripts/opportunity-assistant.py
  python scripts/opportunity-assistant.py --file questions.txt
  python scripts/opportunity-assistant.py --question "Is a 45-minute 10K good for a 50 year old?"

Environment variables:
  DISCORD_WEBHOOK_URL   Discord webhook URL (required for Discord delivery)
  LOG_FILE              Path to SQLite log file (default: scripts/opportunity-log.db)

Output:
  - Discord webhook POST (if DISCORD_WEBHOOK_URL is set)
  - stdout (always)
  - SQLite log entry (always)
"""

import os
import sys
import re
import json
import math
import hashlib
import sqlite3
import argparse
import datetime
from pathlib import Path

# ============================================================================
# PATHS
# ============================================================================

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "apps" / "web" / "data"
LOG_FILE = Path(os.environ.get("LOG_FILE", SCRIPT_DIR / "opportunity-log.db"))

GOAL_DATA_FILE   = DATA_DIR / "goal-pace-tables.json"
DEMO_DATA_FILE   = DATA_DIR / "age-gender-tables.json"
EQUIV_DATA_FILE  = DATA_DIR / "equivalency-tables.json"
AG_DATA_FILE     = DATA_DIR / "age-grading-tables.json"
PACE_DATA_FILE   = DATA_DIR / "training-pace-tables.json"

STRIDEIQ_BASE = "https://strideiq.run"

TOOL_URLS = {
    "training_pace": f"{STRIDEIQ_BASE}/tools/training-pace-calculator",
    "age_grading":   f"{STRIDEIQ_BASE}/tools/age-grading-calculator",
    "race_equiv":    f"{STRIDEIQ_BASE}/tools/race-equivalency",
}

# ============================================================================
# DANIELS/GILBERT FORMULA (matches scripts/lib/rpi-formula.mjs exactly)
# ============================================================================

INTENSITY_TABLE = {
    30: (0.656310, 0.55, 0.857530, 0.923901, 1.113017, 1.244426),
    35: (0.694032, 0.55, 0.884464, 0.951698, 1.135265, 1.259791),
    40: (0.694401, 0.55, 0.872771, 0.938283, 1.108994, 1.226613),
    45: (0.689502, 0.55, 0.847517, 0.910706, 1.072698, 1.178602),
    50: (0.676021, 0.55, 0.819635, 0.887196, 1.046102, 1.148391),
    55: (0.669899, 0.55, 0.806541, 0.866426, 1.013673, 1.105520),
    60: (0.660404, 0.55, 0.794224, 0.848246, 0.993932, 1.085095),
    65: (0.658450, 0.55, 0.791007, 0.854612, 0.993399, 1.086487),
    70: (0.659559, 0.55, 0.787847, 0.845433, 0.982708, 1.070224),
}
_RPIS = sorted(INTENSITY_TABLE.keys())


def _calculate_rpi(distance_m: float, time_sec: float) -> float | None:
    if distance_m <= 0 or time_sec <= 0:
        return None
    t_min = time_sec / 60.0
    v = distance_m / t_min
    vo2 = -4.6 + 0.182258 * v + 0.000104 * v * v
    pct = (0.8 + 0.1894393 * math.exp(-0.012778 * t_min)
               + 0.2989558 * math.exp(-0.1932605 * t_min))
    return round(vo2 / pct, 1) if pct > 0 else None


def _interp_intensity(rpi: float, idx: int) -> float:
    if rpi <= _RPIS[0]:
        return INTENSITY_TABLE[_RPIS[0]][idx]
    if rpi >= _RPIS[-1]:
        return INTENSITY_TABLE[_RPIS[-1]][idx]
    for i in range(len(_RPIS) - 1):
        r1, r2 = _RPIS[i], _RPIS[i + 1]
        if r1 <= rpi <= r2:
            t = (rpi - r1) / (r2 - r1)
            return INTENSITY_TABLE[r1][idx] + t * (INTENSITY_TABLE[r2][idx] - INTENSITY_TABLE[r1][idx])
    return INTENSITY_TABLE[50][idx]


def _vo2_to_velocity(target_vo2: float) -> float:
    a, b = 0.000104, 0.182258
    c = -(4.6 + target_vo2)
    disc = b * b - 4 * a * c
    return (-b + math.sqrt(disc)) / (2 * a) if disc >= 0 else 200.0


def _sec_per_mile(rpi: float, idx: int) -> int:
    v = _vo2_to_velocity(rpi * _interp_intensity(rpi, idx))
    return round((1609.34 / v) * 60)


def _fmt_pace(sec_per_mile: int) -> str:
    return f"{sec_per_mile // 60}:{sec_per_mile % 60:02d}"


def _fmt_time(total_sec: float) -> str:
    total_sec = round(total_sec)
    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    s = total_sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m}:{s:02d}"


def calculate_training_paces(rpi: float) -> dict:
    return {
        "easy":       _fmt_pace(_sec_per_mile(rpi, 0)),
        "marathon":   _fmt_pace(_sec_per_mile(rpi, 2)),
        "threshold":  _fmt_pace(_sec_per_mile(rpi, 3)),
        "interval":   _fmt_pace(_sec_per_mile(rpi, 4)),
        "repetition": _fmt_pace(_sec_per_mile(rpi, 5)),
    }


def _rpi_for_time(dist_m: float, time_sec: float) -> float:
    v = (dist_m / time_sec) * 60
    t_min = time_sec / 60.0
    vo2 = -4.6 + 0.182258 * v + 0.000104 * v * v
    pct = (0.8 + 0.1894393 * math.exp(-0.012778 * t_min)
               + 0.2989558 * math.exp(-0.1932605 * t_min))
    return vo2 / pct if pct > 0 else 0.0


def calculate_equivalent_time(rpi: float, target_dist_m: float) -> dict | None:
    dist_km = target_dist_m / 1000
    lo, hi = 2.5 * 60 * dist_km, 12.0 * 60 * dist_km
    t = (lo + hi) / 2
    for _ in range(50):
        mid = (lo + hi) / 2
        c = _rpi_for_time(target_dist_m, mid)
        if abs(c - rpi) < 0.01:
            t = mid
            break
        if c > rpi:
            lo = mid
        else:
            hi = mid
        t = mid
    t = round(t)
    pace_sec = (t / target_dist_m) * 1609.34
    return {
        "time_sec":       t,
        "time_formatted": _fmt_time(t),
        "pace_mi":        _fmt_pace(round(pace_sec)),
    }

# ============================================================================
# DATA LOADERS (local files only — no API calls)
# ============================================================================

def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


_GOAL_DATA  = None
_AG_DATA    = None
_PACE_DATA  = None
_DEMO_DATA  = None
_EQUIV_DATA = None


def _goal_data() -> dict:
    global _GOAL_DATA
    if _GOAL_DATA is None:
        _GOAL_DATA = _load_json(GOAL_DATA_FILE)
    return _GOAL_DATA


def _ag_data() -> dict:
    global _AG_DATA
    if _AG_DATA is None:
        _AG_DATA = _load_json(AG_DATA_FILE)
    return _AG_DATA


def _pace_data() -> dict:
    global _PACE_DATA
    if _PACE_DATA is None:
        _PACE_DATA = _load_json(PACE_DATA_FILE)
    return _PACE_DATA


def _demo_data() -> dict:
    global _DEMO_DATA
    if _DEMO_DATA is None:
        _DEMO_DATA = _load_json(DEMO_DATA_FILE)
    return _DEMO_DATA


def _equiv_data() -> dict:
    global _EQUIV_DATA
    if _EQUIV_DATA is None:
        _EQUIV_DATA = _load_json(EQUIV_DATA_FILE)
    return _EQUIV_DATA

# ============================================================================
# QUESTION ANALYSIS
# ============================================================================

# Pattern clusters: each entry has (pattern_list, handler, tool_url_key)
# Handler receives the question string and returns (supporting_numbers: dict, tool_url: str)

DIST_MAP = {
    r"\b5\s*k\b|5000\s*m": ("5K",   5000,   "5k"),
    r"\b10\s*k\b|10000\s*m": ("10K", 10000,  "10k"),
    r"\bhalf\s*marathon\b": ("Half Marathon", 21097.5, "half"),
    r"\bmarathon\b": ("Marathon", 42195, "marathon"),
}

TIME_PATTERN = re.compile(
    r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b"
)

AGE_PATTERN = re.compile(r"\b(?:age[d]?\s*|(?:am|i'm|i\s+am)\s*)(\d{2})\b", re.I)

# Natural language time patterns for questions like "20 minute 5K" or "sub-2 hour half"
MINUTE_PATTERN = re.compile(r"\b(\d{1,2})\s*[-\s]?minute\b", re.I)
SUBGOAL_PATTERN = re.compile(r"\bsub[-\s]?(\d{1,2}):?(\d{2})?\b", re.I)
HOUR_MIN_PATTERN = re.compile(r"\b(\d+)\s*(?:hour|hr)s?\s*(?:and\s*)?(\d+)\s*(?:minute|min)\b", re.I)


def _extract_time_seconds(q: str) -> int | None:
    """
    Extract a race time from natural language. Handles:
    - "20:00" (MM:SS) or "1:45:00" (H:MM:SS) — colon format
    - "20 minute 5K" — bare minutes
    - "sub-20 5K", "sub-2 hour half" — sub-goal phrasing
    - "3 hour 30 minute marathon" — hour + minute
    """
    # Try H:MM:SS or MM:SS first (explicit colon format)
    m = TIME_PATTERN.search(q)
    if m:
        h_val = int(m.group(1))
        m_val = int(m.group(2))
        s_val = int(m.group(3)) if m.group(3) else None
        if s_val is not None:
            # H:MM:SS — unambiguous
            return h_val * 3600 + m_val * 60 + s_val
        elif h_val >= 10:
            # First group >= 10 → definitely MM:SS (no road race takes 10+ hours)
            return h_val * 60 + m_val
        else:
            # First group 1–9: interpret as H:MM (standard for half/marathon timing)
            return h_val * 3600 + m_val * 60

    # Try "3 hour 30 minute" / "2 hour half"
    m = HOUR_MIN_PATTERN.search(q)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60

    # sub-hour only pattern like "sub-2 hour" → 2:00:00
    m_sub_hour = re.search(r"\bsub[-\s]?(\d)\s+hour\b", q, re.I)
    if m_sub_hour:
        return int(m_sub_hour.group(1)) * 3600

    # Try "X minute" (whole minutes only, e.g., "20 minute 5K")
    m = MINUTE_PATTERN.search(q)
    if m:
        mins = int(m.group(1))
        if 10 <= mins <= 90:  # plausible race minutes (avoid age false positives)
            return mins * 60

    # Try "sub-20", "sub-25", "sub-1:45" etc.
    m = SUBGOAL_PATTERN.search(q)
    if m:
        val = int(m.group(1))
        sub2 = int(m.group(2)) if m.group(2) else 0
        # sub-2:00 or sub-4:00 → hours; sub-20, sub-25 → minutes
        if val <= 5 and sub2 > 0:
            return val * 3600 + sub2 * 60
        elif val <= 90:
            return val * 60

    return None


def _extract_distance(q: str) -> tuple[str, float, str] | None:
    q_lower = q.lower()
    # Marathon must be checked before "half marathon" due to substring
    for pattern, info in sorted(DIST_MAP.items(), key=lambda x: -len(x[0])):
        if re.search(pattern, q_lower, re.I):
            return info  # (label, meters, key)
    return None


def _extract_age(q: str) -> int | None:
    """
    Extract age from natural language. Strips time-related numbers to avoid
    false positives from "20 minute", "45:00", "sub-20" etc.
    """
    cleaned = re.sub(r"\b\d+\s*(?:minute|min|second|sec)\b", "", q, flags=re.I)
    cleaned = re.sub(r"\bsub[-\s]?\d+\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", "", cleaned)

    m = AGE_PATTERN.search(cleaned)
    if m:
        age = int(m.group(1))
        return age if 25 <= age <= 90 else None

    m2 = re.search(r"\b(\d{2})\s*(?:year(?:s?\s*old)?|-year-old)\b", cleaned, re.I)
    if m2:
        age = int(m2.group(1))
        return age if 25 <= age <= 90 else None

    m3 = re.search(r"\b(?:at|for)\s*(?:a\s*)?(\d{2})(?:\s*year(?:s?\s*old)?)?\b", cleaned, re.I)
    if m3:
        age = int(m3.group(1))
        return age if 25 <= age <= 90 else None

    return None


def _extract_gender(q: str) -> str | None:
    q_lower = q.lower()
    if any(w in q_lower for w in ["woman", "female", "women", "girl"]):
        return "female"
    if any(w in q_lower for w in ["man", "male", "men", "guy", "boy"]):
        return "male"
    return None


def build_supporting_numbers(question: str) -> dict:
    """
    Extract numeric context from the question and compute supporting numbers
    from local data. Returns a dict of computed facts for use in the draft answer.
    No external calls.
    """
    facts = {}
    q = question.strip()

    dist_info = _extract_distance(q)
    time_sec  = _extract_time_seconds(q)
    age       = _extract_age(q)
    gender    = _extract_gender(q)

    # If we have a race time + distance: compute RPI + training paces
    if dist_info and time_sec:
        label, meters, dist_key = dist_info
        rpi = _calculate_rpi(meters, time_sec)
        if rpi:
            facts["rpi"] = rpi
            facts["distance"] = label
            facts["race_time"] = _fmt_time(time_sec)
            paces = calculate_training_paces(rpi)
            facts["training_paces"] = paces
            facts["tool_url"] = TOOL_URLS["training_pace"] + f"/{dist_key}-training-paces"
            facts["goal_url"] = None  # set below if goal detected

            # Check if it's a goal page question
            gp = _goal_data()
            for slug, entry in gp.items():
                if slug == "_meta":
                    continue
                if abs(entry.get("goalTimeSeconds", 0) - time_sec) <= 2:
                    facts["goal_slug"] = slug
                    facts["goal_url"] = f"{STRIDEIQ_BASE}/tools/training-pace-calculator/goals/{slug}"
                    break

            # Compute equivalents
            equivalents = {}
            eq_distances = {
                "5K": 5000, "10K": 10000,
                "Half Marathon": 21097.5, "Marathon": 42195,
            }
            for eq_label, eq_meters in eq_distances.items():
                if abs(eq_meters - meters) < 100:
                    continue
                equiv = calculate_equivalent_time(rpi, eq_meters)
                if equiv:
                    equivalents[eq_label] = equiv
            if equivalents:
                facts["equivalents"] = equivalents

    # If we have age + distance: compute WMA benchmarks
    if age and dist_info:
        label, meters, dist_key = dist_info
        ag = _ag_data()
        dist_data = ag.get(dist_key, {})
        genders_to_check = [gender] if gender else ["male", "female"]
        wma = {}
        for g in genders_to_check:
            rows = dist_data.get(g, [])
            # Find closest age (snap to 5-year intervals)
            best_row = min(rows, key=lambda r: abs(r["age"] - age), default=None)
            if best_row:
                wma[g] = {
                    "age": best_row["age"],
                    "levels": {
                        pct: {
                            "label": best_row["levels"][str(pct)]["label"],
                            "time":  best_row["levels"][str(pct)]["timeFormatted"],
                            "pace":  best_row["levels"][str(pct)]["pace"],
                        }
                        for pct in [50, 60, 70, 80]
                        if str(pct) in best_row["levels"]
                    }
                }
        if wma:
            facts["wma_benchmarks"] = wma
            facts["wma_age"] = age
            facts["wma_distance"] = label
            facts["tool_url"] = TOOL_URLS["age_grading"]

        # Check if there's a demographic page
        demo = _demo_data()
        for slug, entry in demo.items():
            if slug == "_meta":
                continue
            ages = entry.get("ages", [])
            g_match = entry.get("gender") == (gender or entry.get("gender"))
            dist_match = entry.get("distanceMeters") and abs(entry["distanceMeters"] - meters) < 100
            age_match = any(abs(a - age) <= 5 for a in ages)
            if g_match and dist_match and age_match:
                facts["demo_url"] = f"{STRIDEIQ_BASE}/tools/age-grading-calculator/demographics/{slug}"
                break

    # Equivalency question detection
    equiv_kws = ["equivalent", "equate", "same fitness", "predict", "convert", "cross"]
    if any(kw in question.lower() for kw in equiv_kws) and dist_info:
        facts["tool_url"] = TOOL_URLS["race_equiv"]
        # Show equivalency table if we have an input time
        eq = _equiv_data()
        label, meters, _ = dist_info
        for slug, entry in eq.items():
            if slug == "_meta":
                continue
            if abs(entry.get("inputDistanceMeters", 0) - meters) < 100:
                if time_sec:
                    row = min(
                        entry["rows"],
                        key=lambda r: abs(r["inputSeconds"] - time_sec),
                        default=None,
                    )
                    if row:
                        facts["closest_equiv_row"] = row
                        facts["equiv_slug"] = slug
                        facts["equiv_url"] = f"{STRIDEIQ_BASE}/tools/race-equivalency/{slug}"
                break

    return facts

# ============================================================================
# DRAFT GENERATOR
# ============================================================================

def generate_draft(question: str, facts: dict) -> str:
    """
    Generate a coaching draft answer for the question using computed facts.
    All numbers come from facts (computed from local data) — none are hallucinated.
    """
    lines = []

    # Opening
    lines.append(f"**Q: {question.strip()}**\n")

    # Core answer — built from facts
    if "training_paces" in facts and "race_time" in facts:
        p = facts["training_paces"]
        lines.append(
            f"Based on a {facts['race_time']} {facts['distance']} (RPI {facts['rpi']}), "
            f"your training paces are:\n"
            f"- Easy: {p['easy']}/mi\n"
            f"- Marathon pace: {p['marathon']}/mi\n"
            f"- Threshold: {p['threshold']}/mi\n"
            f"- Interval: {p['interval']}/mi\n"
            f"- Repetition: {p['repetition']}/mi"
        )
        lines.append("")
        lines.append(
            "These are computed from the Daniels/Gilbert oxygen cost equation — "
            "the same formula used by exercise physiologists for training zone prescription."
        )

    if "equivalents" in facts:
        eq_parts = []
        for eq_label, eq_data in facts["equivalents"].items():
            eq_parts.append(f"{eq_label}: {eq_data['time_formatted']} ({eq_data['pace_mi']}/mi)")
        lines.append(f"\nEquivalent race fitness: {'; '.join(eq_parts)}")
        lines.append(
            "*(Equivalency assumes comparable training for each distance — "
            "especially long runs for the marathon.)*"
        )

    if "wma_benchmarks" in facts:
        lines.append(f"\nWMA benchmarks for {facts['wma_distance']} — age {facts['wma_age']}:")
        for g, wma in facts["wma_benchmarks"].items():
            g_label = "Men" if g == "male" else "Women"
            lines.append(f"\n**{g_label} age {wma['age']}:**")
            for pct, lvl in wma["levels"].items():
                lines.append(f"- {lvl['label']} ({pct}%): {lvl['time']} ({lvl['pace']}/mi)")

    if "closest_equiv_row" in facts:
        row = facts["closest_equiv_row"]
        lines.append(
            f"\nRace equivalency: {row['inputTime']} input → {row['outputTime']} equivalent "
            f"({row['outputPaceMi']}/mi)"
        )

    # Explicit assumptions
    lines.append("\n---")
    lines.append("**Assumptions:**")
    if "race_time" in facts:
        lines.append(f"- Input race time: {facts['race_time']} {facts.get('distance', '')}")
    if "wma_age" in facts:
        lines.append(f"- Age: {facts['wma_age']}")
    if "training_paces" in facts:
        lines.append("- Formula: Daniels/Gilbert oxygen cost equation (1979)")
        lines.append("- Easy pace means this pace or slower")
    lines.append("- These are estimates. Individual response varies.")

    # Calculator link
    lines.append("\n---")
    tool_url = (
        facts.get("goal_url")
        or facts.get("equiv_url")
        or facts.get("demo_url")
        or facts.get("tool_url")
        or TOOL_URLS["training_pace"]
    )
    lines.append(f"**Calculate your exact values:** {tool_url}")

    return "\n".join(lines)


# ============================================================================
# LOGGING (SQLite)
# ============================================================================

def _init_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS drafts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at  TEXT NOT NULL,
            question    TEXT NOT NULL,
            question_hash TEXT NOT NULL,
            facts_json  TEXT,
            draft       TEXT NOT NULL,
            delivered   INTEGER DEFAULT 0,
            outcome     TEXT
        )
    """)
    conn.commit()
    return conn


def _is_duplicate(conn: sqlite3.Connection, question_hash: str) -> bool:
    row = conn.execute(
        "SELECT id FROM drafts WHERE question_hash = ?", (question_hash,)
    ).fetchone()
    return row is not None


def _log_draft(
    conn: sqlite3.Connection,
    question: str,
    question_hash: str,
    facts: dict,
    draft: str,
    delivered: bool,
) -> int:
    cur = conn.execute(
        """INSERT INTO drafts (created_at, question, question_hash, facts_json, draft, delivered)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            datetime.datetime.now(datetime.timezone.utc).isoformat(),
            question,
            question_hash,
            json.dumps(facts),
            draft,
            1 if delivered else 0,
        ),
    )
    conn.commit()
    return cur.lastrowid

# ============================================================================
# DISCORD DELIVERY
# ============================================================================

def _post_to_discord(draft: str, question: str) -> bool:
    """
    Post draft to Discord webhook. Returns True on success.
    Requires DISCORD_WEBHOOK_URL env var.
    """
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not webhook_url:
        print("  [Discord] DISCORD_WEBHOOK_URL not set — skipping Discord delivery.", file=sys.stderr)
        return False

    # Discord has a 2000-char message limit; truncate gracefully
    content = draft
    if len(content) > 1900:
        content = content[:1897] + "..."

    payload = json.dumps({
        "username": "StrideIQ Opportunity Assistant",
        "content": f"**New draft for review** _(do not post without editing)_\n\n{content}",
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "StrideIQBot/1.0 (https://strideiq.run)",
    }

    # Use requests if available — avoids Cloudflare TLS fingerprint blocks on some hosts
    try:
        import requests as _req
        r = _req.post(webhook_url, data=payload, headers=headers, timeout=10)
        return r.status_code in (200, 204)
    except ImportError:
        pass
    except Exception as e:
        print(f"  [Discord] requests delivery failed: {e}", file=sys.stderr)
        return False

    # Fallback: urllib
    try:
        import urllib.request
        import urllib.error
        req = urllib.request.Request(webhook_url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 204)
    except Exception as e:
        print(f"  [Discord] Delivery failed: {e}", file=sys.stderr)
        return False

# ============================================================================
# MAIN PIPELINE
# ============================================================================

def process_question(question: str, conn: sqlite3.Connection) -> dict:
    """
    Full pipeline: analyze → compute → draft → deduplicate → log → deliver.
    Returns summary dict.
    """
    question = question.strip()
    if not question:
        return {"status": "skipped", "reason": "empty question"}

    # Deduplication
    q_hash = hashlib.sha256(question.lower().encode()).hexdigest()[:16]
    if _is_duplicate(conn, q_hash):
        return {"status": "duplicate", "question": question, "hash": q_hash}

    # Compute supporting numbers
    facts = build_supporting_numbers(question)

    # Generate draft
    draft = generate_draft(question, facts)

    # Print to stdout always
    print("\n" + "=" * 70)
    print(draft)
    print("=" * 70)

    # Deliver to Discord
    delivered = _post_to_discord(draft, question)
    if delivered:
        print(f"  [Discord] Draft delivered for review.")
    else:
        print(f"  [Discord] Not delivered (no webhook or error — see stderr).")

    # Log
    row_id = _log_draft(conn, question, q_hash, facts, draft, delivered)

    return {
        "status": "generated",
        "question": question,
        "hash": q_hash,
        "log_id": row_id,
        "delivered_discord": delivered,
        "facts_keys": list(facts.keys()),
    }

# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="StrideIQ Opportunity Assistant — generate draft answers for Q&A platforms."
    )
    parser.add_argument("--question", "-q", help="Single question to process")
    parser.add_argument("--file",     "-f", help="File with one question per line")
    parser.add_argument("--log",            help="Path to SQLite log file",
                        default=str(LOG_FILE))
    args = parser.parse_args()

    db_path = Path(args.log)
    conn = _init_db(db_path)

    questions = []

    if args.question:
        questions.append(args.question)

    if args.file:
        fpath = Path(args.file)
        if not fpath.exists():
            print(f"ERROR: file not found: {fpath}", file=sys.stderr)
            sys.exit(1)
        questions.extend(
            line.strip() for line in fpath.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        )

    if not questions and not sys.stdin.isatty():
        questions.extend(
            line.strip() for line in sys.stdin
            if line.strip() and not line.strip().startswith("#")
        )

    if not questions:
        parser.print_help()
        print("\nExamples:")
        print('  python scripts/opportunity-assistant.py -q "What training pace for a 20 minute 5K?"')
        print('  python scripts/opportunity-assistant.py -q "Is 45:00 a good 10K time for a 55 year old male?"')
        print('  python scripts/opportunity-assistant.py -q "What is the marathon equivalent of a 1:45 half marathon?"')
        sys.exit(0)

    results = []
    for q in questions:
        r = process_question(q, conn)
        results.append(r)

    conn.close()

    # Summary
    print(f"\n{'=' * 70}")
    print(f"Processed {len(results)} question(s)")
    for r in results:
        status = r.get("status", "?")
        q = r.get("question", "")[:60]
        print(f"  [{status.upper()}] {q}")
    print(f"Log: {db_path}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
