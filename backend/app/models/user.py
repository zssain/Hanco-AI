"""
User model for Firestore
Represents user documents in users collection
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
from google.cloud.firestore_v1 import DocumentSnapshot


@dataclass
class User:
    """User model for Firestore storage"""
    
    uid: str
    email: str
    full_name: str
    phone: str
    role: str = "customer"  # admin, customer, business, partner, support
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_firestore(self) -> Dict[str, Any]:
        """Convert model to Firestore-compatible dictionary"""
        data = {
            'uid': self.uid,
            'email': self.email,
            'full_name': self.full_name,
            'phone': self.phone,
            'role': self.role,
            'is_active': self.is_active,
        }
        
        if self.created_at:
            data['created_at'] = self.created_at
        if self.updated_at:
            data['updated_at'] = self.updated_at
            
        return data
    
    @classmethod
    def from_firestore(cls, doc: DocumentSnapshot) -> Optional['User']:
        """Create User instance from Firestore document"""
        if not doc.exists:
            return None
        
        data = doc.to_dict()
        
        return cls(
            uid=data.get('uid', doc.id),
            email=data.get('email', ''),
            full_name=data.get('full_name', ''),
            phone=data.get('phone', ''),
            role=data.get('role', 'customer'),
            is_active=data.get('is_active', True),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
    
    def validate_role(self) -> bool:
        """Validate user role"""
        valid_roles = ['admin', 'customer', 'business', 'partner', 'support']
        return self.role in valid_roles
