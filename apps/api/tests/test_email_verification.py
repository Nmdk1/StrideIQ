"""
Tests for Email Verification Service

Ensures email change requires verification before taking effect.
Reference: H6 in Security Audit Report (External Security Report)
"""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import patch, MagicMock

from services.email_verification import (
    generate_email_change_token,
    verify_email_change_token,
    initiate_email_change,
    complete_email_change,
    EMAIL_CHANGE_TOKEN_EXPIRE_HOURS,
)


class TestEmailChangeTokenGeneration:
    """Tests for token generation"""
    
    def test_generates_valid_token(self):
        """Should generate a decodable token"""
        user_id = str(uuid4())
        new_email = "new@example.com"
        
        token = generate_email_change_token(user_id, new_email)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are substantial
    
    def test_token_contains_required_fields(self):
        """Token should contain user_id, new_email, purpose"""
        user_id = str(uuid4())
        new_email = "new@example.com"
        
        token = generate_email_change_token(user_id, new_email)
        payload = verify_email_change_token(token)
        
        assert payload is not None
        assert payload["sub"] == user_id
        assert payload["new_email"] == new_email
        assert payload["purpose"] == "email_change"
    
    def test_email_normalized(self):
        """Email should be lowercased and stripped"""
        user_id = str(uuid4())
        
        token = generate_email_change_token(user_id, "  NEW@EXAMPLE.COM  ")
        payload = verify_email_change_token(token)
        
        assert payload["new_email"] == "new@example.com"


class TestEmailChangeTokenVerification:
    """Tests for token verification"""
    
    def test_valid_token_verified(self):
        """Should verify a valid token"""
        user_id = str(uuid4())
        new_email = "new@example.com"
        
        token = generate_email_change_token(user_id, new_email)
        payload = verify_email_change_token(token)
        
        assert payload is not None
        assert payload["sub"] == user_id
    
    def test_invalid_token_rejected(self):
        """Should reject an invalid token"""
        payload = verify_email_change_token("invalid.token.here")
        assert payload is None
    
    def test_tampered_token_rejected(self):
        """Should reject a tampered token"""
        user_id = str(uuid4())
        new_email = "new@example.com"
        
        token = generate_email_change_token(user_id, new_email)
        # Tamper with the token
        parts = token.split(".")
        parts[1] = parts[1][::-1]  # Reverse payload
        tampered = ".".join(parts)
        
        payload = verify_email_change_token(tampered)
        assert payload is None
    
    def test_expired_token_rejected(self):
        """Should reject an expired token"""
        from jose import jwt
        from core.security import SECRET_KEY, ALGORITHM
        
        # Create an expired token manually
        expired_payload = {
            "sub": str(uuid4()),
            "new_email": "new@example.com",
            "purpose": "email_change",
            "exp": datetime.utcnow() - timedelta(hours=1),  # Expired
            "iat": datetime.utcnow() - timedelta(hours=25),
        }
        expired_token = jwt.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)
        
        payload = verify_email_change_token(expired_token)
        assert payload is None
    
    def test_wrong_purpose_rejected(self):
        """Should reject a token with wrong purpose"""
        from jose import jwt
        from core.security import SECRET_KEY, ALGORITHM
        
        wrong_purpose_payload = {
            "sub": str(uuid4()),
            "new_email": "new@example.com",
            "purpose": "password_reset",  # Wrong purpose
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        token = jwt.encode(wrong_purpose_payload, SECRET_KEY, algorithm=ALGORITHM)
        
        payload = verify_email_change_token(token)
        assert payload is None


class TestInitiateEmailChange:
    """Tests for initiating email change"""
    
    @pytest.fixture
    def mock_athlete(self):
        """Create a mock athlete"""
        athlete = MagicMock()
        athlete.id = uuid4()
        athlete.email = "old@example.com"
        athlete.display_name = "Test User"
        return athlete
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session"""
        return MagicMock()
    
    @patch('services.email_service.send_email')
    def test_sends_verification_email(self, mock_send_email, mock_db, mock_athlete):
        """Should send verification email to new address"""
        mock_send_email.return_value = None  # No exception = success
        
        result = initiate_email_change(mock_db, mock_athlete, "new@example.com")
        
        assert result is True
        mock_send_email.assert_called_once()
        
        # Check email was sent to NEW address
        call_args = mock_send_email.call_args
        assert call_args[1]["to_email"] == "new@example.com"
    
    @patch('services.email_service.send_email')
    def test_email_contains_verification_link(self, mock_send_email, mock_db, mock_athlete):
        """Verification email should contain a link with token"""
        mock_send_email.return_value = None
        
        initiate_email_change(mock_db, mock_athlete, "new@example.com")
        
        call_args = mock_send_email.call_args
        html_content = call_args[1]["html_content"]
        
        assert "verify-email-change" in html_content
        assert "token=" in html_content


class TestCompleteEmailChange:
    """Tests for completing email change"""
    
    @pytest.fixture
    def test_athlete(self, db):
        """Create a test athlete"""
        from models import Athlete
        
        # Clean up any existing
        existing = db.query(Athlete).filter(Athlete.email == "emailchange_test@example.com").first()
        if existing:
            db.delete(existing)
            db.commit()
        
        athlete = Athlete(
            email="emailchange_test@example.com",
            display_name="Email Change Test",
            subscription_tier="free"
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)
        
        yield athlete
        
        # Cleanup
        db.query(Athlete).filter(Athlete.id == athlete.id).delete()
        db.commit()
    
    @patch('services.email_service.send_email')
    def test_valid_token_changes_email(self, mock_send_email, db, test_athlete):
        """Valid token should update the email"""
        mock_send_email.return_value = None
        new_email = "changed_email@example.com"
        token = generate_email_change_token(str(test_athlete.id), new_email)

        success, message = complete_email_change(db, token)

        assert success is True
        assert new_email in message

        # Verify email was actually changed
        db.refresh(test_athlete)
        assert test_athlete.email == new_email
    
    def test_invalid_token_rejected(self, db):
        """Invalid token should be rejected"""
        success, message = complete_email_change(db, "invalid.token.here")
        
        assert success is False
        assert "invalid" in message.lower() or "expired" in message.lower()
    
    @patch('services.email_service.send_email')
    def test_email_already_taken_rejected(self, mock_send_email, db, test_athlete):
        """Should reject if new email is already taken"""
        mock_send_email.return_value = None
        from models import Athlete

        # Create another user with the target email
        other_user = Athlete(
            email="taken@example.com",
            display_name="Other User",
            subscription_tier="free"
        )
        db.add(other_user)
        db.commit()

        try:
            # Try to change to the taken email
            token = generate_email_change_token(str(test_athlete.id), "taken@example.com")
            success, message = complete_email_change(db, token)

            assert success is False
            assert "available" in message.lower() or "taken" in message.lower() or "already" in message.lower()
        finally:
            # Cleanup
            db.delete(other_user)
            db.commit()
    
    def test_nonexistent_user_rejected(self, db):
        """Should reject token for non-existent user"""
        fake_user_id = str(uuid4())
        token = generate_email_change_token(fake_user_id, "new@example.com")
        
        success, message = complete_email_change(db, token)
        
        assert success is False
        assert "not found" in message.lower()


class TestEmailChangeEndpoint:
    """Integration tests for the email change verification endpoint"""
    
    @pytest.fixture
    def test_athlete(self, db):
        """Create a test athlete"""
        from models import Athlete
        
        # Clean up any existing
        existing = db.query(Athlete).filter(Athlete.email == "endpoint_test@example.com").first()
        if existing:
            db.delete(existing)
            db.commit()
        
        athlete = Athlete(
            email="endpoint_test@example.com",
            display_name="Endpoint Test",
            subscription_tier="free"
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)
        
        yield athlete
        
        # Cleanup - may have changed email
        db.query(Athlete).filter(Athlete.id == athlete.id).delete()
        db.commit()
    
    @patch('services.email_service.send_email')
    def test_verify_email_change_endpoint(self, mock_send_email, db, test_athlete):
        """POST /v1/auth/verify-email-change should complete email change"""
        mock_send_email.return_value = None
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)
        new_email = "verified_new@example.com"
        token = generate_email_change_token(str(test_athlete.id), new_email)

        response = client.post("/v1/auth/verify-email-change", json={
            "token": token
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify email was changed
        db.refresh(test_athlete)
        assert test_athlete.email == new_email
    
    def test_verify_email_change_invalid_token(self, db):
        """Should reject invalid token"""
        from fastapi.testclient import TestClient
        from main import app
        
        client = TestClient(app)
        
        response = client.post("/v1/auth/verify-email-change", json={
            "token": "invalid.token.here"
        })
        
        assert response.status_code == 400


# Fixture for database session
@pytest.fixture
def db():
    """Provide a database session for testing"""
    from core.database import SessionLocal
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
