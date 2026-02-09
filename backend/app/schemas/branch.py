"""
Branch schemas for API requests/responses
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class BranchBase(BaseModel):
    """Base branch schema"""
    name: str
    city: str
    address: str
    phone: str
    latitude: float
    longitude: float
    is_active: bool = True


class BranchCreate(BranchBase):
    """Create branch request"""
    pass


class BranchResponse(BranchBase):
    """Branch response"""
    id: str
    
    class Config:
        from_attributes = True


class BranchListResponse(BaseModel):
    """List of branches response"""
    branches: List[BranchResponse]
    total: int
