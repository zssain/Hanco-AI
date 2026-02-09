"""
Competitor price model for Firestore
Represents scraped competitor pricing data
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
from google.cloud.firestore_v1 import DocumentSnapshot


@dataclass
class CompetitorPrice:
    """Competitor price model for Firestore storage"""
    
    provider: str  # yelo, lumi, budget, hertz, etc.
    city: str
    category: str  # sedan, suv, luxury, economy
    price: float
    scraped_at: datetime
    id: Optional[str] = None
    currency: str = "SAR"
    source_url: Optional[str] = None
    
    def to_firestore(self) -> Dict[str, Any]:
        """Convert model to Firestore-compatible dictionary"""
        data = {
            'provider': self.provider,
            'city': self.city,
            'category': self.category,
            'price': self.price,
            'scraped_at': self.scraped_at,
            'currency': self.currency,
        }
        
        if self.id:
            data['id'] = self.id
        if self.source_url:
            data['source_url'] = self.source_url
            
        return data
    
    @classmethod
    def from_firestore(cls, doc: DocumentSnapshot) -> Optional['CompetitorPrice']:
        """Create CompetitorPrice instance from Firestore document"""
        if not doc.exists:
            return None
        
        data = doc.to_dict()
        
        return cls(
            id=doc.id,
            provider=data.get('provider', ''),
            city=data.get('city', ''),
            category=data.get('category', ''),
            price=data.get('price', 0.0),
            scraped_at=data.get('scraped_at', datetime.now()),
            currency=data.get('currency', 'SAR'),
            source_url=data.get('source_url')
        )
    
    def validate_provider(self) -> bool:
        """Validate competitor provider"""
        valid_providers = ['yelo', 'lumi', 'budget', 'hertz', 'theeb', 'hala']
        return self.provider.lower() in valid_providers
    
    def is_recent(self, hours: int = 24) -> bool:
        """Check if price data is recent"""
        age = datetime.now() - self.scraped_at
        return age.total_seconds() < (hours * 3600)
