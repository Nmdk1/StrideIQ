"""
Account Security Module

Implements:
- Login attempt tracking
- Account lockout after failed attempts
- Lockout duration management
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple
from collections import defaultdict
import threading

# In-memory store for login attempts (use Redis in production for multi-instance)
# Structure: {email: [(timestamp, success), ...]}
_login_attempts: dict = defaultdict(list)
_lock = threading.Lock()

# Configuration
MAX_FAILED_ATTEMPTS = 5  # Lock after 5 failed attempts
LOCKOUT_DURATION_MINUTES = 15  # Lock for 15 minutes
ATTEMPT_WINDOW_MINUTES = 30  # Count attempts in last 30 minutes


def _clean_old_attempts(email: str) -> None:
    """Remove attempts older than the window."""
    cutoff = datetime.utcnow() - timedelta(minutes=ATTEMPT_WINDOW_MINUTES)
    with _lock:
        _login_attempts[email] = [
            (ts, success) for ts, success in _login_attempts[email]
            if ts > cutoff
        ]


def record_login_attempt(email: str, success: bool) -> None:
    """
    Record a login attempt.
    
    Args:
        email: The email address used for login
        success: Whether the login was successful
    """
    _clean_old_attempts(email)
    with _lock:
        _login_attempts[email].append((datetime.utcnow(), success))
        
        # If successful, clear failed attempts
        if success:
            _login_attempts[email] = [(datetime.utcnow(), True)]


def is_account_locked(email: str) -> Tuple[bool, Optional[int]]:
    """
    Check if an account is locked due to failed attempts.
    
    Args:
        email: The email address to check
        
    Returns:
        Tuple of (is_locked, seconds_until_unlock or None)
    """
    _clean_old_attempts(email)
    
    with _lock:
        attempts = _login_attempts.get(email, [])
        
        # Count recent failed attempts
        failed_attempts = [ts for ts, success in attempts if not success]
        
        if len(failed_attempts) < MAX_FAILED_ATTEMPTS:
            return False, None
        
        # Check if still in lockout period
        last_failed = max(failed_attempts)
        lockout_end = last_failed + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
        
        if datetime.utcnow() < lockout_end:
            seconds_remaining = int((lockout_end - datetime.utcnow()).total_seconds())
            return True, seconds_remaining
        
        return False, None


def get_remaining_attempts(email: str) -> int:
    """
    Get the number of remaining login attempts before lockout.
    
    Args:
        email: The email address to check
        
    Returns:
        Number of remaining attempts (0 if locked)
    """
    _clean_old_attempts(email)
    
    with _lock:
        attempts = _login_attempts.get(email, [])
        failed_attempts = [ts for ts, success in attempts if not success]
        remaining = MAX_FAILED_ATTEMPTS - len(failed_attempts)
        return max(0, remaining)


def clear_lockout(email: str) -> None:
    """
    Manually clear lockout for an account (admin function).
    
    Args:
        email: The email address to unlock
    """
    with _lock:
        if email in _login_attempts:
            del _login_attempts[email]


