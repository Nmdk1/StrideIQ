"""
Clone a real athlete's data into a demo athlete account.

Why this exists:
- The founder needs a navigable demo account loaded with real data so a
  race director can click through StrideIQ exactly the way an athlete
  would, without being able to mutate the founder's actual data or
  link real provider accounts.
- The standalone provision script generates synthetic runs only. This
  script copies the real history (activities, plans, nutrition,
  findings, calibration, recovery) into a demo target.

Safety guarantees:
- The target athlete MUST already exist and have is_demo=True. Refuses
  otherwise. Use scripts/provision_demo_athlete.py to create it first.
- The source athlete MUST NOT be a demo athlete (no demo-on-demo).
- Sensitive tables are explicitly skipped: OAuth tokens (handled at
  Athlete copy), billing (subscription/purchase/stripe), audit logs,
  ingestion telemetry, photos.
- Athlete row provider tokens and connection state are zeroed on the
  demo target to make connect attempts visibly disabled.
- Unknown athlete-scoped tables (added since this script was last
  updated) cause a hard fail. Update COPY_TABLES / SKIP_TABLES to
  classify them deliberately.
- Dry-run by default. Use --commit to persist.
- One transaction; on any error the whole copy rolls back.

Usage (inside api container):
  python scripts/clone_athlete_to_demo.py \
      --source-email "$SOURCE_EMAIL" \
      --demo-email "$DEMO_EMAIL" \
      --through-date 2026-04-15            # optional, defaults to yesterday UTC
  # Add --commit to persist (default is dry-run).
  # Email addresses are intentionally read from env/args (never hardcoded
  # in this file) so scripts/test_scripts_hygiene.py stays green.

Post-clone:
  Invalidate Redis briefing cache for the demo athlete so the next
  /home view triggers a fresh K2.5 generation against the cloned
  data. The script does this automatically when --commit is set.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from core.database import Base, SessionLocal
from models import Activity, Athlete


logger = logging.getLogger("clone_athlete_to_demo")


# ---------------------------------------------------------------------------
# Table classification
#
# COPY_TABLES: tables whose rows are copied for the source athlete. Each
#   entry says (a) whether new primary keys must be tracked so child rows
#   can remap their FKs, (b) any extra FKs (besides athlete_id) that
#   reference another copied table and need remapping.
#
# SKIP_TABLES: explicitly excluded for security/relevance reasons.
#
# Tables not in either set cause a hard fail (forces the developer to
# decide where new athlete-scoped models belong).
# ---------------------------------------------------------------------------

# (table_name, dict)
# track_pk: bool — record old_id -> new_id for FK remapping by children
# extra_remap: dict[str, str] — column_name -> source_table_name in COPY_TABLES
# date_filter_col: str | None — restrict to rows on/before through_date
COPY_TABLES: Dict[str, Dict[str, Any]] = {
    # --- Athlete-scoped parents whose IDs are referenced elsewhere ---
    # Activity has unique (provider, external_activity_id) and
    # (athlete_id, garmin_activity_id) constraints. Prefix external IDs
    # with "demo-" on copy so the demo's rows can coexist alongside the
    # source athlete's rows in the same DB.
    "activity":                 {
        "track_pk": True,
        "date_filter_col": "start_time",
        # Activity has UNIQUE(provider, external_activity_id). Prefix with
        # "demo-" so the demo can carry rows with the same provider as
        # the source athlete. garmin_activity_id is a bigint with no
        # unique constraint, so it's fine to leave alone.
        "prefix_fields": ("external_activity_id",),
    },
    "training_plan":            {"track_pk": True},
    "meal_template":            {"track_pk": True},
    "correlation_finding":      {"track_pk": True},

    # --- Activity-scoped children ---
    "activity_split":           {"extra_remap": {"activity_id": "activity"}, "skip_if_no_parent": True},
    "activity_stream":          {"extra_remap": {"activity_id": "activity"}, "skip_if_no_parent": True},
    "cached_stream_analysis":   {"extra_remap": {"activity_id": "activity"}, "skip_if_no_parent": True},
    "activity_reflection":      {"extra_remap": {"activity_id": "activity"}, "skip_if_no_parent": True},
    "activity_feedback":        {"extra_remap": {"activity_id": "activity"}, "skip_if_no_parent": True},
    "strength_exercise_set":    {"extra_remap": {"activity_id": "activity"}, "skip_if_no_parent": True},
    "personal_best":            {"extra_remap": {"activity_id": "activity"}, "skip_if_no_parent": True},
    "best_effort":              {"extra_remap": {"activity_id": "activity"}, "skip_if_no_parent": True},
    "performance_event":        {"extra_remap": {"activity_id": "activity"}, "skip_if_no_parent": True},

    # --- Plan-scoped children ---
    "planned_workout":          {"extra_remap": {"plan_id": "training_plan", "completed_activity_id": "activity"}},
    "plan_modification_log":    {"extra_remap": {"plan_id": "training_plan"}},
    "plan_adaptation_proposal": {"extra_remap": {"plan_id": "training_plan"}},
    "plan_preview":             {"extra_remap": {"promoted_plan_id": "training_plan"}},
    "training_availability":    {},
    "calendar_note":            {"extra_remap": {"activity_id": "activity"}},
    "calendar_insight":         {"extra_remap": {"activity_id": "activity"}},
    "workout_selection_audit_event": {"extra_remap": {"plan_id": "training_plan"}},

    # --- Profile / calibration ---
    "athlete_fueling_profile":      {},
    "athlete_race_result_anchor":   {},
    "athlete_training_pace_profile": {},
    "athlete_goal":                 {},
    "athlete_calibrated_model":     {},
    "athlete_workout_response":     {},
    "athlete_override":             {},
    "athlete_learning":             {},
    "athlete_adaptation_thresholds": {},
    "athlete_fact":                 {},
    "athlete_route":                {},
    "training_block":               {},

    # --- Recovery / health ---
    "daily_checkin":      {"date_filter_col": "checkin_date"},
    "body_composition":   {"date_filter_col": "measured_at"},
    "work_pattern":       {},
    "intake_questionnaire": {},
    "daily_readiness":    {"date_filter_col": "readiness_date"},
    "garmin_day":         {"date_filter_col": "day"},

    # --- Nutrition ---
    "nutrition_goal":            {},
    "nutrition_entry":           {"extra_remap": {"activity_id": "activity"}, "date_filter_col": "consumed_at"},
    "athlete_food_override":     {},

    # --- Intelligence / findings ---
    "fingerprint_finding":             {},
    "insight_feedback":                {},
    "threshold_calibration_log":       {},
    "self_regulation_log":             {},
    "insight_log":                     {},
    "narration_log":                   {},
    "narrative_feedback":              {},
    "correlation_mediator":            {"extra_remap": {"finding_id": "correlation_finding"}},
    "auto_discovery_run":              {},
    "auto_discovery_experiment":       {},
    "auto_discovery_candidate":        {},
    "auto_discovery_review_log":       {},
    "n1_insight_suppression":          {},

    # --- Coach state ---
    "coaching_recommendation":  {},
    "coach_chat":               {"extra_remap": {"context_plan_id": "training_plan"}},
    "coach_intent_snapshot":    {},
    "coach_usage":              {},

    # --- Strength v1 (athlete-curated training data) ---
    # All three are athlete-entered, no tokens, no PII beyond what the
    # demo already exposes (training history, body composition, etc.).
    # Copying them keeps the demo experience honest — a real athlete's
    # routines, goals, and reported niggles are part of the N=1 picture.
    "strength_routine":      {},
    "strength_goal":         {},
    "body_area_symptom_log": {"date_filter_col": "started_at"},
    # Note: coach_briefing AND coach_briefing_input intentionally NOT
    # copied — see SKIP_TABLES. We want fresh K2.5 generation against the
    # cloned data on first /home view, and the input audit row without
    # its briefing is meaningless.
}


SKIP_TABLES: Dict[str, str] = {
    # --- Billing ---
    "subscriptions":   "billing — exposing customer/subscription IDs is unsafe",
    "purchase":        "billing",
    "plan_purchases":  "billing",
    "stripe_events":   "billing webhook events",
    "race_promo_code": "promo codes scoped to billing",

    # --- Audit / consent / telemetry ---
    "consent_audit_log":    "audit trail; leaks IPs and consent timing",
    "admin_audit_event":    "admin audit trail",
    "invite_audit_event":   "invite audit trail",
    "page_view":            "navigation telemetry; leaks IPs",
    "tool_telemetry_event": "feature usage telemetry; leaks IPs",
    "experience_audit_log": "audit trail",

    # --- Provider sync state (would point at real Garmin/Strava tokens) ---
    "athlete_ingestion_state":  "provider sync state; not relevant for demo",
    "athlete_data_import_job":  "provider import jobs; not relevant for demo",

    # --- PII / media ---
    "athlete_photo":   "real face photos; PII",
    "runtoon_image":   "AI images tied to specific real activities; regenerated on demand",

    # --- Coach output cache (regen on first /home view) ---
    "coach_briefing":        "regenerate against cloned data so demo gets a fresh briefing",
    "coach_briefing_input":  "audit row for coach_briefing; pointless without the briefing it describes",

    # --- Configuration / global lookup tables ---
    "athlete_investigation_config": "global config, not athlete-scoped data",

    # --- Intentional regen / not-needed for demo surfaces ---
    "auto_discovery_change_log":   "internal R&D ledger; not surfaced in product",
    "auto_discovery_scan_coverage": "internal R&D scan coverage; not surfaced in product",
    "coach_action_proposals":      "transient agent proposals; regen on demand",
    "recommendation_outcome":      "feedback ledger on recommendations; not relevant for demo",
}


# ---------------------------------------------------------------------------
# Discovery + validation
# ---------------------------------------------------------------------------

def _discover_athlete_scoped_tables() -> Set[str]:
    """All tables in Base.metadata with an athlete_id column."""
    tables: Set[str] = set()
    for table in Base.metadata.tables.values():
        cols = {c.name for c in table.columns}
        if "athlete_id" in cols and table.name != "athlete":
            tables.add(table.name)
    return tables


def _validate_classification() -> List[str]:
    """Returns a list of unclassified athlete-scoped tables (empty == OK)."""
    discovered = _discover_athlete_scoped_tables()
    classified = set(COPY_TABLES.keys()) | set(SKIP_TABLES.keys())
    return sorted(discovered - classified)


# ---------------------------------------------------------------------------
# Athlete copy / wipe helpers
# ---------------------------------------------------------------------------

# Athlete fields we deliberately overwrite on the demo target so it cannot
# leak personal info or initiate provider connects.
_DEMO_ATHLETE_OVERRIDES = {
    "is_demo": True,
    # Provider tokens / linkage — wipe so connect buttons fail safely.
    "strava_access_token": None,
    "strava_refresh_token": None,
    "strava_token_expires_at": None,
    "strava_athlete_id": None,
    "garmin_access_token": None,
    "garmin_refresh_token": None,
    "garmin_token_expires_at": None,
    "garmin_user_id": None,
    "garmin_connected": False,
    "last_garmin_sync": None,
}

# Athlete fields we DO copy from source so the demo feels like a real
# athlete (calibrated thresholds, units, profile data). Anything not
# listed below stays at the demo athlete's existing value — including
# email, password_hash, role, is_demo, display_name.
_ATHLETE_FIELDS_TO_COPY = {
    "max_hr",
    "resting_hr",
    "threshold_hr",
    "threshold_pace_per_km",
    "preferred_units",
    "timezone",
    "date_of_birth",
    "gender",
    "weight_kg",
    "height_cm",
    "city",
    "state",
    "country",
    "primary_sport",
    "experience_level",
    "weekly_volume_km",
    "longest_recent_run_km",
    "subscription_tier",
    "onboarding_completed",
    "preferred_long_run_day",
    "vo2max",
    "lactate_threshold_pace",
    "running_economy",
}


def _copy_athlete_profile_fields(source: Athlete, demo: Athlete) -> List[str]:
    copied: List[str] = []
    for field in _ATHLETE_FIELDS_TO_COPY:
        if not hasattr(source, field):
            continue
        if not hasattr(demo, field):
            continue
        new_val = getattr(source, field)
        if new_val is None:
            continue
        setattr(demo, field, new_val)
        copied.append(field)

    # Always re-apply the demo overrides last so nothing copied above
    # accidentally re-enables provider linkage.
    for field, value in _DEMO_ATHLETE_OVERRIDES.items():
        if hasattr(demo, field):
            setattr(demo, field, value)
    return copied


def _existing_tables(db: Session) -> Set[str]:
    """Set of table names that actually exist in the connected database.

    Some declared models haven't reached prod yet via Alembic. We must
    skip those silently rather than crash on UndefinedTable.
    """
    rows = db.execute(text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = current_schema()"
    )).all()
    return {row[0] for row in rows}


def _existing_columns(db: Session, table_name: str) -> Set[str]:
    rows = db.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = current_schema() AND table_name = :t"
    ), {"t": table_name}).all()
    return {row[0] for row in rows}


def _wipe_demo_data(db: Session, demo_id: uuid.UUID) -> Dict[str, int]:
    """
    Wipe all rows owned by the demo athlete across COPY_TABLES, in
    reverse-dependency order. Idempotency: re-running the script
    produces the same end state.

    Tables that have only activity_id (no athlete_id) get scoped via
    a subquery on Activity.athlete_id == demo_id.
    """
    counts: Dict[str, int] = {}
    live_tables = _existing_tables(db)

    activity_id_subq = (
        f"SELECT id FROM activity WHERE athlete_id = '{demo_id}'"
    )
    plan_id_subq = (
        f"SELECT id FROM training_plan WHERE athlete_id = '{demo_id}'"
    )
    finding_id_subq = (
        f"SELECT id FROM correlation_finding WHERE athlete_id = '{demo_id}'"
    )

    # Reverse dependency order: children first, then parents.
    delete_order: List[Tuple[str, str]] = [
        # Activity children
        ("activity_split",          f"activity_id IN ({activity_id_subq})"),
        ("activity_stream",         f"activity_id IN ({activity_id_subq})"),
        ("cached_stream_analysis",  f"activity_id IN ({activity_id_subq})"),
        ("activity_reflection",     f"activity_id IN ({activity_id_subq})"),
        ("activity_feedback",       f"activity_id IN ({activity_id_subq})"),
        ("strength_exercise_set",   f"activity_id IN ({activity_id_subq})"),
        ("personal_best",           f"activity_id IN ({activity_id_subq})"),
        ("best_effort",             f"activity_id IN ({activity_id_subq})"),
        ("performance_event",       f"activity_id IN ({activity_id_subq})"),

        # Plan children
        ("planned_workout",             f"plan_id IN ({plan_id_subq})"),
        ("plan_modification_log",       f"plan_id IN ({plan_id_subq})"),
        ("plan_adaptation_proposal",    f"plan_id IN ({plan_id_subq})"),
        ("plan_preview",                f"athlete_id = '{demo_id}'"),
        ("workout_selection_audit_event", f"athlete_id = '{demo_id}'"),
        ("training_availability",       f"athlete_id = '{demo_id}'"),
        ("calendar_note",               f"athlete_id = '{demo_id}'"),
        ("calendar_insight",            f"athlete_id = '{demo_id}'"),

        # Correlation children
        ("correlation_mediator", f"finding_id IN ({finding_id_subq})"),

        # Now parents (athlete_id-scoped)
        ("activity",                f"athlete_id = '{demo_id}'"),
        ("training_plan",           f"athlete_id = '{demo_id}'"),
        ("meal_template",           f"athlete_id = '{demo_id}'"),
        ("correlation_finding",     f"athlete_id = '{demo_id}'"),

        # Profile / calibration
        ("athlete_fueling_profile",      f"athlete_id = '{demo_id}'"),
        ("athlete_race_result_anchor",   f"athlete_id = '{demo_id}'"),
        ("athlete_training_pace_profile", f"athlete_id = '{demo_id}'"),
        ("athlete_goal",                 f"athlete_id = '{demo_id}'"),
        ("athlete_calibrated_model",     f"athlete_id = '{demo_id}'"),
        ("athlete_workout_response",     f"athlete_id = '{demo_id}'"),
        ("athlete_override",             f"athlete_id = '{demo_id}'"),
        ("athlete_learning",             f"athlete_id = '{demo_id}'"),
        ("athlete_adaptation_thresholds", f"athlete_id = '{demo_id}'"),
        ("athlete_fact",                 f"athlete_id = '{demo_id}'"),
        ("athlete_route",                f"athlete_id = '{demo_id}'"),
        ("training_block",               f"athlete_id = '{demo_id}'"),

        # Recovery
        ("daily_checkin",      f"athlete_id = '{demo_id}'"),
        ("body_composition",   f"athlete_id = '{demo_id}'"),
        ("work_pattern",       f"athlete_id = '{demo_id}'"),
        ("intake_questionnaire", f"athlete_id = '{demo_id}'"),
        ("daily_readiness",    f"athlete_id = '{demo_id}'"),
        ("garmin_day",         f"athlete_id = '{demo_id}'"),

        # Nutrition
        ("nutrition_entry",           f"athlete_id = '{demo_id}'"),
        ("nutrition_goal",            f"athlete_id = '{demo_id}'"),
        ("athlete_food_override",     f"athlete_id = '{demo_id}'"),

        # Intelligence
        ("fingerprint_finding",             f"athlete_id = '{demo_id}'"),
        ("insight_feedback",                f"athlete_id = '{demo_id}'"),
        ("threshold_calibration_log",       f"athlete_id = '{demo_id}'"),
        ("self_regulation_log",             f"athlete_id = '{demo_id}'"),
        ("insight_log",                     f"athlete_id = '{demo_id}'"),
        ("narration_log",                   f"athlete_id = '{demo_id}'"),
        ("narrative_feedback",              f"athlete_id = '{demo_id}'"),
        ("auto_discovery_run",              f"athlete_id = '{demo_id}'"),
        ("auto_discovery_experiment",       f"athlete_id = '{demo_id}'"),
        ("auto_discovery_candidate",        f"athlete_id = '{demo_id}'"),
        ("auto_discovery_review_log",       f"athlete_id = '{demo_id}'"),
        ("n1_insight_suppression",          f"athlete_id = '{demo_id}'"),

        # Coach state
        ("coaching_recommendation",  f"athlete_id = '{demo_id}'"),
        ("coach_chat",               f"athlete_id = '{demo_id}'"),
        ("coach_intent_snapshot",    f"athlete_id = '{demo_id}'"),
        ("coach_usage",              f"athlete_id = '{demo_id}'"),
        ("coach_briefing_input",     f"athlete_id = '{demo_id}'"),
        # Also wipe cached briefings so the demo gets fresh K2.5 output.
        ("coach_briefing",           f"athlete_id = '{demo_id}'"),
    ]

    for table_name, where in delete_order:
        if table_name not in Base.metadata.tables:
            continue
        if table_name not in live_tables:
            # Declared model exists in code but no migration on this DB yet.
            continue
        result = db.execute(text(f"DELETE FROM {table_name} WHERE {where}"))
        counts[table_name] = result.rowcount or 0

    return counts


# ---------------------------------------------------------------------------
# Generic table copy
# ---------------------------------------------------------------------------

def _new_pk_value(pk_python_type: Any) -> Any:
    """Generate a new primary key value matching the source column type."""
    if pk_python_type is uuid.UUID:
        return uuid.uuid4()
    # int PKs — let the DB autogenerate by leaving the column out of the
    # insert. Caller handles this.
    return None


def _copy_table(
    db: Session,
    table_name: str,
    config: Dict[str, Any],
    source_id: uuid.UUID,
    demo_id: uuid.UUID,
    through_date: date,
    id_maps: Dict[str, Dict[Any, Any]],
) -> int:
    """
    Copy rows from `table_name` for source athlete to demo athlete.
    Returns the number of rows inserted.
    """
    table = Base.metadata.tables.get(table_name)
    if table is None:
        logger.warning("table %s not in metadata, skipping", table_name)
        return 0

    # Intersect declared columns with what actually exists in the live
    # DB. Some model columns may not have reached prod via Alembic yet.
    live_cols = _existing_columns(db, table_name)
    cols = [c for c in table.columns if c.name in live_cols]
    if not cols:
        logger.info("table %s has no live columns matching model; skipping", table_name)
        return 0
    col_names = [c.name for c in cols]
    pk_cols = [c for c in cols if c.primary_key]
    if len(pk_cols) != 1:
        # Composite or no PK — uncommon among our tables; bail loudly so
        # someone has to think about it.
        logger.warning("table %s has non-singular PK (%d cols); skipping", table_name, len(pk_cols))
        return 0
    pk_col = pk_cols[0]

    # Build the source query.
    where_clauses: List[str] = []
    extra_remap: Dict[str, str] = config.get("extra_remap") or {}
    has_athlete_id = "athlete_id" in col_names

    if has_athlete_id:
        where_clauses.append(f"athlete_id = '{source_id}'")
    else:
        # No athlete_id — must scope by an extra_remap parent that
        # we've already filtered down via id_map.
        parent_filter_added = False
        for fk_col, parent_table in extra_remap.items():
            parent_map = id_maps.get(parent_table)
            if not parent_map:
                continue
            if not parent_map:
                continue
            ids_csv = ",".join(f"'{old}'" for old in parent_map.keys())
            if ids_csv:
                where_clauses.append(f"{fk_col} IN ({ids_csv})")
                parent_filter_added = True
                break  # one parent filter is enough; child must have at most one parent
        if not parent_filter_added:
            logger.info("table %s: no athlete_id and no parent filter, skipping", table_name)
            return 0

    date_filter_col = config.get("date_filter_col")
    if date_filter_col and date_filter_col in col_names:
        where_clauses.append(
            f"{date_filter_col} <= '{through_date.isoformat()} 23:59:59+00'"
        )

    where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
    select_sql = f"SELECT {', '.join(col_names)} FROM {table_name} WHERE {where_sql}"

    rows = db.execute(text(select_sql)).mappings().all()
    if not rows:
        return 0

    track_pk = bool(config.get("track_pk"))
    pk_python_type = pk_col.type.python_type if hasattr(pk_col.type, "python_type") else None

    inserted = 0
    prefix_fields: Tuple[str, ...] = config.get("prefix_fields") or ()

    for row in rows:
        new_row = dict(row)

        # Remap athlete_id.
        if has_athlete_id:
            new_row["athlete_id"] = demo_id

        # Prefix external IDs to avoid colliding with the source
        # athlete's rows under the same unique (provider, external_id)
        # constraint. Only prefixes non-null values.
        for field in prefix_fields:
            if field in new_row and new_row[field] is not None:
                new_row[field] = f"demo-{new_row[field]}"

        # Remap extra FKs to copied parents.
        for fk_col, parent_table in extra_remap.items():
            if fk_col not in new_row:
                continue
            old_val = new_row[fk_col]
            if old_val is None:
                continue
            parent_map = id_maps.get(parent_table) or {}
            new_val = parent_map.get(old_val)
            if new_val is None:
                if config.get("skip_if_no_parent"):
                    new_row = None  # type: ignore[assignment]
                    break
                # FK references something we didn't copy — null it out.
                new_row[fk_col] = None
            else:
                new_row[fk_col] = new_val
        if new_row is None:
            continue

        # Remap primary key.
        old_pk = row[pk_col.name]
        if pk_col.name == "athlete_id":
            # Special case: PK *is* athlete_id (1:1 tables like
            # athlete_calibrated_model). The athlete_id remap above
            # already produced the correct PK; do NOT generate a new
            # UUID or we'll insert with a random key that no Athlete
            # row exists for.
            new_pk = demo_id
            if track_pk:
                id_maps.setdefault(table_name, {})[old_pk] = new_pk
        elif pk_python_type is uuid.UUID:
            new_pk = uuid.uuid4()
            new_row[pk_col.name] = new_pk
            if track_pk:
                id_maps.setdefault(table_name, {})[old_pk] = new_pk
        else:
            # Int/BigInt PK — let the DB autogenerate by removing it.
            new_row.pop(pk_col.name, None)
            new_pk = None  # filled in after insert if track_pk

        # INSERT via SQLAlchemy Core (bound parameters, type-safe).
        if track_pk and pk_python_type is not uuid.UUID:
            # Need RETURNING id to populate id_map for non-uuid PKs.
            ins = table.insert().values(**new_row).returning(pk_col)
            res = db.execute(ins)
            new_pk = res.scalar()
            id_maps.setdefault(table_name, {})[old_pk] = new_pk
        else:
            db.execute(table.insert().values(**new_row))
        inserted += 1

    return inserted


# ---------------------------------------------------------------------------
# Cache invalidation
# ---------------------------------------------------------------------------

def _invalidate_briefing_cache(demo_id: uuid.UUID) -> int:
    """
    Drop any Redis-cached briefing for the demo athlete so the next
    /home view triggers fresh K2.5 generation against cloned data.
    Returns the number of keys deleted (best-effort; 0 if Redis is
    unreachable, which is fine because coach_briefing rows are also
    wiped).
    """
    try:
        from core.cache import get_redis_client
        client = get_redis_client()
        if client is None:
            return 0
        pattern = f"home:briefing:{demo_id}:*"
        keys = list(client.scan_iter(match=pattern))
        if keys:
            client.delete(*keys)
        return len(keys)
    except Exception as exc:
        logger.warning("redis briefing cache invalidation skipped: %s", exc)
        return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-email", required=True,
                        help="email of the source (real) athlete to clone from")
    parser.add_argument("--demo-email", required=True,
                        help="email of the EXISTING demo athlete to clone into")
    parser.add_argument("--through-date", default=None,
                        help="copy data on/before this date (YYYY-MM-DD); defaults to yesterday UTC")
    parser.add_argument("--commit", action="store_true",
                        help="persist changes; default is dry-run")
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    args = _parse_args()

    if args.through_date:
        try:
            through_date = datetime.strptime(args.through_date, "%Y-%m-%d").date()
        except ValueError:
            print(f"ERROR: invalid --through-date {args.through_date!r}; expected YYYY-MM-DD", file=sys.stderr)
            return 2
    else:
        through_date = (datetime.now(timezone.utc).date() - timedelta(days=1))

    # Hard-fail if there are athlete-scoped tables we haven't classified.
    unknown = _validate_classification()
    if unknown:
        print(
            "ERROR: athlete-scoped tables present but unclassified by this script:\n"
            + "\n".join(f"  - {t}" for t in unknown)
            + "\n\nAdd each to COPY_TABLES or SKIP_TABLES and re-run.",
            file=sys.stderr,
        )
        return 3

    db: Session = SessionLocal()
    try:
        source = db.query(Athlete).filter(Athlete.email == args.source_email.strip().lower()).first()
        if source is None:
            print(f"ERROR: source athlete {args.source_email!r} not found", file=sys.stderr)
            return 4
        if getattr(source, "is_demo", False):
            print(f"ERROR: source athlete {args.source_email!r} is itself a demo (is_demo=True); refusing", file=sys.stderr)
            return 5

        demo = db.query(Athlete).filter(Athlete.email == args.demo_email.strip().lower()).first()
        if demo is None:
            print(
                f"ERROR: demo athlete {args.demo_email!r} not found.\n"
                "       Create it first with scripts/provision_demo_athlete.py.",
                file=sys.stderr,
            )
            return 6
        if not getattr(demo, "is_demo", False):
            print(
                f"ERROR: target athlete {args.demo_email!r} does not have is_demo=True.\n"
                "       Refusing to clobber a real account.",
                file=sys.stderr,
            )
            return 7
        if source.id == demo.id:
            print("ERROR: source and demo are the same athlete; refusing", file=sys.stderr)
            return 8

        print(f"SOURCE: {source.email}  ({source.id})")
        print(f"DEMO:   {demo.email}  ({demo.id})")
        print(f"THROUGH-DATE: {through_date.isoformat()}  (UTC)")
        print(f"MODE: {'COMMIT' if args.commit else 'DRY-RUN'}")
        print()

        # Wipe demo's existing data first (idempotent).
        wipe_counts = _wipe_demo_data(db, demo.id)
        wiped_total = sum(wipe_counts.values())
        print(f"Wiped {wiped_total} rows from {sum(1 for v in wipe_counts.values() if v > 0)} tables.")
        for table_name, n in sorted(wipe_counts.items(), key=lambda kv: -kv[1]):
            if n > 0:
                print(f"  -{n:>6}  {table_name}")
        print()

        # Copy the Athlete row's profile fields onto the demo target.
        copied_fields = _copy_athlete_profile_fields(source, demo)
        print(f"Copied {len(copied_fields)} profile fields to demo athlete row.")
        db.flush()

        # Copy in dependency order. First parents that need PK tracking,
        # then children that reference those PKs.
        copy_order = [
            # Parents whose PKs are referenced by children
            "activity", "training_plan", "meal_template", "correlation_finding",
            # Activity children
            "activity_split", "activity_stream", "cached_stream_analysis",
            "activity_reflection", "activity_feedback", "strength_exercise_set",
            "personal_best", "best_effort", "performance_event",
            # Plan children
            "planned_workout", "plan_modification_log", "plan_adaptation_proposal",
            "plan_preview", "workout_selection_audit_event",
            "training_availability", "calendar_note", "calendar_insight",
            # Correlation children
            "correlation_mediator",
            # Profile / calibration
            "athlete_fueling_profile", "athlete_race_result_anchor",
            "athlete_training_pace_profile", "athlete_goal",
            "athlete_calibrated_model", "athlete_workout_response",
            "athlete_override", "athlete_learning",
            "athlete_adaptation_thresholds", "athlete_fact",
            "athlete_route", "training_block",
            # Recovery
            "daily_checkin", "body_composition", "work_pattern",
            "intake_questionnaire", "daily_readiness", "garmin_day",
            # Nutrition
            "nutrition_goal", "nutrition_entry", "athlete_food_override",
            # Intelligence
            "fingerprint_finding", "insight_feedback",
            "threshold_calibration_log", "self_regulation_log",
            "insight_log", "narration_log", "narrative_feedback",
            "auto_discovery_run", "auto_discovery_experiment",
            "auto_discovery_candidate", "auto_discovery_review_log",
            "n1_insight_suppression",
            # Coach state
            "coaching_recommendation", "coach_chat",
            "coach_intent_snapshot", "coach_usage",
        ]

        # Sanity check: every entry must be in COPY_TABLES.
        missing = [t for t in copy_order if t not in COPY_TABLES]
        if missing:
            print(f"ERROR: copy_order references tables not in COPY_TABLES: {missing}", file=sys.stderr)
            db.rollback()
            return 9

        live_tables = _existing_tables(db)
        skipped_missing = [t for t in copy_order if t not in live_tables]
        if skipped_missing:
            print(f"Note: {len(skipped_missing)} declared tables not present in DB (no migration yet); skipping:")
            for t in skipped_missing:
                print(f"  ~ {t}")
            print()

        id_maps: Dict[str, Dict[Any, Any]] = {}
        copy_counts: Dict[str, int] = {}
        for table_name in copy_order:
            if table_name not in live_tables:
                continue
            try:
                n = _copy_table(
                    db=db,
                    table_name=table_name,
                    config=COPY_TABLES[table_name],
                    source_id=source.id,
                    demo_id=demo.id,
                    through_date=through_date,
                    id_maps=id_maps,
                )
                copy_counts[table_name] = n
            except Exception as exc:
                logger.exception("copy failed for table %s", table_name)
                print(f"ERROR: copy failed for table {table_name}: {exc}", file=sys.stderr)
                db.rollback()
                return 10

        copied_total = sum(copy_counts.values())
        print(f"Copied {copied_total} rows across {sum(1 for v in copy_counts.values() if v > 0)} tables.")
        for table_name in copy_order:
            n = copy_counts.get(table_name, 0)
            if n > 0:
                print(f"  +{n:>6}  {table_name}")
        print()

        if not args.commit:
            print("DRY-RUN: rolling back. Re-run with --commit to persist.")
            db.rollback()
            return 0

        db.commit()
        print("COMMITTED.")

        keys_dropped = _invalidate_briefing_cache(demo.id)
        print(f"Invalidated {keys_dropped} Redis briefing cache key(s).")
        print()
        print(f"Demo account ready: login as {demo.email}")
        return 0

    except Exception as exc:
        db.rollback()
        logger.exception("clone failed")
        print(f"ERROR: clone failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
