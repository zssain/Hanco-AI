"""
Branches API endpoints
Handles branch locations for pickup/dropoff
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
import logging

from app.core.firebase import db, Collections
from app.schemas.branch import BranchResponse, BranchListResponse, BranchCreate
from app.models.branch import Branch

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=BranchListResponse)
async def get_branches(
    city: Optional[str] = None,
    is_active: bool = True
):
    """
    Get all branches, optionally filtered by city.
    
    Args:
        city: Filter by city name (e.g., "Riyadh", "Jeddah")
        is_active: Filter by active status
        
    Returns:
        List of branch locations
    """
    try:
        query = db.collection(Collections.BRANCHES)
        
        # Filter by active status
        if is_active:
            query = query.where('is_active', '==', True)
        
        # Filter by city if provided
        if city:
            query = query.where('city', '==', city)
        
        docs = query.stream()
        
        branches = []
        for doc in docs:
            branch = Branch.from_firestore(doc)
            if branch:
                branches.append(BranchResponse(
                    id=branch.id,
                    name=branch.name,
                    city=branch.city,
                    address=branch.address,
                    phone=branch.phone,
                    latitude=branch.latitude,
                    longitude=branch.longitude,
                    is_active=branch.is_active
                ))
        
        return BranchListResponse(
            branches=branches,
            total=len(branches)
        )
        
    except Exception as e:
        logger.error(f"Error fetching branches: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch branches"
        )


@router.get("/{branch_id}", response_model=BranchResponse)
async def get_branch(branch_id: str):
    """Get a specific branch by ID"""
    try:
        doc = db.collection(Collections.BRANCHES).document(branch_id).get()
        
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Branch not found"
            )
        
        branch = Branch.from_firestore(doc)
        
        return BranchResponse(
            id=branch.id,
            name=branch.name,
            city=branch.city,
            address=branch.address,
            phone=branch.phone,
            latitude=branch.latitude,
            longitude=branch.longitude,
            is_active=branch.is_active
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching branch {branch_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch branch"
        )
