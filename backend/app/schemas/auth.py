"""
Authentication request/response schemas
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime


class RegisterRequest(BaseModel):
    """User registration request"""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    full_name: str = Field(..., min_length=2)
    phone: str = Field(..., pattern=r'^\+?[0-9]{10,15}$')
    role: str = Field(default="customer", pattern=r'^(customer|business)$')
    
    @validator('password')
    def validate_password_strength(cls, v):
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        if not any(char.isalpha() for char in v):
            raise ValueError('Password must contain at least one letter')
        return v


class LoginRequest(BaseModel):
    """User login request"""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """User data response"""
    uid: str
    email: str
    full_name: str
    phone: str
    role: str
    is_active: bool = True
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    """Login response with tokens"""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    user: UserResponse


class TokenRefreshRequest(BaseModel):
    """Token refresh request"""
    refresh_token: str


class TokenResponse(BaseModel):
    """Token response"""
    access_token: str
    token_type: str = "Bearer"


class PasswordResetRequest(BaseModel):
    """Password reset request"""
    email: EmailStr


class PasswordUpdateRequest(BaseModel):
    """Password update request"""
    current_password: str
    new_password: str = Field(..., min_length=8)
