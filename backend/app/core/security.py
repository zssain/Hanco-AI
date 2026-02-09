"""
Security utilities for Hanco-AI
Guest ID validation, IDOR protection, log redaction
"""
from fastapi import Depends, HTTPException, status, Request, Header
from typing import Optional, Dict, Any
from google.cloud import firestore
import logging
import re
import uuid

from app.core.firebase import db, Collections, verify_id_token, get_user
from app.core.config import settings

logger = logging.getLogger(__name__)


# ==================== Firebase Auth User Extraction ====================

async def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization")
) -> Dict[str, Any]:
    """
    Extract and verify Firebase Auth user from Authorization header.
    
    Expects header format: "Bearer <firebase_id_token>"
    
    Args:
        authorization: Authorization header with Bearer token
        
    Returns:
        Dict with user info: uid, email, role, full_name
        
    Raises:
        HTTPException 401: If token is missing, invalid, or expired
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Use: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = parts[1]
    
    try:
        # Verify Firebase ID token
        decoded_token = verify_id_token(token)
        uid = decoded_token.get('uid')
        
        if not uid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID"
            )
        
        # Get user profile from Firestore
        user_data = get_user(uid)
        
        if user_data:
            return {
                'uid': uid,
                'email': user_data.get('email', decoded_token.get('email', '')),
                'role': user_data.get('role', 'customer'),
                'full_name': user_data.get('full_name', user_data.get('name', '')),
                'is_active': user_data.get('is_active', True)
            }
        else:
            # User exists in Firebase Auth but not in Firestore
            # Return basic info from token
            return {
                'uid': uid,
                'email': decoded_token.get('email', ''),
                'role': decoded_token.get('role', 'customer'),
                'full_name': decoded_token.get('name', ''),
                'is_active': True
            }
            
    except ValueError as e:
        logger.warning(f"Token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error(f"Auth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_user_optional(
    authorization: Optional[str] = Header(None, alias="Authorization")
) -> Optional[Dict[str, Any]]:
    """
    Optional Firebase Auth user extraction.
    Returns None if no token provided, raises error only if token is invalid.
    """
    if not authorization:
        return None
    
    return await get_current_user(authorization)


# ==================== Guest ID Management ====================

async def get_guest_id(
    x_guest_id: Optional[str] = Header(None, alias="X-Guest-Id")
) -> str:
    """
    Extract and validate guest ID from X-Guest-Id header.
    
    Args:
        x_guest_id: Guest UUID from request header
        
    Returns:
        Validated guest ID string
        
    Raises:
        HTTPException: If guest ID is missing or invalid
    """
    if not x_guest_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Guest-Id header is required"
        )
    
    # Validate UUID format
    try:
        uuid.UUID(x_guest_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid guest ID format"
        )
    
    return x_guest_id


async def get_guest_id_optional(
    x_guest_id: Optional[str] = Header(None, alias="X-Guest-Id")
) -> Optional[str]:
    """
    Optional guest ID extraction.
    Returns None if header is missing or invalid.
    """
    if not x_guest_id:
        return None
    
    try:
        uuid.UUID(x_guest_id)
        return x_guest_id
    except ValueError:
        return None


# ==================== Cron/Admin Secret Verification ====================

async def verify_cron_secret(
    x_cron_secret: Optional[str] = Header(None, alias="X-Cron-Secret")
) -> None:
    """
    Verify X-Cron-Secret header matches CRON_SECRET environment variable.
    
    Used to protect admin/cron endpoints from unauthorized access.
    Cron jobs and internal services must include this header.
    
    Args:
        x_cron_secret: Secret token from X-Cron-Secret header
        
    Raises:
        HTTPException: If secret is missing or invalid
    """
    if not settings.CRON_SECRET:
        # If CRON_SECRET is not configured, log warning but allow access in dev
        if settings.ENVIRONMENT == "production":
            logger.error("CRON_SECRET not configured in production")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Server configuration error"
            )
        else:
            logger.warning("CRON_SECRET not configured - allowing access in development")
            return
    
    if not x_cron_secret:
        logger.warning("Missing X-Cron-Secret header for admin/cron endpoint")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    if x_cron_secret != settings.CRON_SECRET:
        logger.warning("Invalid X-Cron-Secret header for admin/cron endpoint")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization"
        )
    
    # Secret is valid
    return


# ==================== Log Redaction ====================

def redact_sensitive_data(text: str) -> str:
    """
    Redact sensitive information from logs
    Removes: emails, credit cards, tokens, phone numbers
    """
    if not text:
        return text
    
    # Redact email addresses
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]', text)
    
    # Redact credit card patterns (13-19 digits with optional spaces/dashes)
    text = re.sub(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4,7}\b', '[CARD_REDACTED]', text)
    
    # Redact CVV patterns
    text = re.sub(r'\b(cvv|cvc)[:\s]*\d{3,4}\b', '[CVV_REDACTED]', text, flags=re.IGNORECASE)
    
    # Redact API tokens (common patterns)
    text = re.sub(r'\b(AIza[0-9A-Za-z_-]{35})\b', '[API_KEY_REDACTED]', text)
    text = re.sub(r'\b(sk-[a-zA-Z0-9]{48})\b', '[API_KEY_REDACTED]', text)
    
    # Redact phone numbers (escape dash to avoid regex range error)
    text = re.sub(r'\b\+?[\d\s()\-]{10,15}\b', '[PHONE_REDACTED]', text)
    
    return text


def safe_log_error(message: str, error: Exception):
    """Log errors with sensitive data redaction"""
    safe_message = redact_sensitive_data(message)
    safe_error = redact_sensitive_data(str(error))
    logger.error(f"{safe_message}: {safe_error}")


# ==================== IDOR Protection ====================

async def verify_booking_ownership(
    booking_id: str,
    guest_id: str
) -> Dict[str, Any]:
    """
    Verify that the current user owns the booking or is an admin.
    
    Args:
        booking_id: Booking ID to check
        current_user: Current authenticated user
        
    Returns:
        Booking data if authorized
        
    Raises:
        HTTPException: If booking not found or user not authorized
    """
    try:
        booking_ref = db.collection(Collections.BOOKINGS).document(booking_id)
        booking_doc = booking_ref.get()
        
        if not booking_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found"
            )
        
        booking_data = booking_doc.to_dict()
        user_role = current_user.get('role', 'consumer')
        
        # Admin can access any booking
        if user_role in ['admin', 'support']:
            return booking_data
        
        # Regular user can only access their own bookings
        if booking_data.get('user_id') != current_user.get('uid'):
            # Return 404 instead of 403 to prevent info leakage
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found"
            )
        
        return booking_data
        
    except HTTPException:
        raise
    except Exception as e:
        safe_log_error(f"Error verifying booking ownership for {booking_id}", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to verify resource access"
        )


async def verify_payment_ownership(
    payment_id: str,
    guest_id: str
) -> Dict[str, Any]:
    """
    Verify that a payment belongs to the specified guest.
    
    Args:
        payment_id: Payment/Transaction ID to check
        guest_id: Guest UUID
        
    Returns:
        Payment data if authorized
        
    Raises:
        HTTPException: If payment not found or access denied
    """
    try:
        payment_ref = db.collection('payments').document(payment_id)
        payment_doc = payment_ref.get()
        
        if not payment_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found"
            )
        
        payment_data = payment_doc.to_dict()
        
        # Verify ownership
        if payment_data.get('guest_id') != guest_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found"
            )
        
        return payment_data
        
    except HTTPException:
        raise
    except Exception as e:
        safe_log_error(f"Error verifying payment ownership for {payment_id}", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to verify resource access"
        )


# ==================== AI Input Validation ====================

def validate_ai_input(text: str, max_length: int = 2000) -> str:
    """
    Validate and sanitize AI chatbot input.
    Prevents prompt injection and abuse.
    
    Args:
        text: User input text
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text
        
    Raises:
        HTTPException: If input is invalid
    """
    if not text or not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Input cannot be empty"
        )
    
    text = text.strip()
    
    # Check length
    if len(text) > max_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Input too long. Maximum {max_length} characters allowed"
        )
    
    # Remove control characters except newlines and tabs
    text = ''.join(char for char in text if char.isprintable() or char in '\n\t')
    
    # Basic prompt injection detection
    injection_patterns = [
        r'ignore\s+(previous|above|all)\s+instructions',
        r'system\s*:',
        r'<\|im_start\|>',
        r'<\|im_end\|>',
        r'###\s*instruction',
        r'forget\s+(everything|all|previous)',
    ]
    
    text_lower = text.lower()
    for pattern in injection_patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid input detected"
            )
    
    # Check for excessive repetition (potential abuse)
    if len(text) > 50:
        words = text.split()
        if words and words[0] * 10 in text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid input pattern detected"
            )
    
    return text


# ==================== Rate Limiting Support ====================

def get_client_ip(request: Request) -> str:
    """Extract client IP address for rate limiting"""
    # Check X-Forwarded-For header (behind proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    # Check X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fallback to direct client
    if request.client:
        return request.client.host
    
    return "unknown"


# ==================== Legacy Functions (kept for compatibility) ====================


def verify_user_access(user_id: str, current_user: Dict[str, Any]) -> bool:
    """
    Check if current user can access resources belonging to user_id.
    User can access their own resources or admin can access any.
    
    Args:
        user_id: The user ID of the resource owner
        current_user: Current authenticated user
        
    Returns:
        True if access is allowed
        
    Raises:
        HTTPException: If access is denied
    """
    current_uid = current_user.get('uid')
    current_role = current_user.get('role', 'consumer')
    
    # User can access their own data
    if current_uid == user_id:
        return True
    
    # Admin can access any data
    if current_role in ['admin', 'support']:
        return True
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied"
    )


class RateLimiter:
    """Simple in-memory rate limiter (use Redis in production)"""
    
    def __init__(self):
        self._requests = {}
    
    def check_rate_limit(self, key: str, max_requests: int = 60, window: int = 60) -> bool:
        """
        Check if request is within rate limit.
        
        Args:
            key: Identifier (user_id, ip, etc.)
            max_requests: Maximum requests allowed
            window: Time window in seconds
            
        Returns:
            True if within limit, False otherwise
        """
        # TODO: Implement with Redis for production
        # This is a simple placeholder
        return True


rate_limiter = RateLimiter()
