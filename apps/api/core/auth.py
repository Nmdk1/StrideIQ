"""
Authentication and authorization dependencies.

Provides FastAPI dependencies for:
- Getting current authenticated user
- Role-based access control
- Cross-athlete access (admin only)
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from core.database import get_db
from core.security import decode_access_token, get_user_id_from_token
from models import Athlete

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Athlete:
    """
    Get the current authenticated user from JWT token.
    
    Raises HTTPException if token is invalid or user not found.
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    
    try:
        user_id_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format",
        )
    
    user = db.query(Athlete).filter(Athlete.id == user_id_uuid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    return user


def get_current_active_user(
    current_user: Athlete = Depends(get_current_user)
) -> Athlete:
    """
    Get current user and ensure they are active.
    
    For now, all users are considered active.
    Future: Add 'is_active' field if needed.
    """
    return current_user


def require_role(allowed_roles: list[str]):
    """
    Dependency factory for role-based access control.
    
    Usage:
        @router.get("/admin-only")
        def admin_endpoint(user: Athlete = Depends(require_role(["admin"]))):
            ...
    """
    def role_checker(current_user: Athlete = Depends(get_current_active_user)) -> Athlete:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {allowed_roles}",
            )
        return current_user
    
    return role_checker


def require_admin(
    current_user: Athlete = Depends(require_role(["admin", "owner"]))
) -> Athlete:
    """Require admin or owner role."""
    return current_user


def require_athlete_or_admin(
    current_user: Athlete = Depends(get_current_active_user)
) -> Athlete:
    """
    Allow athlete or admin access.
    
    Athletes can only access their own data.
    Admins can access any data.
    """
    return current_user


def get_athlete_or_admin(
    athlete_id: UUID,
    current_user: Athlete = Depends(require_athlete_or_admin),
    db: Session = Depends(get_db)
) -> Athlete:
    """
    Get athlete by ID, ensuring user has permission.
    
    - Athletes can only access their own data
    - Admins can access any athlete's data
    """
    if current_user.role == "admin":
        # Admin can access any athlete
        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Athlete not found"
            )
        return athlete
    else:
        # Athlete can only access their own data
        if current_user.id != athlete_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only access your own data."
            )
        return current_user


# Tier-based access control
TOP_TIERS = ("premium", "pro", "elite", "guided")  # Tiers with advanced features


def require_query_access(
    current_user: Athlete = Depends(get_current_active_user)
) -> Athlete:
    """
    Require query engine access.
    
    Access granted to:
    - Admin/owner roles (always)
    - Premium/pro/elite/guided subscription tiers
    
    This enables top-tier athletes to use advanced data mining features.
    """
    # Admins always have access
    if current_user.role in ("admin", "owner"):
        return current_user
    
    # Check subscription tier
    if current_user.subscription_tier in TOP_TIERS:
        return current_user
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Query access requires a premium subscription or admin role.",
    )


def require_tier(allowed_tiers: list[str]):
    """
    Dependency factory for tier-based access control.
    
    Usage:
        @router.get("/premium-feature")
        def premium_endpoint(user: Athlete = Depends(require_tier(["premium", "pro"]))):
            ...
    """
    def tier_checker(current_user: Athlete = Depends(get_current_active_user)) -> Athlete:
        # Admins bypass tier checks
        if current_user.role in ("admin", "owner"):
            return current_user
        
        if current_user.subscription_tier not in allowed_tiers:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required tiers: {allowed_tiers}",
            )
        return current_user
    
    return tier_checker


# Alias for backward compatibility with routers using get_current_athlete
get_current_athlete = get_current_user

