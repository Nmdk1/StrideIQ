"""Regression: `ensure_fresh_token` must accept naive `strava_token_expires_at`.

Some athletes have their `strava_token_expires_at` stored as a timezone-naive
datetime (historical Garmin/Strava OAuth flows wrote naive UTC values even
though the column is declared `DateTime(timezone=True)`).  The pre-flight
comparison `if expires_at > now + timedelta(minutes=5)` raised
`TypeError: can't compare offset-naive and offset-aware datetimes` for those
athletes, which surfaced for the first time when the new Strava-fallback
worker started calling `ensure_fresh_token` on every Garmin->Strava repair.

This test pins the fix: a naive `expires_at` in the future means "token
fresh" (no refresh attempted, no exception)."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from services.sync.strava_service import ensure_fresh_token


def test_ensure_fresh_token_handles_naive_expires_at_no_exception():
    """Naive expires_at in the future is treated as UTC and skips refresh."""
    athlete = SimpleNamespace(
        id="test-athlete",
        strava_access_token="encrypted-blob",
        strava_refresh_token="encrypted-blob",
        # The bug: naive datetime, well in the future.
        strava_token_expires_at=datetime.utcnow() + timedelta(hours=1),
    )

    result = ensure_fresh_token(athlete, db=None)

    assert result is True


def test_ensure_fresh_token_handles_naive_expires_at_in_past_triggers_refresh(
    monkeypatch,
):
    """Naive expires_at in the past must trigger refresh, not raise.

    We monkeypatch `decrypt_token` and `refresh_access_token` so the test
    stays a pure unit test (no network, no DB).
    """
    import services.sync.strava_service as svc

    monkeypatch.setattr(svc, "refresh_access_token", lambda token: {
        "access_token": "new",
        "refresh_token": "new_refresh",
        "expires_at": int((datetime.now(timezone.utc) + timedelta(hours=6)).timestamp()),
    })
    from services import token_encryption as tenc

    monkeypatch.setattr(tenc, "decrypt_token", lambda blob: "decrypted_refresh")
    monkeypatch.setattr(tenc, "encrypt_token", lambda raw: f"enc:{raw}")

    class _StubDB:
        def commit(self):
            pass

    athlete = SimpleNamespace(
        id="test-athlete-2",
        strava_access_token="encrypted-blob",
        strava_refresh_token="encrypted-blob",
        # Expired 1 hour ago, naive.
        strava_token_expires_at=datetime.utcnow() - timedelta(hours=1),
    )

    result = ensure_fresh_token(athlete, db=_StubDB())

    assert result is True
    assert athlete.strava_access_token == "enc:new"
    # New expires_at must be tz-aware after refresh.
    assert athlete.strava_token_expires_at.tzinfo is not None
