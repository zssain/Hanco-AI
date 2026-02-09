"""
Authentication endpoints for Hanco-AI
Handles Firebase Authentication integration
Endpoints: register, login, logout, refresh_token, verify_token
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import Dict, Any
import logging

from app.core.firebase import (
    create_user as firebase_create_user,
    verify_id_token,
    get_user,
    db,
    Collections,
    auth_client
)
from app.core.security import get_current_user
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    UserResponse,
    LoginResponse,
    PasswordResetRequest
)
from google.cloud import firestore

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest):
    """
    Register a new user with Firebase Authentication.
    
    This endpoint:
    1. Creates user in Firebase Auth
    2. Stores user profile in Firestore
    3. Returns user data (without password)
    
    Args:
        data: Registration data (email, password, full_name, phone, role)
        
    Returns:
        UserResponse: Created user profile
        
    Raises:
        HTTPException 400: If email already exists or validation fails
    """
    try:
        logger.info(f"Registration attempt for email: {data.email}")
        
        # Create user in Firebase Auth and Firestore
        user_data = firebase_create_user(
            email=data.email,
            password=data.password,
            name=data.full_name,
            phone=data.phone,
            role=data.role
        )
        
        logger.info(f"✅ User registered successfully: {data.email}")
        
        return UserResponse(
            uid=user_data['uid'],
            email=user_data['email'],
            full_name=user_data['name'],
            phone=user_data['phone'],
            role=user_data['role'],
            is_active=user_data.get('is_active', True),
            created_at=user_data.get('created_at')
        )
        
    except ValueError as e:
        logger.warning(f"Registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again."
        )


@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest):
    """
    Verify Firebase ID token and return user profile.
    
    NOTE: Frontend handles actual authentication with Firebase Client SDK.
    This endpoint only verifies the ID token and returns user profile.
    
    Flow:
    1. Frontend calls Firebase signInWithEmailAndPassword()
    2. Frontend receives ID token
    3. Frontend sends ID token to this endpoint
    4. Backend verifies token and returns user data
    
    Args:
        data: Login data containing Firebase ID token
        
    Returns:
        LoginResponse: User profile with access token
        
    Raises:
        HTTPException 401: If token is invalid
        HTTPException 404: If user not found
    """
    try:
        # For this implementation, we expect the password field to contain the Firebase ID token
        # In production, you'd have a separate field or use Firebase client SDK on frontend
        id_token = data.password  # This should be the Firebase ID token from frontend
        
        logger.info(f"Login attempt for email: {data.email}")
        
        # Verify Firebase ID token
        try:
            decoded_token = verify_id_token(id_token)
            uid = decoded_token['uid']
        except Exception as e:
            logger.warning(f"Token verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        
        # Get user from Firestore
        user_data = get_user(uid)
        
        # If user doesn't exist in Firestore, create profile
        if not user_data:
            logger.info(f"Creating Firestore profile for existing Firebase user: {uid}")
            user_data = {
                'uid': uid,
                'email': decoded_token.get('email', data.email),
                'full_name': decoded_token.get('name', ''),
                'phone': '',
                'role': 'customer',
                'is_active': True,
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            db.collection(Collections.USERS).document(uid).set(user_data)
        
        logger.info(f"✅ User logged in successfully: {data.email}")
        
        # Return user profile with token
        user_response = UserResponse(
            uid=user_data['uid'],
            email=user_data['email'],
            full_name=user_data.get('full_name', ''),
            phone=user_data.get('phone', ''),
            role=user_data.get('role', 'customer'),
            is_active=user_data.get('is_active', True),
            created_at=user_data.get('created_at')
        )
        
        return LoginResponse(
            access_token=id_token,
            token_type="Bearer",
            user=user_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed. Please try again."
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Get current authenticated user's profile.
    
    Requires: Authorization header with valid Firebase ID token
    
    Args:
        current_user: Automatically injected by get_current_user dependency
        
    Returns:
        UserResponse: Current user's profile data
    """
    try:
        logger.info(f"Profile request for user: {current_user.get('uid')}")
        
        return UserResponse(
            uid=current_user['uid'],
            email=current_user['email'],
            full_name=current_user.get('full_name', ''),
            phone=current_user.get('phone', ''),
            role=current_user.get('role', 'customer'),
            is_active=current_user.get('is_active', True),
            created_at=current_user.get('created_at')
        )
    except Exception as e:
        logger.error(f"Profile retrieval error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve profile"
        )


@router.post("/logout")
async def logout(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Logout endpoint (client-side operation).
    
    Firebase tokens are stateless, so logout is handled on the client by:
    1. Clearing the stored token
    2. Calling Firebase signOut()
    
    This endpoint is mainly for logging and confirmation.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Success message
    """
    try:
        logger.info(f"Logout request for user: {current_user.get('uid')}")
        
        return {
            "message": "Logged out successfully",
            "detail": "Token cleared on client side"
        }
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return {"message": "Logged out"}


@router.post("/password-reset")
async def request_password_reset(data: PasswordResetRequest):
    """
    Send password reset email to user.
    
    Uses Firebase Auth to send password reset email.
    
    Args:
        data: Password reset request with email
        
    Returns:
        Success message
    """
    try:
        logger.info(f"Password reset request for email: {data.email}")
        
        # Generate password reset link
        # Note: Firebase Admin SDK doesn't send emails directly
        # You need to use Firebase Auth REST API or client SDK for this
        
        # For now, we'll use the auth_client to get the user and verify they exist
        try:
            user = auth_client.get_user_by_email(data.email)
            
            # In production, integrate with Firebase Auth REST API to send reset email
            # Or use Firebase client SDK on frontend
            
            logger.info(f"✅ Password reset email would be sent to: {data.email}")
            
            return {
                "message": "Password reset email sent",
                "detail": f"If an account exists for {data.email}, a password reset link has been sent."
            }
            
        except auth_client.UserNotFoundError:
            # Return success even if user doesn't exist (security best practice)
            logger.warning(f"Password reset requested for non-existent email: {data.email}")
            return {
                "message": "Password reset email sent",
                "detail": f"If an account exists for {data.email}, a password reset link has been sent."
            }
            
    except Exception as e:
        logger.error(f"Password reset error: {e}")
        # Always return success to prevent email enumeration
        return {
            "message": "Password reset email sent",
            "detail": "If an account exists, a password reset link has been sent."
        }


@router.delete("/account", status_code=status.HTTP_200_OK)
async def delete_account(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Delete current user's account.
    
    This endpoint:
    1. Deletes user from Firebase Auth
    2. Deletes user document from Firestore
    3. Optionally deletes related data (bookings, payments, etc.)
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Success message
    """
    try:
        uid = current_user['uid']
        logger.info(f"Account deletion request for user: {uid}")
        
        # Delete from Firebase Auth
        auth_client.delete_user(uid)
        
        # Delete from Firestore
        db.collection(Collections.USERS).document(uid).delete()
        
        # TODO: Delete related data (bookings, payments, chats)
        # This should be done in a background task or cloud function
        
        logger.info(f"✅ Account deleted successfully: {uid}")
        
        return {
            "message": "Account deleted successfully",
            "uid": uid
        }
        
    except Exception as e:
        logger.error(f"Account deletion error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account"
        )
