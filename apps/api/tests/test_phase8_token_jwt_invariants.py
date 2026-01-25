from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import or_

import core.security as security
from core.database import SessionLocal
from main import app
from models import AdminAuditEvent, Athlete


client = TestClient(app)


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_user(db, *, role: str) -> Athlete:
    athlete = Athlete(
        email=f"phase8_jwt_{role}_{uuid4()}@example.com",
        display_name=f"Phase8 JWT {role}",
        subscription_tier="elite" if role in ("admin", "owner") else "free",
        role=role,
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    return athlete


def _token_valid(user: Athlete) -> str:
    return security.create_access_token({"sub": str(user.id)})


def _token_expired(user: Athlete) -> str:
    # Negative expiry produces a token whose exp is in the past.
    return security.create_access_token({"sub": str(user.id)}, expires_delta=timedelta(minutes=-1))


def _token_tampered(valid_token: str) -> str:
    # Flip one character in the signature segment; structure stays JWT-like but verification must fail.
    parts = valid_token.split(".")
    assert len(parts) == 3, "Expected JWT with 3 segments"
    sig = parts[2]
    if not sig:
        parts[2] = "x"
    else:
        last = sig[-1]
        parts[2] = sig[:-1] + ("A" if last != "A" else "B")
    return ".".join(parts)


def _token_signed_with_secret(user: Athlete, *, secret: str, expires_delta: timedelta | None = None) -> str:
    payload = {"sub": str(user.id)}
    exp = datetime.utcnow() + (expires_delta or timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload["exp"] = exp
    return jwt.encode(payload, secret, algorithm=security.ALGORITHM)


def _cleanup(db, athlete_ids: list, *, include_audit_events: bool = True) -> None:
    # Delete audit events first to avoid FK violations when removing athletes.
    try:
        if include_audit_events and athlete_ids:
            db.query(AdminAuditEvent).filter(
                or_(
                    AdminAuditEvent.actor_athlete_id.in_(athlete_ids),
                    AdminAuditEvent.target_athlete_id.in_(athlete_ids),
                )
            ).delete(synchronize_session=False)

        if athlete_ids:
            db.query(Athlete).filter(Athlete.id.in_(athlete_ids)).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()


def test_valid_token_succeeds_on_athlete_protected_endpoint():
    """
    Positive control: a valid, non-expired token can access an athlete-protected endpoint.
    """
    db = SessionLocal()
    user = None
    try:
        user = _create_user(db, role="athlete")
        resp = client.get("/v1/gdpr/export", headers=_auth_headers(_token_valid(user)))
        assert resp.status_code == 200, resp.text
    finally:
        try:
            if user is not None:
                _cleanup(db, [user.id], include_audit_events=False)
        finally:
            db.close()


def test_expired_token_is_401_on_protected_endpoints():
    """
    Expired token → 401 on protected endpoints.
    """
    db = SessionLocal()
    athlete = None
    admin = None
    try:
        athlete = _create_user(db, role="athlete")
        admin = _create_user(db, role="admin")

        resp = client.get("/v1/gdpr/export", headers=_auth_headers(_token_expired(athlete)))
        assert resp.status_code == 401, resp.text

        resp = client.get("/v1/admin/users", headers=_auth_headers(_token_expired(admin)))
        assert resp.status_code == 401, resp.text
    finally:
        try:
            ids = [u.id for u in (athlete, admin) if u is not None]
            _cleanup(db, ids)
        finally:
            db.close()


def test_tampered_or_invalid_signature_token_is_401():
    """
    Tampered/invalid signature → 401.
    """
    db = SessionLocal()
    user = None
    try:
        user = _create_user(db, role="athlete")
        valid = _token_valid(user)
        tampered = _token_tampered(valid)

        resp = client.get("/v1/gdpr/export", headers=_auth_headers(tampered))
        assert resp.status_code == 401, resp.text
    finally:
        try:
            if user is not None:
                _cleanup(db, [user.id], include_audit_events=False)
        finally:
            db.close()


def test_token_signed_with_wrong_secret_is_401():
    """
    Token signed with a different secret must be rejected (401).
    """
    db = SessionLocal()
    user = None
    try:
        user = _create_user(db, role="athlete")
        wrong_secret = "wrong_secret_" + ("x" * 40)  # keep >= 32 chars
        token = _token_signed_with_secret(user, secret=wrong_secret, expires_delta=timedelta(minutes=5))

        resp = client.get("/v1/gdpr/export", headers=_auth_headers(token))
        assert resp.status_code == 401, resp.text
    finally:
        try:
            if user is not None:
                _cleanup(db, [user.id], include_audit_events=False)
        finally:
            db.close()


def test_rotation_invalidates_old_token_and_new_token_succeeds(monkeypatch):
    """
    Rotation (old valid token after rotation) → 401.
    Positive control: new token minted after rotation succeeds.
    """
    db = SessionLocal()
    user = None
    try:
        user = _create_user(db, role="athlete")

        old_secret = "old_secret_" + ("a" * 40)
        new_secret = "new_secret_" + ("b" * 40)

        # Mint under old secret.
        monkeypatch.setattr(security, "SECRET_KEY", old_secret)
        old_token = _token_valid(user)

        # Rotate to new secret: old token must fail.
        monkeypatch.setattr(security, "SECRET_KEY", new_secret)
        resp = client.get("/v1/gdpr/export", headers=_auth_headers(old_token))
        assert resp.status_code == 401, resp.text

        # Mint under new secret: must succeed.
        new_token = _token_valid(user)
        resp_ok = client.get("/v1/gdpr/export", headers=_auth_headers(new_token))
        assert resp_ok.status_code == 200, resp_ok.text
    finally:
        try:
            if user is not None:
                _cleanup(db, [user.id], include_audit_events=False)
        finally:
            db.close()


def test_expired_impersonation_token_is_401(monkeypatch):
    """
    Impersonation TTL enforcement: expired impersonation token → 401.
    Positive control: fresh impersonation token works on athlete-protected endpoint.
    """
    db = SessionLocal()
    owner = None
    admin = None
    try:
        owner = _create_user(db, role="owner")
        admin = _create_user(db, role="admin")

        # Owner mints impersonation token for the admin.
        resp = client.post(
            f"/v1/admin/users/{admin.id}/impersonate",
            headers=_auth_headers(_token_valid(owner)),
            json={"reason": "phase8 jwt invariants test", "ttl_minutes": 15},
        )
        assert resp.status_code == 200, resp.text
        imp_token = resp.json()["token"]

        # Positive control: token works on a protected endpoint.
        ok = client.get("/v1/gdpr/export", headers=_auth_headers(imp_token))
        assert ok.status_code == 200, ok.text

        # Force-expire the impersonation token by re-signing the same claims with exp in the past.
        claims = jwt.decode(
            imp_token,
            security.SECRET_KEY,
            algorithms=[security.ALGORITHM],
            options={"verify_exp": False},
        )
        claims["exp"] = datetime.utcnow() - timedelta(minutes=1)
        expired_imp = jwt.encode(claims, security.SECRET_KEY, algorithm=security.ALGORITHM)

        resp_expired = client.get("/v1/gdpr/export", headers=_auth_headers(expired_imp))
        assert resp_expired.status_code == 401, resp_expired.text
    finally:
        try:
            ids = [u.id for u in (owner, admin) if u is not None]
            _cleanup(db, ids)
        finally:
            db.close()

