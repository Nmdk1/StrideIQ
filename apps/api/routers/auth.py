"""
Authentication API endpoints.

Provides:
- User registration
- Login (JWT token generation)
- Token refresh
- Password reset (future)
- Account lockout protection
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, field_serializer, ConfigDict
from typing import Optional
from uuid import UUID
from datetime import timedelta

from core.database import get_db
from core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from core.auth import get_current_user
from core.account_security import (
    record_login_attempt,
    is_account_locked,
    get_remaining_attempts
)
from models import Athlete
from services.invite_service import is_invited, mark_invite_used, normalize_email

router = APIRouter(prefix="/v1/auth", tags=["auth"])
security = HTTPBearer()


class UserRegister(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    password: str
    display_name: Optional[str] = None


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Schema for user response."""
    id: UUID
    email: Optional[str]
    display_name: Optional[str]
    role: str
    subscription_tier: str

    model_config = ConfigDict(from_attributes=True)
    
    @field_serializer('id')
    def serialize_id(self, id: UUID) -> str:
        return str(id)


class TokenResponse(BaseModel):
    """Schema for token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60  # seconds
    athlete: Optional[UserResponse] = None

    model_config = ConfigDict(from_attributes=True)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    """
    Register a new user account.
    
    Creates an athlete account with email/password authentication.
    """
    email = normalize_email(user_data.email)

    # Enforce invite allowlist (Phase 3, Option B).
    ok, invite = is_invited(db, email)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invite required",
        )

    # Check if email already exists
    existing = db.query(Athlete).filter(Athlete.email == email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Validate password strength (basic check)
    if len(user_data.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters"
        )
    
    # Create new athlete
    athlete = Athlete(
        email=email,
        password_hash=get_password_hash(user_data.password),
        display_name=user_data.display_name or email.split("@")[0],
        role="athlete",  # Default role
        subscription_tier="free"  # Default tier
    )
    
    db.add(athlete)
    db.commit()
    db.refresh(athlete)

    # Mark invite as used (auditable domain object).
    if invite:
        try:
            mark_invite_used(db, invite=invite, used_by_athlete_id=athlete.id)
            db.commit()
        except Exception:
            db.rollback()
    
    return athlete


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: UserLogin,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT token.
    
    Returns access token valid for 30 days.
    Implements account lockout after 5 failed attempts.
    """
    email = credentials.email.lower()
    
    # Check if account is locked
    locked, seconds_remaining = is_account_locked(email)
    if locked:
        minutes_remaining = (seconds_remaining or 0) // 60 + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account temporarily locked. Try again in {minutes_remaining} minutes.",
            headers={"Retry-After": str(seconds_remaining)},
        )
    
    # Find user by email
    user = db.query(Athlete).filter(Athlete.email == email).first()
    
    if not user or not user.password_hash:
        # Record failed attempt even for non-existent users (prevents enumeration)
        record_login_attempt(email, success=False)
        remaining = get_remaining_attempts(email)
        
        detail = "Invalid email or password"
        if remaining <= 2 and remaining > 0:
            detail += f" ({remaining} attempts remaining)"
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify password
    if not verify_password(credentials.password, user.password_hash):
        record_login_attempt(email, success=False)
        remaining = get_remaining_attempts(email)
        
        detail = "Invalid email or password"
        if remaining <= 2 and remaining > 0:
            detail += f" ({remaining} attempts remaining)"
        elif remaining == 0:
            detail = "Account temporarily locked due to too many failed attempts"
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Successful login - clear failed attempts
    record_login_attempt(email, success=True)
    
    # Create access token
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "athlete": {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "subscription_tier": user.subscription_tier
        }
    }


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: Athlete = Depends(get_current_user)
):
    """Get current authenticated user information."""
    return current_user


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    current_user: Athlete = Depends(get_current_user)
):
    """
    Refresh access token.
    
    Returns a new token with extended expiration.
    """
    access_token = create_access_token(
        data={"sub": str(current_user.id), "email": current_user.email, "role": current_user.role}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

