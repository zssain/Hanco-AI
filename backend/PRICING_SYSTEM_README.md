# 🧠 Hanco AI Dynamic Pricing System

## Complete Technical Documentation

This document explains the AI-powered dynamic pricing system for Hanco Rent-a-Car, covering the complete flow from competitor data scraping to real-time price calculation.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Phase 1: Competitor Data Scraping](#phase-1-competitor-data-scraping)
4. [Phase 2: Firebase Data Storage](#phase-2-firebase-data-storage)
5. [Phase 3: Unified Pricing Endpoint](#phase-3-unified-pricing-endpoint)
6. [Phase 4: Feature Building](#phase-4-feature-building)
7. [Phase 5: ML Model Prediction (ONNX)](#phase-5-ml-model-prediction-onnx)
8. [Phase 6: Rule Engine](#phase-6-rule-engine)
9. [Phase 7: Price Blending & Guardrails](#phase-7-price-blending--guardrails)
10. [Phase 8: Complete Calculation Example](#phase-8-complete-calculation-example)
11. [Phase 9: Audit Trail](#phase-9-audit-trail)
12. [Key Files Reference](#key-files-reference)
13. [API Endpoints](#api-endpoints)
14. [Configuration](#configuration)
15. [Training the Model](#training-the-model)

---

## System Overview

The Hanco AI pricing system is a **unified pricing engine** that provides **identical prices** across all channels:

- ✅ **Website Booking** (frontend)
- ✅ **AI Chatbot** (orchestrator)
- ✅ **API Consumers** (external integrations)

### Core Components

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           HANCO AI PRICING SYSTEM                                    │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  1. SCRAPER          2. FIREBASE          3. UNIFIED API       4. CONSUMERS        │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  Playwright  │───▶│  Firestore   │───▶│  /unified-   │───▶│  Frontend    │      │
│  │  Crawler     │    │  Database    │    │   price      │    │  Chatbot     │      │
│  │  (24-hour)   │    │              │    │              │    │  API         │      │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │                   │              │
│         ▼                   ▼                   ▼                   ▼              │
│  Yelo, Key, Budget,  competitor_prices   ML + Rules +      Same price             │
│  Lumi websites       vehicles             Guardrails       everywhere!            │
│                      pricing_decisions                                             │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Pricing Philosophy: Profit-First + Market-Aligned

> **Key Principle:** Never sell below **cost + minimum margin**, but stay **market-competitive**.
> This ensures Hanco is always profitable while remaining competitive.

| Scenario | Floor | Ceiling |
|----------|-------|---------|
| **Has Competitor Data** | max(cost × 1.15, market_avg × 0.70) | market_avg × 1.10 |
| **No Competitor Data** | max(cost × 1.15, base × 0.80) | base × 1.10 |

**Critical Constants:**
```python
MIN_MARGIN = 0.15           # 15% minimum profit margin
MARKET_CAP_PCT = 0.10       # Allow up to +10% above competitor avg
```

---

## Architecture Diagram

### Complete Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              COMPLETE PRICING FLOW                                   │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌────────────────────────────────────────────────────────────────────────────┐    │
│  │                    PHASE 1: DATA COLLECTION (Every 24h)                     │    │
│  └────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Yelo.com   │    │   Key.sa     │    │ Budget.sa    │    │  Lumi.sa     │      │
│  │              │    │              │    │              │    │              │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                   │                   │                   │              │
│         └───────────────────┴───────────────────┴───────────────────┘              │
│                                         │                                           │
│                              ┌──────────▼──────────┐                               │
│                              │   Playwright        │                               │
│                              │   Headless Browser  │                               │
│                              │   + BeautifulSoup   │                               │
│                              └──────────┬──────────┘                               │
│                                         │                                           │
│                                         ▼                                           │
│  ┌────────────────────────────────────────────────────────────────────────────┐    │
│  │                    PHASE 2: FIREBASE STORAGE                                │    │
│  └────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                      │
│                              ┌──────────────────────┐                              │
│                              │   Firestore          │                              │
│                              ├──────────────────────┤                              │
│                              │ • competitor_prices  │                              │
│                              │   _latest            │                              │
│                              │ • vehicles           │                              │
│                              │ • pricing_decisions  │                              │
│                              │ • pricing_cache      │                              │
│                              └──────────┬───────────┘                              │
│                                         │                                           │
│                                         ▼                                           │
│  ┌────────────────────────────────────────────────────────────────────────────┐    │
│  │                    PHASE 3: UNIFIED PRICING API                             │    │
│  └────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                      │
│                    POST /api/v1/pricing/unified-price                              │
│                              │                                                      │
│         ┌────────────────────┼────────────────────┐                                │
│         │                    │                    │                                │
│         ▼                    ▼                    ▼                                │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                         │
│  │  ML Model    │    │ Rule Engine  │    │  Guardrails  │                         │
│  │  (ONNX)      │    │ (Discounts/  │    │  (Floor &    │                         │
│  │  40% weight  │    │  Premiums)   │    │   Ceiling)   │                         │
│  │              │    │  60% weight  │    │              │                         │
│  └──────────────┘    └──────────────┘    └──────────────┘                         │
│         │                    │                    │                                │
│         └────────────────────┼────────────────────┘                                │
│                              │                                                      │
│                    ┌─────────▼─────────┐                                           │
│                    │   FINAL PRICE     │                                           │
│                    │   (Rounded)       │                                           │
│                    └─────────┬─────────┘                                           │
│                              │                                                      │
│  ┌────────────────────────────────────────────────────────────────────────────┐    │
│  │                    PHASE 4: CONSUMERS                                       │    │
│  └────────────────────────────────────────────────────────────────────────────┘    │
│                              │                                                      │
│         ┌────────────────────┼────────────────────┐                                │
│         │                    │                    │                                │
│         ▼                    ▼                    ▼                                │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                         │
│  │   Frontend   │    │   Chatbot    │    │   External   │                         │
│  │   React App  │    │ Orchestrator │    │   API        │                         │
│  │              │    │              │    │   Clients    │                         │
│  └──────────────┘    └──────────────┘    └──────────────┘                         │
│                                                                                      │
│         📱 Same price shown on website = chatbot = API                              │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Competitor Data Scraping

### 1.1 How Scraping Works

**File:** `backend/app/services/competitors/crawler.py`

The system uses **Playwright** (headless browser) to scrape competitor websites every 24 hours.

```python
# Playwright scraping flow
async def scrape_provider(provider: str, city: str, pickup_date: datetime, duration: int):
    """
    1. Launch headless Chromium browser
    2. Navigate to competitor website
    3. Fill search form (city, dates, duration)
    4. Wait for results to load
    5. Parse HTML with BeautifulSoup
    6. Extract vehicle names and prices
    7. Normalize category (economy/sedan/suv/luxury)
    8. Store in Firebase
    """
```

### 1.2 Competitors Scraped

| Provider | Website | Method |
|----------|---------|--------|
| **Yelo** | iyelo.com | Playwright headless browser |
| **Key** | key.sa | Playwright headless browser |
| **Budget** | budgetsaudi.com | Playwright headless browser |
| **Lumi** | lumirental.com | Playwright headless browser |

### 1.3 Coverage Matrix

| Dimension | Values |
|-----------|--------|
| **Cities** | Riyadh, Jeddah, Dammam (loaded from Firebase `config/branches`) |
| **Durations** | D1 (1 day), D3 (3 days), D7 (7 days), M1 (30 days) |
| **Categories** | Economy, Compact, Sedan, SUV, Luxury |

### 1.4 Scrape Modes

**File:** `backend/app/workers/scrape_competitors.py`

| Mode | Frequency | Scope | Purpose |
|------|-----------|-------|---------|
| **FAST_GRID** | Every 6h | Tomorrow, D3/D7 only | Quick refresh |
| **FULL_GRID** | Every 24h | All dates, all durations | Comprehensive data |

```python
# Environment variable to set mode
COMPETITOR_SCRAPE_MODE=FAST_GRID  # or FULL_GRID
```

### 1.5 Category Normalization

The scraper normalizes different provider naming conventions:

```python
CATEGORY_MAPPING = {
    "economy": ["economy", "compact", "small", "mini"],
    "sedan": ["sedan", "midsize", "standard", "medium"],
    "suv": ["suv", "4x4", "crossover", "jeep"],
    "luxury": ["luxury", "premium", "executive", "vip"],
}

# Also detects by car name:
# - "Mercedes", "BMW", "Audi" → luxury
# - "Land Cruiser", "RAV4" → suv
# - "Yaris", "Accent" → economy
```

### 1.6 Scheduler (APScheduler)

**File:** `backend/app/core/scheduler.py`

```python
# Runs at 3:00 AM Riyadh time
scheduler.add_job(
    scrape_and_update_prices,
    CronTrigger(hour=3, minute=0, timezone='Asia/Riyadh'),
    id='daily_scrape'
)

# Lite refresh every 6 hours
scheduler.add_job(
    lite_refresh_prices,
    IntervalTrigger(hours=6),
    id='lite_refresh'
)
```

### 1.7 Distributed Lock (Multi-Worker Safety)

When running multiple workers (Uvicorn/Gunicorn), a Firestore-based lock prevents duplicate scrapes:

```python
async def acquire_scheduler_lock(job_name: str, ttl_minutes: int = 30) -> bool:
    """
    Uses Firestore document as distributed lock.
    Only ONE worker can run the scrape job at a time.
    """
    lock_ref = db.collection('scheduler_locks').document(job_name)
    # Atomic transaction to check/acquire lock
    # Returns False if another worker holds the lock
```

---

## Phase 2: Firebase Data Storage

### 2.1 Collections Used

| Collection | Purpose | Key Fields |
|------------|---------|------------|
| `competitor_prices_latest` | Scraped competitor prices | `provider`, `branch_id`, `vehicle_class`, `price_per_day`, `scraped_at` |
| `vehicles` | Hanco vehicle inventory | `id`, `name`, `base_daily_rate`, `category`, `cost_per_day` |
| `pricing_decisions` | Audit log of every price calculation | Full breakdown of ML, rules, guardrails |
| `pricing_cache` | 1-hour cache to avoid recalculation | `branch_key`, `vehicle_id`, `pickup_date`, `final_price` |
| `config/branches` | Branch configuration | `city`, `branch_key`, `type`, `label` |

### 2.2 Competitor Price Document Structure

```json
{
    "doc_id": "yelo_riyadh_sedan_camry_20260115_D3",
    "provider": "yelo",
    "branch_id": "riyadh",
    "vehicle_class": "sedan",
    "vehicle_name": "Toyota Camry",
    "price_per_day": 150,
    "currency": "SAR",
    "duration_days": 3,
    "scraped_at": "2026-01-12T03:00:00Z"
}
```

### 2.3 How Market Stats Are Calculated

When pricing is requested, the system queries competitor prices and calculates statistics:

```python
def get_market_stats(branch_key: str, duration_key: str, vehicle_class: str) -> Dict:
    """
    IMPORTANT: branch_key (e.g., 'riyadh_airport') must be mapped to city_id
    because scraper stores by city, not full branch_key.
    
    Also includes duration_key (D1/D3/D7/M1) to avoid mixing durations.
    """
    # Extract city from branch_key
    city_id = branch_key.split("_")[0]  # "riyadh_airport" -> "riyadh"
    
    # Document ID format: {provider}_{city_id}_{duration_key}_{vehicle_class}
    for provider in providers:
        doc_id = f"{provider}_{city_id}_{duration_key}_{vehicle_class}"
        # ... query document
    
    return {
        'count': len(prices),
        'avg': np.mean(prices),        # ← Market reference
        'median': np.median(prices),
        'p75': np.percentile(prices, 75),
        'p90': np.percentile(prices, 90),
        'min': min(prices),
        'max': max(prices)
    }
```

**⚠️ Key Implementation Details:**
1. **Branch Key → City Mapping**: `riyadh_airport` → `riyadh` because scraper stores by city
2. **Duration Filtering**: Query includes `duration_key` (D1/D3/D7/M1) to avoid mixing 1-day and 30-day prices
3. **Staleness Check**: Data older than 48 hours is marked as stale

---

## Phase 3: Unified Pricing Endpoint

### 3.1 The Single Source of Truth

**File:** `backend/app/api/v1/pricing.py`
**Endpoint:** `POST /api/v1/pricing/unified-price`

This is the **ONLY** endpoint that calculates prices. Both the frontend and chatbot call this endpoint.

```python
@router.post("/unified-price")
async def get_unified_price(request: UnifiedPriceRequest):
    """
    UNIFIED PRICING ENDPOINT - Single source of truth for ALL pricing.
    
    Used by:
    - Chatbot (orchestrator.py calls this via HTTP)
    - Frontend (pricingService.ts calls this via fetch)
    - Any external API consumers
    
    This ensures consistent pricing across all channels.
    """
```

### 3.2 Request/Response Schema

**Request:**
```json
{
    "vehicle_id": "luxury_001",
    "branch_key": "riyadh",
    "pickup_date": "2026-01-15",
    "dropoff_date": "2026-01-18",
    "include_insurance": false
}
```

**Response:**
```json
{
    "vehicle_id": "luxury_001",
    "vehicle_name": "Mercedes S-Class 2024",
    "daily_rate": 385.0,
    "duration_days": 3,
    "base_total": 1155.0,
    "insurance_amount": 0.0,
    "final_total": 1155.0,
    "market_ref": 354.0,
    "savings_vs_market": 0.0,
    "breakdown": {
        "ml_price": 320.5,
        "rule_price": 557.75,
        "blended": 462.85,
        "floor": 247.8,
        "ceiling": 389.4,
        "final": 385.0,
        "discounts": {"duration_3d": 0.03},
        "premiums": {},
        "market_data_used": true
    },
    "source": "unified_pricing_engine"
}
```

### 3.3 How Frontend Calls It

**File:** `frontend/src/services/pricingService.ts`

```typescript
export async function getUnifiedPrice(
    vehicleId: string,
    branchKey: string,
    pickupDate: Date,
    dropoffDate: Date,
    includeInsurance: boolean = false
): Promise<UnifiedPriceResponse> {
    const response = await fetch(`${API_URL}/api/v1/pricing/unified-price`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            vehicle_id: vehicleId,
            branch_key: branchKey,
            pickup_date: pickupDate.toISOString().split('T')[0],
            dropoff_date: dropoffDate.toISOString().split('T')[0],
            include_insurance: includeInsurance
        })
    });
    return response.json();
}
```

### 3.4 How Chatbot Calls It

**File:** `backend/app/services/chatbot/orchestrator.py`

```python
async def _call_unified_pricing_api(
    self,
    vehicle_id: str,
    branch_key: str,
    pickup_date: date,
    dropoff_date: date,
    include_insurance: bool,
) -> Optional[Dict[str, Any]]:
    """
    Call the UNIFIED PRICING API - the single source of truth.
    This is the SAME endpoint that the frontend calls.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            "http://localhost:8000/api/v1/pricing/unified-price",
            json={
                "vehicle_id": vehicle_id,
                "branch_key": branch_key,
                "pickup_date": pickup_date.isoformat(),
                "dropoff_date": dropoff_date.isoformat(),
                "include_insurance": include_insurance,
            }
        )
        return response.json()
```

---

## Phase 4: Feature Building

### 4.1 The 10 Features

**File:** `backend/app/services/pricing/feature_builder.py`

The system builds **10 features** for the ML model:

| # | Feature | Type | Example | Description |
|---|---------|------|---------|-------------|
| 1 | `rental_length_days` | float | 3.0 | Duration of rental |
| 2 | `day_of_week` | float | 4.0 | Day of pickup (0=Mon, 6=Sun) |
| 3 | `month` | float | 1.0 | Month of pickup (1-12) |
| 4 | `base_daily_rate` | float | 575.0 | Vehicle's base price from Firebase |
| 5 | `avg_temp` | float | 25.0 | Weather temperature |
| 6 | `rain` | float | 0.0 | Rain probability (0-1) |
| 7 | `wind` | float | 10.0 | Wind speed |
| 8 | `avg_competitor_price` | float | 354.0 | From scraped competitor data |
| 9 | `demand_index` | float | 0.65 | Calculated demand score (0-1) |
| 10 | `bias` | float | 1.0 | Constant term for model |

### 4.2 Feature Vector Example

```python
features = {
    'rental_length_days': 3.0,
    'day_of_week': 4.0,       # Friday
    'month': 1.0,             # January
    'base_daily_rate': 575.0,
    'avg_temp': 18.0,
    'rain': 0.0,
    'wind': 12.0,
    'avg_competitor_price': 354.0,  # ← From scraped MEDIAN
    'demand_index': 0.65,
    'bias': 1.0
}
```

### 4.3 Missing Competitor Data Fallback

**⚠️ Important:** If no competitor data exists, we use `base_daily_rate` as the fallback for the `avg_competitor_price` feature to prevent the ML model from seeing 0:

```python
# Step 2: Get competitor price for ML features
# Use MEDIAN as market reference (more robust than avg)
avg_competitor_price = vehicle.base_daily_rate  # Fallback
market_data_used = False

if market_stats and market_stats.get('median') and market_stats['median'] > 0:
    avg_competitor_price = market_stats['median']
    market_data_used = True

# Build features
features = {
    ...
    'avg_competitor_price': avg_competitor_price,  # Never 0
    ...
}
```

This ensures:
1. ML model never sees `avg_competitor_price = 0` (would learn weird patterns)
2. `market_data_used` flag is logged for auditing
3. Pricing falls back to internal mode (base rate guardrails) when no data

### 4.4 Demand Index Calculation

```python
def compute_demand_index(pickup_date: date, branch_key: str) -> float:
    """
    Calculate demand index based on various factors.
    Returns value between 0.0 (low demand) and 1.0 (high demand).
    """
    demand = 0.5  # Base demand (neutral)
    
    # Weekend: Thu=3, Fri=4, Sat=5 (Saudi weekend)
    if pickup_date.weekday() in [3, 4, 5]:
        demand += 0.20
    
    # Holidays
    if is_saudi_holiday(pickup_date):
        demand += 0.25
    
    # Summer season
    if pickup_date.month in [6, 7, 8]:
        demand += 0.15
    
    # Airport location
    if 'airport' in branch_key.lower():
        demand += 0.10
    
    return min(max(demand, 0.0), 1.0)  # Clamp to [0, 1]
```

---

## Phase 5: ML Model Prediction (ONNX)

### 5.1 ONNX Runtime

**File:** `backend/app/services/pricing/onnx_runtime.py`
**Model:** `backend/app/ml/models/model.onnx`

The system uses **ONNX** (Open Neural Network Exchange) for fast, portable ML inference with **session caching**.

```python
import onnxruntime as ort
import numpy as np

# Feature order MUST match training
FEATURE_ORDER = [
    'rental_length_days', 'day_of_week', 'month', 'base_daily_rate',
    'avg_temp', 'rain', 'wind', 'avg_competitor_price', 'demand_index', 'bias'
]

# SINGLETON SESSION - loaded once, reused for all requests
# This is CRITICAL for performance (avoid re-loading model per request)
_model_cache = ModelCache(registry_ttl_seconds=60)

def predict_price(features: Dict[str, float]) -> float:
    """
    Run ONNX inference using CACHED session.
    Session is reused across requests for performance.
    """
    # Get cached session (with hot-reload support)
    session = _model_cache.get_session('baseline_pricing_model')
    
    # Convert to ordered numpy array
    feature_vector = np.array(
        [[features[key] for key in FEATURE_ORDER]], 
        dtype=np.float32
    )
    
    # Run inference on cached session
    result = session.run(None, {"features": feature_vector})
    
    return float(result[0][0][0])  # e.g., 320.5 SAR
```

> ⚠️ **Performance Note:** Never create a new `InferenceSession` per request.
> The `ModelCache` singleton ensures the session is loaded once and reused.

### 5.2 Model Architecture

The model is a **GradientBoostingRegressor** trained on historical data:

```python
from sklearn.ensemble import GradientBoostingRegressor

model = GradientBoostingRegressor(
    n_estimators=100,
    max_depth=5,
    learning_rate=0.1,
    random_state=42
)
```

### 5.3 Model Hot-Reload

The system supports hot-reloading models from Firebase Storage:

```python
class ModelCache:
    """
    - Caches ONNX sessions in memory
    - Checks Firestore ml_models collection for version updates
    - Downloads new versions from Firebase Storage
    - 60-second TTL on version checks
    """
```

---

## Phase 6: Rule Engine

### 6.1 Duration Discounts

**File:** `backend/app/api/v1/pricing.py` (lines 608-622)

```python
# Duration discounts applied to base rate
if duration_days >= 30:
    discount = 0.15  # 15% off for monthly
    rule_price *= (1 - discount)
elif duration_days >= 7:
    discount = 0.07  # 7% off for weekly
    rule_price *= (1 - discount)
elif duration_days >= 3:
    discount = 0.03  # 3% off for 3+ days
    rule_price *= (1 - discount)
```

| Duration | Discount |
|----------|----------|
| 1-2 days | 0% |
| 3-6 days | 3% |
| 7-29 days | 7% |
| 30+ days | 15% |

### 6.2 Location Premiums

```python
# Airport premium
if branch_type.lower() == "airport":
    premium = 0.05  # +5%
    rule_price *= (1 + premium)
```

| Location | Premium |
|----------|---------|
| Airport | +5% |
| City/Downtown | 0% |

### 6.3 Weekend Premium

```python
# Saudi weekend: Thursday, Friday, Saturday
if is_weekend:  # pickup_date.weekday() in [3, 4, 5]
    premium = 0.03  # +3%
    rule_price *= (1 + premium)
```

---

## Phase 7: Price Blending & Guardrails

### 7.1 The Core Algorithm

**File:** `backend/app/api/v1/pricing.py` (lines 636-710)

```python
import math

async def compute_vehicle_price(...):
    # Step 1: Get ML price from ONNX model
    ml_price_per_day = predict_price(features)  # e.g., 320.5 SAR
    
    # Step 2: Calculate rule-based price
    rule_price = base_daily_rate  # e.g., 575 SAR
    rule_price *= (1 - duration_discount)  # Apply discounts
    rule_price *= (1 + airport_premium)    # Apply premiums
    rule_price *= (1 + weekend_premium)
    # rule_price = e.g., 557.75 SAR
    
    # Step 3: PROFIT-FIRST + MARKET-ALIGNED GUARDRAILS
    MIN_MARGIN = 0.15           # 15% minimum profit margin
    MARKET_CAP_PCT = 0.10       # Allow up to +10% above market ref
    
    # Always start with cost floor (never go below cost + margin)
    cost_floor = vehicle.cost_per_day * (1 + MIN_MARGIN)
    
    # Use MEDIAN (not avg) as market reference - more robust against outliers
    has_competitor_data = market_stats and market_stats.get('median') > 0
    
    if has_competitor_data:
        market_ref = market_stats['median']  # ← Use MEDIAN, not avg
        market_ceiling = market_ref * (1 + MARKET_CAP_PCT)
        market_floor = market_ref * 0.70
        floor_price = max(cost_floor, market_floor)
        ceiling_price = market_ceiling
    else:
        # No market data - use base rate with cost protection
        floor_price = max(cost_floor, base_daily_rate * 0.80)
        ceiling_price = base_daily_rate * 1.10
    
    # Handle impossible case: floor > ceiling
    if floor_price > ceiling_price:
        ceiling_price = floor_price  # Profit-first override
    
    # Step 4: Blend ML (40%) + Rules (60%)
    blended_price = (0.6 * rule_price) + (0.4 * ml_price_per_day)
    
    # Step 5: Apply guardrails (clamp to floor/ceiling)
    clamped_price = max(floor_price, min(blended_price, ceiling_price))
    
    # Step 6: BOUNDED ROUNDING - round to step within bounds
    # Ensures final price is ALWAYS a multiple of step AND within [floor, ceiling]
    step = 5.0
    rounded = round(clamped_price / step) * step
    
    # If rounding exceeds ceiling, round DOWN to allowed step
    if rounded > ceiling_price:
        rounded = math.floor(ceiling_price / step) * step
    
    # If rounding falls below floor, round UP to allowed step
    if rounded < floor_price:
        rounded = math.ceil(floor_price / step) * step
    
    # Final safety clamp
    final_price = max(floor_price, min(rounded, ceiling_price))
    
    return final_price
```

### 7.2 Guardrails Explained

```
┌─────────────────────────────────────────────────────────────────┐
│                     GUARDRAILS LOGIC (PROFIT-FIRST)             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  SCENARIO: Luxury vehicle                                        │
│    - cost_per_day = 200 SAR                                     │
│    - competitor MEDIAN = 354 SAR  (use median, not avg)         │
│                                                                  │
│  Has Competitor Data: YES                                        │
│  ─────────────────────                                           │
│                                                                  │
│  Cost Floor = 200 × 1.15 = 230 SAR  (15% min margin)            │
│  Market Floor = 354 × 0.70 = 248 SAR                            │
│  Final Floor = max(230, 248) = 248 SAR                          │
│                                                                  │
│  Market Ceiling = 354 × 1.10 = 389.4 SAR  (+10% above median)   │
│                                                                  │
│  ML Price:    320.5 SAR                                         │
│  Rule Price:  557.75 SAR                                        │
│  Blended:     462.85 SAR  (60% rule + 40% ML)                   │
│                                                                  │
│  Since blended (462) > ceiling (389):                           │
│  → Clamped = ceiling = 389.4 SAR                                │
│  → Bounded round = 385 SAR (highest step ≤ ceiling) ✓           │
│                                                                  │
│  ✅ PROFITABLE (385 > cost 200)                                  │
│  ✅ COMPETITIVE (385 ≈ median 354 + 10%)                         │
│  ✅ CLEAN PRICE (multiple of 5 SAR)                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  SCENARIO: Cost too high for market (impossible case)           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│    - cost_per_day = 400 SAR                                     │
│    - competitor median = 350 SAR                                │
│                                                                  │
│  Cost Floor = 400 × 1.15 = 460 SAR                              │
│  Market Ceiling = 350 × 1.10 = 385 SAR                          │
│                                                                  │
│  ❌ IMPOSSIBLE: floor (460) > ceiling (385)                      │
│                                                                  │
│  Policy: PROFIT-FIRST override                                  │
│  → ceiling = floor = 460 SAR                                    │
│                                                                  │
│  ⚠️ Warning logged: "Impossible pricing case"                   │
│  → Business may need to review cost structure                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  SCENARIO: No competitor data available                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Has Competitor Data: NO                                         │
│  ─────────────────────                                           │
│                                                                  │
│  Cost Floor = cost × 1.15 = 230 SAR                             │
│  Floor = max(230, base × 0.80) = max(230, 460) = 460 SAR        │
│  Ceiling = base × 1.10 = 632.5 SAR                              │
│                                                                  │
│  Blended: 462.85 SAR                                            │
│                                                                  │
│  Since floor (460) < blended (462) < ceiling (632):             │
│  → Final = blended = 465 SAR (rounded)                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 7.3 Why Profit-First + Market-Aligned

The new logic ensures **both profitability AND competitiveness**:

| Old Logic (Broken) | New Logic (Fixed) |
|-------------------|-------------------|
| ceiling = competitor avg (hard cap) | ceiling = avg × 1.10 (market band) |
| floor = ceiling × 0.70 (ignores cost!) | floor = max(cost × 1.15, market × 0.70) |
| Could sell below cost | **Never sells below cost + 15% margin** |
| Impossible case = undefined | Impossible case = profit-first override |

---

## Phase 8: Complete Calculation Example

### Scenario

- **Vehicle:** Mercedes S-Class 2024 (luxury_001)
- **Base Rate:** 575 SAR/day (from Firebase `vehicles` collection)
- **Cost Per Day:** 200 SAR (from Firebase `vehicles` collection)
- **Competitor Avg:** 354 SAR/day (from `competitor_prices_latest`)
- **Pickup:** Wednesday, January 15, 2026
- **Duration:** 3 days
- **Branch:** Riyadh (city, not airport)

### Step-by-Step Calculation

```
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Fetch Data                                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ Vehicle (from Firebase vehicles/luxury_001):                    │
│   base_daily_rate = 575 SAR                                     │
│   cost_per_day = 200 SAR                                        │
│   category = "luxury"                                           │
│                                                                  │
│ Competitor Stats (query uses city_id extracted from branch_key):│
│   branch_key = "riyadh" → city_id = "riyadh"                    │
│   Query doc IDs: {provider}_riyadh_D3_luxury                    │
│   avg = 354 SAR                                                 │
│   median = 350 SAR                                              │
│   p90 = 400 SAR                                                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: Build Features                                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ features = {                                                     │
│   'rental_length_days': 3.0,                                    │
│   'day_of_week': 2.0,        # Wednesday                        │
│   'month': 1.0,              # January                          │
│   'base_daily_rate': 575.0,                                     │
│   'avg_temp': 18.0,                                             │
│   'rain': 0.0,                                                  │
│   'wind': 12.0,                                                 │
│   'avg_competitor_price': 354.0,   ←── From scraped data        │
│   'demand_index': 0.5,             # Weekday, no holidays       │
│   'bias': 1.0                                                   │
│ }                                                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: ML Prediction (ONNX)                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ ml_price = predict_price(features)                              │
│ ml_price = 320.5 SAR                                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: Rule-Based Price                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ Start: base_daily_rate = 575 SAR                                │
│                                                                  │
│ Duration discount (3 days = 3%):                                │
│   575 × 0.97 = 557.75 SAR                                       │
│                                                                  │
│ Airport premium: NO (city branch)                               │
│ Weekend premium: NO (Wednesday)                                 │
│                                                                  │
│ rule_price = 557.75 SAR                                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: Blend Prices                                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ ML Price:   320.5 SAR  (weight: 40%)                            │
│ Rule Price: 557.75 SAR (weight: 60%)                            │
│                                                                  │
│ blended = (0.4 × 320.5) + (0.6 × 557.75)                        │
│         = 128.2 + 334.65                                        │
│         = 462.85 SAR                                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 6: Apply Guardrails (PROFIT-FIRST + MARKET-ALIGNED)       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ Has competitor data: YES                                         │
│                                                                  │
│ MIN_MARGIN = 0.15 (15% min profit)                              │
│ MARKET_CAP_PCT = 0.10 (10% above avg)                           │
│                                                                  │
│ Cost Floor = 200 × 1.15 = 230 SAR                               │
│ Market Floor = 354 × 0.70 = 247.8 SAR                           │
│ Floor = max(230, 247.8) = 247.8 SAR                             │
│                                                                  │
│ Market Ceiling = 354 × 1.10 = 389.4 SAR                         │
│                                                                  │
│ Is floor (247.8) > ceiling (389.4)?                             │
│   NO → Normal pricing                                           │
│                                                                  │
│ Is blended (462.85) within [247.8, 389.4]?                      │
│   462.85 > 389.4 ← Above ceiling!                               │
│                                                                  │
│ Clamped = min(462.85, 389.4) = 389.4 SAR                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 7: Bounded Rounding                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ Clamped price: 389.4 SAR                                        │
│ Ceiling: 389.4 SAR                                              │
│                                                                  │
│ Standard round(389.4 / 5) * 5 = 390 SAR                         │
│   → 390 > ceiling (389.4) ← EXCEEDS CEILING!                    │
│                                                                  │
│ Bounded rounding: floor(389.4 / 5) * 5 = 385 SAR                │
│   → 385 ≤ ceiling (389.4) ✓                                     │
│   → 385 ≥ floor (247.8) ✓                                       │
│                                                                  │
│ FINAL PRICE = 385 SAR/day                                       │
│                                                                  │
│ Total for 3 days = 385 × 3 = 1,155 SAR                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FINAL RESULT                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           AI-Powered Dynamic Price                       │   │
│  │                                                          │   │
│  │              385 SAR /day                                │   │
│  │                                                          │   │
│  │         Total for 3 days: 1,155 SAR                     │   │
│  │                                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ✅ PROFITABLE (385 > cost 200 + 15% margin)                    │
│  ✅ COMPETITIVE (385 ≈ market avg 354 + 10%)                    │
│  ✅ Same price on Website AND Chatbot                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 9: Audit Trail

### 9.1 Pricing Decision Log

**Collection:** `pricing_decisions`

Every price calculation is logged with full transparency:

```json
{
    "id": "pd_20260115_luxury001_abc123",
    "created_at": "2026-01-12T10:30:00Z",
    
    "vehicle": {
        "id": "luxury_001",
        "name": "Mercedes S-Class 2024",
        "category": "luxury",
        "base_daily_rate": 575.0,
        "cost_per_day": 200.0
    },
    
    "booking": {
        "branch_key": "riyadh",
        "pickup_at": "2026-01-15T10:00:00Z",
        "dropoff_at": "2026-01-18T10:00:00Z",
        "duration_days": 3
    },
    
    "market_stats": {
        "count": 4,
        "median": 354.0,
        "avg": 360.0,
        "p75": 380.0,
        "p90": 400.0,
        "market_data_used": true
    },
    
    "features": {
        "rental_length_days": 3.0,
        "day_of_week": 2.0,
        "month": 1.0,
        "base_daily_rate": 575.0,
        "avg_temp": 18.0,
        "rain": 0.0,
        "wind": 12.0,
        "avg_competitor_price": 354.0,
        "demand_index": 0.5,
        "bias": 1.0
    },
    
    "pricing": {
        "ml_price": 320.5,
        "rule_price": 557.75,
        "blended": 462.85,
        "cost_floor": 230.0,
        "market_floor": 247.8,
        "floor": 247.8,
        "ceiling": 389.4,
        "clamped": 389.4,
        "final_price_per_day": 385.0,
        "total_price": 1155.0,
        "impossible_case": false
    },
    
    "adjustments": {
        "discounts_applied": {"duration_3d": 0.03},
        "premiums_applied": {}
    },
    
    "model_version": "onnx_v1"
}
```

---

## Key Files Reference

### Core Pricing Files

| File | Purpose |
|------|---------|
| `backend/app/api/v1/pricing.py` | Unified pricing endpoint + `compute_vehicle_price()` |
| `backend/app/services/pricing/onnx_runtime.py` | ONNX model inference |
| `backend/app/services/pricing/feature_builder.py` | Feature engineering |
| `backend/app/services/chatbot/orchestrator.py` | Chatbot calls unified API |
| `frontend/src/services/pricingService.ts` | Frontend calls unified API |

### Competitor Scraping Files

| File | Purpose |
|------|---------|
| `backend/app/services/competitors/crawler.py` | Playwright scraper |
| `backend/app/workers/scrape_competitors.py` | Scraping worker |
| `backend/app/core/scheduler.py` | APScheduler jobs |

### ML Training Files

| File | Purpose |
|------|---------|
| `backend/app/ml/training/train_pricing_model.py` | Model training script |
| `backend/app/ml/models/model.onnx` | Trained ONNX model |

---

## API Endpoints

### Unified Pricing (Use This!)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/v1/pricing/unified-price` | **Single source of truth for all pricing** |

### Other Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/v1/pricing/quote` | Legacy batch quote (uses same compute function) |
| `GET` | `/api/v1/competitors/stats` | Get competitor statistics |
| `POST` | `/api/v1/competitors/scheduler/trigger` | Manual scrape trigger |

---

## Configuration

### Environment Variables

```bash
# Firebase
GOOGLE_APPLICATION_CREDENTIALS=/path/to/firebase-key.json
FIREBASE_PROJECT_ID=hanco-ai

# Scraping Mode
COMPETITOR_SCRAPE_MODE=FAST_GRID  # or FULL_GRID

# Backend URL (for chatbot to call pricing API)
BACKEND_URL=http://localhost:8000
```

### Guardrails Configuration

In `backend/app/api/v1/pricing.py`:

```python
# Tunable constants
MIN_MARGIN = 0.15           # 15% minimum profit margin
MARKET_CAP_PCT = 0.10       # Allow up to +10% above market ref

# Cost floor (ALWAYS applied - never sell below cost + margin)
cost_floor = vehicle.cost_per_day * (1 + MIN_MARGIN)

# When competitor data exists:
# Use MEDIAN as market reference (more robust than avg against outliers)
market_ref = market_stats['median']  # ← Use MEDIAN, not avg
market_ceiling = market_ref * (1 + MARKET_CAP_PCT)  # +10% above median
market_floor = market_ref * 0.70                    # -30% below median
floor_price = max(cost_floor, market_floor)         # Profit-first
ceiling_price = market_ceiling

# When NO competitor data:
floor_price = max(cost_floor, base_daily_rate * 0.80)
ceiling_price = base_daily_rate * 1.10

# Impossible case handler:
if floor_price > ceiling_price:
    ceiling_price = floor_price  # Profit-first override
```

### Bounded Rounding

To ensure final price is always a clean multiple of 5 SAR **and** within bounds:

```python
import math

def bounded_round(x: float, floor: float, ceiling: float, step: float = 5.0) -> float:
    """Round to step while respecting floor/ceiling bounds."""
    r = round(x / step) * step
    
    # If rounding exceeds ceiling, round DOWN
    if r > ceiling:
        r = math.floor(ceiling / step) * step
    
    # If rounding falls below floor, round UP
    if r < floor:
        r = math.ceil(floor / step) * step
    
    return max(floor, min(r, ceiling))
```

### Cache Key Discipline

The pricing cache key MUST include all price-affecting factors:

```python
# Required cache key components:
cache_key = f"{vehicle_id}_{branch_key}_{pickup_date}_{duration_key}"

# Also consider (for full correctness):
# - include_insurance (affects final total)
# - model_version (if hot-reload is enabled)
# - market_stats_as_of (for consistency across refresh)
```

---

## Training the Model

### Train from Real Data

```bash
cd backend
python -m app.ml.training.train_pricing_model --source real
```

### Train from Synthetic Data

```bash
python -m app.ml.training.train_pricing_model --source synthetic
```

### Model Saved To

```
backend/app/ml/models/model.onnx
```

---

## Summary

The Hanco AI Dynamic Pricing System provides:

✅ **Unified Pricing** - Same price across website, chatbot, and API  
✅ **Profit-First** - Never sells below cost + 15% minimum margin  
✅ **Market-Aligned** - Uses median (not avg) as market reference, with ±% band  
✅ **ML-Powered** - ONNX model with cached sessions for fast inference  
✅ **Rule-Based** - Business rules for discounts/premiums  
✅ **60/40 Blend** - 60% rules + 40% ML for stability  
✅ **Bounded Rounding** - Final price always a multiple of 5 SAR within bounds  
✅ **Full Audit Trail** - Every decision logged to Firebase with full breakdown  
✅ **Auto-Scraping** - FAST_GRID (6h) + FULL_GRID (24h) competitor refresh  
✅ **Distributed Locks** - Safe for multi-worker deployment  

---

*Last updated: January 2026*
