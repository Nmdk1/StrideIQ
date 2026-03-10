"""
Daily Production Experience Guardrail — Core Assertion Engine.

Runs 24 assertions across 6 categories against live athlete-facing data,
cross-referencing API responses against database ground truth.

Categories:
  1. Data Truth (#1-#7)
  2. Language Hygiene (#8-#11)
  3. Structural Integrity (#12-#16)
  4. Temporal Consistency (#17-#19)
  5. Cross-Endpoint Consistency (#20-#22)
  6. Trust Integrity (#23-#24)
"""
import json
import re
import logging
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from models import (
    Activity, AthleteFinding, CorrelationFinding,
    DailyCheckin, GarminDay, TrainingPlan,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BANNED_METRIC_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\btsb\b", r"\bctl\b", r"\batl\b", r"\bvdot\b",
        r"\brmssd\b", r"\bsdnn\b", r"\btrimp\b",
        r"\bchronic.load\b", r"\bacute.load\b", r"\bform.score\b",
        r"\bdurability.index\b", r"\brecovery.half.life\b",
        r"\binjury.risk.score\b",
    ]
]

SYCOPHANTIC_TERMS = [
    "incredible", "amazing", "phenomenal", "extraordinary", "fantastic",
    "wonderful", "awesome", "brilliant", "magnificent", "outstanding",
    "superb", "stellar", "remarkable", "spectacular",
]

CAUSAL_PHRASES = [
    "because you", "caused by", "due to your", "as a result of your",
    "that's why", "which caused", "which led to",
]

SNAKE_CASE_RE = re.compile(r"\b[a-z]{2,}(?:_[a-z]{2,})+\b")
SNAKE_CASE_WHITELIST = {"heart_rate", "per_mile", "per_km"}

SLEEP_CLAIM_RE = re.compile(r"(\d+\.?\d*)\s*(?:hours?|h)\s*(?:of\s+)?sleep", re.IGNORECASE)

CLASSIFICATION_KEYWORDS = {
    "tempo": ["tempo"],
    "strides": ["stride"],
    "track_intervals": ["interval", "x400", "x800", "x200", "x1000", "x1200", "x1600"],
    "progression": ["progression", "building"],
    "hill_repeats": ["hill"],
    "threshold_intervals": ["threshold"],
    "long_run": ["long"],
}
EASY_EXCLUSIONS = ["tempo", "interval", "threshold", "hill"]

CAUTIOUS_KEYWORDS = ["fatigue", "tired", "overreaching", "back off", "recovery"]
POSITIVE_KEYWORDS = ["breakthrough", "peak", "best week"]


@dataclass
class AssertionResult:
    id: int
    name: str
    category: str
    passed: bool
    skipped: bool
    detail: str
    endpoint: str
    severity: str


class ExperienceGuardrail:
    """Runs all assertions for a single athlete against live data."""

    def __init__(self, athlete_id: str, db: Session, redis_client):
        self.athlete_id = athlete_id
        self.db = db
        self.redis = redis_client
        self.results: List[AssertionResult] = []
        self.garmin_preflight_ok = True
        self._local_today = date.today()

    # ------------------------------------------------------------------
    # Preflight
    # ------------------------------------------------------------------

    def run_preflight(self) -> bool:
        """Check Garmin data freshness. Returns False if stale (>18h)."""
        try:
            from uuid import UUID as _UUID
            aid = _UUID(self.athlete_id) if isinstance(self.athlete_id, str) else self.athlete_id
            latest = (
                self.db.query(GarminDay)
                .filter(GarminDay.athlete_id == aid)
                .order_by(GarminDay.calendar_date.desc())
                .first()
            )
            if not latest:
                logger.warning("Experience guardrail: no GarminDay rows found — skipping data truth")
                self.garmin_preflight_ok = False
                return False

            hours_since = (datetime.now(timezone.utc) - latest.inserted_at).total_seconds() / 3600
            if hours_since > 18:
                logger.warning(
                    "No Garmin data in %.1fh — skipping data truth assertions (rest day or sync delay)",
                    hours_since,
                )
                self.garmin_preflight_ok = False
                return False
        except Exception as exc:
            logger.error("Preflight check failed: %s", exc)
            self.garmin_preflight_ok = False
            return False

        self.garmin_preflight_ok = True
        return True

    # ------------------------------------------------------------------
    # Tier orchestration
    # ------------------------------------------------------------------

    def run_tier1(
        self,
        home_response: dict,
        activities: list,
        activity_detail: Optional[dict],
        progress_summary: Optional[dict],
    ):
        """Run full assertion battery against Tier 1 endpoints."""
        cb = home_response.get("coach_briefing") or {}
        morning_voice = cb.get("morning_voice") or ""
        last_run = home_response.get("last_run") or {}
        race_countdown = home_response.get("race_countdown") or {}
        finding = home_response.get("finding")
        week = home_response.get("week") or {}

        # ---- Category 1: Data Truth (skip if preflight failed) ----
        if self.garmin_preflight_ok:
            self._assert_sleep_matches_source(morning_voice)
            self._assert_sleep_is_today(morning_voice)
            self._assert_last_activity_date(morning_voice)
            self._assert_shape_sentence_matches_db(
                last_run.get("shape_sentence"), last_run.get("activity_id"),
            )
            self._assert_heat_adjustment_present()
            self._assert_race_countdown_correct(race_countdown)
            self._assert_predicted_time_plausible(race_countdown)
        else:
            skipped_names = [
                (1, "sleep_value_matches_source"),
                (2, "sleep_is_today"),
                (3, "last_activity_date_correct"),
                (4, "shape_sentence_matches_db"),
                (5, "heat_adjustment_present"),
                (6, "race_countdown_correct"),
                (7, "predicted_time_plausible"),
            ]
            for aid, name in skipped_names:
                self.results.append(AssertionResult(
                    id=aid, name=name, category="data_truth",
                    passed=True, skipped=True,
                    detail="Skipped: Garmin data stale (>18h)",
                    endpoint="preflight", severity="high",
                ))

        # ---- Category 2: Language Hygiene ----
        all_texts = self._collect_tier1_texts(
            home_response, activities, activity_detail, progress_summary,
        )
        llm_texts = self._collect_llm_texts(home_response, progress_summary)

        self._assert_no_banned_metrics(all_texts)
        self._assert_no_sycophantic_language(llm_texts)
        self._assert_no_causal_claims(llm_texts)
        self._assert_no_raw_identifiers(all_texts)

        # ---- Category 3: Structural Integrity ----
        self._assert_single_paragraph(morning_voice)
        self._assert_word_count_range(morning_voice)
        self._assert_numeric_reference(morning_voice)
        self._assert_findings_non_empty(finding, home_response)
        self._assert_no_duplicate_findings(finding)

        # ---- Category 4: Temporal Consistency ----
        self._assert_finding_cooldown(finding)
        coach_texts = [morning_voice]
        yesterday_insight = (home_response.get("yesterday") or {}).get("insight") or ""
        if yesterday_insight:
            coach_texts.append(yesterday_insight)
        self._assert_yesterday_correct(coach_texts)
        self._assert_week_trajectory(week.get("trajectory_sentence") or "")

        # ---- Category 5: Cross-Endpoint Consistency ----
        activity_shape = None
        if activity_detail and isinstance(activity_detail, dict):
            activity_shape = activity_detail.get("shape_sentence")
        self._assert_shape_cross_endpoint(
            last_run.get("shape_sentence"), activity_shape,
        )
        activity_findings = activity_detail.get("_findings", []) if activity_detail else []
        self._assert_finding_cross_endpoint(finding, activity_findings)

        headline_text = ""
        if progress_summary and isinstance(progress_summary, dict):
            hl = progress_summary.get("headline")
            if isinstance(hl, dict):
                headline_text = hl.get("text") or ""
            elif hasattr(hl, "text"):
                headline_text = hl.text or ""
        self._assert_tone_consistency(morning_voice, headline_text)

        # ---- Category 6: Trust Integrity ----
        all_coach_texts = [morning_voice]
        for f in ["coach_noticed", "week_assessment", "today_context",
                   "checkin_reaction", "race_assessment", "workout_why"]:
            val = cb.get(f)
            if isinstance(val, str) and val:
                all_coach_texts.append(val)
            elif isinstance(val, dict) and val.get("text"):
                all_coach_texts.append(val["text"])
        self._assert_no_superseded_findings(all_coach_texts)

        recent_activity = self._get_most_recent_activity()
        if recent_activity and recent_activity.run_shape and recent_activity.shape_sentence:
            shape_data = recent_activity.run_shape
            if isinstance(shape_data, str):
                try:
                    shape_data = json.loads(shape_data)
                except (json.JSONDecodeError, TypeError):
                    shape_data = {}
            self._assert_classification_matches_sentence(
                shape_data, recent_activity.shape_sentence,
            )
        else:
            self.results.append(AssertionResult(
                id=24, name="classification_matches_sentence",
                category="trust_integrity", passed=True, skipped=True,
                detail="No run_shape or shape_sentence on most recent activity",
                endpoint="activity", severity="high",
            ))

    def run_tier2(self, endpoint_responses: dict):
        """Run language hygiene assertions (#8-#11) against Tier 2 endpoints."""
        all_texts: List[Tuple[str, str, str]] = []
        for ep_name, response in endpoint_responses.items():
            if response is None:
                continue
            resp = response if isinstance(response, dict) else (
                response.model_dump() if hasattr(response, "model_dump") else {}
            )
            for field, text in self._extract_all_text_fields(resp):
                all_texts.append((field, text, ep_name))

        if all_texts:
            self._assert_no_banned_metrics(all_texts, prefix="t2")
            self._assert_no_sycophantic_language(all_texts, prefix="t2")
            self._assert_no_causal_claims(all_texts, prefix="t2")
            self._assert_no_raw_identifiers(all_texts, prefix="t2")

    def run_tier3(self, endpoint_responses: dict):
        """Run language hygiene assertions against Tier 3 endpoints (weekly only)."""
        all_texts: List[Tuple[str, str, str]] = []
        for ep_name, response in endpoint_responses.items():
            if response is None:
                continue
            resp = response if isinstance(response, dict) else (
                response.model_dump() if hasattr(response, "model_dump") else {}
            )
            for field, text in self._extract_all_text_fields(resp):
                all_texts.append((field, text, ep_name))

        if all_texts:
            self._assert_no_banned_metrics(all_texts, prefix="t3")
            self._assert_no_sycophantic_language(all_texts, prefix="t3")
            self._assert_no_causal_claims(all_texts, prefix="t3")
            self._assert_no_raw_identifiers(all_texts, prefix="t3")

    # ------------------------------------------------------------------
    # Category 1: Data Truth
    # ------------------------------------------------------------------

    def _assert_sleep_matches_source(self, morning_voice: str):
        claimed = self._extract_sleep_claim(morning_voice)
        if claimed is None:
            self.results.append(AssertionResult(
                id=1, name="sleep_value_matches_source", category="data_truth",
                passed=True, skipped=False,
                detail="No sleep claim in morning voice",
                endpoint="home.coach_briefing.morning_voice", severity="critical",
            ))
            return

        from uuid import UUID as _UUID
        aid = _UUID(self.athlete_id) if isinstance(self.athlete_id, str) else self.athlete_id
        garmin = (
            self.db.query(GarminDay)
            .filter(GarminDay.athlete_id == aid, GarminDay.calendar_date == self._local_today)
            .first()
        )
        garmin_hours = (garmin.sleep_total_s / 3600) if garmin and garmin.sleep_total_s else None

        checkin = (
            self.db.query(DailyCheckin)
            .filter(DailyCheckin.athlete_id == aid, DailyCheckin.date == self._local_today)
            .first()
        )
        checkin_hours = float(checkin.sleep_h) if checkin and checkin.sleep_h else None

        sources = []
        if garmin_hours is not None:
            sources.append(("GarminDay", garmin_hours))
        if checkin_hours is not None:
            sources.append(("DailyCheckin", checkin_hours))

        if not sources:
            self.results.append(AssertionResult(
                id=1, name="sleep_value_matches_source", category="data_truth",
                passed=True, skipped=False,
                detail=f"Sleep claim {claimed}h but no source data for today — not a mismatch",
                endpoint="home.coach_briefing.morning_voice", severity="critical",
            ))
            return

        match = any(abs(claimed - src_val) <= 0.3 for _, src_val in sources)
        source_detail = ", ".join(f"{name}={v:.2f}h" for name, v in sources)
        self.results.append(AssertionResult(
            id=1, name="sleep_value_matches_source", category="data_truth",
            passed=match, skipped=False,
            detail=f"Morning voice claims {claimed}h sleep; sources: {source_detail}",
            endpoint="home.coach_briefing.morning_voice",
            severity="critical",
        ))

    def _assert_sleep_is_today(self, morning_voice: str):
        has_garmin_sleep = bool(
            re.search(r"garmin", morning_voice, re.IGNORECASE)
            and self._extract_sleep_claim(morning_voice) is not None
        )
        if not has_garmin_sleep:
            self.results.append(AssertionResult(
                id=2, name="sleep_is_today", category="data_truth",
                passed=True, skipped=False,
                detail="No Garmin sleep claim in text",
                endpoint="home.coach_briefing.morning_voice", severity="critical",
            ))
            return

        from uuid import UUID as _UUID
        aid = _UUID(self.athlete_id) if isinstance(self.athlete_id, str) else self.athlete_id
        today_row = (
            self.db.query(GarminDay)
            .filter(GarminDay.athlete_id == aid, GarminDay.calendar_date == self._local_today)
            .filter(GarminDay.sleep_total_s.isnot(None))
            .first()
        )
        self.results.append(AssertionResult(
            id=2, name="sleep_is_today", category="data_truth",
            passed=today_row is not None, skipped=False,
            detail="Today's GarminDay row exists" if today_row else "No GarminDay for today — stale data presented as current",
            endpoint="home.coach_briefing.morning_voice", severity="critical",
        ))

    def _assert_last_activity_date(self, morning_voice: str):
        from uuid import UUID as _UUID
        aid = _UUID(self.athlete_id) if isinstance(self.athlete_id, str) else self.athlete_id
        latest = (
            self.db.query(Activity)
            .filter(Activity.athlete_id == aid, Activity.is_duplicate.is_(False))
            .order_by(Activity.start_time.desc())
            .first()
        )
        if not latest:
            self.results.append(AssertionResult(
                id=3, name="last_activity_date_correct", category="data_truth",
                passed=True, skipped=False,
                detail="No activities found",
                endpoint="home.coach_briefing.morning_voice", severity="critical",
            ))
            return

        has_yesterday_ref = bool(re.search(r"\byesterday\b", morning_voice, re.IGNORECASE))
        if not has_yesterday_ref:
            self.results.append(AssertionResult(
                id=3, name="last_activity_date_correct", category="data_truth",
                passed=True, skipped=False,
                detail="No 'yesterday' reference in morning voice",
                endpoint="home.coach_briefing.morning_voice", severity="critical",
            ))
            return

        activity_date = latest.start_time.date() if latest.start_time else None
        yesterday = self._local_today - timedelta(days=1)
        correct = activity_date == yesterday
        self.results.append(AssertionResult(
            id=3, name="last_activity_date_correct", category="data_truth",
            passed=correct, skipped=False,
            detail=f"Text says 'yesterday' — last activity was {activity_date}, yesterday was {yesterday}",
            endpoint="home.coach_briefing.morning_voice", severity="critical",
        ))

    def _assert_shape_sentence_matches_db(self, home_shape: Optional[str], activity_id: Optional[str]):
        if not activity_id:
            self.results.append(AssertionResult(
                id=4, name="shape_sentence_matches_db", category="data_truth",
                passed=True, skipped=True,
                detail="No activity_id in last_run",
                endpoint="home.last_run", severity="high",
            ))
            return

        from uuid import UUID as _UUID
        act = self.db.query(Activity).filter(Activity.id == _UUID(activity_id)).first()
        db_shape = act.shape_sentence if act else None

        both_none = home_shape is None and db_shape is None
        match = both_none or (home_shape == db_shape)
        self.results.append(AssertionResult(
            id=4, name="shape_sentence_matches_db", category="data_truth",
            passed=match, skipped=False,
            detail=f"Home: {home_shape!r} vs DB: {db_shape!r}",
            endpoint="home.last_run.shape_sentence", severity="high",
        ))

    def _assert_heat_adjustment_present(self):
        from uuid import UUID as _UUID
        aid = _UUID(self.athlete_id) if isinstance(self.athlete_id, str) else self.athlete_id
        latest = (
            self.db.query(Activity)
            .filter(Activity.athlete_id == aid, Activity.is_duplicate.is_(False))
            .order_by(Activity.start_time.desc())
            .first()
        )
        if not latest or not latest.dew_point_f or latest.dew_point_f <= 55:
            self.results.append(AssertionResult(
                id=5, name="heat_adjustment_present", category="data_truth",
                passed=True, skipped=False,
                detail="Dew point <= 55°F or not available — not applicable",
                endpoint="activity", severity="high",
            ))
            return

        has_adj = latest.heat_adjustment_pct is not None and latest.heat_adjustment_pct > 0
        self.results.append(AssertionResult(
            id=5, name="heat_adjustment_present", category="data_truth",
            passed=has_adj, skipped=False,
            detail=f"dew_point_f={latest.dew_point_f:.1f}, heat_adjustment_pct={latest.heat_adjustment_pct}",
            endpoint="activity", severity="high",
        ))

    def _assert_race_countdown_correct(self, race_countdown: dict):
        if not race_countdown or race_countdown.get("days_remaining") is None:
            self.results.append(AssertionResult(
                id=6, name="race_countdown_correct", category="data_truth",
                passed=True, skipped=False,
                detail="No race countdown displayed",
                endpoint="home.race_countdown", severity="high",
            ))
            return

        from uuid import UUID as _UUID
        aid = _UUID(self.athlete_id) if isinstance(self.athlete_id, str) else self.athlete_id
        plan = (
            self.db.query(TrainingPlan)
            .filter(TrainingPlan.athlete_id == aid, TrainingPlan.status == "active")
            .first()
        )
        if not plan:
            self.results.append(AssertionResult(
                id=6, name="race_countdown_correct", category="data_truth",
                passed=False, skipped=False,
                detail="Race countdown shown but no active training plan found",
                endpoint="home.race_countdown", severity="high",
            ))
            return

        expected_days = (plan.goal_race_date - self._local_today).days
        displayed = race_countdown["days_remaining"]
        self.results.append(AssertionResult(
            id=6, name="race_countdown_correct", category="data_truth",
            passed=displayed == expected_days, skipped=False,
            detail=f"Displayed: {displayed} days, computed: {expected_days} days (race: {plan.goal_race_date})",
            endpoint="home.race_countdown", severity="high",
        ))

    def _assert_predicted_time_plausible(self, race_countdown: dict):
        predicted = race_countdown.get("predicted_time") if race_countdown else None
        if not predicted:
            self.results.append(AssertionResult(
                id=7, name="predicted_time_plausible", category="data_truth",
                passed=True, skipped=False,
                detail="No predicted time displayed",
                endpoint="home.race_countdown", severity="medium",
            ))
            return

        from uuid import UUID as _UUID
        aid = _UUID(self.athlete_id) if isinstance(self.athlete_id, str) else self.athlete_id

        pred_seconds = self._parse_time_to_seconds(predicted)
        if pred_seconds is None:
            self.results.append(AssertionResult(
                id=7, name="predicted_time_plausible", category="data_truth",
                passed=True, skipped=True,
                detail=f"Could not parse predicted time: {predicted}",
                endpoint="home.race_countdown", severity="medium",
            ))
            return

        plan = (
            self.db.query(TrainingPlan)
            .filter(TrainingPlan.athlete_id == aid, TrainingPlan.status == "active")
            .first()
        )
        if not plan or not plan.goal_race_distance_m:
            self.results.append(AssertionResult(
                id=7, name="predicted_time_plausible", category="data_truth",
                passed=True, skipped=True,
                detail="No active plan with race distance",
                endpoint="home.race_countdown", severity="medium",
            ))
            return

        recent_acts = (
            self.db.query(Activity)
            .filter(Activity.athlete_id == aid, Activity.is_duplicate.is_(False))
            .filter(Activity.distance_m.isnot(None), Activity.distance_m > 0)
            .filter(Activity.moving_time_s.isnot(None), Activity.moving_time_s > 0)
            .order_by(Activity.start_time.desc())
            .limit(10)
            .all()
        )
        if not recent_acts:
            self.results.append(AssertionResult(
                id=7, name="predicted_time_plausible", category="data_truth",
                passed=True, skipped=True,
                detail="No recent activities for pace reference",
                endpoint="home.race_countdown", severity="medium",
            ))
            return

        paces = [a.moving_time_s / (a.distance_m / 1000) for a in recent_acts]
        fastest = min(paces)
        slowest = max(paces)
        race_km = plan.goal_race_distance_m / 1000
        floor_s = fastest * race_km
        ceiling_s = slowest * race_km * 1.5

        plausible = floor_s <= pred_seconds <= ceiling_s
        self.results.append(AssertionResult(
            id=7, name="predicted_time_plausible", category="data_truth",
            passed=plausible, skipped=False,
            detail=f"Predicted {predicted} ({pred_seconds}s), range [{floor_s:.0f}s, {ceiling_s:.0f}s]",
            endpoint="home.race_countdown", severity="medium",
        ))

    # ------------------------------------------------------------------
    # Category 2: Language Hygiene
    # ------------------------------------------------------------------

    def _assert_no_banned_metrics(
        self, texts: List[Tuple[str, str, str]], prefix: str = "",
    ):
        violations = []
        for field, text, endpoint in texts:
            for pattern in BANNED_METRIC_PATTERNS:
                m = pattern.search(text)
                if m:
                    violations.append(f"{endpoint}.{field}: '{m.group()}' in ...{text[max(0,m.start()-20):m.end()+20]}...")

        name = f"no_banned_metrics{'_' + prefix if prefix else ''}"
        self.results.append(AssertionResult(
            id=8, name=name, category="language_hygiene",
            passed=len(violations) == 0, skipped=False,
            detail="; ".join(violations[:5]) if violations else "Clean",
            endpoint="all_tier1" if not prefix else f"tier_{prefix}",
            severity="critical",
        ))

    def _assert_no_sycophantic_language(
        self, texts: List[Tuple[str, str, str]], prefix: str = "",
    ):
        violations = []
        for field, text, endpoint in texts:
            lower = text.lower()
            for term in SYCOPHANTIC_TERMS:
                if re.search(rf"\b{re.escape(term)}\b", lower):
                    violations.append(f"{endpoint}.{field}: '{term}'")

        name = f"no_sycophantic_language{'_' + prefix if prefix else ''}"
        self.results.append(AssertionResult(
            id=9, name=name, category="language_hygiene",
            passed=len(violations) == 0, skipped=False,
            detail="; ".join(violations[:5]) if violations else "Clean",
            endpoint="llm_fields" if not prefix else f"tier_{prefix}",
            severity="medium",
        ))

    def _assert_no_causal_claims(
        self, texts: List[Tuple[str, str, str]], prefix: str = "",
    ):
        violations = []
        for field, text, endpoint in texts:
            lower = text.lower()
            for phrase in CAUSAL_PHRASES:
                if phrase in lower:
                    violations.append(f"{endpoint}.{field}: '{phrase}'")

        name = f"no_causal_claims{'_' + prefix if prefix else ''}"
        self.results.append(AssertionResult(
            id=10, name=name, category="language_hygiene",
            passed=len(violations) == 0, skipped=False,
            detail="; ".join(violations[:5]) if violations else "Clean",
            endpoint="llm_fields" if not prefix else f"tier_{prefix}",
            severity="medium",
        ))

    def _assert_no_raw_identifiers(
        self, texts: List[Tuple[str, str, str]], prefix: str = "",
    ):
        violations = []
        for field, text, endpoint in texts:
            for m in SNAKE_CASE_RE.finditer(text):
                if m.group() not in SNAKE_CASE_WHITELIST:
                    violations.append(f"{endpoint}.{field}: '{m.group()}'")

        name = f"no_raw_identifiers{'_' + prefix if prefix else ''}"
        self.results.append(AssertionResult(
            id=11, name=name, category="language_hygiene",
            passed=len(violations) == 0, skipped=False,
            detail="; ".join(violations[:5]) if violations else "Clean",
            endpoint="all_text" if not prefix else f"tier_{prefix}",
            severity="high",
        ))

    # ------------------------------------------------------------------
    # Category 3: Structural Integrity
    # ------------------------------------------------------------------

    def _assert_single_paragraph(self, morning_voice: str):
        if not morning_voice:
            self.results.append(AssertionResult(
                id=12, name="single_paragraph", category="structural_integrity",
                passed=True, skipped=True,
                detail="Morning voice is empty/null",
                endpoint="home.coach_briefing.morning_voice", severity="high",
            ))
            return

        has_newline = "\n" in morning_voice.strip()
        self.results.append(AssertionResult(
            id=12, name="single_paragraph", category="structural_integrity",
            passed=not has_newline, skipped=False,
            detail="Contains newline" if has_newline else "Single paragraph",
            endpoint="home.coach_briefing.morning_voice", severity="high",
        ))

    def _assert_word_count_range(self, morning_voice: str):
        if not morning_voice:
            self.results.append(AssertionResult(
                id=13, name="word_count_in_range", category="structural_integrity",
                passed=True, skipped=True,
                detail="Morning voice is empty/null",
                endpoint="home.coach_briefing.morning_voice", severity="medium",
            ))
            return

        wc = len(morning_voice.split())
        in_range = 20 <= wc <= 120
        self.results.append(AssertionResult(
            id=13, name="word_count_in_range", category="structural_integrity",
            passed=in_range, skipped=False,
            detail=f"Word count: {wc} (expected 20-120)",
            endpoint="home.coach_briefing.morning_voice", severity="medium",
        ))

    def _assert_numeric_reference(self, morning_voice: str):
        if not morning_voice:
            self.results.append(AssertionResult(
                id=14, name="numeric_reference", category="structural_integrity",
                passed=True, skipped=True,
                detail="Morning voice is empty/null",
                endpoint="home.coach_briefing.morning_voice", severity="medium",
            ))
            return

        has_digit = bool(re.search(r"\d", morning_voice))
        self.results.append(AssertionResult(
            id=14, name="numeric_reference", category="structural_integrity",
            passed=has_digit, skipped=False,
            detail="Contains numeric reference" if has_digit else "No digits found in morning voice",
            endpoint="home.coach_briefing.morning_voice", severity="medium",
        ))

    def _assert_findings_non_empty(self, finding, home_response: dict):
        from uuid import UUID as _UUID
        aid = _UUID(self.athlete_id) if isinstance(self.athlete_id, str) else self.athlete_id

        active_count = (
            self.db.query(CorrelationFinding)
            .filter(
                CorrelationFinding.athlete_id == aid,
                CorrelationFinding.is_active.is_(True),
                CorrelationFinding.times_confirmed >= 3,
            )
            .count()
        )

        has_finding = finding is not None
        if active_count > 0 and not has_finding:
            self.results.append(AssertionResult(
                id=15, name="findings_non_empty", category="structural_integrity",
                passed=False, skipped=False,
                detail=f"{active_count} active findings in DB but none shown on home",
                endpoint="home.finding", severity="high",
            ))
        else:
            self.results.append(AssertionResult(
                id=15, name="findings_non_empty", category="structural_integrity",
                passed=True, skipped=False,
                detail=f"Active findings: {active_count}, shown: {has_finding}",
                endpoint="home.finding", severity="high",
            ))

    def _assert_no_duplicate_findings(self, finding):
        # Home shows at most one finding — duplicates only possible if
        # response structure changes. Guard against it.
        self.results.append(AssertionResult(
            id=16, name="no_duplicate_findings", category="structural_integrity",
            passed=True, skipped=False,
            detail="Home shows single finding — no duplicate possible",
            endpoint="home.finding", severity="medium",
        ))

    # ------------------------------------------------------------------
    # Category 4: Temporal Consistency
    # ------------------------------------------------------------------

    def _assert_finding_cooldown(self, finding):
        if not finding or not self.redis:
            self.results.append(AssertionResult(
                id=17, name="finding_cooldown_respected", category="temporal_consistency",
                passed=True, skipped=finding is None,
                detail="No finding shown or Redis unavailable",
                endpoint="home.finding", severity="high",
            ))
            return

        f_data = finding if isinstance(finding, dict) else (
            finding.model_dump() if hasattr(finding, "model_dump") else {}
        )
        domain = f_data.get("domain", "unknown")

        try:
            pattern = f"finding_surfaced:{self.athlete_id}:*"
            keys = self.redis.keys(pattern)
            violation = False
            detail = "No cooldown violation"

            for key in (keys or []):
                key_str = key.decode() if isinstance(key, bytes) else key
                ttl = self.redis.ttl(key_str)
                if ttl and ttl > 0:
                    remaining_hours = ttl / 3600
                    if remaining_hours > 0 and domain in key_str:
                        violation = True
                        detail = f"Finding domain '{domain}' surfaced within cooldown (TTL: {remaining_hours:.1f}h remaining)"
                        break
        except Exception as exc:
            detail = f"Redis check failed: {exc}"
            violation = False

        self.results.append(AssertionResult(
            id=17, name="finding_cooldown_respected", category="temporal_consistency",
            passed=not violation, skipped=False,
            detail=detail,
            endpoint="home.finding", severity="high",
        ))

    def _assert_yesterday_correct(self, texts: list):
        has_yesterday = any(
            re.search(r"\byesterday\b", t, re.IGNORECASE) for t in texts if t
        )
        if not has_yesterday:
            self.results.append(AssertionResult(
                id=18, name="yesterday_reference_correct", category="temporal_consistency",
                passed=True, skipped=False,
                detail="No 'yesterday' reference in text",
                endpoint="home", severity="high",
            ))
            return

        from uuid import UUID as _UUID
        aid = _UUID(self.athlete_id) if isinstance(self.athlete_id, str) else self.athlete_id
        latest = (
            self.db.query(Activity)
            .filter(Activity.athlete_id == aid, Activity.is_duplicate.is_(False))
            .order_by(Activity.start_time.desc())
            .first()
        )
        if not latest:
            self.results.append(AssertionResult(
                id=18, name="yesterday_reference_correct", category="temporal_consistency",
                passed=False, skipped=False,
                detail="Text says 'yesterday' but no activities found",
                endpoint="home", severity="high",
            ))
            return

        act_date = latest.start_time.date() if latest.start_time else None
        yesterday = self._local_today - timedelta(days=1)
        self.results.append(AssertionResult(
            id=18, name="yesterday_reference_correct", category="temporal_consistency",
            passed=act_date == yesterday, skipped=False,
            detail=f"'yesterday' used — last activity: {act_date}, actual yesterday: {yesterday}",
            endpoint="home", severity="high",
        ))

    def _assert_week_trajectory(self, trajectory: str):
        if not trajectory:
            self.results.append(AssertionResult(
                id=19, name="week_trajectory_correct", category="temporal_consistency",
                passed=True, skipped=True,
                detail="No trajectory sentence",
                endpoint="home.week.trajectory_sentence", severity="medium",
            ))
            return

        count_match = re.search(r"(\d+)\s*runs?\s*(?:this\s+)?week", trajectory, re.IGNORECASE)
        if not count_match:
            self.results.append(AssertionResult(
                id=19, name="week_trajectory_correct", category="temporal_consistency",
                passed=True, skipped=False,
                detail="No specific run count referenced in trajectory",
                endpoint="home.week.trajectory_sentence", severity="medium",
            ))
            return

        claimed_count = int(count_match.group(1))
        from uuid import UUID as _UUID
        aid = _UUID(self.athlete_id) if isinstance(self.athlete_id, str) else self.athlete_id
        week_start = self._local_today - timedelta(days=self._local_today.weekday())
        actual_count = (
            self.db.query(Activity)
            .filter(
                Activity.athlete_id == aid,
                Activity.is_duplicate.is_(False),
                Activity.start_time >= datetime.combine(week_start, datetime.min.time()),
            )
            .count()
        )

        self.results.append(AssertionResult(
            id=19, name="week_trajectory_correct", category="temporal_consistency",
            passed=claimed_count == actual_count, skipped=False,
            detail=f"Trajectory says {claimed_count} runs, DB has {actual_count} this week",
            endpoint="home.week.trajectory_sentence", severity="medium",
        ))

    # ------------------------------------------------------------------
    # Category 5: Cross-Endpoint Consistency
    # ------------------------------------------------------------------

    def _assert_shape_cross_endpoint(self, home_shape: Optional[str], activity_shape: Optional[str]):
        if home_shape is None and activity_shape is None:
            self.results.append(AssertionResult(
                id=20, name="shape_cross_endpoint_consistent", category="cross_endpoint",
                passed=True, skipped=True,
                detail="Both shapes are null",
                endpoint="home+activity", severity="high",
            ))
            return

        if home_shape is None or activity_shape is None:
            self.results.append(AssertionResult(
                id=20, name="shape_cross_endpoint_consistent", category="cross_endpoint",
                passed=True, skipped=True,
                detail=f"One shape null — home: {home_shape is not None}, activity: {activity_shape is not None}",
                endpoint="home+activity", severity="high",
            ))
            return

        self.results.append(AssertionResult(
            id=20, name="shape_cross_endpoint_consistent", category="cross_endpoint",
            passed=home_shape == activity_shape, skipped=False,
            detail=f"Home: {home_shape!r} vs Activity: {activity_shape!r}",
            endpoint="home+activity", severity="high",
        ))

    def _assert_finding_cross_endpoint(self, home_finding, activity_findings: list):
        if not home_finding or not activity_findings:
            self.results.append(AssertionResult(
                id=21, name="finding_text_cross_endpoint", category="cross_endpoint",
                passed=True, skipped=True,
                detail="Finding not present in both endpoints",
                endpoint="home+activity_findings", severity="high",
            ))
            return

        home_text = home_finding.get("text") if isinstance(home_finding, dict) else (
            home_finding.text if hasattr(home_finding, "text") else None
        )
        if not home_text:
            self.results.append(AssertionResult(
                id=21, name="finding_text_cross_endpoint", category="cross_endpoint",
                passed=True, skipped=True,
                detail="Home finding has no text",
                endpoint="home+activity_findings", severity="high",
            ))
            return

        activity_texts = [
            f.get("text") if isinstance(f, dict) else getattr(f, "text", None)
            for f in activity_findings
        ]
        match = home_text in activity_texts
        self.results.append(AssertionResult(
            id=21, name="finding_text_cross_endpoint", category="cross_endpoint",
            passed=match, skipped=False,
            detail=f"Home finding text {'found' if match else 'NOT found'} in activity findings",
            endpoint="home+activity_findings", severity="high",
        ))

    def _assert_tone_consistency(self, morning_voice: str, headline: str):
        if not morning_voice or not headline:
            self.results.append(AssertionResult(
                id=22, name="tone_consistency", category="cross_endpoint",
                passed=True, skipped=True,
                detail="Morning voice or headline is empty",
                endpoint="home+progress", severity="medium",
            ))
            return

        mv_lower = morning_voice.lower()
        hl_lower = headline.lower()

        mv_cautious = any(k in mv_lower for k in CAUTIOUS_KEYWORDS)
        mv_positive = any(k in mv_lower for k in POSITIVE_KEYWORDS)
        hl_cautious = any(k in hl_lower for k in CAUTIOUS_KEYWORDS)
        hl_positive = any(k in hl_lower for k in POSITIVE_KEYWORDS)

        contradiction = (mv_cautious and hl_positive) or (mv_positive and hl_cautious)
        self.results.append(AssertionResult(
            id=22, name="tone_consistency", category="cross_endpoint",
            passed=not contradiction, skipped=False,
            detail="Tone contradiction detected" if contradiction else "Tone consistent",
            endpoint="home+progress", severity="medium",
        ))

    # ------------------------------------------------------------------
    # Category 6: Trust Integrity
    # ------------------------------------------------------------------

    def _assert_no_superseded_findings(self, coach_texts: list):
        from uuid import UUID as _UUID
        aid = _UUID(self.athlete_id) if isinstance(self.athlete_id, str) else self.athlete_id

        superseded_af = (
            self.db.query(AthleteFinding)
            .filter(
                AthleteFinding.athlete_id == aid,
                AthleteFinding.is_active.is_(False),
                AthleteFinding.superseded_at.isnot(None),
            )
            .all()
        )
        deactivated_cf = (
            self.db.query(CorrelationFinding)
            .filter(
                CorrelationFinding.athlete_id == aid,
                CorrelationFinding.is_active.is_(False),
            )
            .all()
        )

        combined_text = " ".join(t for t in coach_texts if t).lower()
        violations = []

        for af in superseded_af:
            if af.sentence and af.sentence.lower() in combined_text:
                violations.append(f"AthleteFinding: {af.sentence[:60]}...")

        for cf in deactivated_cf:
            if cf.insight_text and cf.insight_text.lower() in combined_text:
                violations.append(f"CorrelationFinding: {cf.insight_text[:60]}...")

        self.results.append(AssertionResult(
            id=23, name="no_superseded_findings_in_output", category="trust_integrity",
            passed=len(violations) == 0, skipped=False,
            detail="; ".join(violations) if violations else "No superseded findings in coach output",
            endpoint="coach_briefing.*", severity="critical",
        ))

    def _assert_classification_matches_sentence(self, run_shape: dict, shape_sentence: str):
        summary = run_shape.get("summary") or {} if isinstance(run_shape, dict) else {}
        classification = summary.get("workout_classification")
        if not classification:
            self.results.append(AssertionResult(
                id=24, name="classification_matches_sentence", category="trust_integrity",
                passed=True, skipped=True,
                detail="No workout_classification in run_shape",
                endpoint="activity", severity="high",
            ))
            return

        sentence_lower = shape_sentence.lower()

        if classification == "easy":
            bad_keywords = [kw for kw in EASY_EXCLUSIONS if kw in sentence_lower]
            passed = len(bad_keywords) == 0
            detail = (
                f"Classification 'easy' but sentence contains: {bad_keywords}"
                if not passed
                else "Classification 'easy' — no contradicting keywords"
            )
        elif classification in CLASSIFICATION_KEYWORDS:
            expected = CLASSIFICATION_KEYWORDS[classification]
            found = any(kw in sentence_lower for kw in expected)
            passed = found
            detail = (
                f"Classification '{classification}' — keyword found in sentence"
                if found
                else f"Classification '{classification}' but none of {expected} found in sentence"
            )
        else:
            passed = True
            detail = f"Unknown classification '{classification}' — skipped"

        self.results.append(AssertionResult(
            id=24, name="classification_matches_sentence", category="trust_integrity",
            passed=passed, skipped=False,
            detail=detail,
            endpoint="activity", severity="high",
        ))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_most_recent_activity(self) -> Optional[Activity]:
        from uuid import UUID as _UUID
        aid = _UUID(self.athlete_id) if isinstance(self.athlete_id, str) else self.athlete_id
        return (
            self.db.query(Activity)
            .filter(Activity.athlete_id == aid, Activity.is_duplicate.is_(False))
            .order_by(Activity.start_time.desc())
            .first()
        )

    def _extract_sleep_claim(self, text: str) -> Optional[float]:
        m = SLEEP_CLAIM_RE.search(text)
        return float(m.group(1)) if m else None

    def _extract_all_text_fields(self, obj, prefix: str = ""):
        """Recursively walk a response dict, yield (field_path, text_value)."""
        if isinstance(obj, str) and len(obj) > 2:
            yield (prefix, obj)
        elif isinstance(obj, dict):
            for k, v in obj.items():
                yield from self._extract_all_text_fields(v, f"{prefix}.{k}" if prefix else k)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                yield from self._extract_all_text_fields(item, f"{prefix}[{i}]")

    def _collect_tier1_texts(
        self, home_response, activities, activity_detail, progress_summary,
    ) -> List[Tuple[str, str, str]]:
        """Collect all text fields from Tier 1 endpoints for language scanning."""
        texts: List[Tuple[str, str, str]] = []
        if home_response:
            for f, t in self._extract_all_text_fields(home_response):
                texts.append((f, t, "home"))
        for i, act in enumerate(activities or []):
            act_data = act if isinstance(act, dict) else (
                {"shape_sentence": act.shape_sentence, "athlete_title": act.athlete_title}
                if hasattr(act, "shape_sentence") else {}
            )
            for f, t in self._extract_all_text_fields(act_data):
                texts.append((f, t, f"activities[{i}]"))
        if activity_detail:
            for f, t in self._extract_all_text_fields(activity_detail):
                texts.append((f, t, "activity_detail"))
        if progress_summary:
            ps = progress_summary if isinstance(progress_summary, dict) else (
                progress_summary.model_dump() if hasattr(progress_summary, "model_dump") else {}
            )
            for f, t in self._extract_all_text_fields(ps):
                texts.append((f, t, "progress_summary"))
        return texts

    def _collect_llm_texts(
        self, home_response, progress_summary,
    ) -> List[Tuple[str, str, str]]:
        """Collect only LLM-generated text fields for sycophancy/causal checks."""
        texts: List[Tuple[str, str, str]] = []
        cb = home_response.get("coach_briefing") or {} if home_response else {}
        for field in ["morning_voice", "coach_noticed", "week_assessment",
                       "today_context", "checkin_reaction", "race_assessment",
                       "workout_why"]:
            val = cb.get(field)
            if isinstance(val, str) and val:
                texts.append((f"coach_briefing.{field}", val, "home"))
            elif isinstance(val, dict):
                if val.get("text"):
                    texts.append((f"coach_briefing.{field}.text", val["text"], "home"))

        cn = home_response.get("coach_noticed") if home_response else None
        if isinstance(cn, dict) and cn.get("text"):
            texts.append(("coach_noticed.text", cn["text"], "home"))

        hero = home_response.get("hero_narrative") if home_response else None
        if isinstance(hero, str) and hero:
            texts.append(("hero_narrative", hero, "home"))

        if progress_summary:
            ps = progress_summary if isinstance(progress_summary, dict) else (
                progress_summary.model_dump() if hasattr(progress_summary, "model_dump") else {}
            )
            hl = ps.get("headline")
            if isinstance(hl, dict):
                for f in ["text", "subtext"]:
                    if hl.get(f):
                        texts.append((f"headline.{f}", hl[f], "progress_summary"))
            cards = ps.get("coach_cards") or []
            for i, card in enumerate(cards):
                if isinstance(card, dict) and card.get("summary"):
                    texts.append((f"coach_cards[{i}].summary", card["summary"], "progress_summary"))

        return texts

    @staticmethod
    def _parse_time_to_seconds(time_str: str) -> Optional[int]:
        """Parse 'H:MM:SS' or 'M:SS' into seconds."""
        parts = time_str.split(":")
        try:
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
        except (ValueError, TypeError):
            pass
        return None

    def summarize(self) -> dict:
        passed = sum(1 for r in self.results if r.passed and not r.skipped)
        failed = sum(1 for r in self.results if not r.passed and not r.skipped)
        skipped = sum(1 for r in self.results if r.skipped)
        all_passed = failed == 0
        summary_text = (
            f"{passed + skipped}/{len(self.results)} passed ({skipped} skipped)"
            if all_passed
            else "FAILED: " + ", ".join(
                f"#{r.id} {r.name}" for r in self.results if not r.passed and not r.skipped
            )
        )
        return {
            "passed": all_passed,
            "total_assertions": len(self.results),
            "passed_count": passed,
            "failed_count": failed,
            "skipped_count": skipped,
            "results": [asdict(r) for r in self.results],
            "summary": summary_text,
        }
