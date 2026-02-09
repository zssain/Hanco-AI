"""
Payment model for Firestore
Represents payment transactions
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
from google.cloud.firestore_v1 import DocumentSnapshot


@dataclass
class Payment:
    """Payment model for Firestore storage"""
    
    id: str
    booking_id: str
    user_id: str
    amount: float
    currency: str = "SAR"
    status: str = "pending"  # pending, completed, failed, refunded
    payment_method: str = "card"  # card, apple_pay, mada
    transaction_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_firestore(self) -> Dict[str, Any]:
        """Convert model to Firestore-compatible dictionary"""
        data = {
            'id': self.id,
            'booking_id': self.booking_id,
            'user_id': self.user_id,
            'amount': self.amount,
            'currency': self.currency,
            'status': self.status,
            'payment_method': self.payment_method,
        }
        
        if self.transaction_id:
            data['transaction_id'] = self.transaction_id
        if self.created_at:
            data['created_at'] = self.created_at
        if self.updated_at:
            data['updated_at'] = self.updated_at
            
        return data
    
    @classmethod
    def from_firestore(cls, doc: DocumentSnapshot) -> Optional['Payment']:
        """Create Payment instance from Firestore document"""
        if not doc.exists:
            return None
        
        data = doc.to_dict()
        
        return cls(
            id=data.get('id', doc.id),
            booking_id=data.get('booking_id', ''),
            user_id=data.get('user_id', ''),
            amount=data.get('amount', 0.0),
            currency=data.get('currency', 'SAR'),
            status=data.get('status', 'pending'),
            payment_method=data.get('payment_method', 'card'),
            transaction_id=data.get('transaction_id'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
    
    def validate_status(self) -> bool:
        """Validate payment status"""
        valid_statuses = ['pending', 'completed', 'failed', 'refunded']
        return self.status in valid_statuses
    
    def validate_payment_method(self) -> bool:
        """Validate payment method"""
        valid_methods = ['card', 'apple_pay', 'mada', 'stc_pay']
        return self.payment_method in valid_methods
