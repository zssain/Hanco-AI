"""
Vehicle model for Firestore
Represents vehicle documents in vehicles collection
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from google.cloud.firestore_v1 import DocumentSnapshot


@dataclass
class Vehicle:
    """Vehicle model for Firestore storage"""
    
    id: str
    name: str
    brand: str
    category: str  # sedan, suv, luxury, economy, etc.
    base_daily_rate: float
    city: str
    status: str = "available"  # available, rented, maintenance
    image_url: str = ""
    cost_per_day: Optional[float] = None  # Cost to company per day (for floor pricing)
    year: Optional[int] = None
    features: List[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_firestore(self) -> Dict[str, Any]:
        """Convert model to Firestore-compatible dictionary"""
        data = {
            'id': self.id,
            'name': self.name,
            'brand': self.brand,
            'category': self.category,
            'base_daily_rate': self.base_daily_rate,
            'city': self.city,
            'status': self.status,
            'image_url': self.image_url,
            'features': self.features,
        }
        
        if self.cost_per_day is not None:
            data['cost_per_day'] = self.cost_per_day
        if self.year:
            data['year'] = self.year
        if self.created_at:
            data['created_at'] = self.created_at
        if self.updated_at:
            data['updated_at'] = self.updated_at
            
        return data
    
    @classmethod
    def from_firestore(cls, doc: DocumentSnapshot) -> Optional['Vehicle']:
        """Create Vehicle instance from Firestore document"""
        if not doc.exists:
            return None
        
        data = doc.to_dict()
        
        return cls(
            id=data.get('id', doc.id),
            name=data.get('name', ''),
            brand=data.get('brand', ''),
            category=data.get('category', ''),
            base_daily_rate=data.get('base_daily_rate', 0.0),
            city=data.get('city', ''),
            status=data.get('status', 'available'),
            image_url=data.get('image_url', ''),
            cost_per_day=data.get('cost_per_day'),
            year=data.get('year'),
            features=data.get('features', []),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
    
    def validate_status(self) -> bool:
        """Validate vehicle status"""
        valid_statuses = ['available', 'rented', 'maintenance']
        return self.status in valid_statuses
    
    def validate_category(self) -> bool:
        """Validate vehicle category"""
        valid_categories = ['sedan', 'suv', 'luxury', 'economy', 'sports', 'van', 'truck']
        return self.category.lower() in valid_categories
