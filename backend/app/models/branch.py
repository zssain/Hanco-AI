"""
Branch model for Firestore
Represents pickup/dropoff branch locations
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any
from google.cloud.firestore_v1 import DocumentSnapshot


@dataclass
class Branch:
    """Branch location model"""
    
    id: str
    name: str
    city: str
    address: str
    phone: str
    latitude: float
    longitude: float
    is_active: bool = True
    
    def to_firestore(self) -> Dict[str, Any]:
        """Convert model to Firestore-compatible dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'city': self.city,
            'address': self.address,
            'phone': self.phone,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'is_active': self.is_active,
        }
    
    @classmethod
    def from_firestore(cls, doc: DocumentSnapshot) -> Optional['Branch']:
        """Create Branch instance from Firestore document"""
        if not doc.exists:
            return None
        
        data = doc.to_dict()
        return cls(
            id=doc.id,
            name=data.get('name', ''),
            city=data.get('city', ''),
            address=data.get('address', ''),
            phone=data.get('phone', ''),
            latitude=data.get('latitude', 0.0),
            longitude=data.get('longitude', 0.0),
            is_active=data.get('is_active', True),
        )
