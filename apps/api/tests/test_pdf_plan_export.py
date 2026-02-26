"""
PDF Plan Export — Test Suite

Categories:
  1. Unit: plan_pdf helper functions (no WeasyPrint required)
  2. Unit: template rendering — verifies HTML content via sys.modules mock
     (weasyprint not required to be installed locally)
  3. Unit: generation guardrails (scope cap, byte-size cap, timeout)
  4. Integration: GET /v1/plans/{plan_id}/pdf endpoint access control
     - 404 for missing / non-owned plan
     - 403 for free athlete without purchase
     - 200 + PDF bytes for one-time purchaser
     - 200 + PDF bytes for guided / premium athlete
"""

import io
import sys
import types
from datetime import date
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models import Athlete, TrainingPlan, PlannedWorkout, PlanPurchase

client = TestClient(app)

FAKE_PDF = b"%PDF-1.4 fake pdf content for testing"


# =============================================================================
# WeasyPrint sys.modules mock fixture
# =============================================================================

@pytest.fixture
def mock_weasyprint(monkeypatch):
    """
    Inject a fake 'weasyprint' module into sys.modules so that
    plan_pdf.generate_plan_pdf can run without weasyprint installed.
    Returns a dict that will be populated with the rendered HTML string.
    """
    captured = {}

    def html_constructor(string=None, base_url=None, **kwargs):
        captured["html"] = string or ""
        inst = MagicMock()
        inst.write_pdf.side_effect = lambda buf: buf.write(FAKE_PDF)
        return inst

    mock_wp = MagicMock()
    mock_wp.HTML.side_effect = html_constructor

    monkeypatch.setitem(sys.modules, "weasyprint", mock_wp)
    return captured


# =============================================================================
# HELPERS (shared with monetization tests)
# =============================================================================

def _headers(user: Athlete) -> dict:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def _make_athlete(tier: str = "free") -> Athlete:
    db = SessionLocal()
    a = Athlete(
        email=f"pdftest_{uuid4()}@test.com",
        display_name=f"PDF-{tier}",
        role="athlete",
        subscription_tier=tier,
        preferred_units="imperial",
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    db.close()
    return a


def _make_plan(athlete: Athlete, with_rpi: bool = True) -> TrainingPlan:
    """Create a minimal plan with one easy and one threshold workout."""
    db = SessionLocal()
    plan = TrainingPlan(
        athlete_id=athlete.id,
        name="PDF Test Marathon Plan",
        status="active",
        goal_race_date=date(2026, 11, 1),
        goal_race_distance_m=42195,
        plan_start_date=date(2026, 6, 1),
        plan_end_date=date(2026, 11, 1),
        total_weeks=3,
        plan_type="marathon",
        generation_method="framework_v2",
        baseline_rpi=52.0 if with_rpi else None,
    )
    db.add(plan)
    db.flush()

    workouts = [
        PlannedWorkout(
            plan_id=plan.id, athlete_id=athlete.id,
            scheduled_date=date(2026, 6, 2), week_number=1, day_of_week=1,
            workout_type="easy", phase="base", title="Easy Run",
            description="Comfortable aerobic effort",
            coach_notes="8:00-8:30/mile easy pace",
            target_distance_km=10.0,
            target_pace_per_km_seconds=300,
        ),
        PlannedWorkout(
            plan_id=plan.id, athlete_id=athlete.id,
            scheduled_date=date(2026, 6, 4), week_number=1, day_of_week=3,
            workout_type="threshold", phase="base", title="Threshold Run",
            description="Comfortably hard sustained effort",
            coach_notes="7:00/mile threshold pace",
            target_distance_km=8.0,
            target_pace_per_km_seconds=262,
        ),
        PlannedWorkout(
            plan_id=plan.id, athlete_id=athlete.id,
            scheduled_date=date(2026, 6, 7), week_number=1, day_of_week=6,
            workout_type="rest", phase="base", title="Rest",
            description=None, coach_notes=None,
            target_distance_km=None,
            target_pace_per_km_seconds=None,
        ),
        PlannedWorkout(
            plan_id=plan.id, athlete_id=athlete.id,
            scheduled_date=date(2026, 6, 9), week_number=2, day_of_week=1,
            workout_type="long", phase="build", title="Long Run",
            description="Steady aerobic long run",
            coach_notes=None,
            target_distance_km=22.0,
            target_pace_per_km_seconds=320,
        ),
    ]
    db.add_all(workouts)
    db.commit()
    db.refresh(plan)
    db.close()
    return plan


def _make_purchase(athlete: Athlete, plan: TrainingPlan) -> PlanPurchase:
    from datetime import datetime, timezone
    db = SessionLocal()
    p = PlanPurchase(
        athlete_id=athlete.id,
        plan_snapshot_id=str(plan.id),
        stripe_session_id=f"cs_test_{uuid4()}",
        purchased_at=datetime.now(timezone.utc),
        amount_cents=500,
    )
    db.add(p)
    db.commit()
    db.close()
    return p


def _cleanup_plan(plan: TrainingPlan):
    """Delete plan + its workouts before deleting the parent athlete."""
    if plan is None:
        return
    db = SessionLocal()
    try:
        db.query(PlannedWorkout).filter(PlannedWorkout.plan_id == plan.id).delete()
        db.query(PlanPurchase).filter(PlanPurchase.plan_snapshot_id == str(plan.id)).delete()
        p = db.merge(plan)
        db.delete(p)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _cleanup_athlete(athlete: Athlete):
    if athlete is None:
        return
    db = SessionLocal()
    try:
        a = db.merge(athlete)
        db.delete(a)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _cleanup(plan=None, *athletes):
    _cleanup_plan(plan)
    for a in athletes:
        _cleanup_athlete(a)


# =============================================================================
# CATEGORY 1: plan_pdf helper functions (pure unit, no WeasyPrint)
# =============================================================================

class TestFilenameHelper:
    def test_safe_basic_name(self):
        from services.plan_pdf import sanitize_pdf_filename
        assert sanitize_pdf_filename("My Marathon Plan") == "My_Marathon_Plan"

    def test_strips_slashes_and_quotes(self):
        from services.plan_pdf import sanitize_pdf_filename
        result = sanitize_pdf_filename('Plan "A"/B\\C')
        assert "/" not in result
        assert "\\" not in result
        assert '"' not in result

    def test_strips_control_chars(self):
        from services.plan_pdf import sanitize_pdf_filename
        assert "\n" not in sanitize_pdf_filename("Plan\nA")
        assert ";" not in sanitize_pdf_filename("Plan;A")

    def test_truncates_at_50_chars(self):
        from services.plan_pdf import sanitize_pdf_filename
        long_name = "A" * 100
        assert len(sanitize_pdf_filename(long_name)) <= 50

    def test_empty_name_returns_fallback(self):
        from services.plan_pdf import sanitize_pdf_filename
        assert sanitize_pdf_filename("") == "training_plan"
        assert sanitize_pdf_filename("!!!") == "training_plan"

    def test_preserves_hyphens(self):
        from services.plan_pdf import sanitize_pdf_filename
        assert sanitize_pdf_filename("Boston-Qualifier-2026") == "Boston-Qualifier-2026"


class TestDistanceFormat:
    def test_imperial_output(self):
        from services.plan_pdf import _fmt_distance
        result = _fmt_distance(10.0, "imperial")
        assert "mi" in result
        assert "6.2" in result  # 10 km ≈ 6.2 mi

    def test_metric_output(self):
        from services.plan_pdf import _fmt_distance
        result = _fmt_distance(10.0, "metric")
        assert "km" in result
        assert "10.0" in result

    def test_none_returns_dash(self):
        from services.plan_pdf import _fmt_distance
        assert _fmt_distance(None, "imperial") == "—"
        assert _fmt_distance(0, "metric") == "—"


class TestPaceFormat:
    def test_mmss_format(self):
        from services.plan_pdf import _fmt_mmss
        assert _fmt_mmss(300) == "5:00"   # 5:00/km = 300 sec/km
        assert _fmt_mmss(270) == "4:30"
        assert _fmt_mmss(495) == "8:15"

    def test_none_returns_none(self):
        from services.plan_pdf import _fmt_mmss
        assert _fmt_mmss(None) is None
        assert _fmt_mmss(0) is None

    def test_sec_km_to_sec_mi(self):
        from services.plan_pdf import _sec_km_to_sec_mi
        # 5:00/km ≈ 8:03/mi
        result = _sec_km_to_sec_mi(300)
        assert 480 < result < 490


# =============================================================================
# CATEGORY 2: template rendering — mock weasyprint, verify HTML content
# =============================================================================

class TestPdfRendering:
    """
    Test that the PDF service produces correct HTML and valid PDF bytes.
    Uses mock_weasyprint fixture so weasyprint need not be installed locally.
    """

    @staticmethod
    def _minimal_plan():
        plan = types.SimpleNamespace(
            id=uuid4(),
            name="Boston Qualifier 2026",
            goal_race_name="Boston Marathon",
            goal_race_date=date(2026, 4, 20),
            goal_race_distance_m=42195,
            plan_start_date=date(2025, 12, 1),
            plan_end_date=date(2026, 4, 20),
            total_weeks=2,
            baseline_rpi=55.0,
            status="active",
        )
        athlete = types.SimpleNamespace(
            id=uuid4(),
            display_name="Test Runner",
            email="runner@test.com",
            preferred_units="imperial",
        )
        workouts = [
            types.SimpleNamespace(
                week_number=1, day_of_week=1, workout_type="easy",
                phase="base", title="Easy Run", description="Easy effort",
                coach_notes="8:00/mile", target_distance_km=10.0,
                target_pace_per_km_seconds=300, target_pace_per_km_seconds_max=None,
            ),
            types.SimpleNamespace(
                week_number=1, day_of_week=6, workout_type="rest",
                phase="base", title="Rest", description=None,
                coach_notes=None, target_distance_km=None,
                target_pace_per_km_seconds=None, target_pace_per_km_seconds_max=None,
            ),
        ]
        return plan, athlete, workouts

    def test_pdf_generates_valid_bytes(self, mock_weasyprint):
        """generate_plan_pdf must return bytes starting with %PDF."""
        from services.plan_pdf import generate_plan_pdf
        plan, athlete, workouts = self._minimal_plan()
        pdf = generate_plan_pdf(plan, workouts, athlete)
        assert pdf.startswith(b"%PDF"), f"Expected PDF header, got: {pdf[:20]}"

    def test_pdf_html_contains_plan_name(self, mock_weasyprint):
        """The HTML passed to WeasyPrint must contain the plan name."""
        from services.plan_pdf import generate_plan_pdf
        plan, athlete, workouts = self._minimal_plan()
        generate_plan_pdf(plan, workouts, athlete)
        html = mock_weasyprint.get("html", "")
        assert "Boston Qualifier 2026" in html, "Plan name must appear in HTML"

    def test_pdf_html_contains_pace_reference_card(self, mock_weasyprint):
        """HTML must contain pace reference card section when RPI is available."""
        from services.plan_pdf import generate_plan_pdf
        plan, athlete, workouts = self._minimal_plan()
        mock_paces = {
            "easy": {"mi": "9:00", "km": "5:35"},
            "marathon": {"mi": "8:00", "km": "4:58"},
            "threshold": {"mi": "7:15", "km": "4:30"},
            "interval": {"mi": "6:30", "km": "4:02"},
            "repetition": {"mi": "5:45", "km": "3:35"},
        }
        with patch("services.rpi_calculator.calculate_training_paces", return_value=mock_paces):
            generate_plan_pdf(plan, workouts, athlete)
        html = mock_weasyprint.get("html", "")
        assert "Training Pace Reference" in html, "Pace card section header missing"
        assert "9:00" in html, "Easy pace must appear in HTML"
        assert "7:15" in html, "Threshold pace must appear in HTML"
        assert "/mi" in html, "Per-mile label must appear in pace card"
        assert "/km" in html, "Per-km label must appear in pace card"

    def test_pdf_html_contains_all_weeks(self, mock_weasyprint):
        """HTML must contain a section for every week in the plan."""
        from services.plan_pdf import generate_plan_pdf
        plan, athlete, workouts = self._minimal_plan()
        workouts.append(types.SimpleNamespace(
            week_number=2, day_of_week=1, workout_type="long",
            phase="build", title="Long Run", description="Steady",
            coach_notes=None, target_distance_km=22.0,
            target_pace_per_km_seconds=320, target_pace_per_km_seconds_max=None,
        ))
        generate_plan_pdf(plan, workouts, athlete)
        html = mock_weasyprint.get("html", "")
        assert "Week 1" in html
        assert "Week 2" in html

    def test_pdf_html_renders_rest_days(self, mock_weasyprint):
        """Rest-day rows must appear in the weekly table HTML."""
        from services.plan_pdf import generate_plan_pdf
        plan, athlete, workouts = self._minimal_plan()
        generate_plan_pdf(plan, workouts, athlete)
        html = mock_weasyprint.get("html", "")
        assert "Rest" in html, "Rest day must appear in HTML"

    def test_pdf_handles_missing_paces_gracefully(self, mock_weasyprint):
        """Plans with no pace fields still render without error."""
        from services.plan_pdf import generate_plan_pdf
        plan, athlete, workouts = self._minimal_plan()
        for w in workouts:
            w.target_pace_per_km_seconds = None
            w.target_pace_per_km_seconds_max = None
            w.coach_notes = None
        pdf = generate_plan_pdf(plan, workouts, athlete)
        assert pdf.startswith(b"%PDF")

    def test_pdf_handles_no_baseline_rpi(self, mock_weasyprint):
        """Plans without baseline_rpi render without a pace reference card."""
        from services.plan_pdf import generate_plan_pdf
        plan, athlete, workouts = self._minimal_plan()
        plan.baseline_rpi = None
        pdf = generate_plan_pdf(plan, workouts, athlete)
        assert pdf.startswith(b"%PDF")
        html = mock_weasyprint.get("html", "")
        assert "Training Pace Reference" not in html


# =============================================================================
# CATEGORY 3: Guardrail unit tests
# =============================================================================

class TestPdfGuardrails:
    """
    Verify that generate_plan_pdf raises RuntimeError for inputs that
    would exceed the safety limits defined in plan_pdf.py constants.
    All tests use the mock_weasyprint fixture so no WeasyPrint install needed.
    """

    @staticmethod
    def _plan():
        return types.SimpleNamespace(
            id=uuid4(), name="Guardrail Test Plan",
            goal_race_name=None, goal_race_date=None,
            goal_race_distance_m=None,
            plan_start_date=None, plan_end_date=None,
            total_weeks=1, baseline_rpi=None, status="active",
        )

    @staticmethod
    def _athlete():
        return types.SimpleNamespace(
            id=uuid4(), display_name="Runner",
            email="r@test.com", preferred_units="imperial",
        )

    @staticmethod
    def _workout(week: int, day: int = 1):
        return types.SimpleNamespace(
            week_number=week, day_of_week=day,
            workout_type="easy", phase="base",
            title="Easy Run", description="Easy effort",
            coach_notes=None, target_distance_km=8.0,
            target_pace_per_km_seconds=None,
            target_pace_per_km_seconds_max=None,
        )

    # ── 1. Workout-row cap ────────────────────────────────────────────────────
    # The row cap is checked against len(workouts) BEFORE grouping, so we
    # can trigger it with duplicated (week, day) entries — which is what
    # this guard is designed to catch (data anomalies bypassing the DB
    # unique constraint).

    def test_too_many_workout_rows_raises(self, mock_weasyprint):
        from services.plan_pdf import generate_plan_pdf, MAX_WORKOUT_ROWS
        plan = self._plan()
        athlete = self._athlete()
        # All in week 1, all same day — only len() matters for the cap
        workouts = [self._workout(week=1, day=0) for _ in range(MAX_WORKOUT_ROWS + 1)]
        with pytest.raises(RuntimeError, match="workout rows"):
            generate_plan_pdf(plan, workouts, athlete)

    def test_exactly_at_row_limit_does_not_raise(self, mock_weasyprint):
        from services.plan_pdf import generate_plan_pdf, MAX_WORKOUT_ROWS
        plan = self._plan()
        athlete = self._athlete()
        workouts = [self._workout(week=1, day=0) for _ in range(MAX_WORKOUT_ROWS)]
        # Should not raise; mock_weasyprint handles the render
        result = generate_plan_pdf(plan, workouts, athlete)
        assert result.startswith(b"%PDF")

    # ── 2. Week count cap ─────────────────────────────────────────────────────

    def test_too_many_weeks_raises(self, mock_weasyprint):
        from services.plan_pdf import generate_plan_pdf, MAX_PLAN_WEEKS
        plan = self._plan()
        athlete = self._athlete()
        # One workout per week, one over the week limit
        workouts = [self._workout(week=i + 1) for i in range(MAX_PLAN_WEEKS + 1)]
        with pytest.raises(RuntimeError, match="weeks"):
            generate_plan_pdf(plan, workouts, athlete)

    def test_exactly_at_week_limit_does_not_raise(self, mock_weasyprint):
        from services.plan_pdf import generate_plan_pdf, MAX_PLAN_WEEKS
        plan = self._plan()
        athlete = self._athlete()
        workouts = [self._workout(week=i + 1) for i in range(MAX_PLAN_WEEKS)]
        result = generate_plan_pdf(plan, workouts, athlete)
        assert result.startswith(b"%PDF")

    # ── 3. Output byte-size cap ───────────────────────────────────────────────

    def test_oversized_output_raises(self, monkeypatch):
        """WeasyPrint mock returns a PDF that exceeds MAX_PDF_BYTES."""
        import sys
        from services.plan_pdf import MAX_PDF_BYTES

        oversized = b"%PDF-1.4 " + b"x" * (MAX_PDF_BYTES + 1)

        def html_constructor(string=None, base_url=None, **kwargs):
            inst = MagicMock()
            inst.write_pdf.side_effect = lambda buf: buf.write(oversized)
            return inst

        mock_wp = MagicMock()
        mock_wp.HTML.side_effect = html_constructor
        monkeypatch.setitem(sys.modules, "weasyprint", mock_wp)

        from services.plan_pdf import generate_plan_pdf
        plan = self._plan()
        athlete = self._athlete()
        workouts = [self._workout(week=1)]
        with pytest.raises(RuntimeError, match="exceeds"):
            generate_plan_pdf(plan, workouts, athlete)

    def test_output_at_size_limit_succeeds(self, monkeypatch):
        """PDF exactly at MAX_PDF_BYTES must not raise."""
        import sys
        from services.plan_pdf import MAX_PDF_BYTES

        at_limit = b"%PDF-1.4 " + b"x" * (MAX_PDF_BYTES - len(b"%PDF-1.4 "))
        assert len(at_limit) == MAX_PDF_BYTES

        def html_constructor(string=None, base_url=None, **kwargs):
            inst = MagicMock()
            inst.write_pdf.side_effect = lambda buf: buf.write(at_limit)
            return inst

        mock_wp = MagicMock()
        mock_wp.HTML.side_effect = html_constructor
        monkeypatch.setitem(sys.modules, "weasyprint", mock_wp)

        from services.plan_pdf import generate_plan_pdf
        plan = self._plan()
        athlete = self._athlete()
        workouts = [self._workout(week=1)]
        result = generate_plan_pdf(plan, workouts, athlete)
        assert result.startswith(b"%PDF")

    # ── 4. Generation timeout ─────────────────────────────────────────────────

    def test_timeout_raises_runtime_error(self, monkeypatch):
        """WeasyPrint mock sleeps beyond the (patched) timeout budget."""
        import sys
        import time

        # Patch the module constant to 1 s BEFORE building the mock,
        # so generate_plan_pdf's future.result(timeout=1) fires quickly.
        monkeypatch.setattr("services.plan_pdf.GENERATION_TIMEOUT_SECONDS", 1)

        def html_constructor(string=None, base_url=None, **kwargs):
            inst = MagicMock()
            def slow_render(buf):
                time.sleep(5)  # 5 s >> 1 s patched timeout
                buf.write(FAKE_PDF)
            inst.write_pdf.side_effect = slow_render
            return inst

        mock_wp = MagicMock()
        mock_wp.HTML.side_effect = html_constructor
        monkeypatch.setitem(sys.modules, "weasyprint", mock_wp)

        from services.plan_pdf import generate_plan_pdf
        plan = self._plan()
        athlete = self._athlete()
        workouts = [self._workout(week=1)]
        with pytest.raises(RuntimeError, match="timed out"):
            generate_plan_pdf(plan, workouts, athlete)

    def test_fast_render_completes_within_timeout(self, mock_weasyprint):
        """A normal render (instant mock) completes successfully."""
        from services.plan_pdf import generate_plan_pdf
        plan = self._plan()
        athlete = self._athlete()
        workouts = [self._workout(week=1)]
        result = generate_plan_pdf(plan, workouts, athlete)
        assert result.startswith(b"%PDF")


# =============================================================================
# CATEGORY 4: Integration tests — GET /v1/plans/{plan_id}/pdf
# =============================================================================

class TestPdfEndpointAccessControl:
    """
    Access-control matrix for the PDF endpoint.
    generate_plan_pdf is patched so tests don't need WeasyPrint installed.
    """

    def test_pdf_endpoint_404_for_non_owner(self):
        """A plan belonging to another athlete returns 404 (not 403)."""
        owner = _make_athlete("guided")
        other = _make_athlete("guided")
        plan  = _make_plan(owner)
        try:
            resp = client.get(f"/v1/plans/{plan.id}/pdf", headers=_headers(other))
            assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
        finally:
            _cleanup(plan, owner, other)

    def test_pdf_endpoint_404_for_nonexistent_plan(self):
        """A non-existent plan_id returns 404."""
        athlete = _make_athlete("premium")
        try:
            resp = client.get(f"/v1/plans/{uuid4()}/pdf", headers=_headers(athlete))
            assert resp.status_code == 404
        finally:
            _cleanup(None, athlete)

    def test_pdf_endpoint_403_for_free_without_purchase(self):
        """Free athlete without a purchase record is blocked with 403."""
        athlete = _make_athlete("free")
        plan    = _make_plan(athlete)
        try:
            resp = client.get(f"/v1/plans/{plan.id}/pdf", headers=_headers(athlete))
            assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        finally:
            _cleanup(plan, athlete)

    def test_pdf_endpoint_200_for_plan_purchaser(self):
        """Free athlete who purchased this specific plan gets the PDF."""
        athlete  = _make_athlete("free")
        plan     = _make_plan(athlete)
        purchase = _make_purchase(athlete, plan)
        try:
            with patch("services.plan_pdf.generate_plan_pdf", return_value=FAKE_PDF):
                resp = client.get(f"/v1/plans/{plan.id}/pdf", headers=_headers(athlete))
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
            assert resp.headers["content-type"] == "application/pdf"
            assert resp.content == FAKE_PDF
        finally:
            _cleanup(plan, athlete)

    def test_pdf_endpoint_200_for_guided_athlete(self):
        """Guided-tier athlete gets PDF for their own plan."""
        athlete = _make_athlete("guided")
        plan    = _make_plan(athlete)
        try:
            with patch("services.plan_pdf.generate_plan_pdf", return_value=FAKE_PDF):
                resp = client.get(f"/v1/plans/{plan.id}/pdf", headers=_headers(athlete))
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "application/pdf"
        finally:
            _cleanup(plan, athlete)

    def test_pdf_endpoint_200_for_premium_athlete(self):
        """Premium-tier athlete gets PDF for their own plan."""
        athlete = _make_athlete("premium")
        plan    = _make_plan(athlete)
        try:
            with patch("services.plan_pdf.generate_plan_pdf", return_value=FAKE_PDF):
                resp = client.get(f"/v1/plans/{plan.id}/pdf", headers=_headers(athlete))
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "application/pdf"
        finally:
            _cleanup(plan, athlete)

    def test_pdf_endpoint_returns_correct_content_disposition(self):
        """Content-Disposition header contains a safe filename."""
        import re
        athlete = _make_athlete("guided")
        plan    = _make_plan(athlete)
        try:
            with patch("services.plan_pdf.generate_plan_pdf", return_value=FAKE_PDF):
                resp = client.get(f"/v1/plans/{plan.id}/pdf", headers=_headers(athlete))
            assert resp.status_code == 200
            cd = resp.headers.get("content-disposition", "")
            assert "attachment" in cd, "Must be attachment, not inline"
            assert ".pdf" in cd, "Filename must have .pdf extension"
            filename_match = re.search(r'filename="([^"]+)"', cd)
            assert filename_match, "content-disposition must include quoted filename"
            fname = filename_match.group(1)
            assert "/" not in fname
            assert "\\" not in fname
        finally:
            _cleanup(plan, athlete)

    def test_pdf_endpoint_unauthenticated_returns_401(self):
        """Unauthenticated requests must be rejected."""
        resp = client.get(f"/v1/plans/{uuid4()}/pdf")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"
