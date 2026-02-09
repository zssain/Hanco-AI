"""
Payment Simulator Service
Simulates payment processing without actual payment gateway integration
"""
import logging
import re
import uuid
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def validate_card_number(card_number: str) -> bool:
    """
    Validate credit card number format
    
    Args:
        card_number: Card number string (may contain spaces/dashes)
        
    Returns:
        True if valid format, False otherwise
    """
    # Remove spaces and dashes
    cleaned = re.sub(r'[\s-]', '', card_number)
    
    # Check if only digits
    if not cleaned.isdigit():
        return False
    
    # Check length (13-19 digits for most cards)
    if len(cleaned) < 13 or len(cleaned) > 19:
        return False
    
    # Optional: Luhn algorithm validation
    return luhn_check(cleaned)


def luhn_check(card_number: str) -> bool:
    """
    Validate card number using Luhn algorithm
    
    Args:
        card_number: Card number string (digits only)
        
    Returns:
        True if valid, False otherwise
    """
    def digits_of(n):
        return [int(d) for d in str(n)]
    
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d * 2))
    
    return checksum % 10 == 0


def validate_expiry(expiry_month: int, expiry_year: int) -> bool:
    """
    Validate card expiry date
    
    Args:
        expiry_month: Month (1-12)
        expiry_year: Year (2025+)
        
    Returns:
        True if not expired, False otherwise
    """
    if expiry_month < 1 or expiry_month > 12:
        return False
    
    current_date = datetime.now()
    current_year = current_date.year
    current_month = current_date.month
    
    # Check if card is expired
    if expiry_year < current_year:
        return False
    if expiry_year == current_year and expiry_month < current_month:
        return False
    
    return True


def validate_cvv(cvv: str) -> bool:
    """
    Validate CVV format
    
    Args:
        cvv: CVV string
        
    Returns:
        True if valid format, False otherwise
    """
    # CVV should be 3 or 4 digits
    if not cvv.isdigit():
        return False
    
    return len(cvv) in [3, 4]


async def process_payment(
    booking_id: str,
    amount: float,
    card_details: Dict[str, any]
) -> Dict[str, any]:
    """
    Simulates payment processing
    
    In development mode, this always succeeds after basic validation.
    In production, this would integrate with a real payment gateway.
    
    Args:
        booking_id: Booking ID being paid for
        amount: Amount to charge (in SAR)
        card_details: Dictionary containing:
            - card_number: str
            - expiry_month: int
            - expiry_year: int
            - cvv: str
            - cardholder_name: str
            
    Returns:
        Dictionary with:
            - status: "success" or "failed"
            - transaction_id: Unique transaction ID
            - message: Success/error message
            - timestamp: Payment timestamp
            
    Raises:
        ValueError: If card details are invalid
    """
    try:
        logger.info(f"Processing payment for booking {booking_id}, amount: {amount} SAR")
        
        # Extract card details
        card_number = card_details.get('card_number', '')
        expiry_month = card_details.get('expiry_month')
        expiry_year = card_details.get('expiry_year')
        cvv = card_details.get('cvv', '')
        cardholder_name = card_details.get('cardholder_name', '')
        
        # Validate card number
        if not validate_card_number(card_number):
            raise ValueError("Invalid card number format")
        
        # Validate expiry
        if not validate_expiry(expiry_month, expiry_year):
            raise ValueError("Card has expired or invalid expiry date")
        
        # Validate CVV
        if not validate_cvv(cvv):
            raise ValueError("Invalid CVV format (must be 3 or 4 digits)")
        
        # Validate cardholder name
        if not cardholder_name or len(cardholder_name.strip()) < 2:
            raise ValueError("Invalid cardholder name")
        
        # Validate amount
        if amount <= 0:
            raise ValueError("Amount must be greater than 0")
        
        # ==================== SIMULATION ====================
        # In development, always succeed after validation
        # In production, this would call actual payment gateway
        
        transaction_id = f"TXN_{uuid.uuid4().hex[:12].upper()}"
        timestamp = datetime.utcnow()
        
        logger.info(f"✅ Payment simulated successfully: {transaction_id}")
        
        return {
            "status": "success",
            "transaction_id": transaction_id,
            "message": "Payment processed successfully (simulated)",
            "timestamp": timestamp.isoformat(),
            "amount": amount,
            "currency": "SAR",
            "booking_id": booking_id,
            "card_last4": card_number[-4:] if len(card_number) >= 4 else "****"
        }
        
    except ValueError as e:
        logger.error(f"Payment validation failed for booking {booking_id}: {str(e)}")
        return {
            "status": "failed",
            "transaction_id": None,
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            "amount": amount,
            "currency": "SAR",
            "booking_id": booking_id
        }
    
    except Exception as e:
        logger.error(f"Payment processing error for booking {booking_id}: {str(e)}")
        return {
            "status": "failed",
            "transaction_id": None,
            "message": "Payment processing failed",
            "timestamp": datetime.utcnow().isoformat(),
            "amount": amount,
            "currency": "SAR",
            "booking_id": booking_id
        }


async def mark_booking_paid(booking_id: str, firestore_client) -> bool:
    """
    Mark a booking as paid and confirmed
    
    Updates the booking status in Firestore:
    - payment_status: "paid"
    - status: "confirmed"
    - paid_at: current timestamp
    
    Args:
        booking_id: ID of the booking to update
        firestore_client: Firestore database client
        
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Marking booking {booking_id} as paid")
        
        # Get booking reference
        booking_ref = firestore_client.collection('bookings').document(booking_id)
        booking_doc = booking_ref.get()
        
        if not booking_doc.exists:
            logger.error(f"Booking {booking_id} not found")
            return False
        
        # Update booking status
        from google.cloud import firestore
        
        booking_ref.update({
            'payment_status': 'paid',
            'status': 'confirmed',
            'paid_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP
        })
        
        logger.info(f"✅ Booking {booking_id} marked as paid and confirmed")
        return True
        
    except Exception as e:
        logger.error(f"Error marking booking {booking_id} as paid: {str(e)}")
        return False


async def refund_payment(
    transaction_id: str,
    booking_id: str,
    amount: Optional[float] = None
) -> Dict[str, any]:
    """
    Simulates payment refund
    
    Args:
        transaction_id: Original transaction ID
        booking_id: Booking ID
        amount: Amount to refund (None = full refund)
        
    Returns:
        Dictionary with refund details
    """
    try:
        logger.info(f"Processing refund for transaction {transaction_id}")
        
        # ==================== SIMULATION ====================
        # In development, always succeed
        # In production, this would call actual payment gateway
        
        refund_id = f"RFD_{uuid.uuid4().hex[:12].upper()}"
        timestamp = datetime.utcnow()
        
        logger.info(f"✅ Refund simulated successfully: {refund_id}")
        
        return {
            "status": "success",
            "refund_id": refund_id,
            "transaction_id": transaction_id,
            "message": "Refund processed successfully (simulated)",
            "timestamp": timestamp.isoformat(),
            "amount": amount,
            "currency": "SAR",
            "booking_id": booking_id
        }
        
    except Exception as e:
        logger.error(f"Refund processing error: {str(e)}")
        return {
            "status": "failed",
            "refund_id": None,
            "transaction_id": transaction_id,
            "message": "Refund processing failed",
            "timestamp": datetime.utcnow().isoformat()
        }
