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

# Use auto_error=False to handle missing credentials manually and return 401 (not 403)
security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Athlete:
    """
    Get the current authenticated user from JWT token.
    
    Raises HTTPException if token is invalid or user not found.
    """
    # Check if credentials are missing (return 401, not 403)
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
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

    # Hard block enforcement (Phase 4). This prevents blocked users from accessing
    # any authenticated endpoints, including /v1/auth/me.
    if getattr(user, "is_blocked", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is blocked",
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


def require_owner(
    current_user: Athlete = Depends(require_role(["owner"]))
) -> Athlete:
    """Require owner role (highest privilege)."""
    return current_user


def require_permission(permission_key: str):
    """
    Dependency factory for admin permission checks.

    Phase 4 policy:
    - owner: always allowed
    - admin: allowed iff permission is present OR admin has no explicit permissions yet
      (bootstrap mode to avoid breaking existing admin workflows).

    Note: This is a deliberate "permissions seam" to allow later expansion to
    support/ops/finance roles without rewriting endpoint guards.
    """

    def permission_checker(current_user: Athlete = Depends(require_admin)) -> Athlete:
        if current_user.role == "owner":
            return current_user

        perms = getattr(current_user, "admin_permissions", None) or []
        # Bootstrap mode: if no explicit permissions set, treat as full admin EXCEPT
        # for system-level controls which must be explicitly granted.
        if len(perms) == 0:
            if (permission_key or "").startswith("system."):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing permission: {permission_key}",
                )
            return current_user

        if permission_key not in perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {permission_key}",
            )
        return current_user

    return permission_checker


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


# Tier-based access control (legacy)
# Phase 6: converge to Free vs Pro. Keep legacy paid values for backward compatibility.
TOP_TIERS = ("pro", "elite", "premium", "guided", "subscription")


def require_query_access(
    current_user: Athlete = Depends(get_current_active_user)
) -> Athlete:
    """
    Require query engine access.
    
    Access granted to:
    - Admin/owner roles (always)
    - Pro (paid) access (legacy values included)
    
    This enables top-tier athletes to use advanced data mining features.
    """
    # Admins always have access
    if current_user.role in ("admin", "owner"):
        return current_user
    
    # Check subscription tier / paid access
    if getattr(current_user, "has_active_subscription", False) or current_user.subscription_tier in TOP_TIERS:
        return current_user
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Query access requires Pro membership or admin role.",
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


def get_current_athlete_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
) -> Optional[Athlete]:
    """
    Get the current authenticated user if token is provided.
    Returns None if no token or invalid token.
    
    Useful for endpoints that work both authenticated and unauthenticated.
    """
    if not credentials:
        return None
    
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if not payload:
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        return None
    
    try:
        user_id_uuid = UUID(user_id)
    except ValueError:
        return None
    
    user = db.query(Athlete).filter(Athlete.id == user_id_uuid).first()
    return user
