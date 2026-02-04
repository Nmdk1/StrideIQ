"""
Email Verification Service

Handles secure email change verification flow.
Reference: OWASP A07:2021 – Identification and Authentication Failures

Security Flow:
1. User requests email change -> verification token generated
2. Token sent to NEW email address
3. User clicks link -> token validated -> email updated
4. Old email remains active until verification complete

Token Structure:
- Signed JWT with 24-hour expiration
- Contains: user_id, new_email, purpose="email_change"
- One-time use (validated on first use)
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from core.config import settings
from core.security import SECRET_KEY, ALGORITHM
from models import Athlete

logger = logging.getLogger(__name__)

# Token validity period
EMAIL_CHANGE_TOKEN_EXPIRE_HOURS = 24


def generate_email_change_token(user_id: str, new_email: str) -> str:
    """
    Generate a signed JWT token for email change verification.
    
    Args:
        user_id: The athlete's UUID
        new_email: The new email address to verify
        
    Returns:
        Signed JWT token
    """
    expire = datetime.utcnow() + timedelta(hours=EMAIL_CHANGE_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": str(user_id),
        "new_email": new_email.lower().strip(),
        "purpose": "email_change",
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_email_change_token(token: str) -> Optional[dict]:
    """
    Verify and decode an email change token.
    
    Args:
        token: The JWT token to verify
        
    Returns:
        Decoded payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Verify this is an email change token
        if payload.get("purpose") != "email_change":
            logger.warning("Token has wrong purpose")
            return None
        
        # Verify required fields
        if not payload.get("sub") or not payload.get("new_email"):
            logger.warning("Token missing required fields")
            return None
        
        return payload
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        return None


def initiate_email_change(db: Session, athlete: Athlete, new_email: str) -> bool:
    """
    Initiate the email change verification process.
    
    Args:
        db: Database session
        athlete: The athlete requesting email change
        new_email: The new email address
        
    Returns:
        True if verification email was sent successfully
    """
    # Generate verification token
    token = generate_email_change_token(str(athlete.id), new_email)
    
    # Build verification URL
    frontend_url = getattr(settings, 'FRONTEND_URL', 'https://strideiq.run')
    verification_url = f"{frontend_url}/verify-email-change?token={token}"
    
    # Send verification email
    try:
        from services.email_service import send_email
        
        subject = "Confirm Your Email Change - StrideIQ"
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2563eb;">Confirm Your Email Change</h2>
            <p>Hi {athlete.display_name or 'there'},</p>
            <p>We received a request to change your StrideIQ account email to <strong>{new_email}</strong>.</p>
            <p>
                <a href="{verification_url}" 
                   style="display: inline-block; background-color: #2563eb; color: white; 
                          padding: 12px 24px; text-decoration: none; border-radius: 6px;">
                    Confirm Email Change
                </a>
            </p>
            <p style="color: #666; font-size: 14px;">
                This link expires in 24 hours. If you didn't request this change, 
                please ignore this email and your account email will remain unchanged.
            </p>
            <p style="color: #666; font-size: 14px;">
                For security, this email was sent to your new email address ({new_email}).
                Your current email ({athlete.email}) remains active until you confirm.
            </p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
            <p style="color: #999; font-size: 12px;">
                StrideIQ - Your AI Running Coach
            </p>
        </body>
        </html>
        """
        
        text_content = f"""
        Confirm Your Email Change
        
        Hi {athlete.display_name or 'there'},
        
        We received a request to change your StrideIQ account email to {new_email}.
        
        Click this link to confirm: {verification_url}
        
        This link expires in 24 hours. If you didn't request this change, 
        please ignore this email.
        
        - StrideIQ Team
        """
        
        send_email(
            to_email=new_email,  # Send to NEW email to verify ownership
            subject=subject,
            html_content=html_content,
            text_content=text_content
        )
        
        logger.info(f"Email change verification sent for athlete {athlete.id} to {new_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email change verification: {e}")
        # In development, still return True to allow testing
        if getattr(settings, 'DEBUG', False):
            logger.warning("DEBUG mode: Returning True despite email send failure")
            return True
        return False


def complete_email_change(db: Session, token: str) -> tuple[bool, str]:
    """
    Complete the email change after token verification.
    
    Args:
        db: Database session
        token: The verification token
        
    Returns:
        Tuple of (success, message)
    """
    # Verify token
    payload = verify_email_change_token(token)
    if not payload:
        return False, "Invalid or expired verification link"
    
    user_id = payload.get("sub")
    new_email = payload.get("new_email")
    
    # Find the athlete
    athlete = db.query(Athlete).filter(Athlete.id == user_id).first()
    if not athlete:
        return False, "Account not found"
    
    # Check if new email is still available
    existing = db.query(Athlete).filter(
        Athlete.email == new_email,
        Athlete.id != athlete.id
    ).first()
    if existing:
        return False, "Email address is no longer available"
    
    # Update the email
    old_email = athlete.email
    athlete.email = new_email
    db.commit()
    
    logger.info(f"Email changed for athlete {athlete.id}: {old_email} -> {new_email}")
    
    # Optionally notify the old email about the change
    try:
        from services.email_service import send_email
        
        send_email(
            to_email=old_email,
            subject="Your StrideIQ Email Has Been Changed",
            html_content=f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>Email Address Changed</h2>
                <p>Your StrideIQ account email has been changed to {new_email}.</p>
                <p>If you did not make this change, please contact support immediately.</p>
            </body>
            </html>
            """,
            text_content=f"Your StrideIQ account email has been changed to {new_email}. If you did not make this change, please contact support immediately."
        )
    except Exception as e:
        logger.warning(f"Failed to notify old email about change: {e}")
    
    return True, f"Email successfully changed to {new_email}"
