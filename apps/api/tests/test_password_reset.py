"""
Password Reset Tests

Tests for both:
1. Self-service password reset (forgot password flow)
2. Admin password reset
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from jose import jwt
from fastapi.testclient import TestClient

from main import app
from core.database import SessionLocal
from core.security import SECRET_KEY, ALGORITHM, get_password_hash, verify_password, create_access_token
from models import Athlete

client = TestClient(app)


def _headers(user: Athlete) -> dict:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def db():
    """Database session fixture with rollback for test isolation."""
    session = SessionLocal()
    try:
        yield session
    finally:
        # Rollback any uncommitted changes to avoid FK issues
        session.rollback()
        session.close()


@pytest.fixture
def test_user(db):
    """Create a test user with a known password."""
    athlete = Athlete(
        email=f"pwdreset_{uuid4()}@example.com",
        password_hash=get_password_hash("OldPassword123!"),
        display_name="Password Test User",
        role="athlete",
        subscription_tier="free",
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    return athlete  # No cleanup - users persist (unique emails prevent conflicts)


@pytest.fixture
def owner_user(db):
    """Create an owner user for admin tests."""
    athlete = Athlete(
        email=f"owner_{uuid4()}@example.com",
        password_hash=get_password_hash("OwnerPass123!"),
        display_name="Owner User",
        role="owner",
        subscription_tier="pro",
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    return athlete  # No cleanup - users persist (unique emails prevent conflicts)


class TestForgotPasswordEndpoint:
    """Tests for POST /v1/auth/forgot-password"""

    def test_forgot_password_existing_user(self, test_user):
        """Should return success for existing user (email would be sent)"""
        response = client.post(
            "/v1/auth/forgot-password",
            json={"email": test_user.email}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "message" in data

    def test_forgot_password_nonexistent_user(self):
        """Should return success even for non-existent user (prevents enumeration)"""
        response = client.post(
            "/v1/auth/forgot-password",
            json={"email": "nonexistent_pwdreset@example.com"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Same message as existing user to prevent enumeration
        assert "message" in data

    def test_forgot_password_invalid_email_format(self):
        """Should reject invalid email format"""
        response = client.post(
            "/v1/auth/forgot-password",
            json={"email": "not-an-email"}
        )
        assert response.status_code == 422  # Validation error

    def test_forgot_password_empty_email(self):
        """Should reject empty email"""
        response = client.post(
            "/v1/auth/forgot-password",
            json={"email": ""}
        )
        assert response.status_code == 422


class TestResetPasswordEndpoint:
    """Tests for POST /v1/auth/reset-password"""

    def test_reset_password_valid_token(self, test_user, db):
        """Should reset password with valid token"""
        # Generate a valid reset token
        reset_token = jwt.encode(
            {
                "sub": str(test_user.id),
                "email": test_user.email,
                "purpose": "password_reset",
                "exp": datetime.utcnow() + timedelta(hours=1),
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )

        new_password = "NewSecurePassword123!"
        response = client.post(
            "/v1/auth/reset-password",
            json={"token": reset_token, "new_password": new_password}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "reset" in data["message"].lower()

        # Verify the password was actually changed
        db.refresh(test_user)
        assert verify_password(new_password, test_user.password_hash)

    def test_reset_password_expired_token(self, test_user):
        """Should reject expired token"""
        # Generate an expired token
        reset_token = jwt.encode(
            {
                "sub": str(test_user.id),
                "email": test_user.email,
                "purpose": "password_reset",
                "exp": datetime.utcnow() - timedelta(hours=1),  # Expired
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )

        response = client.post(
            "/v1/auth/reset-password",
            json={"token": reset_token, "new_password": "NewPassword123!"}
        )
        assert response.status_code == 400
        assert "expired" in response.json()["detail"].lower() or "invalid" in response.json()["detail"].lower()

    def test_reset_password_invalid_token(self):
        """Should reject invalid token"""
        response = client.post(
            "/v1/auth/reset-password",
            json={"token": "invalid-token-here", "new_password": "NewPassword123!"}
        )
        assert response.status_code == 400

    def test_reset_password_wrong_purpose(self, test_user):
        """Should reject token with wrong purpose"""
        # Generate a token with wrong purpose (e.g., access token)
        wrong_token = jwt.encode(
            {
                "sub": str(test_user.id),
                "email": test_user.email,
                "purpose": "access",  # Wrong purpose
                "exp": datetime.utcnow() + timedelta(hours=1),
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )

        response = client.post(
            "/v1/auth/reset-password",
            json={"token": wrong_token, "new_password": "NewPassword123!"}
        )
        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()

    def test_reset_password_short_password(self, test_user):
        """Should reject password less than 8 characters"""
        reset_token = jwt.encode(
            {
                "sub": str(test_user.id),
                "email": test_user.email,
                "purpose": "password_reset",
                "exp": datetime.utcnow() + timedelta(hours=1),
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )

        response = client.post(
            "/v1/auth/reset-password",
            json={"token": reset_token, "new_password": "short"}  # Only 5 chars
        )
        assert response.status_code == 400
        assert "8 characters" in response.json()["detail"]

    def test_reset_password_nonexistent_user(self):
        """Should reject token for non-existent user"""
        # Generate token for non-existent user ID
        reset_token = jwt.encode(
            {
                "sub": "00000000-0000-0000-0000-000000000000",
                "email": "nonexistent@example.com",
                "purpose": "password_reset",
                "exp": datetime.utcnow() + timedelta(hours=1),
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )

        response = client.post(
            "/v1/auth/reset-password",
            json={"token": reset_token, "new_password": "NewPassword123!"}
        )
        assert response.status_code == 400


class TestAdminPasswordReset:
    """Tests for POST /v1/admin/users/{user_id}/password/reset"""

    def test_admin_reset_password_success(self, owner_user, test_user, db):
        """Owner should be able to reset another user's password"""
        response = client.post(
            f"/v1/admin/users/{test_user.id}/password/reset",
            headers=_headers(owner_user),
            json={"reason": "User locked out"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "temporary_password" in data
        assert len(data["temporary_password"]) >= 10  # Secure password length
        assert data["email"] == test_user.email

        # Verify the password was changed
        db.refresh(test_user)
        assert verify_password(data["temporary_password"], test_user.password_hash)

    def test_admin_reset_password_unauthorized(self, test_user):
        """Should reject unauthenticated request"""
        response = client.post(
            f"/v1/admin/users/{test_user.id}/password/reset",
            json={"reason": "Test"}
        )
        assert response.status_code == 401

    def test_admin_reset_password_nonexistent_user(self, owner_user):
        """Should return 404 for non-existent user"""
        response = client.post(
            "/v1/admin/users/00000000-0000-0000-0000-000000000000/password/reset",
            headers=_headers(owner_user),
            json={"reason": "Test"}
        )
        assert response.status_code == 404

    def test_admin_reset_password_audit_logged(self, owner_user, test_user, db):
        """Should create audit log entry for password reset"""
        from models import AdminAuditEvent

        # Count existing audit events
        before_count = db.query(AdminAuditEvent).filter(
            AdminAuditEvent.action == "password.reset"
        ).count()

        response = client.post(
            f"/v1/admin/users/{test_user.id}/password/reset",
            headers=_headers(owner_user),
            json={"reason": "Audit test"}
        )
        assert response.status_code == 200

        # Verify audit event was created
        db.commit()  # Ensure changes are visible
        after_count = db.query(AdminAuditEvent).filter(
            AdminAuditEvent.action == "password.reset"
        ).count()
        assert after_count == before_count + 1

        # Verify audit event does NOT contain the password
        audit_event = db.query(AdminAuditEvent).filter(
            AdminAuditEvent.action == "password.reset",
            AdminAuditEvent.target_athlete_id == str(test_user.id)
        ).order_by(AdminAuditEvent.created_at.desc()).first()

        assert audit_event is not None
        # Password should NOT be in the payload
        payload_str = str(audit_event.payload)
        assert "temporary_password" not in payload_str
        assert response.json()["temporary_password"] not in payload_str


class TestLoginAfterPasswordReset:
    """Integration tests for login after password reset"""

    def test_login_with_new_password_after_self_reset(self, test_user, db):
        """Should be able to login with new password after self-service reset"""
        # Generate reset token
        reset_token = jwt.encode(
            {
                "sub": str(test_user.id),
                "email": test_user.email,
                "purpose": "password_reset",
                "exp": datetime.utcnow() + timedelta(hours=1),
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )

        new_password = "MyNewSecurePassword123!"

        # Reset password
        reset_response = client.post(
            "/v1/auth/reset-password",
            json={"token": reset_token, "new_password": new_password}
        )
        assert reset_response.status_code == 200

        # Try to login with new password
        login_response = client.post(
            "/v1/auth/login",
            json={"email": test_user.email, "password": new_password}
        )
        assert login_response.status_code == 200
        assert "access_token" in login_response.json()

    def test_login_with_old_password_fails_after_reset(self, test_user, db):
        """Should NOT be able to login with old password after reset"""
        old_password = "OldPassword123!"
        
        # Set a known old password first
        test_user.password_hash = get_password_hash(old_password)
        db.add(test_user)
        db.commit()

        # Verify old password works
        login_response = client.post(
            "/v1/auth/login",
            json={"email": test_user.email, "password": old_password}
        )
        assert login_response.status_code == 200

        # Reset password
        reset_token = jwt.encode(
            {
                "sub": str(test_user.id),
                "email": test_user.email,
                "purpose": "password_reset",
                "exp": datetime.utcnow() + timedelta(hours=1),
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )

        new_password = "NewPassword456!"
        reset_response = client.post(
            "/v1/auth/reset-password",
            json={"token": reset_token, "new_password": new_password}
        )
        assert reset_response.status_code == 200

        # Old password should now fail
        login_response = client.post(
            "/v1/auth/login",
            json={"email": test_user.email, "password": old_password}
        )
        assert login_response.status_code == 401

    def test_login_with_admin_reset_password(self, owner_user, test_user, db):
        """Should be able to login with admin-generated temporary password"""
        # Admin resets password
        reset_response = client.post(
            f"/v1/admin/users/{test_user.id}/password/reset",
            headers=_headers(owner_user),
            json={"reason": "Test login"}
        )
        assert reset_response.status_code == 200
        temp_password = reset_response.json()["temporary_password"]

        # Login with temporary password
        login_response = client.post(
            "/v1/auth/login",
            json={"email": test_user.email, "password": temp_password}
        )
        assert login_response.status_code == 200
        assert "access_token" in login_response.json()
