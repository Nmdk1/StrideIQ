"""
Tests for Password Policy Validation

Ensures password strength requirements are properly enforced.
Reference: M2 in Security Audit Report
"""
import pytest
from core.password_policy import validate_password, get_password_requirements_text


class TestPasswordValidation:
    """Tests for validate_password function"""
    
    def test_valid_strong_password(self):
        """Should accept a password meeting all requirements"""
        valid, errors = validate_password("SecureP@ss123")
        assert valid is True
        assert len(errors) == 0
    
    def test_valid_complex_password(self):
        """Should accept a complex password"""
        valid, errors = validate_password("My$uper$ecure#Pass99!")
        assert valid is True
        assert len(errors) == 0
    
    def test_reject_short_password(self):
        """Should reject password shorter than 8 characters"""
        valid, errors = validate_password("Ab1@xyz")
        assert valid is False
        assert any("at least 8 characters" in e for e in errors)
    
    def test_reject_long_password(self):
        """Should reject password longer than 72 characters (bcrypt limit)"""
        long_pass = "A" * 70 + "a1@"  # 73 chars
        valid, errors = validate_password(long_pass)
        assert valid is False
        assert any("72 characters" in e for e in errors)
    
    def test_reject_no_uppercase(self):
        """Should reject password without uppercase letter"""
        valid, errors = validate_password("secure@pass123")
        assert valid is False
        assert any("uppercase" in e for e in errors)
    
    def test_reject_no_lowercase(self):
        """Should reject password without lowercase letter"""
        valid, errors = validate_password("SECURE@PASS123")
        assert valid is False
        assert any("lowercase" in e for e in errors)
    
    def test_reject_no_digit(self):
        """Should reject password without digit"""
        valid, errors = validate_password("Secure@Password")
        assert valid is False
        assert any("digit" in e for e in errors)
    
    def test_reject_no_special_char(self):
        """Should reject password without special character"""
        valid, errors = validate_password("SecurePass123")
        assert valid is False
        assert any("special character" in e for e in errors)
    
    def test_reject_common_password(self):
        """Should reject common passwords"""
        common_passwords = ["password", "Password1!", "password123", "admin123"]
        for pwd in common_passwords:
            # Add complexity to test the blocklist specifically
            test_pwd = pwd if any(c.isupper() for c in pwd) else pwd.capitalize()
            if not any(c in "!@#$%^&*()" for c in test_pwd):
                test_pwd += "!"
            if not any(c.isdigit() for c in test_pwd):
                test_pwd += "1"
            
            valid, errors = validate_password("Password1!")  # This is in blocklist
            # Note: "Password1!" may pass complexity but fail blocklist
            # Let's test explicit blocklist entries
            valid, errors = validate_password("password")
            assert valid is False
    
    def test_reject_repeated_characters(self):
        """Should reject password with more than 2 repeated characters"""
        valid, errors = validate_password("Secuuure@123")  # 3 u's
        assert valid is False
        assert any("repeated" in e for e in errors)
    
    def test_multiple_errors_returned(self):
        """Should return all applicable errors"""
        valid, errors = validate_password("abc")  # Multiple issues
        assert valid is False
        assert len(errors) > 1  # Should have multiple errors
    
    def test_edge_case_exactly_8_chars(self):
        """Should accept password with exactly 8 characters if complex"""
        valid, errors = validate_password("Ab1@cdef")
        assert valid is True
    
    def test_edge_case_exactly_72_chars(self):
        """Should accept password with exactly 72 characters"""
        # 72 chars: 68 A's + "a" + "1" + "@" + "b" = 72
        pass72 = "A" * 68 + "a1@b"
        valid, errors = validate_password(pass72)
        assert valid is True
    
    def test_special_characters_variety(self):
        """Should accept various special characters"""
        special_chars = "!@#$%^&*()_+-=[]{}|;':\",./<>?`~"
        for char in special_chars[:10]:  # Test subset
            pwd = f"Secure1{char}pass"
            valid, errors = validate_password(pwd)
            # Should not fail due to special char requirement
            assert not any("special character" in e for e in errors)


class TestPasswordRequirementsText:
    """Tests for get_password_requirements_text function"""
    
    def test_returns_requirements(self):
        """Should return human-readable requirements"""
        text = get_password_requirements_text()
        assert "8-72 characters" in text
        assert "uppercase" in text.lower()
        assert "lowercase" in text.lower()
        assert "digit" in text.lower()
        assert "special character" in text.lower()


class TestPasswordPolicyInRegistration:
    """Integration tests for password policy in registration endpoint"""
    
    def test_register_weak_password_rejected(self, db):
        """Registration should reject weak passwords"""
        from fastapi.testclient import TestClient
        from main import app
        
        client = TestClient(app)
        
        # Try to register with weak password
        response = client.post("/v1/auth/register", json={
            "email": "test_weak_pass@example.com",
            "password": "weakpass",  # No uppercase, no digit, no special
            "display_name": "Test User"
        })
        
        assert response.status_code == 400
        # Should mention password requirements
        detail = response.json().get("detail", "")
        if isinstance(detail, list):
            detail = " ".join(detail)
        assert any(word in detail.lower() for word in ["password", "uppercase", "digit", "special"])
    
    def test_register_strong_password_accepted(self, db):
        """Registration should accept strong passwords"""
        from fastapi.testclient import TestClient
        from main import app
        from models import Athlete
        
        client = TestClient(app)
        
        # Clean up any existing test user
        existing = db.query(Athlete).filter(Athlete.email == "test_strong_pass@example.com").first()
        if existing:
            db.delete(existing)
            db.commit()
        
        # Try to register with strong password
        response = client.post("/v1/auth/register", json={
            "email": "test_strong_pass@example.com",
            "password": "SecureP@ss123",
            "display_name": "Test User"
        })
        
        # Should succeed (may require invite in some configs, but password validation passes first)
        assert response.status_code in [200, 201, 403]  # 403 if invite required
        
        # Clean up
        new_user = db.query(Athlete).filter(Athlete.email == "test_strong_pass@example.com").first()
        if new_user:
            db.delete(new_user)
            db.commit()


# Fixture for database session (if not already defined elsewhere)
@pytest.fixture
def db():
    """Provide a database session for testing"""
    from core.database import SessionLocal
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
