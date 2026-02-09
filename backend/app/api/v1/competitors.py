"""
Competitor prices API endpoints
View and refresh competitor rental car pricing data
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from app.core.firebase import db, Collections
from app.core.security import get_guest_id_optional, verify_cron_secret
from app.services.competitors.crawler import (
    refresh_competitor_prices,
    get_supported_cities,
    get_supported_providers,
    cleanup_old_prices,
    get_branches_cached
)
from google.cloud.firestore_v1 import FieldFilter

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== SCHEMAS ====================

class CompetitorPrice(BaseModel):
    """Competitor price document"""
    id: str
    provider: str
    city: str
    category: str
    price: float
    currency: str = "SAR"
    url: Optional[str] = None
    vehicle_name: Optional[str] = None
    scraped_at: datetime
    created_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "abc123",
                "provider": "yelo",
                "city": "riyadh",
                "category": "sedan",
                "vehicle_name": "Toyota Camry",
                "price": 120.0,
                "currency": "SAR",
                "url": "https://yelo.sa",
                "scraped_at": "2024-01-15T10:30:00Z"
            }
        }


class CompetitorPricesList(BaseModel):
    """List of competitor prices with metadata"""
    prices: List[CompetitorPrice]
    total: int
    filters_applied: dict
    
    class Config:
        json_schema_extra = {
            "example": {
                "prices": [],
                "total": 15,
                "filters_applied": {
                    "provider": "yelo",
                    "city": "riyadh"
                }
            }
        }


class RefreshRequest(BaseModel):
    """Request to refresh competitor prices"""
    cities: Optional[List[str]] = Field(
        default=None,
        description="List of cities to scrape (defaults to all supported)"
    )
    providers: Optional[List[str]] = Field(
        default=None,
        description="List of providers to scrape (defaults to all)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "cities": ["riyadh", "jeddah"],
                "providers": ["yelo", "lumi"]
            }
        }


class RefreshResponse(BaseModel):
    """Response from refresh operation"""
    message: str
    total_offers: int
    offers_by_provider: dict
    cities_scraped: List[str]
    errors: List[str]
    duration_seconds: Optional[float] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Competitor price refresh started in background",
                "total_offers": 24,
                "offers_by_provider": {
                    "yelo": 12,
                    "lumi": 12
                },
                "cities_scraped": ["riyadh", "jeddah"],
                "errors": [],
                "duration_seconds": 15.3
            }
        }


class SupportedOptionsResponse(BaseModel):
    """Supported cities and providers"""
    cities: List[str]
    providers: List[str]
    
    class Config:
        json_schema_extra = {
            "example": {
                "cities": ["riyadh", "jeddah", "dammam"],
                "providers": ["budget", "hertz", "yelo", "lumi"]
            }
        }


# ==================== ENDPOINTS ====================

@router.get(
    "/",
    response_model=CompetitorPricesList,
    summary="List competitor prices",
    description="Get competitor rental prices with optional filters"
)
async def list_competitor_prices(
    provider: Optional[str] = Query(None, description="Filter by provider"),
    city: Optional[str] = Query(None, description="Filter by city (branch_id)"),
    category: Optional[str] = Query(None, description="Filter by vehicle category (vehicle_class)"),
    limit: int = Query(50, ge=1, le=100, description="Maximum results")
):
    """
    Get list of competitor prices from Firestore.
    
    Can filter by provider, city (branch_id), and/or category (vehicle_class).
    
    NOTE: Uses competitor_prices_latest collection with field mapping:
    - city -> branch_id (partial match)
    - category -> vehicle_class  
    - price -> price_per_day
    """
    try:
        # Use competitor_prices_latest collection (has the actual scraped data)
        competitor_ref = db.collection('competitor_prices_latest')
        
        filters_applied = {}
        
        # Get all documents first (small collection, ~100 docs max)
        docs = competitor_ref.limit(limit * 2).stream()
        
        prices = []
        for doc in docs:
            doc_data = doc.to_dict()
            
            # Apply filters in Python (avoids Firestore index requirements)
            if provider and doc_data.get('provider', '').lower() != provider.lower():
                continue
            
            # City filter - partial match on branch_id
            if city:
                branch_id = doc_data.get('branch_id', '').lower()
                if city.lower() not in branch_id and branch_id not in city.lower():
                    continue
                filters_applied['city'] = city.lower()
            
            # Category filter - STRICT match on vehicle_class
            if category:
                vehicle_class = doc_data.get('vehicle_class', '').lower()
                category_lower = category.lower()
                # Map similar category names (but DON'T mix unrelated categories)
                category_map = {
                    'compact': ['economy', 'compact', 'small'],  # compact uses economy prices
                    'economy': ['economy', 'compact', 'small'],
                    'sedan': ['sedan', 'standard', 'mid-size', 'midsize'],
                    'suv': ['suv', 'crossover', '4x4', 'full-size suv'],  # SUV only
                    'luxury': ['luxury', 'premium', 'executive'],  # Luxury only - NO sedan fallback
                    'minivan': ['van', 'minivan'],
                    'truck': ['truck', 'pickup'],
                }
                valid_classes = category_map.get(category_lower, [category_lower])
                if vehicle_class not in valid_classes:
                    continue
                filters_applied['category'] = category_lower
            
            # Map Firestore field names to API schema
            scraped_at = doc_data.get('scraped_at')
            if scraped_at and hasattr(scraped_at, 'isoformat'):
                scraped_at_dt = scraped_at
            else:
                scraped_at_dt = datetime.utcnow()
                
            prices.append(CompetitorPrice(
                id=doc.id,
                provider=doc_data.get('provider', ''),
                city=doc_data.get('branch_id', ''),  # branch_id -> city
                category=doc_data.get('vehicle_class', ''),  # vehicle_class -> category
                price=float(doc_data.get('price_per_day', 0)),  # price_per_day -> price
                currency=doc_data.get('currency', 'SAR'),
                url=doc_data.get('source_url'),
                vehicle_name=doc_data.get('vehicle_name'),  # Include car name
                scraped_at=scraped_at_dt,
                created_at=doc_data.get('created_at')
            ))
            
            if len(prices) >= limit:
                break
        
        # Sort by scraped_at descending (in Python)
        prices.sort(key=lambda x: x.scraped_at, reverse=True)
        
        return CompetitorPricesList(
            prices=prices[:limit],
            total=len(prices),
            filters_applied=filters_applied
        )
        
    except Exception as e:
        logger.error(f"Error listing competitor prices: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/options",
    response_model=SupportedOptionsResponse,
    summary="Get supported options",
    description="List supported cities and providers for scraping"
)
async def get_supported_options():
    """
    Get list of supported cities and providers.
    
    Use these values for filtering and refresh requests.
    """
    # Load branches from Firestore first
    await get_branches_cached(db)
    
    return SupportedOptionsResponse(
        cities=get_supported_cities(),
        providers=get_supported_providers()
    )


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    summary="Refresh competitor prices",
    description="Scrape competitor websites and update prices",
    
)
async def refresh_prices(
    request: RefreshRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(verify_cron_secret)
):
    """
    Refresh competitor prices by scraping provider websites.
    
    **Cron/Admin only** - Requires X-Cron-Secret header.
    
    Runs as a background task to avoid timeout.
    Returns immediately with a summary once started.
    
    ⚠️ **Important**: Web scraping must comply with:
    - robots.txt policies
    - Terms of Service
    - Rate limiting
    - Legal requirements
    
    Consider using official APIs where available.
    """
    try:
        # Load branches from Firestore first
        await get_branches_cached(db)
        
        # Get cities and providers
        cities = request.cities if request.cities else get_supported_cities()
        providers = request.providers if request.providers else get_supported_providers()
        
        logger.info(
            f"Competitor refresh started: "
            f"{len(cities)} cities, {len(providers)} providers"
        )
        
        # Run refresh in background
        background_tasks.add_task(
            refresh_competitor_prices,
            cities=cities,
            firestore_client=db,
            providers=providers
        )
        
        return RefreshResponse(
            message="Competitor price refresh started in background",
            total_offers=0,  # Will be updated as task runs
            offers_by_provider={},
            cities_scraped=cities,
            errors=[],
            duration_seconds=None
        )
        
    except Exception as e:
        logger.error(f"Error starting competitor refresh: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/cleanup",
    summary="Cleanup old prices",
    description="Delete competitor prices older than specified days",
    
)
async def cleanup_prices(
    days_old: int = Query(7, ge=1, le=365, description="Delete prices older than this"),
    _: None = Depends(verify_cron_secret)
):
    """
    Delete old competitor prices from database.
    
    **Cron/Admin only** - Requires X-Cron-Secret header.
    
    Helps keep database clean and reduces storage costs.
    Default is 7 days - adjust based on your refresh frequency.
    """
    try:
        deleted_count = await cleanup_old_prices(db, days_old)
        
        logger.info(
            f"Cleaned up {deleted_count} competitor prices older than {days_old} days"
        )
        
        return {
            "message": f"Deleted {deleted_count} old competitor prices",
            "days_old": days_old,
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up prices: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/stats",
    summary="Get competitor price statistics",
    description="Summary statistics about competitor prices in database"
)
async def get_competitor_stats():
    """
    Get statistics about competitor prices.
    
    Provides overview of:
    - Total prices in database
    - Breakdown by provider
    - Breakdown by city
    - Latest scrape time
    """
    try:
        competitor_ref = db.collection('competitor_prices')
        
        # Get all documents (consider pagination for large datasets)
        docs = competitor_ref.stream()
        
        stats = {
            "total_prices": 0,
            "by_provider": {},
            "by_city": {},
            "by_category": {},
            "latest_scrape": None
        }
        
        for doc in docs:
            doc_data = doc.to_dict()
            stats["total_prices"] += 1
            
            # Count by provider
            provider = doc_data.get('provider', 'unknown')
            stats["by_provider"][provider] = stats["by_provider"].get(provider, 0) + 1
            
            # Count by city
            city = doc_data.get('city', 'unknown')
            stats["by_city"][city] = stats["by_city"].get(city, 0) + 1
            
            # Count by category
            category = doc_data.get('category', 'unknown')
            stats["by_category"][category] = stats["by_category"].get(category, 0) + 1
            
            # Track latest scrape
            scraped_at = doc_data.get('scraped_at')
            if scraped_at and (not stats["latest_scrape"] or scraped_at > stats["latest_scrape"]):
                stats["latest_scrape"] = scraped_at
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting competitor stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Scheduler Endpoints ====================

@router.get(
    "/scheduler/status",
    summary="Get scheduler status",
    description="View background scheduler status and scheduled jobs"
)
async def get_scheduler_status_endpoint():
    """
    Get the current status of the background scheduler.
    
    Shows:
    - Whether scheduler is running
    - List of scheduled jobs with next run times
    """
    try:
        from app.core.scheduler import get_scheduler_status
        return get_scheduler_status()
    except Exception as e:
        logger.error(f"Error getting scheduler status: {str(e)}")
        return {"status": "error", "error": str(e)}


@router.post(
    "/scheduler/trigger",
    summary="Trigger scrape and price update now",
    description="Manually trigger competitor scraping and automatic price update"
)
async def trigger_scrape_now_endpoint(
    background_tasks: BackgroundTasks,
    _: None = Depends(verify_cron_secret)
):
    """
    Manually trigger a competitor scrape and price update.
    
    **Cron/Admin only** - Requires X-Cron-Secret header.
    
    This runs the same job that the scheduler runs every 24 hours:
    1. Scrapes all competitor websites
    2. Updates vehicle prices based on competitor data
    
    The task runs in the background to avoid timeout.
    """
    try:
        from app.core.scheduler import trigger_scrape_now
        
        # Run in background
        background_tasks.add_task(trigger_scrape_now)
        
        return {
            "message": "Scrape and price update triggered",
            "status": "started",
            "note": "Check /api/v1/competitors/scheduler/status for results"
        }
    except Exception as e:
        logger.error(f"Error triggering scrape: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

