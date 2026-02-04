"""
Password Policy Validation

Implements strong password requirements to prevent weak credentials.
Reference: OWASP A07:2021 – Identification and Authentication Failures

Requirements:
- Minimum 8 characters
- Maximum 72 characters (bcrypt limit)
- At least 1 uppercase letter
- At least 1 lowercase letter
- At least 1 digit
- At least 1 special character
- Not in common password blocklist
"""
import re
from typing import Tuple, List

# Common weak passwords to block (subset - add more as needed)
COMMON_PASSWORDS = {
    "password", "password1", "password123", "123456", "12345678", "1234567890",
    "qwerty", "qwerty123", "abc123", "letmein", "welcome", "monkey", "dragon",
    "master", "login", "admin", "admin123", "root", "toor", "pass", "test",
    "guest", "iloveyou", "princess", "sunshine", "football", "baseball",
    "passw0rd", "p@ssw0rd", "p@ssword", "trustno1", "starwars", "whatever",
    "shadow", "ashley", "michael", "jennifer", "joshua", "mustang", "fuckme",
    "fuckyou", "asshole", "batman", "superman", "killer", "pepper", "ranger",
    "harley", "thomas", "robert", "jordan", "zxcvbn", "zxcvbnm", "asdfgh",
    "qazwsx", "summer", "winter", "spring", "autumn", "monday", "tuesday",
    "strideiq", "strideiq123", "running", "runner", "marathon", "5k", "10k",
}


def validate_password(password: str) -> Tuple[bool, List[str]]:
    """
    Validate password against security policy.
    
    Args:
        password: The password to validate
        
    Returns:
        Tuple of (is_valid, list_of_error_messages)
    """
    errors = []
    
    # Length checks
    if len(password) < 8:
        errors.append("Password must be at least 8 characters")
    
    if len(password) > 72:
        errors.append("Password must not exceed 72 characters (bcrypt limit)")
    
    # Complexity checks
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")
    
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")
    
    if not re.search(r'\d', password):
        errors.append("Password must contain at least one digit")
    
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?`~]', password):
        errors.append("Password must contain at least one special character (!@#$%^&*...)")
    
    # Common password check (case-insensitive)
    if password.lower() in COMMON_PASSWORDS:
        errors.append("Password is too common, please choose a stronger password")
    
    # Check for sequential patterns
    if re.search(r'(.)\1{2,}', password):
        errors.append("Password must not contain more than 2 repeated characters in a row")
    
    is_valid = len(errors) == 0
    return is_valid, errors


def get_password_requirements_text() -> str:
    """Return human-readable password requirements."""
    return """Password requirements:
• 8-72 characters
• At least one uppercase letter (A-Z)
• At least one lowercase letter (a-z)
• At least one digit (0-9)
• At least one special character (!@#$%^&*...)
• Must not be a commonly used password"""
