"""
Dynamic pricing endpoints for Hanco-AI
ML-powered pricing using ONNX Runtime with rule engine and guardrails
"""
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field, validator
from typing import Dict, Any, Optional, List
from datetime import date, datetime, timedelta
import logging
import uuid
import time
import hashlib
import asyncio
import numpy as np

from app.core.firebase import db, Collections, update_vehicle_base_rate
from app.core.config import settings
from app.core.security import get_current_user_optional, get_guest_id
from app.services.pricing.feature_builder import (
    build_pricing_features,
    compute_utilization_snapshot,
    compute_demand_signal
)
from app.services.pricing.onnx_runtime import predict_price
from app.services.pricing.rule_engine import PricingFactors, PricingRuleEngine
from google.cloud import firestore

logger = logging.getLogger(__name__)

router = APIRouter()

# ==================== Pricing Configuration ====================
# Profit-first pricing with market-aware guardrails

# Freshness threshold - competitor data older than this is considered stale
STALE_AFTER_HOURS = 12

# Minimum profit margin over cost
MIN_MARGIN = 0.15  # 15%

# Maximum drop from base rate (protects against cost data errors)
MAX_RATE_DROP = 0.25  # 25% max drop from base

# Premium cap when market data is fresh (Hanco = premium brand)
MARKET_PREMIUM_CAP = 0.15  # Up to 15% above p90

# Internal surge cap when market data is stale
INTERNAL_SURGE_CAP = 0.25  # Up to 25% above base


# ==================== Helper Functions ====================

def _map_duration_to_key(duration_days: int) -> str:
    """Map rental duration to standard key: D1/D3/D7/M1"""
    if duration_days == 1:
        return "D1"
    elif 2 <= duration_days <= 4:
        return "D3"
    elif 5 <= duration_days <= 10:
        return "D7"
    else:
        return "M1"


def compute_demand_index(branch_key: str, class_bucket: str, pickup_date: date) -> float:
    """
    Compute demand index for ONNX model (0.0 to 1.0).
    
    Args:
        branch_key: Branch identifier
        class_bucket: Vehicle class bucket
        pickup_date: Rental pickup date
        
    Returns:
        Float between 0.0 and 1.0 representing demand level
    """
    try:
        # Try to get real-time demand signal from Firestore
        from datetime import datetime, timedelta
        from app.services.pricing.feature_builder import compute_demand_signal
        
        # Map class_bucket to vehicle_class for demand signal
        class_map = {
            'Compact': 'economy',
            'Sedan': 'sedan',
            'SUV': 'suv',
            'Luxury': 'luxury',
            'Other': 'sedan'  # fallback
        }
        vehicle_class = class_map.get(class_bucket, 'sedan')
        
        # Use current hour bucket for demand signal
        now = datetime.utcnow()
        hour_bucket = now.strftime('%Y-%m-%d-%H')
        
        signal = compute_demand_signal(
            firestore_client=db,
            branch_id=branch_key,
            vehicle_class=vehicle_class,
            hour_bucket=hour_bucket
        )
        
        if signal and 'demand_index' in signal:
            demand_idx = float(signal['demand_index'])
            # Ensure it's between 0 and 1
            return max(0.0, min(1.0, demand_idx))
    except Exception as e:
        logger.debug(f"Could not compute demand index, using fallback: {str(e)}")
    
    # Fallback: Use date-based heuristic
    # Weekend bookings typically have higher demand
    # Saudi weekend: Thursday (3), Friday (4), Saturday (5)
    is_weekend = pickup_date.weekday() in [3, 4, 5]  # Thursday, Friday, Saturday
    
    # Check if booking is far in advance (lower demand) or last-minute (higher demand)
    days_until_pickup = (pickup_date - date.today()).days
    
    if days_until_pickup < 0:
        return 0.5  # Past date, neutral
    elif days_until_pickup <= 2:
        # Last-minute booking, high demand
        base_demand = 0.75
    elif days_until_pickup <= 7:
        # Within a week, moderate demand
        base_demand = 0.6
    elif days_until_pickup <= 30:
        # 1-4 weeks advance, normal demand
        base_demand = 0.5
    else:
        # Far advance, lower demand
        base_demand = 0.4
    
    # Add weekend premium
    if is_weekend:
        base_demand = min(1.0, base_demand + 0.1)
    
    return base_demand


async def get_competitor_market_stats(
    branch_key: str,
    duration_key: str,
    class_bucket: str,
    max_age_hours: int = 168  # 7 days - relaxed for stale data scenarios
) -> Dict[str, Any]:
    """
    Fetch competitor market statistics from Firestore by querying by FIELDS.
    
    The scraper stores documents with random IDs, so we query by:
    - branch_id (contains city)
    - vehicle_class (matches class_bucket)
    - duration_days (mapped from duration_key, with flexible matching)
    
    Args:
        branch_key: Branch identifier (e.g., 'riyadh_airport', 'jeddah_downtown')
        duration_key: Duration key (D1/D3/D7/M1)
        class_bucket: Vehicle bucket (economy, compact, sedan, suv, luxury)
        max_age_hours: Maximum age of competitor data in hours (default 168 = 7 days)
    
    Returns:
        Dict with market statistics or empty stats if no data
    """
    try:
        # Extract city from branch_key (e.g., "riyadh_airport" -> "riyadh")
        city_id = branch_key.split("_")[0] if "_" in branch_key else branch_key
        
        # Map duration_key to duration_days
        duration_map = {'D1': 1, 'D3': 3, 'D7': 7, 'M1': 30}
        target_duration = duration_map.get(duration_key, 1)
        
        def _fetch_market_stats():
            from datetime import timezone as tz
            from google.cloud.firestore_v1 import FieldFilter
            
            prices = []
            providers_used = []
            newest_scraped_at = None
            competitor_ref = db.collection("competitor_prices_latest")
            
            # Query by vehicle_class field (case-insensitive matching)
            # The scraper stores class as lowercase: 'economy', 'sedan', 'suv', 'luxury'
            target_class = class_bucket.lower()
            
            # Also try related classes for better matching
            class_variants = [target_class]
            if target_class == 'luxury':
                class_variants.extend(['premium', 'executive'])
            elif target_class == 'economy':
                class_variants.extend(['compact', 'small'])
            elif target_class == 'compact':
                class_variants.extend(['economy', 'small'])
            elif target_class == 'suv':
                class_variants.extend(['crossover', '4x4'])
            
            # Query all documents and filter
            # (Firestore doesn't support OR queries easily, so we filter in Python)
            cutoff_time = datetime.now(tz.utc) - timedelta(hours=max_age_hours)
            
            try:
                docs = competitor_ref.stream()
                
                for doc in docs:
                    data = doc.to_dict()
                    
                    # Check city match (branch_id contains city OR city matches exactly)
                    branch_id = (data.get('branch_id') or '').lower()
                    if city_id.lower() not in branch_id and branch_id != city_id.lower():
                        continue
                    
                    # Check vehicle class match
                    vehicle_class = (data.get('vehicle_class') or '').lower()
                    if vehicle_class not in class_variants:
                        continue
                    
                    # Check duration match - FLEXIBLE: use any available data
                    # We prefer exact matches but will accept any duration data for daily rate reference
                    doc_duration = data.get('duration_days', 1)
                    # For now, accept all durations since we only have 1-day data
                    # The per-day price is still valid as a market reference
                    
                    # Check freshness
                    scraped_at = data.get('scraped_at')
                    if scraped_at:
                        if hasattr(scraped_at, 'tzinfo') and scraped_at.tzinfo is None:
                            scraped_at = scraped_at.replace(tzinfo=tz.utc)
                        if scraped_at < cutoff_time:
                            continue  # Skip stale data
                    
                    # Extract price
                    price = data.get('price_per_day') or data.get('last_price_per_day')
                    if price and price > 0:
                        prices.append(float(price))
                        provider = data.get('provider', 'unknown')
                        if provider not in providers_used:
                            providers_used.append(provider)
                        
                        # Track newest scraped_at
                        if scraped_at:
                            if newest_scraped_at is None or scraped_at > newest_scraped_at:
                                newest_scraped_at = scraped_at
                                
            except Exception as query_error:
                logger.error(f"Error querying competitor prices: {query_error}")
            
            # No data found
            if not prices:
                logger.info(f"No competitor data found for {city_id}/{class_bucket}/{duration_key}")
                return {
                    'count': 0,
                    'min': None,
                    'median': None,
                    'mean': None,
                    'p75': None,
                    'p90': None,
                    'std': None,
                    'providers_used': [],
                    'is_stale': True,
                    'newest_scraped_at': None
                }
            
            logger.info(f"Found {len(prices)} competitor prices for {city_id}/{class_bucket}/{duration_key}: {prices}")
            
            # Compute statistics
            prices_array = np.array(prices)
            return {
                'count': len(prices),
                'min': float(np.min(prices_array)),
                'median': float(np.median(prices_array)),
                'mean': float(np.mean(prices_array)),
                'p75': float(np.percentile(prices_array, 75)),
                'p90': float(np.percentile(prices_array, 90)),
                'std': float(np.std(prices_array)) if len(prices) > 1 else 0.0,
                'providers_used': providers_used,
                'is_stale': False,
                'newest_scraped_at': newest_scraped_at.isoformat() if newest_scraped_at else None
            }
        
        return await asyncio.to_thread(_fetch_market_stats)
        
    except Exception as e:
        logger.error(f"Error fetching competitor market stats: {str(e)}")
        return {
            'count': 0,
            'min': None,
            'median': None,
            'mean': None,
            'p75': None,
            'p90': None,
            'std': None,
            'providers_used': [],
            'is_stale': True,
            'newest_scraped_at': None
        }


async def check_pricing_cache(
    branch_key: str,
    vehicle_id: str,
    pickup_date: date,
    duration_key: str
) -> Optional[Dict[str, Any]]:
    """
    Check if cached price exists and is still valid.
    
    Returns cached price data if valid, None otherwise.
    """
    if not settings.PRICING_CACHE_ENABLED:
        return None
    
    try:
        pickup_str = pickup_date.strftime("%Y%m%d")
        cache_key = f"{branch_key}_{vehicle_id}_{pickup_str}_{duration_key}"
        
        def _check_cache():
            cache_ref = db.collection("fleet_prices_cache").document(cache_key)
            cache_doc = cache_ref.get()
            
            if not cache_doc.exists:
                return None
            
            cache_data = cache_doc.to_dict()
            expires_at = cache_data.get('expires_at')
            
            # Check expiration
            if expires_at and datetime.utcnow() < expires_at:
                logger.debug(f"Cache HIT: {cache_key}")
                return cache_data
            else:
                logger.debug(f"Cache EXPIRED: {cache_key}")
                return None
        
        return await asyncio.to_thread(_check_cache)
        
    except Exception as e:
        logger.warning(f"Error checking cache: {str(e)}")
        return None


async def write_pricing_cache(
    branch_key: str,
    vehicle_id: str,
    pickup_date: date,
    duration_key: str,
    final_price_per_day: float,
    total_price: float,
    currency: str,
    breakdown: Optional[Dict] = None,
    model_version: str = "onnx_v1",
    competitor_median: Optional[float] = None
) -> None:
    """
    Write computed price to cache with TTL.
    """
    if not settings.PRICING_CACHE_ENABLED:
        return
    
    try:
        pickup_str = pickup_date.strftime("%Y%m%d")
        cache_key = f"{branch_key}_{vehicle_id}_{pickup_str}_{duration_key}"
        
        created_at = datetime.utcnow()
        expires_at = created_at + timedelta(minutes=settings.PRICING_CACHE_TTL_MINUTES)
        
        cache_data = {
            'final_price_per_day': final_price_per_day,
            'total_price': total_price,
            'currency': currency,
            'created_at': created_at,
            'expires_at': expires_at,
            'model_version': model_version
        }
        
        if breakdown:
            cache_data['breakdown'] = breakdown
        
        if competitor_median:
            cache_data['competitor_snapshot_used'] = competitor_median
        
        def _write_cache():
            cache_ref = db.collection("fleet_prices_cache").document(cache_key)
            cache_ref.set(cache_data)
            logger.debug(f"Cache WRITE: {cache_key}")
        
        await asyncio.to_thread(_write_cache)
        
    except Exception as e:
        logger.warning(f"Error writing cache: {str(e)}")


async def write_pricing_decision(
    decision_id: str,
    vehicle_id: str,
    vehicle_name: Optional[str],
    branch_key: str,
    branch_type: str,
    city: Optional[str],
    pickup_at: datetime,
    dropoff_at: datetime,
    class_bucket: str,
    duration_days: int,
    duration_key: str,
    base_daily_rate: float,
    cost_per_day: float,
    market_stats: Optional[Dict],
    features: Dict[str, float],
    ml_price: float,
    rule_price: float,
    blended_price: float,
    final_price: float,
    floor_price: float,
    ceiling_price: float,
    model_version: str,
    discounts_applied: Dict[str, float],
    premiums_applied: Dict[str, float],
    cache_hit: bool = False
) -> None:
    """
    Write comprehensive pricing decision log to Firestore for analytics and debugging.
    
    Logs all inputs, intermediate calculations, and final pricing decisions
    for each vehicle quote to enable performance analysis and model debugging.
    """
    try:
        # Build comprehensive decision log
        decision_data = {
            'created_at': firestore.SERVER_TIMESTAMP,
            'decision_id': decision_id,
            
            # Location & Branch Info
            'branch_key': branch_key,
            'branch_type': branch_type,
            'city': city or branch_key,  # Fallback to branch_key if city not provided
            
            # Rental Period
            'pickup_at': pickup_at,
            'dropoff_at': dropoff_at,
            'duration_days': duration_days,
            'durationKey': duration_key,
            
            # Vehicle Info
            'vehicle_id': vehicle_id,
            'class_bucket': class_bucket,
            'base_daily_rate': base_daily_rate,
            'cost_per_day': cost_per_day,
            
            # Market Intelligence
            'market_stats': {
                'count': market_stats.get('count', 0) if market_stats else 0,
                'median': market_stats.get('median') if market_stats else None,
                'p75': market_stats.get('p75') if market_stats else None,
                'p90': market_stats.get('p90') if market_stats else None,
                'providers_used': market_stats.get('providers_used', []) if market_stats else []
            },
            
            # ONNX Features (in FEATURE_ORDER)
            'onnx_features': {
                'rental_length_days': features.get('rental_length_days'),
                'day_of_week': features.get('day_of_week'),
                'month': features.get('month'),
                'base_daily_rate': features.get('base_daily_rate'),
                'avg_temp': features.get('avg_temp'),
                'rain': features.get('rain'),
                'wind': features.get('wind'),
                'avg_competitor_price': features.get('avg_competitor_price'),
                'demand_index': features.get('demand_index'),
                'bias': features.get('bias')
            },
            
            # Pricing Calculations
            'ml_price_per_day': ml_price,
            'rule_price_per_day': rule_price,
            'blended': blended_price,
            'floor': floor_price,
            'ceiling': ceiling_price,
            'final_price_per_day': final_price,
            
            # Applied Adjustments
            'discounts_applied': discounts_applied,
            'premiums_applied': premiums_applied,
            
            # Metadata
            'model_version': model_version,
            'cache_hit': cache_hit
        }
        
        # Add vehicle_name if provided
        if vehicle_name:
            decision_data['vehicle_name'] = vehicle_name
        
        def _write_decision():
            db.collection(Collections.PRICING_DECISIONS).document(decision_id).set(decision_data)
        
        await asyncio.to_thread(_write_decision)
        logger.debug(f"Pricing decision logged: {decision_id} for vehicle {vehicle_id}")
        
    except Exception as e:
        logger.error(f"Error writing pricing decision: {str(e)}")


# ==================== Schemas ====================

class VehicleQuoteInput(BaseModel):
    """Vehicle data for quote pricing"""
    vehicle_id: str
    vehicle_name: Optional[str] = None  # Vehicle display name
    class_bucket: str  # economy, compact, sedan, suv, luxury, van
    base_daily_rate: float
    cost_per_day: float
    branch_type: Optional[str] = "City"  # City or Airport


class QuoteRequest(BaseModel):
    """Request for quote-time pricing of all vehicles"""
    branch_key: str = Field(..., description="Branch identifier (e.g., 'riyadh')")
    pickup_at: datetime = Field(..., description="Pickup datetime")
    dropoff_at: datetime = Field(..., description="Dropoff datetime")
    vehicles: List[VehicleQuoteInput] = Field(..., description="List of available vehicles")


class VehiclePriceResult(BaseModel):
    """Pricing result for a single vehicle"""
    vehicle_id: str
    daily_price: float
    total_price: float
    breakdown: Dict[str, float]
    cached: bool = False


class QuoteResponse(BaseModel):
    """Response with all vehicle prices"""
    quote_id: str
    branch_key: str
    duration_days: int
    duration_key: str
    vehicles: List[VehiclePriceResult]
    market_stats_available: bool
    timestamp: datetime


class PricingRequest(BaseModel):
    """Request schema for price calculation"""
    vehicle_id: str = Field(..., description="Vehicle ID")
    city: str = Field(..., description="City name")
    start_date: date = Field(..., description="Rental start date")
    end_date: date = Field(..., description="Rental end date")
    km_package: Optional[str] = Field(
        default="A",
        description="Kilometer package tier: A (250km/day), B (400km/day), C (600km/day)"
    )
    estimated_trip_km: Optional[float] = Field(
        default=None,
        description="Optional: estimated trip distance in km for accurate fee calculation"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional: session ID for stable A/B test assignment"
    )


class PricingResponse(BaseModel):
    """Response schema for price calculation"""
    quote_id: str
    vehicle_id: str
    city: str
    rental_length_days: int
    daily_price: float
    total_price: float
    distance_fee: float
    distance_breakdown: Dict[str, Any]  # Transparent km package breakdown
    weather: Dict[str, float]
    competitor_summary: Dict[str, float]
    features: Dict[str, float]
    pricing_breakdown: Dict[str, float]
    experiment_group: Optional[str] = None  # A/B test group assignment
    guardrails_applied: list
    model_version: str
    timestamp: datetime
    warnings: Optional[list] = Field(default_factory=list)  # Warning flags


# ==================== Core Pricing Function ====================

async def compute_vehicle_price(
    vehicle: VehicleQuoteInput,
    branch_key: str,
    pickup_at: datetime,
    dropoff_at: datetime,
    duration_days: int,
    duration_key: str,
    pickup_date: date,
    is_weekend: bool,
    market_stats: Optional[Dict[str, float]],
    weather_defaults: Dict[str, float]
) -> Dict[str, Any]:
    """
    Compute price for a single vehicle using ML + Rule-based blending with guardrails.
    
    Returns dict with: daily_price, total_price, breakdown, cached flag
    """
    try:
        # Step 1: Check cache
        cached_data = await check_pricing_cache(
            branch_key=branch_key,
            vehicle_id=vehicle.vehicle_id,
            pickup_date=pickup_date,
            duration_key=duration_key
        )
        
        if cached_data:
            return {
                'vehicle_id': vehicle.vehicle_id,
                'daily_price': cached_data['final_price_per_day'],
                'total_price': cached_data['total_price'],
                'breakdown': cached_data.get('breakdown', {}),
                'cached': True
            }
        
        # Step 2: Get competitor average
        avg_competitor_price = vehicle.base_daily_rate
        if market_stats and market_stats.get('median'):
            avg_competitor_price = market_stats['median']
        
        # Step 3: Compute demand index (simplified - use 0.5 default)
        demand_index = 0.5
        
        # Step 4: Build features for ONNX
        features = {
            'rental_length_days': float(duration_days),
            'day_of_week': float(pickup_date.weekday()),
            'month': float(pickup_date.month),
            'base_daily_rate': vehicle.base_daily_rate,
            'avg_temp': weather_defaults['avg_temp'],
            'rain': weather_defaults['rain'],
            'wind': weather_defaults['wind'],
            'avg_competitor_price': avg_competitor_price,
            'demand_index': demand_index,
            'bias': 1.0
        }
        
        # Step 5: ML price from ONNX
        ml_price_per_day = predict_price(features)
        
        # Step 6: Rule-based price with discounts/premiums
        rule_price = vehicle.base_daily_rate
        discounts_applied = {}
        premiums_applied = {}
        
        # Duration discounts
        if duration_days >= 30:
            discount = 0.15
            rule_price *= (1 - discount)
            discounts_applied['duration_30d'] = discount
        elif duration_days >= 7:
            discount = 0.07
            rule_price *= (1 - discount)
            discounts_applied['duration_7d'] = discount
        elif duration_days >= 3:
            discount = 0.03
            rule_price *= (1 - discount)
            discounts_applied['duration_3d'] = discount
        
        # Airport premium
        if vehicle.branch_type and vehicle.branch_type.lower() == "airport":
            premium = 0.05
            rule_price *= (1 + premium)
            premiums_applied['airport'] = premium
        
        # Weekend premium (Saudi Friday/Saturday)
        if is_weekend:
            premium = 0.03
            rule_price *= (1 + premium)
            premiums_applied['weekend'] = premium
        
        # Step 7: PROFIT-FIRST + MARKET-ALIGNED guardrails
        # Key principle: Never sell below cost + minimum margin, but stay market-competitive
        
        MIN_MARGIN = 0.15           # 15% minimum profit margin
        MARKET_CAP_PCT = 0.10       # Allow up to +10% above market reference
        
        # Always start with cost floor (never go below cost + margin)
        cost_floor = vehicle.cost_per_day * (1 + MIN_MARGIN) if vehicle.cost_per_day else vehicle.base_daily_rate * 0.70
        
        has_competitor_data = market_stats and market_stats.get('median') and market_stats.get('median') > 0
        
        if has_competitor_data:
            # Use MEDIAN as market reference (more robust than avg against outliers)
            market_ref = market_stats['median']
            
            # CEILING: Hard cap at market median + 10%
            # This is the KEY to staying competitive - we NEVER exceed this
            ceiling_price = market_ref * (1 + MARKET_CAP_PCT)
            
            # FLOOR: Based on cost (profit protection) and market (don't undercut too much)
            market_floor = market_ref * 0.85  # Don't undercut market by more than 15%
            floor_price = max(cost_floor, market_floor)
            
            logger.info(f"Competitive mode: market_ref={market_ref:.2f}, floor={floor_price:.2f}, ceiling={ceiling_price:.2f}")
        else:
            # No market data - use base rate with cost protection
            floor_price = max(cost_floor, vehicle.base_daily_rate * 0.80)
            ceiling_price = vehicle.base_daily_rate * 1.10
            logger.debug(f"Internal mode: cost_floor={cost_floor:.2f}, floor={floor_price:.2f}, ceiling={ceiling_price:.2f}")
        
        # Handle impossible case: floor > ceiling (can't be profitable AND competitive)
        # Policy: profit-first (override market ceiling)
        if floor_price > ceiling_price:
            logger.warning(f"Impossible pricing case: floor ({floor_price:.2f}) > ceiling ({ceiling_price:.2f}). Profit-first override.")
            ceiling_price = floor_price
        
        # Step 8: Blend ML and rule-based (60% rule, 40% ML)
        blended_price = (0.6 * rule_price) + (0.4 * ml_price_per_day)
        
        # Step 9: Apply guardrails
        clamped_price = max(floor_price, min(blended_price, ceiling_price))
        
        # Step 10: Bounded rounding - round to step while respecting bounds
        # This ensures final price is ALWAYS a multiple of step AND within [floor, ceiling]
        import math
        step = 5.0 if clamped_price >= 50 else 1.0
        rounded_price = round(clamped_price / step) * step
        
        # If rounding breaks ceiling, round DOWN to allowed step under ceiling
        if rounded_price > ceiling_price:
            rounded_price = math.floor(ceiling_price / step) * step
        
        # If rounding breaks floor, round UP to allowed step above floor
        if rounded_price < floor_price:
            rounded_price = math.ceil(floor_price / step) * step
        
        # Final safety clamp (handles edge cases)
        final_price = max(floor_price, min(rounded_price, ceiling_price))
        
        total_price = final_price * duration_days
        
        # Breakdown for transparency
        breakdown = {
            'ml_price': round(ml_price_per_day, 2),
            'rule_price': round(rule_price, 2),
            'blended': round(blended_price, 2),
            'floor': round(floor_price, 2),
            'ceiling': round(ceiling_price, 2),
            'final': round(final_price, 2),
            'discounts': discounts_applied,
            'premiums': premiums_applied
        }
        
        # Write decision log
        decision_id = str(uuid.uuid4())
        await write_pricing_decision(
            decision_id=decision_id,
            vehicle_id=vehicle.vehicle_id,
            vehicle_name=getattr(vehicle, 'vehicle_name', None),
            branch_key=branch_key,
            branch_type=vehicle.branch_type or "City",
            city=branch_key,
            pickup_at=pickup_at,
            dropoff_at=dropoff_at,
            class_bucket=vehicle.class_bucket,
            duration_days=duration_days,
            duration_key=duration_key,
            base_daily_rate=vehicle.base_daily_rate,
            cost_per_day=vehicle.cost_per_day,
            market_stats=market_stats,
            features=features,
            ml_price=ml_price_per_day,
            rule_price=rule_price,
            blended_price=blended_price,
            final_price=final_price,
            floor_price=floor_price,
            ceiling_price=ceiling_price,
            model_version="onnx_v1",
            discounts_applied=discounts_applied,
            premiums_applied=premiums_applied,
            cache_hit=False
        )
        
        # Write cache
        await write_pricing_cache(
            branch_key=branch_key,
            vehicle_id=vehicle.vehicle_id,
            pickup_date=pickup_date,
            duration_key=duration_key,
            final_price_per_day=final_price,
            total_price=total_price,
            currency="SAR",
            breakdown=breakdown,
            model_version="onnx_v1",
            competitor_median=market_stats.get('median') if market_stats else None
        )
        
        return {
            'vehicle_id': vehicle.vehicle_id,
            'daily_price': final_price,
            'total_price': total_price,
            'breakdown': breakdown,
            'cached': False
        }
        
    except Exception as e:
        logger.error(f"Error computing price for vehicle {vehicle.vehicle_id}: {str(e)}")
        # Fallback to base rate
        fallback_price = vehicle.base_daily_rate
        return {
            'vehicle_id': vehicle.vehicle_id,
            'daily_price': fallback_price,
            'total_price': fallback_price * duration_days,
            'breakdown': {'error': str(e), 'fallback': fallback_price},
            'cached': False
        }


# ==================== Endpoints ====================

@router.post("/quote", response_model=QuoteResponse)
async def price_quote_vehicles(request: QuoteRequest):
    """
    Quote-time pricing engine: Price all available vehicles for a rental period.
    
    This endpoint efficiently prices multiple vehicles at once with:
    - Caching (30min TTL)
    - Market statistics from competitor data
    - ML pricing via ONNX
    - Rule-based discounts/premiums
    - Guardrails (floor/ceiling)
    - Decision logging
    
    Returns pricing for all vehicles with breakdown.
    """
    try:
        # Validate dates
        if request.dropoff_at <= request.pickup_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Dropoff must be after pickup"
            )
        
        if request.pickup_at.date() < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pickup date cannot be in the past"
            )
        
        # Calculate duration
        duration_delta = request.dropoff_at - request.pickup_at
        duration_days = max(1, duration_delta.days)
        duration_key = _map_duration_to_key(duration_days)
        
        # Determine if weekend (Thursday-Saturday in Saudi Arabia)
        pickup_date = request.pickup_at.date()
        is_weekend = pickup_date.weekday() in [3, 4, 5]  # Thu=3, Fri=4, Sat=5
        
        # Weather defaults (could be enhanced with real API)
        weather_defaults = {
            'avg_temp': 25.0,
            'rain': 0.0,
            'wind': 10.0
        }
        
        # Get market stats (shared across all vehicles in same class)
        # We'll fetch stats per class_bucket as needed
        class_to_stats = {}
        
        # Group vehicles by class_bucket to minimize market stats queries
        from collections import defaultdict
        vehicles_by_class = defaultdict(list)
        for vehicle in request.vehicles:
            vehicles_by_class[vehicle.class_bucket].append(vehicle)
        
        # Fetch market stats for each unique class
        for class_bucket in vehicles_by_class.keys():
            stats = await get_competitor_market_stats(
                branch_key=request.branch_key,
                duration_key=duration_key,
                class_bucket=class_bucket
            )
            class_to_stats[class_bucket] = stats
        
        # Price all vehicles concurrently
        pricing_tasks = []
        for vehicle in request.vehicles:
            market_stats = class_to_stats.get(vehicle.class_bucket)
            task = compute_vehicle_price(
                vehicle=vehicle,
                branch_key=request.branch_key,
                pickup_at=request.pickup_at,
                dropoff_at=request.dropoff_at,
                duration_days=duration_days,
                duration_key=duration_key,
                pickup_date=pickup_date,
                is_weekend=is_weekend,
                market_stats=market_stats,
                weather_defaults=weather_defaults
            )
            pricing_tasks.append(task)
        
        # Execute all pricing computations in parallel
        results = await asyncio.gather(*pricing_tasks)
        
        # Build response
        quote_id = str(uuid.uuid4())
        market_stats_available = any(
            stats and stats.get('count', 0) > 0 for stats in class_to_stats.values()
        )
        
        vehicle_results = [
            VehiclePriceResult(**result) for result in results
        ]
        
        logger.info(
            f"Quote {quote_id}: priced {len(vehicle_results)} vehicles for {request.branch_key}, "
            f"duration={duration_days}d, cached={sum(1 for r in results if r['cached'])}"
        )
        
        return QuoteResponse(
            quote_id=quote_id,
            branch_key=request.branch_key,
            duration_days=duration_days,
            duration_key=duration_key,
            vehicles=vehicle_results,
            market_stats_available=market_stats_available,
            timestamp=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in quote pricing: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute quote: {str(e)}"
        )


@router.post("/calculate", response_model=PricingResponse)
async def calculate_pricing(request: PricingRequest):
    """
    Calculate dynamic price for a vehicle rental
    
    Full pipeline:
    1. Build feature snapshot (competitors, utilization, demand, distance, time)
    2. Call ONNX baseline pricing model
    3. Apply rule engine with guardrails
    4. Compute distance fees
    5. Generate quote and store in price_quotes
    6. Store pricing history
    
    Returns total price with complete breakdown.
    start_time = time.time()
    warnings = []
    
    """
    try:
        # Validate dates
        if request.end_date <= request.start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End date must be after start date"
            )
        
        if request.start_date < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start date cannot be in the past"
            )
        
        # Get vehicle from Firestore
        vehicle_ref = db.collection(Collections.VEHICLES).document(request.vehicle_id)
        vehicle_doc = vehicle_ref.get()
        
        if not vehicle_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vehicle with ID {request.vehicle_id} not found"
            )
        
        vehicle_data = vehicle_doc.to_dict()
        base_daily_rate = vehicle_data.get('base_daily_rate', 100.0)
        vehicle_category = vehicle_data.get('category', 'sedan')
        
        # === STEP 1: Build Full Feature Snapshot ===
        
        rental_length_days = (request.end_date - request.start_date).days
        lead_time_days = (request.start_date - date.today()).days
        
        # Build ML features
        features = await build_pricing_features(
            vehicle_doc=vehicle_data,
            start_date=request.start_date,
            end_date=request.end_date,
            city=request.city,
            firestore_client=db
        )
        
        # Get real-time utilization
        utilization_snapshot = compute_utilization_snapshot(
            db,
            branch_id=request.city,
            vehicle_class=vehicle_category,
            target_date=request.start_date
        )
        utilization_rate = utilization_snapshot.get('utilization_rate', 0.5) if utilization_snapshot else 0.5
        
        # Get real-time demand signal
        current_hour = datetime.utcnow().strftime('%Y-%m-%d-%H')
        demand_signal = compute_demand_signal(
            db,
            branch_id=request.city,
            vehicle_class=vehicle_category,
            hour_bucket=current_hour
        )
        demand_index = demand_signal.get('demand_index', 0.5) if demand_signal else 0.5
        
        # === Check competitor data staleness ===
        competitor_age_hours = None
        try:
            # Check competitor_aggregates last_updated timestamp
            city_slug = request.city.lower().replace(' ', '-')
            aggregate_ref = db.collection('competitor_aggregates').document(f"{city_slug}_{vehicle_category}")
            aggregate_doc = aggregate_ref.get()
            
            if aggregate_doc.exists:
                aggregate_data = aggregate_doc.to_dict()
                last_updated = aggregate_data.get('last_updated')
                if last_updated:
                    age = datetime.utcnow() - last_updated
                    competitor_age_hours = age.total_seconds() / 3600
                    
                    if competitor_age_hours > 2.0:
                        warning = f"Competitor data is {competitor_age_hours:.1f} hours old (>2h threshold)"
                        warnings.append(warning)
                        logger.warning(warning)
        except Exception as e:
            logger.warning(f"Error checking competitor data age: {str(e)}")
        
        # === STEP 1.5: Get Last Price with Three-Tier Fallback ===
        
        # Ensures rule engine receives reliable last_price for continuity and rate-of-change guardrails
        last_quoted_price = None
        last_price_source = None
        
        # Try 1: Latest pricing_history for this vehicle (most reliable source)
        try:
            history_query = db.collection(Collections.PRICING_HISTORY) \
                .where('vehicle_id', '==', request.vehicle_id) \
                .order_by('timestamp', direction=firestore.Query.DESCENDING) \
                .limit(1)
            
            history_docs = list(history_query.stream())
            if history_docs:
                history_data = history_docs[0].to_dict()
                last_quoted_price = history_data.get('final_daily_price')
                if last_quoted_price:
                    last_price_source = 'pricing_history'
                    logger.debug(f"Last price from pricing_history: {last_quoted_price:.2f}")
        except Exception as e:
            logger.warning(f"Error querying pricing_history: {str(e)}")
        
        # Try 2: Latest price_quotes for this vehicle (fallback)
        if last_quoted_price is None:
            try:
                quotes_query = db.collection(Collections.PRICE_QUOTES) \
                    .where('vehicle_id', '==', request.vehicle_id) \
                    .order_by('created_at', direction=firestore.Query.DESCENDING) \
                    .limit(1)
                
                quote_docs = list(quotes_query.stream())
                if quote_docs:
                    quote_data = quote_docs[0].to_dict()
                    last_quoted_price = quote_data.get('daily_price')
                    if last_quoted_price:
                        last_price_source = 'price_quotes'
                        logger.debug(f"Last price from price_quotes: {last_quoted_price:.2f}")
            except Exception as e:
                logger.warning(f"Error querying price_quotes: {str(e)}")
        
        # === STEP 2: Call ONNX Baseline Model ===
        
        baseline_price_ml = predict_price(features)
        
        # Try 3: Use baseline_price_ml as final fallback
        if last_quoted_price is None:
            last_quoted_price = baseline_price_ml
            last_price_source = 'baseline_ml'
        
        # === STEP 2.5: A/B Test Assignment ===
        
        # Assign stable experiment group based on session_id (or generate if not provided)
        session_id = request.session_id or str(uuid.uuid4())
        
        # Hash session_id and use modulo for stable assignment
        # Group A: 90% (hash % 100 < 90)
        # Group B: 10% (hash % 100 >= 90)
        session_hash = int(hashlib.md5(session_id.encode()).hexdigest(), 16)
        experiment_group = "A" if session_hash % 100 < 90 else "B"
        
        logger.debug(f"A/B test assignment: session={session_id[:8]}..., group={experiment_group}")
        
        # === STEP 3: Apply Rule Engine with A/B Test Variants ===
        
        # Group A: Current production settings (control)
        # Group B: Variant with tighter competitor band (1.12x vs 1.15x utilization cap)
        if experiment_group == "A":
            # Control group - current settings
            rule_engine = PricingRuleEngine(
                min_margin=0.15,
                max_ceiling_multiplier=3.0,
                competitor_band_tolerance=0.20,
                max_rate_change=0.08,
                smoothing_alpha=0.3
            )
        else:
            # Experiment group B - tighter competitor band
            rule_engine = PricingRuleEngine(
                min_margin=0.15,
                max_ceiling_multiplier=3.0,
                competitor_band_tolerance=0.17,  # Tighter band (17% vs 20%)
                max_rate_change=0.08,
                smoothing_alpha=0.3
            )
        
        pricing_factors = PricingFactors(
            baseline_price_ml=baseline_price_ml,
            base_daily_rate=base_daily_rate,
            rental_length_days=rental_length_days,
            lead_time_days=lead_time_days,
            utilization_rate=utilization_rate,
            demand_index=demand_index,
            avg_competitor_price=features.get('avg_competitor_price', 0.0),
            day_of_week=request.start_date.weekday(),
            month=request.start_date.month,
            hour_of_booking=datetime.utcnow().hour,
            last_quoted_price=last_quoted_price
        )
        
        pricing_result = rule_engine.calculate_price(pricing_factors)
        
        # === STEP 4: Compute Distance Fees with Tier Packages ===
        
        # KM Package Tiers (per day)
        KM_PACKAGES = {
            'A': {'included_km_per_day': 250, 'daily_surcharge': 0.0, 'extra_km_rate': 0.50},
            'B': {'included_km_per_day': 400, 'daily_surcharge': 15.0, 'extra_km_rate': 0.50},
            'C': {'included_km_per_day': 600, 'daily_surcharge': 30.0, 'extra_km_rate': 0.50}
        }
        
        # Validate and get package
        km_package = (request.km_package or 'A').upper()
        if km_package not in KM_PACKAGES:
            km_package = 'A'
        
        package_config = KM_PACKAGES[km_package]
        included_km_per_day = package_config['included_km_per_day']
        daily_surcharge = package_config['daily_surcharge']
        extra_km_rate = package_config['extra_km_rate']
        
        # Calculate total included km
        included_km_total = included_km_per_day * rental_length_days
        
        # Estimate trip km (use provided or default heuristic)
        if request.estimated_trip_km:
            estimated_trip_km = request.estimated_trip_km
        else:
            # Default heuristic: 150 km/day for short trips, 200 km/day for longer trips
            estimated_trip_km = rental_length_days * (150 if rental_length_days <= 3 else 200)
        
        # Calculate extra km and fees
        extra_km_estimated = max(0, estimated_trip_km - included_km_total)
        extra_km_fee = extra_km_estimated * extra_km_rate
        package_surcharge_total = daily_surcharge * rental_length_days
        distance_fee_total = extra_km_fee + package_surcharge_total
        
        # Distance breakdown for transparency
        distance_breakdown = {
            'km_package': km_package,
            'included_km_per_day': included_km_per_day,
            'included_km_total': included_km_total,
            'estimated_trip_km': estimated_trip_km,
            'extra_km_estimated': extra_km_estimated,
            'extra_km_rate': extra_km_rate,
            'extra_km_fee': extra_km_fee,
            'daily_surcharge': daily_surcharge,
            'package_surcharge_total': package_surcharge_total,
            'distance_fee_total': distance_fee_total
        }
        
        logger.info(
            f"Distance pricing: package={km_package}, "
            f"included={included_km_total}km, estimated={estimated_trip_km}km, "
            f"extra={extra_km_estimated}km, fee={distance_fee_total:.2f} SAR"
        )
        
        # === STEP 5: Calculate Final Prices ===
        
        daily_price = pricing_result.final_price_per_day
        distance_fee = distance_fee_total
        total_price = (daily_price * rental_length_days) + distance_fee
        
        # === STEP 6: Generate Quote and Store in price_quotes ===
        
        quote_id = str(uuid.uuid4())
        
        feature_snapshot = {
            'ml_features': features,
            'utilization_rate': utilization_rate,
            'demand_index': demand_index,
            'lead_time_days': lead_time_days,
            'rental_length_days': rental_length_days,
            'last_quoted_price': last_quoted_price,
            'last_price_source': last_price_source  # Track source for debugging
        }
        
        price_quote = {
            'quote_id': quote_id,
            'vehicle_id': request.vehicle_id,
            'branch_id': request.city,
            'vehicle_class': vehicle_category,
            'city': request.city,
            'start_date': request.start_date.isoformat(),
            'end_date': request.end_date.isoformat(),
            'rental_length_days': rental_length_days,
            'lead_time_days': lead_time_days,
            # Pricing
            'baseline_price_ml': baseline_price_ml,
            'daily_price': daily_price,
            'total_price': total_price,
            'distance_fee': distance_fee,
            'distance_breakdown': distance_breakdown,  # Store full km package breakdown
            'last_price': last_quoted_price,  # Store for next quote
            'last_price_source': last_price_source,  # Track source (pricing_history|price_quotes|baseline)
            # Feature snapshot
            'feature_snapshot': feature_snapshot,
            'pricing_breakdown': pricing_result.price_breakdown,
            'factors_applied': pricing_result.factors_applied,
            'guardrails_applied': pricing_result.guardrails_applied,
            # Metadata
            'model_version': 'onnx_v1',
            'rule_engine_version': 'v1',
            'created_at': firestore.SERVER_TIMESTAMP,
            'expires_at': None,  # Can add expiration logic
            'warnings': warnings,  # Store warnings for analysis
            'experiment_group': experiment_group,  # A/B test group
            'session_id': session_id  # Session tracking
        }
        
        db.collection(Collections.PRICE_QUOTES).document(quote_id).set(price_quote)
        
        # === STEP 7: Store Pricing History ===
        
        history_id = str(uuid.uuid4())
        pricing_history = {
            'history_id': history_id,
            'quote_id': quote_id,
            'vehicle_id': request.vehicle_id,
            'city': request.city,
            'vehicle_class': vehicle_category,
            'date': request.start_date.isoformat(),
            # Price changes
            'baseline_price_ml': baseline_price_ml,
            'final_daily_price': daily_price,
            'previous_price': last_quoted_price,
            'price_change': daily_price - last_quoted_price if last_quoted_price else 0.0,
            'price_change_pct': ((daily_price - last_quoted_price) / last_quoted_price * 100) if last_quoted_price else 0.0,
            # Context
            'utilization_rate': utilization_rate,
            'demand_index': demand_index,
            'competitor_avg': features.get('avg_competitor_price', 0.0),
            'factors_applied': pricing_result.factors_applied,
            'guardrails_applied': pricing_result.guardrails_applied,
            # Metadata
            'timestamp': firestore.SERVER_TIMESTAMP
        }
        
        db.collection(Collections.PRICING_HISTORY).document(history_id).set(pricing_history)
        
        # === Calculate latency and log performance ===
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Log key signals for monitoring
        logger.info(
            f"Pricing quote: quote_id={quote_id}, vehicle={request.vehicle_id}, "
            f"latency={latency_ms}ms, competitor_avg={features.get('avg_competitor_price', 0):.2f}, "
            f"utilization={utilization_rate:.2f}, demand_index={demand_index:.2f}, "
            f"experiment_group={experiment_group}, warnings={len(warnings)}"
        )
        
        # Prepare response data
        weather_summary = {
            'avg_temp': features['avg_temp'],
            'rain': features['rain'],
            'wind': features['wind']
        }
        
        competitor_summary = {
            'avg_competitor_price': features['avg_competitor_price'],
            'sample_count': utilization_snapshot.get('total_fleet', 0) if utilization_snapshot else 0
        }
        
        logger.info(
            f"Pricing calculated: quote={quote_id}, vehicle={request.vehicle_id}, "
            f"city={request.city}, days={rental_length_days}, "
            f"baseline={baseline_price_ml:.2f}, final={daily_price:.2f}, "
            f"guardrails={pricing_result.guardrails_applied}"
        )
        
        return PricingResponse(
            quote_id=quote_id,
            vehicle_id=request.vehicle_id,
            city=request.city,
            rental_length_days=rental_length_days,
            daily_price=round(daily_price, 2),
            total_price=round(total_price, 2),
            distance_fee=round(distance_fee, 2),
            distance_breakdown=distance_breakdown,
            weather=weather_summary,
            competitor_summary=competitor_summary,
            features=features,
            pricing_breakdown=pricing_result.price_breakdown,
            guardrails_applied=pricing_result.guardrails_applied,
            model_version='onnx_v1',
            timestamp=datetime.utcnow(),
            warnings=warnings,
            experiment_group=experiment_group
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating pricing: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate pricing: {str(e)}"
        )


# ==================== Apply Recommendation Endpoint ====================

class ApplyRecommendationRequest(BaseModel):
    """Request to apply a pricing recommendation to a vehicle"""
    vehicle_id: str = Field(..., description="Vehicle document ID")
    new_base_daily_rate: float = Field(..., gt=0, description="New base daily rate to apply")
    pricing_decision_id: Optional[str] = Field(None, description="ID of the pricing_decision doc that generated this recommendation")
    model_version: Optional[str] = Field(None, description="Model version used for recommendation")
    competitor_snapshot: Optional[Dict[str, Any]] = Field(None, description="Competitor data snapshot at time of recommendation")


class ApplyRecommendationResponse(BaseModel):
    """Response from applying a pricing recommendation"""
    status: str
    vehicle_id: str
    old_base_daily_rate: Optional[float] = None
    new_base_daily_rate: float
    delta_amount: Optional[float] = None
    delta_percent: Optional[float] = None
    history_id: Optional[str] = None
    vehicle_name: Optional[str] = None
    message: Optional[str] = None


@router.post("/apply", response_model=ApplyRecommendationResponse)
async def apply_pricing_recommendation(
    request: ApplyRecommendationRequest,
    guest_id: str = Depends(get_guest_id),
    current_user: dict = Depends(get_current_user_optional)
):
    """
    Apply a pricing recommendation to update a vehicle's base_daily_rate.
    
    This endpoint is used by admin/pricing managers to apply ML-generated
    or manually reviewed price recommendations to vehicles.
    
    Behavior:
    1. Validates new_base_daily_rate >= vehicle's cost_per_day (cost floor)
    2. Atomically updates vehicle and creates audit trail in vehicle_history
    3. Returns updated vehicle info and history record ID
    
    Request body:
    - vehicle_id: Vehicle to update
    - new_base_daily_rate: New rate to apply
    - pricing_decision_id: Optional reference to pricing decision
    - model_version: Optional model version info
    - competitor_snapshot: Optional competitor data context
    """
    try:
        # Fetch vehicle to validate and get cost floor
        vehicle_ref = db.collection(Collections.VEHICLES).document(request.vehicle_id)
        vehicle_doc = vehicle_ref.get()
        
        if not vehicle_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vehicle {request.vehicle_id} not found"
            )
        
        vehicle_data = vehicle_doc.to_dict()
        vehicle_name = vehicle_data.get('name')
        cost_per_day = vehicle_data.get('cost_per_day')
        current_rate = vehicle_data.get('base_daily_rate')
        
        # Validate against cost floor if available
        if cost_per_day and cost_per_day > 0:
            if request.new_base_daily_rate < cost_per_day:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"New rate {request.new_base_daily_rate} is below cost floor {cost_per_day}"
                )
        
        # Build triggered_by from auth context
        triggered_by = None
        if current_user and current_user.get('uid'):
            triggered_by = {
                'uid': current_user.get('uid'),
                'email': current_user.get('email')
            }
        
        # Build request context for audit trail
        request_context = {}
        if request.pricing_decision_id:
            request_context['pricing_decision_id'] = request.pricing_decision_id
        if request.model_version:
            request_context['model_version'] = request.model_version
        if request.competitor_snapshot:
            request_context['competitor_snapshot'] = request.competitor_snapshot
        
        # Apply using atomic update function
        result = update_vehicle_base_rate(
            vehicle_id=request.vehicle_id,
            new_base_daily_rate=request.new_base_daily_rate,
            reason='apply_recommendation',
            triggered_by=triggered_by,
            context=request_context if request_context else None
        )
        
        if result['status'] == 'error':
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to apply recommendation: {result.get('error')}"
            )
        
        if result['status'] == 'no_change':
            logger.info(
                f"Apply recommendation: vehicle {request.vehicle_id} already at rate {request.new_base_daily_rate}"
            )
            return ApplyRecommendationResponse(
                status='no_change',
                vehicle_id=request.vehicle_id,
                new_base_daily_rate=request.new_base_daily_rate,
                vehicle_name=vehicle_name,
                message=f'Vehicle already at target rate {request.new_base_daily_rate}'
            )
        
        logger.info(
            f"Apply recommendation: vehicle {request.vehicle_id} ({vehicle_name}) "
            f"{result['old_base_daily_rate']} -> {result['new_base_daily_rate']} "
            f"(decision: {request.pricing_decision_id}, history: {result['history_id']})"
        )
        
        return ApplyRecommendationResponse(
            status='applied',
            vehicle_id=request.vehicle_id,
            old_base_daily_rate=result['old_base_daily_rate'],
            new_base_daily_rate=result['new_base_daily_rate'],
            delta_amount=result['delta_amount'],
            delta_percent=result['delta_percent'],
            history_id=result['history_id'],
            vehicle_name=vehicle_name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying recommendation to vehicle {request.vehicle_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply pricing recommendation: {str(e)}"
        )


# ==================== UNIFIED SINGLE VEHICLE PRICING ====================
# This endpoint is the SINGLE SOURCE OF TRUTH for all pricing - chatbot, frontend, API

class UnifiedPriceRequest(BaseModel):
    """Simple request for pricing a single vehicle - used by chatbot and frontend"""
    vehicle_id: str = Field(..., description="Vehicle ID from Firebase")
    branch_key: str = Field(..., description="Pickup branch/city key (e.g., 'riyadh_airport')")
    dropoff_branch_key: Optional[str] = Field(default=None, description="Dropoff branch/city key (if different from pickup, one-way rental)")
    pickup_date: date = Field(..., description="Pickup date")
    dropoff_date: date = Field(..., description="Dropoff date")
    include_insurance: bool = Field(default=False, description="Include 15% insurance")


class UnifiedPriceResponse(BaseModel):
    """Unified pricing response for all consumers"""
    vehicle_id: str
    vehicle_name: str
    daily_rate: float
    duration_days: int
    base_total: float
    insurance_amount: float
    final_total: float
    competitor_avg: Optional[float] = None
    savings_vs_competitor: Optional[float] = None
    class_bucket: str = Field(default="sedan", description="Vehicle class used for pricing")
    market_data_used: bool = Field(default=False, description="Whether competitor data was available")
    is_one_way: bool = Field(default=False, description="True if pickup and dropoff cities differ (one-way rental)")
    one_way_premium: float = Field(default=0.0, description="One-way rental premium applied (e.g., 0.15 = 15%)")
    breakdown: Dict[str, Any]
    source: str = "unified_pricing_engine"


@router.post("/unified-price", response_model=UnifiedPriceResponse)
async def get_unified_price(request: UnifiedPriceRequest):
    """
    UNIFIED PRICING ENDPOINT - Single source of truth for ALL pricing.
    
    Used by:
    - Chatbot (orchestrator.py)
    - Frontend (pricingService.ts)
    - Any other consumer
    
    This ensures consistent pricing across all channels.
    """
    try:
        # Validate dates
        if request.dropoff_date <= request.pickup_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Dropoff must be after pickup"
            )
        
        if request.pickup_date < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pickup date cannot be in the past"
            )
        
        # Calculate duration
        duration_days = max(1, (request.dropoff_date - request.pickup_date).days)
        duration_key = _map_duration_to_key(duration_days)
        
        # Fetch vehicle from Firebase
        def _get_vehicle():
            doc = db.collection("vehicles").document(request.vehicle_id).get()
            if doc.exists:
                return doc.to_dict()
            return None
        
        vehicle_data = await asyncio.to_thread(_get_vehicle)
        
        if not vehicle_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vehicle {request.vehicle_id} not found"
            )
        
        # Extract vehicle info
        vehicle_name = vehicle_data.get('name', vehicle_data.get('vehicle_name', 'Unknown Vehicle'))
        base_daily_rate = float(vehicle_data.get('base_daily_rate', 0) or 
                                vehicle_data.get('daily_rate', 0) or 
                                vehicle_data.get('current_price', 0) or 200)
        cost_per_day = float(vehicle_data.get('cost_per_day', base_daily_rate * 0.6))
        class_bucket = vehicle_data.get('class', vehicle_data.get('category', 'sedan')).lower()
        
        # Map class names
        class_mapping = {
            'economy': 'economy',
            'compact': 'compact', 
            'sedan': 'sedan',
            'suv': 'suv',
            'luxury': 'luxury',
            'full-size suv': 'suv',
            'mid-size': 'sedan',
            'sports': 'luxury',
            'van': 'van'
        }
        class_bucket = class_mapping.get(class_bucket, 'sedan')
        
        # Build VehicleQuoteInput for compute_vehicle_price
        vehicle_input = VehicleQuoteInput(
            vehicle_id=request.vehicle_id,
            vehicle_name=vehicle_name,
            class_bucket=class_bucket,
            base_daily_rate=base_daily_rate,
            cost_per_day=cost_per_day,
            branch_type="City"
        )
        
        # Convert dates to datetime
        pickup_at = datetime.combine(request.pickup_date, datetime.min.time())
        dropoff_at = datetime.combine(request.dropoff_date, datetime.min.time())
        
        # Get market stats
        market_stats = await get_competitor_market_stats(
            branch_key=request.branch_key,
            duration_key=duration_key,
            class_bucket=class_bucket
        )
        
        # Weather defaults
        weather_defaults = {
            'avg_temp': 25.0,
            'rain': 0.0,
            'wind': 10.0
        }
        
        # Is weekend?
        is_weekend = request.pickup_date.weekday() in [3, 4, 5]  # Thu=3, Fri=4, Sat=5
        
        # Call the core pricing function
        pricing_result = await compute_vehicle_price(
            vehicle=vehicle_input,
            branch_key=request.branch_key,
            pickup_at=pickup_at,
            dropoff_at=dropoff_at,
            duration_days=duration_days,
            duration_key=duration_key,
            pickup_date=request.pickup_date,
            is_weekend=is_weekend,
            market_stats=market_stats,
            weather_defaults=weather_defaults
        )
        
        daily_rate = pricing_result['daily_price']
        base_total = pricing_result['total_price']
        
        # Detect one-way rental (pickup city != dropoff city)
        is_one_way = False
        one_way_premium = 0.0
        ONE_WAY_PREMIUM_PCT = 0.15  # 15% premium for one-way rentals
        
        if request.dropoff_branch_key:
            # Extract city from branch keys (e.g., "riyadh_airport" -> "riyadh")
            pickup_city = request.branch_key.split('_')[0].lower()
            dropoff_city = request.dropoff_branch_key.split('_')[0].lower()
            
            if pickup_city != dropoff_city:
                is_one_way = True
                one_way_premium = ONE_WAY_PREMIUM_PCT
                # Apply one-way premium to daily rate and total
                daily_rate = round(daily_rate * (1 + ONE_WAY_PREMIUM_PCT))
                base_total = round(daily_rate * duration_days)
                logger.info(f"One-way rental detected: {pickup_city} -> {dropoff_city}, +{ONE_WAY_PREMIUM_PCT*100}% premium applied")
        
        # Calculate insurance if requested
        insurance_amount = 0.0
        if request.include_insurance:
            insurance_amount = round(base_total * 0.15, 2)
        
        final_total = round(base_total + insurance_amount, 2)
        
        # Get competitor average for display
        competitor_avg = None
        savings = None
        market_data_used = market_stats and market_stats.get('count', 0) > 0 and market_stats.get('median', 0) > 0
        if market_stats and market_stats.get('median'):
            competitor_avg = market_stats['median']  # Use median for display too
            # For one-way, adjust competitor avg estimate (they also charge premium)
            if is_one_way:
                competitor_avg = round(competitor_avg * (1 + ONE_WAY_PREMIUM_PCT))
            savings = round(competitor_avg - daily_rate, 2) if competitor_avg > daily_rate else 0
        
        logger.info(
            f"Unified pricing: vehicle={request.vehicle_id}, branch={request.branch_key}, "
            f"dropoff={request.dropoff_branch_key}, is_one_way={is_one_way}, "
            f"days={duration_days}, daily={daily_rate}, total={final_total}, "
            f"class_bucket={class_bucket}, market_data_used={market_data_used}, insurance={insurance_amount}"
        )
        
        # Add one-way info to breakdown
        breakdown = pricing_result['breakdown'].copy() if pricing_result.get('breakdown') else {}
        if is_one_way:
            breakdown['one_way_premium'] = one_way_premium
        
        return UnifiedPriceResponse(
            vehicle_id=request.vehicle_id,
            vehicle_name=vehicle_name,
            daily_rate=daily_rate,
            duration_days=duration_days,
            base_total=base_total,
            insurance_amount=insurance_amount,
            final_total=final_total,
            competitor_avg=competitor_avg,
            savings_vs_competitor=savings,
            class_bucket=class_bucket,
            market_data_used=market_data_used,
            is_one_way=is_one_way,
            one_way_premium=one_way_premium,
            breakdown=breakdown,
            source="unified_pricing_engine"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in unified pricing: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute price: {str(e)}"
        )
