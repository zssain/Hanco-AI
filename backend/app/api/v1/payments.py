"""
Payment API endpoints
Handles payment processing for bookings
"""
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field, validator
from typing import Optional
import logging

from app.core.firebase import db
from app.core.security import get_guest_id, verify_payment_ownership, safe_log_error, redact_sensitive_data
from app.core.config import settings
from app.schemas.auth import UserResponse
from app.services.payments.simulator import process_payment, mark_booking_paid

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Payments"])


# ==================== REQUEST MODELS ====================

class PaymentRequest(BaseModel):
    """Payment request schema"""
    booking_id: str = Field(..., description="Booking ID to pay for")
    card_number: str = Field(..., description="Credit card number")
    expiry_month: int = Field(..., ge=1, le=12, description="Card expiry month (1-12)")
    expiry_year: int = Field(..., ge=2025, description="Card expiry year")
    cvv: str = Field(..., min_length=3, max_length=4, description="Card CVV (3-4 digits)")
    cardholder_name: str = Field(..., min_length=2, description="Cardholder name")
    
    @validator('cvv')
    def validate_cvv(cls, v):
        if not v.isdigit():
            raise ValueError('CVV must contain only digits')
        return v
    
    @validator('card_number')
    def validate_card_number(cls, v):
        # Remove spaces and dashes for validation
        import re
        cleaned = re.sub(r'[\s-]', '', v)
        if not cleaned.isdigit():
            raise ValueError('Card number must contain only digits')
        if len(cleaned) < 13 or len(cleaned) > 19:
            raise ValueError('Card number must be 13-19 digits')
        return v


# ==================== RESPONSE MODELS ====================

class PaymentResponse(BaseModel):
    """Payment response schema"""
    status: str
    transaction_id: Optional[str]
    booking_status: str
    message: str
    amount: float
    currency: str
    timestamp: str
    card_last4: Optional[str]


# ==================== ENDPOINTS ====================

@router.post("/pay", response_model=PaymentResponse, status_code=status.HTTP_200_OK)
async def pay_for_booking(
    request: PaymentRequest,
    guest_id: str = Depends(get_guest_id)
):
    """
    Process payment for a booking
    
    Simulates payment processing in development mode.
    Always succeeds after basic card validation.
    
    Args:
        request: Payment request with booking_id and card details
        guest_id: Guest UUID from X-Guest-Id header
        
    Returns:
        Payment response with transaction details
        
    Raises:
        HTTPException 404: Booking not found
        HTTPException 400: Booking already paid or invalid
        HTTPException 500: Payment processing error
        HTTPException 501: Payment simulator disabled in production
    """
    try:
        # Gate payment simulator - should NOT be enabled in production
        if not settings.ENABLE_PAYMENT_SIMULATOR:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Payment processing is not available. Please use production payment gateway."
            )
        
        # Never log full card numbers (redact for security)
        safe_booking_id = redact_sensitive_data(request.booking_id)
        logger.info(f"Processing payment for booking {safe_booking_id}")
        
        # Load booking from Firestore
        booking_ref = db.collection('bookings').document(request.booking_id)
        booking_doc = booking_ref.get()
        
        if not booking_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )
        
        booking_data = booking_doc.to_dict()
        
        # IDOR protection: Ensure guest owns this booking before allowing payment
        if booking_data.get('guest_id') != guest_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"  # Return 404 to prevent ID enumeration
            )
        
        # Check if already paid
        if booking_data.get('payment_status') == 'paid':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Booking has already been paid"
            )
        
        # Check if booking is cancelled
        if booking_data.get('status') == 'cancelled':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot pay for cancelled booking"
            )
        
        # Get total price
        total_price = booking_data.get('total_price', 0)
        
        if total_price <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid booking total price"
            )
        
        # Prepare card details
        card_details = {
            'card_number': request.card_number,
            'expiry_month': request.expiry_month,
            'expiry_year': request.expiry_year,
            'cvv': request.cvv,
            'cardholder_name': request.cardholder_name
        }
        
        # Process payment (simulated)
        payment_result = await process_payment(
            booking_id=request.booking_id,
            amount=total_price,
            card_details=card_details
        )
        
        # Check payment status
        if payment_result['status'] == 'failed':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=payment_result['message']
            )
        
        # Mark booking as paid
        success = await mark_booking_paid(request.booking_id, db)
        
        if not success:
            logger.error(f"Failed to update booking {request.booking_id} after successful payment")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Payment succeeded but booking update failed"
            )
        
        # Store payment record in Firestore (NEVER store full card numbers or CVV)
        payment_record = {
            'booking_id': request.booking_id,
            'guest_id': guest_id,  # Track which guest made the payment
            'transaction_id': payment_result['transaction_id'],
            'amount': total_price,
            'currency': 'SAR',
            'status': 'success',
            'card_last4': payment_result['card_last4'],  # Only store last 4 digits
            'cardholder_name': request.cardholder_name,
            'timestamp': payment_result['timestamp'],
            'method': 'simulated'
        }
        
        db.collection('payments').document(payment_result['transaction_id']).set(payment_record)
        
        logger.info(f"✅ Payment successful for booking {request.booking_id}")
        
        return PaymentResponse(
            status="success",
            transaction_id=payment_result['transaction_id'],
            booking_status="confirmed",
            message="Payment processed successfully",
            amount=total_price,
            currency="SAR",
            timestamp=payment_result['timestamp'],
            card_last4=payment_result['card_last4']
        )
        
    except HTTPException:
        raise
    
    except Exception as e:
        safe_log_error("Payment processing error", e)  # Never log card details
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment processing failed"
        )


@router.get("/{transaction_id}", status_code=status.HTTP_200_OK)
async def get_payment_details(
    transaction_id: str,
    guest_id: str = Depends(get_guest_id)
):
    """
    Get payment details by transaction ID
    
    Guests can only view their own payments.
    
    Args:
        transaction_id: Transaction ID
        guest_id: Guest UUID from X-Guest-Id header
        
    Returns:
        Payment record details
        
    Raises:
        HTTPException 404: Payment not found or unauthorized
    """
    try:
        # IDOR protection via helper function
        await verify_payment_ownership(transaction_id, guest_id)
        payment_ref = db.collection('payments').document(transaction_id)
        payment_doc = payment_ref.get()
        
        if not payment_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment with transaction ID {transaction_id} not found"
            )
        
        return payment_doc.to_dict()
        
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Error fetching payment details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch payment details"
        )
