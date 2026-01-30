"""
Authentication API endpoints.

Provides:
- User registration
- Login (JWT token generation)
- Token refresh
- Password reset (self-service via email)
- Account lockout protection
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, field_serializer, ConfigDict
from typing import Optional
from uuid import UUID
from datetime import timedelta, datetime
import logging

from core.database import get_db
from core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    SECRET_KEY,
    ALGORITHM,
)
from core.auth import get_current_user
from core.account_security import (
    record_login_attempt,
    is_account_locked,
    get_remaining_attempts
)
from models import Athlete
from services.invite_service import is_invited, mark_invite_used, normalize_email
from services.system_flags import are_invites_required
from jose import jwt, JWTError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/auth", tags=["auth"])
security = HTTPBearer()

# Password reset token expiry (1 hour)
PASSWORD_RESET_EXPIRE_MINUTES = 60


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
    stripe_customer_id: Optional[str] = None
    onboarding_stage: Optional[str] = None
    onboarding_completed: bool = False
    # Phase 6: trials (7-day access)
    trial_started_at: Optional[datetime] = None
    trial_ends_at: Optional[datetime] = None
    trial_source: Optional[str] = None
    # Derived entitlement signal (includes trials)
    has_active_subscription: bool = False

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


class ForgotPasswordRequest(BaseModel):
    """Schema for forgot password request."""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Schema for reset password request."""
    token: str
    new_password: str


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    """
    Register a new user account.
    
    Creates an athlete account with email/password authentication.
    """
    email = normalize_email(user_data.email)

    # Invite allowlist (Phase 3) is now an operator control, default OFF.
    # If enabled, enforce; if disabled, still mark invites used for audit.
    ok, invite = is_invited(db, email)
    if are_invites_required(db) and not ok:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invite required")

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

    # Issue token immediately so the web app can proceed to onboarding without
    # requiring a second login call.
    access_token = create_access_token(
        data={"sub": str(athlete.id), "email": athlete.email, "role": athlete.role}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "athlete": {
            "id": str(athlete.id),
            "email": athlete.email,
            "display_name": athlete.display_name,
            "role": athlete.role,
            "subscription_tier": athlete.subscription_tier,
            "stripe_customer_id": getattr(athlete, "stripe_customer_id", None),
            "onboarding_stage": getattr(athlete, "onboarding_stage", None),
            "onboarding_completed": bool(getattr(athlete, "onboarding_completed", False)),
            "trial_started_at": athlete.trial_started_at,
            "trial_ends_at": athlete.trial_ends_at,
            "trial_source": getattr(athlete, "trial_source", None),
            "has_active_subscription": bool(getattr(athlete, "has_active_subscription", False)),
        },
    }


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
            "subscription_tier": user.subscription_tier,
            "stripe_customer_id": getattr(user, "stripe_customer_id", None),
            "onboarding_stage": getattr(user, "onboarding_stage", None),
            "onboarding_completed": bool(getattr(user, "onboarding_completed", False)),
            "trial_started_at": user.trial_started_at,
            "trial_ends_at": user.trial_ends_at,
            "trial_source": getattr(user, "trial_source", None),
            "has_active_subscription": bool(getattr(user, "has_active_subscription", False)),
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


@router.post("/forgot-password")
def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Request a password reset email.
    
    Sends an email with a reset link if the email exists.
    Always returns success to prevent email enumeration.
    """
    from core.config import settings
    from services.email_service import email_service
    
    email = request.email.lower()
    
    # Find user (but don't reveal if they exist)
    user = db.query(Athlete).filter(Athlete.email == email).first()
    
    if user:
        # Generate password reset token (JWT with short expiry)
        reset_token = jwt.encode(
            {
                "sub": str(user.id),
                "email": user.email,
                "purpose": "password_reset",
                "exp": datetime.utcnow() + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES),
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )
        
        # Build reset URL
        frontend_url = getattr(settings, "FRONTEND_URL", "https://strideiq.run")
        reset_url = f"{frontend_url}/reset-password?token={reset_token}"
        
        # Send email
        html_content = f"""
        <h2>Password Reset Request</h2>
        <p>You requested to reset your password for StrideIQ.</p>
        <p>Click the link below to set a new password:</p>
        <p><a href="{reset_url}" style="background-color: #f97316; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">Reset Password</a></p>
        <p>This link expires in 1 hour.</p>
        <p>If you didn't request this, you can safely ignore this email.</p>
        <p>— StrideIQ</p>
        """
        
        text_content = f"""
Password Reset Request

You requested to reset your password for StrideIQ.

Click the link below to set a new password:
{reset_url}

This link expires in 1 hour.

If you didn't request this, you can safely ignore this email.

— StrideIQ
        """
        
        sent = email_service.send_email(
            to_email=user.email,
            subject="Reset your StrideIQ password",
            html_content=html_content,
            text_content=text_content,
        )
        
        if sent:
            logger.info(f"Password reset email sent to {email}")
        else:
            # Email not configured - log for debugging
            logger.warning(f"Password reset requested for {email} but email service is disabled")
            logger.info(f"Reset URL (dev only): {reset_url}")
    else:
        # Don't reveal that email doesn't exist
        logger.info(f"Password reset requested for non-existent email: {email}")
    
    # Always return success to prevent email enumeration
    return {
        "success": True,
        "message": "If an account with that email exists, a password reset link has been sent.",
    }


@router.post("/reset-password")
def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Reset password using a valid reset token.
    
    Validates the token and updates the password.
    """
    # Validate password strength
    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters"
        )
    
    # Decode and validate token
    try:
        payload = jwt.decode(request.token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Verify this is a password reset token
        if payload.get("purpose") != "password_reset":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reset token"
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reset token"
            )
        
    except JWTError as e:
        logger.warning(f"Invalid password reset token: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token. Please request a new password reset."
        )
    
    # Find user
    user = db.query(Athlete).filter(Athlete.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token"
        )
    
    # Update password
    user.password_hash = get_password_hash(request.new_password)
    db.add(user)
    db.commit()
    
    logger.info(f"Password reset successful for user {user.id}")
    
    return {
        "success": True,
        "message": "Password has been reset. You can now log in with your new password.",
    }

