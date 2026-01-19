"""
Security utilities for authentication and authorization.

Provides:
- Password hashing (bcrypt)
- JWT token generation and validation
- Role-based access control

SECURITY REQUIREMENTS:
- SECRET_KEY must be set via environment variable
- SECRET_KEY must be cryptographically secure (32+ characters)
- SECRET_KEY must be different for each environment (dev/staging/prod)
- SECRET_KEY must NEVER be committed to source control
"""
from datetime import datetime, timedelta
from typing import Optional, Dict
from jose import JWTError, jwt
import bcrypt
from core.config import settings

# JWT settings - SECRET_KEY is required by config.py, will fail at startup if not set
SECRET_KEY = settings.SECRET_KEY

# Validate SECRET_KEY strength at module load
if len(SECRET_KEY) < 32:
    raise ValueError(
        "SECRET_KEY must be at least 32 characters. "
        "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24 * 60  # 30 days


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


def get_password_hash(password: str) -> str:
    """Hash a password."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def get_user_id_from_token(token: str) -> Optional[str]:
    """Extract user ID from JWT token."""
    payload = decode_access_token(token)
    if payload:
        return payload.get("sub")  # Standard JWT claim for subject (user ID)
    return None


