"""
Pricing log model for Firestore
Stores pricing calculation history
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
from google.cloud.firestore_v1 import DocumentSnapshot


@dataclass
class PricingLog:
    """Pricing log model for Firestore storage"""
    
    vehicle_id: str
    request_time: datetime
    base_rate: float
    predicted_rate: float
    weather_factor: float
    competitor_factor: float
    demand_factor: float = 1.0
    seasonal_factor: float = 1.0
    duration_days: int = 1
    total_price: float = 0.0
    city: str = ""
    id: Optional[str] = None
    
    def to_firestore(self) -> Dict[str, Any]:
        """Convert model to Firestore-compatible dictionary"""
        data = {
            'vehicle_id': self.vehicle_id,
            'request_time': self.request_time,
            'base_rate': self.base_rate,
            'predicted_rate': self.predicted_rate,
            'weather_factor': self.weather_factor,
            'competitor_factor': self.competitor_factor,
            'demand_factor': self.demand_factor,
            'seasonal_factor': self.seasonal_factor,
            'duration_days': self.duration_days,
            'total_price': self.total_price,
            'city': self.city,
        }
        
        if self.id:
            data['id'] = self.id
            
        return data
    
    @classmethod
    def from_firestore(cls, doc: DocumentSnapshot) -> Optional['PricingLog']:
        """Create PricingLog instance from Firestore document"""
        if not doc.exists:
            return None
        
        data = doc.to_dict()
        
        return cls(
            id=doc.id,
            vehicle_id=data.get('vehicle_id', ''),
            request_time=data.get('request_time', datetime.now()),
            base_rate=data.get('base_rate', 0.0),
            predicted_rate=data.get('predicted_rate', 0.0),
            weather_factor=data.get('weather_factor', 1.0),
            competitor_factor=data.get('competitor_factor', 1.0),
            demand_factor=data.get('demand_factor', 1.0),
            seasonal_factor=data.get('seasonal_factor', 1.0),
            duration_days=data.get('duration_days', 1),
            total_price=data.get('total_price', 0.0),
            city=data.get('city', '')
        )
