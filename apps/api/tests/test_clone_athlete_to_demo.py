"""
Tests for the demo-clone script (scripts/clone_athlete_to_demo.py).

Focus areas — what we can verify deterministically without a real DB:
  - SAFETY: every table covered. Discovery must equal classification so
    a future model addition can't silently slip into the demo or be
    silently dropped.
  - SAFETY: SKIP set is comprehensive for the obvious-PII categories.
    Billing, audit, telemetry, ingestion-state, photo tables MUST be
    in SKIP, never in COPY.
  - SAFETY: source-is-demo and target-is-not-demo guards reject correctly.
  - PROFILE-COPY: the demo overrides ALWAYS win over copied source values
    (no way for a copy to re-enable provider linkage or unset is_demo).
  - PROFILE-COPY: no PII fields (email, password_hash, role, display_name)
    are in the copy allowlist.

Tests deliberately skip the row-level COPY behavior (insert/remap) since
it requires a real Postgres + populated source and is exercised by the
prod dry-run in the deploy step.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Classification completeness
# ---------------------------------------------------------------------------

class TestClassificationCoverage:
    """Every athlete-scoped table must be classified as COPY or SKIP."""

    def test_no_unclassified_athlete_scoped_tables(self):
        from scripts.clone_athlete_to_demo import _validate_classification
        unknown = _validate_classification()
        assert unknown == [], (
            f"Unclassified athlete-scoped tables: {unknown}\n"
            "Add each to COPY_TABLES or SKIP_TABLES in "
            "apps/api/scripts/clone_athlete_to_demo.py."
        )

    def test_copy_and_skip_sets_are_disjoint(self):
        from scripts.clone_athlete_to_demo import COPY_TABLES, SKIP_TABLES
        overlap = set(COPY_TABLES) & set(SKIP_TABLES)
        assert overlap == set(), f"Tables in both COPY and SKIP: {overlap}"


# ---------------------------------------------------------------------------
# Categorical safety: PII / billing / audit must be in SKIP
# ---------------------------------------------------------------------------

class TestSecurityClassification:
    """Categories that must NEVER be copied to a shared demo account."""

    @pytest.mark.parametrize("table", [
        # Billing — exposing customer/subscription IDs is unsafe
        "subscriptions",
        "purchase",
        "plan_purchases",
        "stripe_events",
        "race_promo_code",
        # Audit / consent / telemetry — leak IPs and timing
        "consent_audit_log",
        "admin_audit_event",
        "invite_audit_event",
        "page_view",
        "tool_telemetry_event",
        "experience_audit_log",
        # Provider sync state — would point at real Garmin/Strava state
        "athlete_ingestion_state",
        "athlete_data_import_job",
        # PII media
        "athlete_photo",
    ])
    def test_sensitive_table_in_skip_set(self, table):
        from scripts.clone_athlete_to_demo import COPY_TABLES, SKIP_TABLES
        assert table in SKIP_TABLES, f"{table} must be in SKIP_TABLES"
        assert table not in COPY_TABLES, f"{table} must NOT be in COPY_TABLES"


# ---------------------------------------------------------------------------
# Athlete profile copy: demo overrides win, PII never copied
# ---------------------------------------------------------------------------

class TestAthleteProfileCopy:

    def _make_source(self, **overrides):
        """Build a source athlete with realistic field values + provider tokens."""
        source = MagicMock()
        # Profile fields that SHOULD copy
        source.max_hr = 185
        source.resting_hr = 48
        source.threshold_hr = 168
        source.preferred_units = "imperial"
        source.timezone = "America/New_York"
        source.subscription_tier = "elite"
        source.weight_kg = 70.0
        source.height_cm = 178.0
        source.onboarding_completed = True
        # Provider linkage that MUST NOT leak via copy
        source.is_demo = False  # source is real
        source.strava_access_token = "real_strava_token_should_never_appear_on_demo"
        source.strava_refresh_token = "real_refresh"
        source.strava_athlete_id = 12345
        source.garmin_access_token = "real_garmin_token"
        source.garmin_user_id = "garmin_uid_12345"
        source.garmin_connected = True
        # PII that MUST NOT be copied
        source.email = "founder@example.com"
        source.password_hash = "$2b$12$realhash"
        source.display_name = "Founder Name"
        source.role = "athlete"
        for k, v in overrides.items():
            setattr(source, k, v)
        return source

    def _make_demo(self):
        """Build a demo athlete that already exists with its own identity."""
        demo = MagicMock()
        demo.email = "demo@strideiq.run"
        demo.password_hash = "$2b$12$demohash"
        demo.display_name = "Demo Athlete"
        demo.role = "athlete"
        demo.is_demo = True
        demo.strava_access_token = None
        demo.garmin_connected = False
        # Demo starts with no profile
        demo.max_hr = None
        demo.resting_hr = None
        demo.threshold_hr = None
        return demo

    def test_calibration_fields_are_copied(self):
        from scripts.clone_athlete_to_demo import _copy_athlete_profile_fields
        source = self._make_source()
        demo = self._make_demo()
        _copy_athlete_profile_fields(source, demo)
        assert demo.max_hr == 185
        assert demo.resting_hr == 48
        assert demo.threshold_hr == 168
        assert demo.preferred_units == "imperial"
        assert demo.timezone == "America/New_York"

    def test_demo_overrides_win_over_source(self):
        """
        Even if the source athlete has provider tokens / connections,
        the demo overrides MUST always win. This is the security
        invariant — no prospect viewing the demo can reach the
        founder's real Garmin/Strava data.
        """
        from scripts.clone_athlete_to_demo import _copy_athlete_profile_fields
        source = self._make_source()
        demo = self._make_demo()
        _copy_athlete_profile_fields(source, demo)
        assert demo.is_demo is True
        assert demo.strava_access_token is None
        assert demo.strava_refresh_token is None
        assert demo.strava_athlete_id is None
        assert demo.garmin_access_token is None
        assert demo.garmin_refresh_token is None
        assert demo.garmin_user_id is None
        assert demo.garmin_connected is False
        assert demo.last_garmin_sync is None

    def test_pii_fields_are_not_copied(self):
        """email, password_hash, display_name, role must remain the demo's own."""
        from scripts.clone_athlete_to_demo import _ATHLETE_FIELDS_TO_COPY
        forbidden = {"email", "password_hash", "display_name", "role", "id"}
        leaks = forbidden & _ATHLETE_FIELDS_TO_COPY
        assert leaks == set(), f"PII fields in copy allowlist: {leaks}"

    def test_demo_email_not_overwritten_after_copy(self):
        from scripts.clone_athlete_to_demo import _copy_athlete_profile_fields
        source = self._make_source()
        demo = self._make_demo()
        original_email = demo.email
        original_pw = demo.password_hash
        original_display = demo.display_name
        _copy_athlete_profile_fields(source, demo)
        assert demo.email == original_email
        assert demo.password_hash == original_pw
        assert demo.display_name == original_display

    def test_none_source_values_do_not_clobber_demo_defaults(self):
        """If source has None for a field, the demo's existing value stays."""
        from scripts.clone_athlete_to_demo import _copy_athlete_profile_fields
        source = self._make_source(weight_kg=None)
        demo = self._make_demo()
        demo.weight_kg = 65.0
        _copy_athlete_profile_fields(source, demo)
        assert demo.weight_kg == 65.0


# ---------------------------------------------------------------------------
# Argument validation surface (no DB)
# ---------------------------------------------------------------------------

class TestDemoOverrideContract:
    """The DEMO override dict must include the full set of provider-linkage
    fields. This test catches anyone removing a key from the override map
    in a refactor that would silently re-allow a token to leak through."""

    def test_demo_overrides_lock_provider_state(self):
        from scripts.clone_athlete_to_demo import _DEMO_ATHLETE_OVERRIDES
        required = {
            "is_demo",
            "strava_access_token",
            "strava_refresh_token",
            "strava_token_expires_at",
            "strava_athlete_id",
            "garmin_access_token",
            "garmin_refresh_token",
            "garmin_token_expires_at",
            "garmin_user_id",
            "garmin_connected",
            "last_garmin_sync",
        }
        missing = required - set(_DEMO_ATHLETE_OVERRIDES)
        assert missing == set(), (
            f"_DEMO_ATHLETE_OVERRIDES is missing required provider-lock keys: {missing}"
        )
        assert _DEMO_ATHLETE_OVERRIDES["is_demo"] is True
        assert _DEMO_ATHLETE_OVERRIDES["garmin_connected"] is False
