"""
Vehicle request/response schemas
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime


class VehicleBase(BaseModel):
    """Base vehicle schema"""
    name: str = Field(..., min_length=2)
    brand: Optional[str] = Field(default="Unknown")
    category: str
    base_daily_rate: float = Field(..., gt=0)
    cost_per_day: Optional[float] = Field(None, gt=0, description="Cost to company per day (for floor pricing)")
    city: str
    image_url: Optional[str] = None
    year: Optional[int] = Field(None, ge=2000, le=2030)
    features: List[str] = Field(default_factory=list)
    
    # Additional vehicle details
    model: Optional[str] = None
    make: Optional[str] = None
    seats: Optional[int] = Field(None, ge=2, le=15)
    transmission: Optional[str] = None
    fuel_type: Optional[str] = None
    location: Optional[str] = None
    branch: Optional[str] = None
    type: Optional[str] = None
    daily_rate: Optional[float] = None
    available: Optional[bool] = True
    image: Optional[str] = None
    
    @validator('category')
    def validate_category(cls, v):
        valid_categories = ['sedan', 'suv', 'luxury', 'economy', 'compact', 'sports', 'van', 'truck', 'minivan']
        if v.lower() not in valid_categories:
            raise ValueError(f'Category must be one of: {", ".join(valid_categories)}')
        return v.lower()
    
    @validator('brand', pre=True, always=True)
    def set_default_brand(cls, v):
        return v if v else "Unknown"


class VehicleCreate(VehicleBase):
    """Create vehicle request"""
    status: str = Field(default="available", pattern=r'^(available|maintenance)$')


class VehicleUpdate(BaseModel):
    """Update vehicle request (all fields optional)"""
    name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    base_daily_rate: Optional[float] = Field(None, gt=0)
    cost_per_day: Optional[float] = Field(None, gt=0, description="Cost to company per day")
    city: Optional[str] = None
    status: Optional[str] = None
    image_url: Optional[str] = None
    year: Optional[int] = None
    features: Optional[List[str]] = None
    
    # Audit trail fields
    reason: Optional[str] = Field(
        None, 
        description="Reason for change: manual_update, apply_recommendation, migration, etc."
    )
    request_context: Optional[dict] = Field(
        None,
        description="Optional traceability context: pricing_decision_id, model_version, competitor_snapshot"
    )


class VehicleResponse(VehicleBase):
    """Vehicle response with additional fields"""
    id: str
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class VehicleListResponse(BaseModel):
    """List of vehicles response"""
    vehicles: List[VehicleResponse]
    total: int
    page: int = 1
    page_size: int = 20


class VehicleSearchRequest(BaseModel):
    """Vehicle search/filter request"""
    city: Optional[str] = None
    category: Optional[str] = None
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)
    status: Optional[str] = "available"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class RollbackRequest(BaseModel):
    """Request to rollback vehicle base_daily_rate"""
    history_id: Optional[str] = Field(
        None,
        description="ID of the vehicle_history document to rollback to (uses old_base_daily_rate from that record)"
    )
    target_base_daily_rate: Optional[float] = Field(
        None,
        gt=0,
        description="Target base_daily_rate to set (alternative to history_id)"
    )
    reason: str = Field(
        default="rollback",
        description="Reason for the rollback"
    )
    
    @validator('target_base_daily_rate', always=True)
    def validate_rollback_target(cls, v, values):
        history_id = values.get('history_id')
        if not history_id and not v:
            raise ValueError('Either history_id or target_base_daily_rate must be provided')
        if history_id and v:
            raise ValueError('Provide either history_id or target_base_daily_rate, not both')
        return v
