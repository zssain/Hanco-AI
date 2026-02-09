"""
Booking request/response schemas
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime, date


class BookingBase(BaseModel):
    """Base booking schema"""
    vehicle_id: str
    start_date: date
    end_date: date
    pickup_branch_id: str
    dropoff_branch_id: str
    insurance_selected: bool = False
    payment_mode: str = Field(default="cash", pattern=r'^(cash|card)$')
    
    @validator('end_date')
    def validate_dates(cls, v, values):
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('End date must be after start date')
        return v
    
    @validator('start_date')
    def validate_start_date(cls, v):
        if v < date.today():
            raise ValueError('Start date cannot be in the past')
        return v


class BookingCreate(BookingBase):
    """Create booking request"""
    quote_id: Optional[str] = Field(None, description="Optional price quote ID to link")


class BookingUpdate(BaseModel):
    """Update booking request"""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = Field(None, pattern=r'^(pending|confirmed|active|completed|cancelled)$')
    payment_status: Optional[str] = Field(None, pattern=r'^(pending|completed|refunded|failed)$')


class BookingResponse(BookingBase):
    """Booking response with additional fields"""
    id: str
    guest_id: str
    total_price: float
    insurance_amount: float
    status: str
    payment_status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class BookingListResponse(BaseModel):
    """List of bookings response"""
    bookings: List[BookingResponse]
    total: int
    page: int = 1
    page_size: int = 20


class BookingSearchRequest(BaseModel):
    """Booking search/filter request"""
    guest_id: Optional[str] = None
    vehicle_id: Optional[str] = None
    status: Optional[str] = None
    payment_status: Optional[str] = None
    start_date_from: Optional[date] = None
    start_date_to: Optional[date] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
