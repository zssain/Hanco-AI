"""
Payment request/response schemas
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class PaymentCreate(BaseModel):
    """Create payment request"""
    booking_id: str
    amount: float = Field(..., gt=0)
    currency: str = Field(default="SAR", pattern=r'^[A-Z]{3}$')
    payment_method: str = Field(default="card", pattern=r'^(card|apple_pay|mada|stc_pay)$')


class PaymentResponse(BaseModel):
    """Payment response"""
    id: str
    booking_id: str
    user_id: str
    amount: float
    currency: str
    status: str
    payment_method: str
    transaction_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class PaymentIntentRequest(BaseModel):
    """Payment intent creation request"""
    booking_id: str
    amount: float = Field(..., gt=0)
    currency: str = "SAR"


class PaymentIntentResponse(BaseModel):
    """Payment intent response"""
    payment_intent_id: str
    client_secret: str
    amount: float
    currency: str
    status: str


class PaymentConfirmRequest(BaseModel):
    """Payment confirmation request"""
    payment_id: str
    transaction_id: str


class RefundRequest(BaseModel):
    """Payment refund request"""
    payment_id: str
    amount: Optional[float] = None  # None = full refund
    reason: Optional[str] = None
