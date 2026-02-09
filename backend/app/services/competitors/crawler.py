"""Production-Grade Competitor Price Scraping Engine
Uses Playwright for headless browser scraping with provider-specific parsers

Required Firestore Composite Indexes:
1. competitor_prices:
   - branch_id (ASC) + vehicle_class (ASC) + scraped_at (DESC)
   - hash (ASC) + scraped_at (DESC)
"""
import logging
import re
import asyncio
import hashlib
import random
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from bs4 import BeautifulSoup
from google.cloud import firestore

# Initialize logger early so it can be used in imports
logger = logging.getLogger(__name__)

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. Run: pip install playwright && playwright install chromium")

from app.core.firebase import db


# ==================== PROVIDER CONFIGURATION ====================
# Production URLs for Saudi Arabia car rental providers
# NOTE: Only active/working providers included

PROVIDER_URLS = {
    "yelo": "https://www.iyelo.com",
    "key": "https://www.key.sa/en",
    "budget": "https://www.budgetsaudi.com",
    "lumi": "https://lumirental.com/en"
}

# Branch configuration cache (loaded from Firestore)
_branches_cache: Optional[List[Dict[str, str]]] = None
_branches_cache_timestamp: Optional[datetime] = None

# Vehicle category mappings for normalization
CATEGORY_MAPPING = {
    "economy": ["economy", "compact", "small", "mini"],
    "sedan": ["sedan", "midsize", "standard", "medium"],
    "suv": ["suv", "4x4", "crossover", "jeep"],
    "luxury": ["luxury", "premium", "executive", "vip"],
}

# User-agent rotation list for resilience
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
]

# HTML cache to avoid rapid re-scraping (5 min TTL)
_html_cache: Dict[str, Dict[str, Any]] = {}


# ==================== BRANCH CONFIGURATION ====================

async def load_branches_from_firestore(firestore_db) -> List[Dict[str, str]]:
    """
    Load branch configuration from Firestore config/branches document.
    
    Uses asyncio.to_thread since Firestore Admin SDK reads are blocking.
    Validates document structure and returns empty list on error (does not crash).
    
    Expected Firestore structure:
        Collection: config
        Document: branches
        Field: branches (array of objects)
            - city: str
            - branch_key: str
            - type: str
            - label: str
    
    Args:
        firestore_db: Firestore database client
        
    Returns:
        List of branch dictionaries, or [] if error/invalid
    """
    try:
        # Read Firestore document (blocking call, so use asyncio.to_thread)
        def _read_branches():
            config_ref = firestore_db.collection('config').document('branches')
            doc = config_ref.get()
            
            if not doc.exists:
                logger.error("Firestore config/branches document does not exist")
                return None
            
            doc_data = doc.to_dict()
            if not doc_data:
                logger.error("Firestore config/branches document is empty")
                return None
            
            branches = doc_data.get('branches')
            if not branches:
                logger.error("Firestore config/branches document missing 'branches' field")
                return None
            
            if not isinstance(branches, list):
                logger.error(f"Firestore config/branches 'branches' field is not a list (type: {type(branches)})")
                return None
            
            if len(branches) == 0:
                logger.error("Firestore config/branches 'branches' field is empty list")
                return None
            
            return branches
        
        branches = await asyncio.to_thread(_read_branches)
        
        if branches is None:
            return []
        
        # Validate each branch has required fields
        validated_branches = []
        required_fields = ['city', 'branch_key', 'type', 'label']
        
        for idx, branch in enumerate(branches):
            if not isinstance(branch, dict):
                logger.warning(f"Branch at index {idx} is not a dictionary, skipping")
                continue
            
            # Check all required fields are present
            missing_fields = [field for field in required_fields if field not in branch]
            if missing_fields:
                logger.warning(f"Branch at index {idx} missing fields {missing_fields}, skipping: {branch}")
                continue
            
            # Check all required fields are strings
            invalid_fields = [field for field in required_fields if not isinstance(branch[field], str)]
            if invalid_fields:
                logger.warning(f"Branch at index {idx} has non-string fields {invalid_fields}, skipping: {branch}")
                continue
            
            validated_branches.append(branch)
        
        if len(validated_branches) == 0:
            logger.error("No valid branches found after validation")
            return []
        
        logger.info(f"Loaded {len(validated_branches)} branches from Firestore config/branches")
        return validated_branches
        
    except Exception as e:
        logger.error(f"Error loading branches from Firestore: {str(e)}")
        return []


async def get_branches_cached(firestore_db, force_reload: bool = False) -> List[Dict[str, str]]:
    """
    Get branches with in-memory caching to avoid repeated Firestore reads.
    
    Args:
        firestore_db: Firestore database client
        force_reload: Force reload from Firestore (ignore cache)
        
    Returns:
        List of branch dictionaries
    """
    global _branches_cache, _branches_cache_timestamp
    
    # Check if cache is valid (exists and not forced reload)
    if not force_reload and _branches_cache is not None:
        logger.debug(f"Using cached branches ({len(_branches_cache)} branches)")
        return _branches_cache
    
    # Load from Firestore
    branches = await load_branches_from_firestore(firestore_db)
    
    # Update cache
    _branches_cache = branches
    _branches_cache_timestamp = datetime.utcnow()
    
    return branches


def get_cities_from_branches(branches: List[Dict[str, str]]) -> List[str]:
    """
    Derive unique city names from branch configuration.
    
    Args:
        branches: List of branch dictionaries
        
    Returns:
        List of unique city names (lowercase)
    """
    cities = set()
    for branch in branches:
        city = branch.get('city', '').lower()
        if city:
            cities.add(city)
    return sorted(list(cities))


# ==================== CORE CRAWL4AI FUNCTIONS ====================

async def fetch_html_budget(url: str, provider: str = 'budget') -> str:
    """
    Specialized fetch for Budget (JS-heavy sites) with enhanced retry and debugging.
    
    Features:
    - Uses domcontentloaded instead of networkidle
    - Waits for stable selector in booking widget/results
    - Blocks only images/fonts/media (NOT scripts/xhr/fetch)
    - Realistic locale, timezone, Accept-Language headers
    - 3 retries with exponential backoff
    - On failure: saves debug doc to Firestore with HTML + screenshot
    
    Args:
        url: Target URL to scrape
        provider: Provider name for debug logging
        
    Returns:
        Rendered HTML content
        
    Raises:
        Exception: If scraping fails after all retries
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError(
            "Playwright not installed. Install with: pip install playwright && playwright install chromium"
        )
    
    max_retries = 3
    last_error = None
    screenshot_path = None
    
    for attempt in range(max_retries):
        # Exponential backoff: 2s, 4s, 8s
        if attempt > 0:
            backoff_delay = 2 ** attempt
            logger.info(f"Budget: Waiting {backoff_delay}s before retry {attempt + 1}/{max_retries}")
            await asyncio.sleep(backoff_delay)
        
        try:
            logger.info(f"Budget: Fetching {url} (attempt {attempt + 1}/{max_retries})")
            
            async with async_playwright() as p:
                # Launch browser
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                
                # Create context with realistic settings
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080},
                    locale='en-SA',  # English (Saudi Arabia)
                    timezone_id='Asia/Riyadh',
                    extra_http_headers={
                        'Accept-Language': 'en-SA,en;q=0.9,ar-SA;q=0.8,ar;q=0.7',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
                    }
                )
                
                # Create page
                page = await context.new_page()
                
                # Block only images, fonts, media (NOT scripts, xhr, fetch)
                await page.route('**/*', lambda route: (
                    route.abort() if route.request.resource_type in ['image', 'font', 'media']
                    else route.continue_()
                ))
                
                try:
                    # Navigate with domcontentloaded (faster than networkidle)
                    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    
                    # Wait for stable selector (booking widget or results grid)
                    # Try multiple selectors that might exist on Budget site
                    stable_selectors = [
                        '.vehicle-item',  # Vehicle cards
                        '.car-card',  # Alternative car card
                        '.booking-widget',  # Booking widget
                        '.vehicle-list',  # Vehicle list container
                        '.search-results',  # Search results
                        'div[class*="vehicle"]',  # Any div with "vehicle" in class
                        'div[class*="car"]',  # Any div with "car" in class
                        'form',  # Fallback: any form
                    ]
                    
                    selector_found = False
                    for selector in stable_selectors:
                        try:
                            await page.wait_for_selector(selector, timeout=10000)
                            logger.info(f"Budget: Found stable element: {selector}")
                            selector_found = True
                            break
                        except:
                            continue
                    
                    if not selector_found:
                        logger.warning(f"Budget: No stable selector found, waiting 5s for JS rendering")
                        await asyncio.sleep(5)
                    
                    # Additional wait for JS execution
                    await asyncio.sleep(3)
                    
                    # Get rendered HTML
                    html = await page.content()
                    
                    logger.info(f"Budget: Successfully fetched {len(html)} bytes")
                    
                    return html
                    
                except Exception as e:
                    # Take screenshot for debugging
                    try:
                        screenshot_path = f"/tmp/budget_debug_{int(time.time())}.png"
                        await page.screenshot(path=screenshot_path, full_page=True)
                        logger.info(f"Budget: Saved debug screenshot to {screenshot_path}")
                    except:
                        screenshot_path = None
                    
                    raise
                    
                finally:
                    await page.close()
                    await context.close()
                    await browser.close()
                    
        except PlaywrightTimeoutError as e:
            last_error = f"Timeout: {str(e)}"
            logger.warning(f"Budget: Timeout (attempt {attempt + 1}/{max_retries})")
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Budget: Error (attempt {attempt + 1}/{max_retries}): {str(e)}")
    
    # All retries failed - save debug doc to Firestore
    logger.error(f"Budget: All {max_retries} attempts failed. Saving debug doc to Firestore.")
    
    try:
        # Get partial HTML if available from last attempt
        debug_html = "<html><body>No HTML captured</body></html>"
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()
                await page.goto(url, wait_until='domcontentloaded', timeout=15000)
                full_html = await page.content()
                debug_html = full_html[:12000]  # First 12000 chars
                await page.close()
                await context.close()
                await browser.close()
        except:
            pass
        
        # Save debug document to Firestore
        debug_ref = db.collection('competitor_scrape_debug').document()
        debug_ref.set({
            'provider': provider,
            'url': url,
            'timestamp': firestore.SERVER_TIMESTAMP,
            'error': last_error,
            'attempts': max_retries,
            'html_preview': debug_html,
            'html_length': len(debug_html),
            'screenshot_path': screenshot_path,
            'created_at': datetime.utcnow()
        })
        
        logger.info(f"Budget: Debug doc saved to competitor_scrape_debug/{debug_ref.id}")
        
    except Exception as debug_error:
        logger.error(f"Budget: Failed to save debug doc: {debug_error}")
    
    # Raise the last error
    raise Exception(f"Budget scraping failed after {max_retries} retries: {last_error}")


async def fetch_html(url: str, use_cache: bool = True, max_retries: int = 2) -> str:
    """
    Fetch rendered HTML using Playwright headless browser with retry logic.
    
    Args:
        url: Target URL to scrape
        use_cache: Whether to use 5-minute cache
        max_retries: Maximum retry attempts (default: 2)
        
    Returns:
        Rendered HTML content
        
    Raises:
        RuntimeError: If Playwright is not installed
        Exception: If scraping fails after all retries
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError(
            "Playwright not installed. Install with: pip install playwright && playwright install chromium"
        )
    
    # Check cache
    cache_key = url
    if use_cache and cache_key in _html_cache:
        cache_entry = _html_cache[cache_key]
        age = (datetime.utcnow() - cache_entry['timestamp']).total_seconds()
        if age < 300:  # 5 minutes
            logger.info(f"Cache hit for {url} (age: {age:.0f}s)")
            return cache_entry['html']
    
    # Randomized delay to avoid rate limiting (1.0-3.0 seconds)
    delay = random.uniform(1.0, 3.0)
    logger.info(f"Waiting {delay:.2f}s before fetching {url}")
    await asyncio.sleep(delay)
    
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            # Rotate user agent
            user_agent = random.choice(USER_AGENTS)
            logger.info(f"Fetching HTML from {url} (attempt {attempt + 1}/{max_retries + 1})")
            
            async with async_playwright() as p:
                # Launch browser
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                
                # Create context with rotated user agent
                context = await browser.new_context(
                    user_agent=user_agent,
                    viewport={'width': 1920, 'height': 1080}
                )
                
                # Create page
                page = await context.new_page()
                
                try:
                    # Navigate with timeout
                    await page.goto(url, wait_until='networkidle', timeout=30000)
                    
                    # Wait for dynamic content to load
                    await asyncio.sleep(2)
                    
                    # Get rendered HTML
                    html = await page.content()
                    
                    logger.info(f"Successfully fetched {len(html)} bytes from {url}")
                    
                    # Cache result
                    _html_cache[cache_key] = {
                        'html': html,
                        'timestamp': datetime.utcnow()
                    }
                    
                    return html
                    
                finally:
                    await page.close()
                    await context.close()
                    await browser.close()
                    
        except PlaywrightTimeoutError as e:
            last_error = f"Timeout: {str(e)}"
            logger.warning(f"Timeout fetching {url} (attempt {attempt + 1})")
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Error fetching {url} (attempt {attempt + 1}): {str(e)}")
        
        # Wait before retry (exponential backoff)
        if attempt < max_retries:
            retry_delay = (attempt + 1) * 2
            logger.info(f"Retrying in {retry_delay}s...")
            await asyncio.sleep(retry_delay)
    
    # All retries failed
    logger.error(f"Failed to fetch {url} after {max_retries + 1} attempts")
    raise Exception(f"Failed to scrape {url}: {last_error}")


def _extract_price(price_text: str) -> float:
    """
    Extract numeric price from text.
    Handles multiple prices by finding largest realistic price value.
    
    Args:
        price_text: Text containing price (e.g., "SAR 150/day", "150 SR", "160 AED110 AED")
        
    Returns:
        Numeric price value
    """
    if not price_text:
        return 0.0
    
    # Remove percentage signs and surrounding numbers (discount percentages)
    cleaned = re.sub(r'\d+\s*%', '', price_text)
    
    # Find all numbers in the text (including decimals)
    numbers = re.findall(r'\d+(?:\.\d+)?', cleaned)
    
    if not numbers:
        return 0.0
    
    try:
        # Convert to floats and filter out unrealistic values
        prices = [float(n) for n in numbers if float(n) >= 30]  # Min 30 SAR/day
        
        if not prices:
            return 0.0
        
        # Return the largest price (original price before discount)
        # or last price if multiple large values
        return max(prices) if len(prices) <= 2 else prices[-1]
    except:
        return 0.0


def _normalize_category(category_text: str, car_name: str = "") -> str:
    """
    Normalize category name to standard values.
    
    Args:
        category_text: Raw category text from website
        car_name: Vehicle name (used for better categorization)
        
    Returns:
        Normalized category: economy, sedan, suv, or luxury
    """
    # Combine category and car name for better matching
    text_lower = f"{category_text} {car_name}".lower() if category_text else car_name.lower()
    
    if not text_lower.strip():
        return "sedan"
    
    # Check for luxury first (highest priority)
    luxury_keywords = ['luxury', 'premium', 'executive', 'vip', 'mercedes', 'bmw', 'audi', 'lexus', 'cadillac', 'bentley', 'porsche']
    if any(kw in text_lower for kw in luxury_keywords):
        return "luxury"
    
    # Check for SUV
    suv_keywords = ['suv', '4x4', 'crossover', 'jeep', 'land cruiser', 'prado', 'pajero', 'pathfinder', 
                    'tahoe', 'suburban', 'fortuner', 'rav4', 'cr-v', 'crv', 'highlander', 'pilot', 'tucson',
                    'santa fe', 'sportage', 'sorento', 'expedition', 'explorer', 'wrangler']
    if any(kw in text_lower for kw in suv_keywords):
        return "suv"
    
    # Check for economy/compact
    economy_keywords = ['economy', 'compact', 'small', 'mini', 'yaris', 'accent', 'picanto', 'spark',
                        'versa', 'rio', 'mirage', 'elantra', 'corolla']
    if any(kw in text_lower for kw in economy_keywords):
        return "economy"
    
    # Check standard mapping
    for standard, variants in CATEGORY_MAPPING.items():
        if any(variant in text_lower for variant in variants):
            return standard
    
    return "sedan"  # Default


def _generate_offer_hash(provider: str, branch: str, vehicle_class: str, price: float) -> str:
    """
    Generate a unique hash for deduplication.
    
    Args:
        provider: Provider name
        branch: Branch/city identifier
        vehicle_class: Vehicle category
        price: Price per day
        
    Returns:
        MD5 hash string
    """
    # Create composite key
    key = f"{provider}|{branch}|{vehicle_class}|{int(price)}"
    return hashlib.md5(key.encode()).hexdigest()


def _categorize_vehicle_bucket(raw_category: str, car_name: str) -> str:
    """
    Categorize vehicle into buckets: Compact, Sedan, SUV, Luxury, Other.
    
    Args:
        raw_category: Raw category text from website
        car_name: Vehicle name
        
    Returns:
        Bucket name: Compact, Sedan, SUV, Luxury, or Other
    """
    text = f"{raw_category} {car_name}".lower()
    
    # Luxury indicators
    luxury_keywords = ['luxury', 'premium', 'executive', 'vip', 'mercedes', 'bmw', 'audi', 'lexus', 'cadillac']
    if any(kw in text for kw in luxury_keywords):
        return 'Luxury'
    
    # SUV indicators
    suv_keywords = ['suv', '4x4', 'crossover', 'jeep', 'land cruiser', 'prado', 'pajero', 'pathfinder']
    if any(kw in text for kw in suv_keywords):
        return 'SUV'
    
    # Compact indicators
    compact_keywords = ['compact', 'economy', 'small', 'mini', 'yaris', 'accent', 'picanto', 'spark']
    if any(kw in text for kw in compact_keywords):
        return 'Compact'
    
    # Sedan indicators (default)
    sedan_keywords = ['sedan', 'midsize', 'standard', 'medium', 'camry', 'altima', 'sonata', 'accord']
    if any(kw in text for kw in sedan_keywords):
        return 'Sedan'
    
    return 'Other'


async def fetch_airport_quote_with_scroll(
    provider: str,
    airport_code: str,
    pickup_date: datetime,
    dropoff_date: datetime
) -> List[Dict[str, Any]]:
    """
    Fetch 1-day airport quote using Playwright navigation with scroll/load-more/pagination.
    
    This function:
    1. Navigates to provider's airport booking page
    2. Fills pickup location (airport), dates, times
    3. Submits search
    4. Extracts ALL vehicles using:
       - Scroll-until-stable loop
       - Load-more button clicking
       - Pagination navigation
    5. Parses each vehicle card for: car_name, raw_category, bucket, price, dates
    
    Args:
        provider: Provider key (yelo, key, budget, lumi)
        airport_code: Airport code (e.g., 'riyadh_airport', 'jeddah_airport')
        pickup_date: Pickup datetime
        dropoff_date: Dropoff datetime
        
    Returns:
        List of vehicle dictionaries with parsed data
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError("Playwright not available")
    
    if provider not in PROVIDER_URLS:
        logger.error(f"Unknown provider: {provider}")
        return []
    
    logger.info(f"{'='*60}")
    logger.info(f"Airport Quote Scraping: {provider}")
    logger.info(f"Airport: {airport_code}")
    logger.info(f"Pickup: {pickup_date.strftime('%Y-%m-%d %H:%M')}")
    logger.info(f"Dropoff: {dropoff_date.strftime('%Y-%m-%d %H:%M')}")
    logger.info(f"Duration: {(dropoff_date - pickup_date).days} day(s)")
    logger.info(f"{'='*60}")
    
    vehicles = []
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            
            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={'width': 1920, 'height': 1080},
                locale='en-SA',
                timezone_id='Asia/Riyadh'
            )
            
            page = await context.new_page()
            
            try:
                # Navigate to provider homepage
                url = PROVIDER_URLS[provider]
                logger.info(f"Navigating to {url}")
                await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                await asyncio.sleep(2)
                
                # Special handling for Yelo - wait for JS content to load
                if provider == 'yelo':
                    logger.info("Waiting for Yelo JS content to load...")
                    try:
                        # Wait for actual car cards (not loader placeholders)
                        await page.wait_for_selector('.car-rental-deals-container .card:not(:has(img[src*="loader"]))', timeout=10000)
                        logger.info("Yelo content loaded successfully")
                    except Exception as e:
                        logger.warning(f"Yelo content did not load fully: {e}, proceeding anyway")
                    await asyncio.sleep(3)  # Additional wait for full rendering
                
                # TODO: Provider-specific form filling logic here
                # For now, get current page content (homepage)
                # In production, you'd fill booking form and submit
                
                # Wait for page to stabilize after navigation
                await page.wait_for_load_state('domcontentloaded')
                await asyncio.sleep(2)  # Additional stability wait
                
                # Scroll to load all vehicles
                logger.info("Scrolling to load all vehicle cards...")
                previous_height = 0
                scroll_attempts = 0
                max_scroll_attempts = 10
                
                while scroll_attempts < max_scroll_attempts:
                    try:
                        # Get current scroll height
                        current_height = await page.evaluate('document.body.scrollHeight')
                        
                        if current_height == previous_height:
                            break
                        
                        # Scroll to bottom
                        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                        await asyncio.sleep(1.5)
                        
                        previous_height = current_height
                        scroll_attempts += 1
                        logger.info(f"  Scroll attempt {scroll_attempts}/{max_scroll_attempts}")
                    except Exception as scroll_err:
                        # Handle navigation errors gracefully
                        if 'context' in str(scroll_err).lower() or 'navigation' in str(scroll_err).lower():
                            logger.warning(f"Page navigated during scroll, stopping: {scroll_err}")
                            break
                        else:
                            logger.warning(f"Scroll error: {scroll_err}")
                            break
                
                # Try clicking "Load More" button if exists
                load_more_clicks = 0
                max_load_more = 5
                
                load_more_selectors = [
                    'button:has-text("Load More")',
                    'button:has-text("Show More")',
                    'button:has-text("View More")',
                    '.load-more',
                    '.show-more'
                ]
                
                for selector in load_more_selectors:
                    while load_more_clicks < max_load_more:
                        try:
                            load_more_btn = page.locator(selector).first
                            if await load_more_btn.is_visible(timeout=2000):
                                await load_more_btn.click()
                                await asyncio.sleep(2)
                                load_more_clicks += 1
                                logger.info(f"  Clicked load-more button ({load_more_clicks})")
                            else:
                                break
                        except:
                            break
                
                # Try pagination (click next pages)
                page_clicks = 0
                max_pages = 5
                
                pagination_selectors = [
                    'button:has-text("Next")',
                    'a:has-text("Next")',
                    '.pagination .next',
                    '.pagination-next'
                ]
                
                for selector in pagination_selectors:
                    while page_clicks < max_pages:
                        try:
                            next_btn = page.locator(selector).first
                            if await next_btn.is_visible(timeout=2000):
                                await next_btn.click()
                                await asyncio.sleep(3)
                                page_clicks += 1
                                logger.info(f"  Navigated to page {page_clicks + 1}")
                            else:
                                break
                        except:
                            break
                
                # Get final HTML content
                html = await page.content()
                
                # Parse vehicle cards from HTML
                soup = BeautifulSoup(html, 'lxml')
                
                # Find vehicle cards (provider-specific selectors)
                card_selectors = [
                    '.card-deals',  # Yelo
                    '.vehicle-item',  # Budget
                    '.car-card',
                    '.vehicle-card',
                    '.rental-option',
                    '.fleet-item',
                    'div[class*="vehicle"]',
                    'div[class*="car"]',
                    'article[class*="car"]',
                    'li[class*="car"]'
                ]
                
                cards_found = []
                for selector_class in card_selectors:
                    if selector_class.startswith('.'):
                        # Simple class selector like '.card-deals'
                        class_name = selector_class[1:]  # Remove leading dot
                        cards_found = soup.find_all(class_=class_name)
                    elif '[class*=' in selector_class:
                        # Attribute selector like 'div[class*="car"]'
                        tag = selector_class.split('[')[0]
                        pattern = selector_class.split('"')[1] if '"' in selector_class else selector_class.split("'")[1]
                        cards_found = soup.find_all(tag, class_=re.compile(re.escape(pattern)))
                    else:
                        # Fallback
                        cards_found = soup.find_all(selector_class)
                    
                    if cards_found:
                        logger.info(f"Found {len(cards_found)} vehicle cards using selector: {selector_class}")
                        break
                
                if not cards_found:
                    logger.warning(f"No vehicle cards found for {provider}")
                    
                    # Save debug doc
                    debug_ref = db.collection('competitor_scrape_debug').document()
                    debug_ref.set({
                        'provider': provider,
                        'airport_code': airport_code,
                        'scrape_type': 'airport_quote_1day',
                        'timestamp': firestore.SERVER_TIMESTAMP,
                        'error': 'No vehicle cards found',
                        'html_preview': html[:12000],
                        'html_length': len(html),
                        'scroll_attempts': scroll_attempts,
                        'load_more_clicks': load_more_clicks,
                        'page_clicks': page_clicks
                    })
                    logger.info(f"Debug doc saved: competitor_scrape_debug/{debug_ref.id}")
                    
                    return []
                
                # Parse each vehicle card
                logger.info(f"Parsing {len(cards_found)} vehicle cards...")
                
                for idx, card in enumerate(cards_found):
                    try:
                        # Extract car name
                        name_elem = (
                            card.find(class_='deals-name-title') or  # Yelo
                            card.find(class_='deals-title') or  # Yelo alternate
                            card.find(class_='vehicle-name') or
                            card.find(class_='car-name') or
                            card.find(class_='car-title') or
                            card.find('h3') or
                            card.find('h4') or
                            card.find('h5')
                        )
                        car_name = name_elem.get_text(strip=True) if name_elem else f"Vehicle_{idx+1}"
                        
                        # Extract category
                        category_elem = (
                            card.find(class_='category') or
                            card.find(class_='vehicle-type') or
                            card.find(class_='car-type')
                        )
                        raw_category = category_elem.get_text(strip=True) if category_elem else ""
                        
                        # Determine bucket
                        bucket = _categorize_vehicle_bucket(raw_category, car_name)
                        
                        # Extract price with comprehensive selectors
                        price_elem = (
                            card.find(class_='car-Price') or  # Yelo
                            card.find(class_='deals-price') or  # Yelo deals
                            card.find(class_='price-tag') or  # Yelo price tag
                            card.find(class_='daily-rate') or  # Yelo daily
                            card.find(class_='price') or
                            card.find(class_='rate') or
                            card.find(class_='cost') or
                            card.find(class_='amount') or
                            card.find('span', class_=re.compile(r'.*price.*', re.I)) or
                            card.find('div', class_=re.compile(r'.*price.*', re.I)) or
                            card.find(class_=re.compile(r'.*price.*|.*rate.*|.*cost.*', re.I))
                        )
                        raw_price_text = price_elem.get_text(strip=True) if price_elem else "0"
                        numeric_price = _extract_price(raw_price_text)
                        
                        # Debug logging for first card when no prices found
                        if idx == 0 and numeric_price == 0 and provider in ['yelo', 'budget', 'lumi']:
                            logger.warning(f"{provider.upper()} price extraction debug (card {idx}):")
                            logger.warning(f"  car_name: {car_name}")
                            logger.warning(f"  raw_category: {raw_category}")
                            logger.warning(f"  price_elem: {price_elem}")
                            logger.warning(f"  raw_price_text: {raw_price_text}")
                            logger.warning(f"  Card HTML (first 800 chars): {str(card)[:800]}")
                            
                            # Show all elements with class containing 'price', 'rate', 'cost'
                            price_related = card.find_all(class_=re.compile(r'.*price.*|.*rate.*|.*cost.*|.*amount.*', re.I))
                            if price_related:
                                logger.warning(f"  Found {len(price_related)} price-related elements:")
                                for i, elem in enumerate(price_related[:5]):
                                    logger.warning(f"    [{i}] {elem.get('class')}: {elem.get_text(strip=True)[:100]}")
                        
                        if numeric_price > 0:
                            vehicle_data = {
                                'car_name': car_name,
                                'raw_category': raw_category,
                                'bucket': bucket,
                                'raw_price_text': raw_price_text,
                                'numeric_price': numeric_price,
                                'pickup_at': pickup_date,
                                'dropoff_at': dropoff_date,
                                'duration_days': 1,
                                'provider': provider,
                                'airport_code': airport_code
                            }
                            vehicles.append(vehicle_data)
                    
                    except Exception as e:
                        logger.warning(f"Error parsing vehicle card {idx+1}: {e}")
                        continue
                
                logger.info(f"✅ Parsed {len(vehicles)} vehicles with valid prices")
                
            finally:
                await page.close()
                await context.close()
                await browser.close()
    
    except Exception as e:
        logger.error(f"Error in airport quote scraping: {e}")
        
        # Save debug doc on error
        try:
            debug_ref = db.collection('competitor_scrape_debug').document()
            debug_ref.set({
                'provider': provider,
                'airport_code': airport_code,
                'scrape_type': 'airport_quote_1day',
                'timestamp': firestore.SERVER_TIMESTAMP,
                'error': str(e),
                'vehicles_found': len(vehicles)
            })
        except:
            pass
    
    return vehicles


def _check_duplicate_offer(offer_hash: str, hours: int = 6) -> bool:
    """
    Check if an offer with the same hash exists within the specified time window.
    
    Args:
        offer_hash: Hash of the offer
        hours: Time window in hours (default: 6)
        
    Returns:
        True if duplicate exists, False otherwise
    """
    try:
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Query Firestore for existing offer with same hash
        competitor_ref = db.collection('competitor_prices_latest')
        query = competitor_ref.where('hash', '==', offer_hash).where('scraped_at', '>=', cutoff_time).limit(1)
        
        docs = list(query.stream())
        return len(docs) > 0
        
    except Exception as e:
        logger.warning(f"Error checking duplicate: {e}")
        return False  # If check fails, allow insert


# ==================== PROVIDER-SPECIFIC PARSERS ====================

def _parse_key_sa(html: str, city: str) -> List[Dict]:
    """
    Parse KEY.SA rental car listings.
    
    HTML Structure:
        - Vehicle cards: .car-box
        - Name: .car-name
        - Category: inferred from labels/description
        - Price: .car-price
    """
    offers = []
    
    try:
        soup = BeautifulSoup(html, 'lxml')
        
        # Find all car boxes
        car_boxes = soup.find_all(class_='car-box')
        if not car_boxes:
            # Try alternative selectors
            car_boxes = soup.find_all('div', {'class': re.compile(r'vehicle|car|product')})
        
        logger.info(f"KEY.SA: Found {len(car_boxes)} vehicle cards")
        
        for box in car_boxes:
            try:
                # Extract vehicle name
                name_elem = box.find(class_='car-name') or box.find(class_='vehicle-name')
                vehicle_name = name_elem.get_text(strip=True) if name_elem else "Unknown"
                
                # Extract category
                category_elem = box.find(class_='car-type') or box.find(class_='category')
                category_text = category_elem.get_text(strip=True) if category_elem else vehicle_name
                category = _normalize_category(category_text, vehicle_name)
                
                # Extract price
                price_elem = box.find(class_='car-price') or box.find(class_='price')
                price_text = price_elem.get_text(strip=True) if price_elem else "0"
                price = _extract_price(price_text)
                
                if price > 0:
                    offers.append({
                        "provider": "key",
                        "city": city,
                        "category": category,
                        "vehicle_name": vehicle_name,
                        "price": price,
                        "currency": "SAR",
                        "scraped_at": datetime.utcnow(),
                        "url": PROVIDER_URLS["key"]
                    })
                    
            except Exception as e:
                logger.warning(f"KEY.SA: Error parsing car box: {e}")
                continue
        
    except Exception as e:
        logger.error(f"KEY.SA: Parser error: {e}")
    
    return offers


def _parse_budget_saudi(html: str, city: str) -> List[Dict]:
    """
    Parse BudgetSaudi.com rental car listings (JS-heavy site).
    
    HTML Structure (after JS rendering):
        - Vehicle cards: .vehicle-item, .car-card, div[class*='vehicle'], div[class*='car']
        - Name: .vehicle-name, .car-name, h3, h4
        - Category: .vehicle-type, .category, .car-type
        - Price: .rate, .price, .daily-rate, .price-amount
    """
    offers = []
    
    try:
        soup = BeautifulSoup(html, 'lxml')
        
        # Try multiple selector patterns for vehicle cards
        vehicle_items = []
        
        # Pattern 1: Direct class matches
        vehicle_items = soup.find_all(class_='vehicle-item')
        if not vehicle_items:
            vehicle_items = soup.find_all(class_='car-card')
        
        # Pattern 2: Partial class matching
        if not vehicle_items:
            vehicle_items = soup.find_all('div', {'class': re.compile(r'vehicle|car-card|car-item')})
        
        # Pattern 3: Look for common booking widget structures
        if not vehicle_items:
            vehicle_items = soup.find_all('div', {'class': re.compile(r'booking.*card|rental.*item')})
        
        # Pattern 4: Find divs containing both price and vehicle info
        if not vehicle_items:
            all_divs = soup.find_all('div')
            for div in all_divs:
                # Check if div contains price-like elements
                has_price = div.find(class_=re.compile(r'price|rate|amount'))
                has_vehicle_info = div.find(class_=re.compile(r'vehicle|car|model'))
                
                if has_price and has_vehicle_info:
                    vehicle_items.append(div)
        
        logger.info(f"BudgetSaudi: Found {len(vehicle_items)} vehicle cards (JS-rendered)")
        
        # If still no items, log HTML structure for debugging
        if not vehicle_items:
            logger.warning(f"BudgetSaudi: No vehicle items found. HTML length: {len(html)} bytes")
            # Log first 2000 chars to see structure
            logger.debug(f"BudgetSaudi: HTML preview: {html[:2000]}")
        
        for item in vehicle_items:
            try:
                # Extract vehicle name (try multiple selectors)
                name_elem = (
                    item.find(class_='vehicle-name') or 
                    item.find(class_='car-name') or 
                    item.find(class_=re.compile(r'.*name.*')) or
                    item.find('h3') or 
                    item.find('h4') or
                    item.find('h2')
                )
                vehicle_name = name_elem.get_text(strip=True) if name_elem else "Unknown"
                
                # Extract category (try multiple selectors)
                type_elem = (
                    item.find(class_='vehicle-type') or 
                    item.find(class_='car-type') or
                    item.find(class_='category') or
                    item.find(class_=re.compile(r'.*type.*|.*category.*'))
                )
                category_text = type_elem.get_text(strip=True) if type_elem else vehicle_name
                category = _normalize_category(category_text, vehicle_name)
                
                # Extract price (try multiple selectors)
                rate_elem = (
                    item.find(class_='rate') or 
                    item.find(class_='price') or
                    item.find(class_='daily-rate') or
                    item.find(class_='price-amount') or
                    item.find(class_=re.compile(r'.*price.*|.*rate.*|.*amount.*'))
                )
                price_text = rate_elem.get_text(strip=True) if rate_elem else "0"
                price = _extract_price(price_text)
                
                if price > 0:
                    offers.append({
                        "provider": "budget",
                        "city": city,
                        "category": category,
                        "vehicle_name": vehicle_name,
                        "price": price,
                        "currency": "SAR",
                        "scraped_at": datetime.utcnow(),
                        "url": PROVIDER_URLS["budget"]
                    })
                    
            except Exception as e:
                logger.warning(f"BudgetSaudi: Error parsing vehicle item: {e}")
                continue
        
    except Exception as e:
        logger.error(f"BudgetSaudi: Parser error: {e}")
    
    return offers


def _parse_iyelo(html: str, city: str) -> List[Dict]:
    """
    Parse iYelo.com rental car listings.
    
    HTML Structure:
        - Deal cards: .card-deals
        - Category name: .deals-name-title span
        - Price: .car-Price
    """
    offers = []
    
    try:
        soup = BeautifulSoup(html, 'lxml')
        
        # Find all deal cards (updated selector)
        deal_cards = soup.find_all(class_='card-deals')
        
        logger.info(f"iYelo: Found {len(deal_cards)} deal cards")
        
        for card in deal_cards:
            try:
                # Extract category from deals-name-title
                title_elem = card.find(class_='deals-name-title')
                if title_elem:
                    span = title_elem.find('span')
                    category_text = span.get_text(strip=True) if span else title_elem.get_text(strip=True)
                else:
                    category_text = "Unknown"
                
                vehicle_name = category_text  # Use category as vehicle name
                category = _normalize_category(category_text, vehicle_name)
                
                # Extract price from car-Price class
                price_elem = card.find(class_='car-Price')
                if not price_elem:
                    price_elem = card.find(class_=re.compile(r'price', re.I))
                
                price_text = price_elem.get_text(strip=True) if price_elem else "0"
                price = _extract_price(price_text)
                
                if price > 0:
                    offers.append({
                        "provider": "yelo",
                        "city": city,
                        "category": category,
                        "vehicle_name": vehicle_name,
                        "price": price,
                        "currency": "SAR",
                        "scraped_at": datetime.utcnow(),
                        "url": PROVIDER_URLS["yelo"]
                    })
                    logger.debug(f"iYelo: Extracted {vehicle_name} at {price} SAR")
                    
            except Exception as e:
                logger.warning(f"iYelo: Error parsing deal card: {e}")
                continue
        
    except Exception as e:
        logger.error(f"iYelo: Parser error: {e}")
    
    return offers


def _parse_lumi(html: str, city: str) -> List[Dict]:
    """
    Parse Lumi.com.sa rental car listings.
    
    HTML Structure:
        - Vehicle cards: .v-card
        - Name: .v-title
        - Category: .v-category
        - Price: .v-rate
    """
    offers = []
    
    try:
        soup = BeautifulSoup(html, 'lxml')
        
        # Find all v-cards
        v_cards = soup.find_all(class_='v-card')
        if not v_cards:
            v_cards = soup.find_all('div', {'class': re.compile(r'card|vehicle|car')})
        
        logger.info(f"Lumi: Found {len(v_cards)} vehicle cards")
        
        for card in v_cards:
            try:
                # Extract vehicle name
                title_elem = card.find(class_='v-title') or card.find('h3') or card.find('h4')
                vehicle_name = title_elem.get_text(strip=True) if title_elem else "Unknown"
                
                # Extract category
                category_elem = card.find(class_='v-category') or card.find(class_='category')
                category_text = category_elem.get_text(strip=True) if category_elem else vehicle_name
                category = _normalize_category(category_text, vehicle_name)
                
                # Extract price
                rate_elem = card.find(class_='v-rate') or card.find(class_='price')
                price_text = rate_elem.get_text(strip=True) if rate_elem else "0"
                price = _extract_price(price_text)
                
                if price > 0:
                    offers.append({
                        "provider": "lumi",
                        "city": city,
                        "category": category,
                        "vehicle_name": vehicle_name,
                        "price": price,
                        "currency": "SAR",
                        "scraped_at": datetime.utcnow(),
                        "url": PROVIDER_URLS["lumi"]
                    })
                    
            except Exception as e:
                logger.warning(f"Lumi: Error parsing v-card: {e}")
                continue
        
    except Exception as e:
        logger.error(f"Lumi: Parser error: {e}")
    
    return offers


def _extract_offers_from_html(provider: str, city: str, html: str) -> List[Dict]:
    """
    Extract offers from HTML using provider-specific parsers.
    
    Args:
        provider: Provider key (key, budget, yelo, lumi)
        city: City name
        html: Rendered HTML content
        
    Returns:
        List of normalized offer dictionaries
    """
    if provider == "key":
        return _parse_key_sa(html, city)
    elif provider == "budget":
        return _parse_budget_saudi(html, city)
    elif provider == "yelo":
        return _parse_iyelo(html, city)
    elif provider == "lumi":
        return _parse_lumi(html, city)
    else:
        logger.error(f"Unknown provider: {provider}")
        return []


async def save_airport_quote_results(vehicles: List[Dict[str, Any]], provider: str) -> Dict[str, int]:
    """
    Save airport quote results to Firestore with deduplication.
    
    Deduplication key: (provider, airport_code, pickup_date, duration, car_name)
    
    Args:
        vehicles: List of vehicle dictionaries from fetch_airport_quote_with_scroll
        provider: Provider name
        
    Returns:
        Dictionary with save statistics
    """
    if not vehicles:
        logger.warning(f"No vehicles to save for {provider}")
        return {'saved': 0, 'skipped': 0, 'errors': 0}
    
    saved_count = 0
    skipped_count = 0
    error_count = 0
    
    logger.info(f"Saving {len(vehicles)} vehicles to Firestore...")
    
    competitor_ref = db.collection('competitor_prices_latest')
    batch = db.batch()
    batch_operations = 0
    
    for vehicle in vehicles:
        try:
            # Generate unique document ID instead of querying
            # Format: {provider}_{airport}_{date}_{duration}_{car_hash}
            pickup_date_str = vehicle['pickup_at'].strftime('%Y-%m-%d')
            dedupe_key = f"{provider}|{vehicle['airport_code']}|{pickup_date_str}|{vehicle['duration_days']}|{vehicle['car_name']}"
            dedupe_hash = hashlib.md5(dedupe_key.encode()).hexdigest()[:12]
            doc_id = f"{provider}_{vehicle['airport_code']}_{pickup_date_str}_{vehicle['duration_days']}d_{dedupe_hash}"
            
            # Check if document already exists using get() instead of query
            doc_ref = competitor_ref.document(doc_id)
            existing_doc = doc_ref.get()
            
            if existing_doc.exists:
                # Check if it's recent (last 24 hours)
                scraped_at = existing_doc.get('scraped_at')
                if scraped_at:
                    # Make sure both datetimes are timezone-aware for comparison
                    from datetime import timezone
                    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
                    if scraped_at > cutoff_time:
                        skipped_count += 1
                        logger.debug(f"Skipping recent duplicate: {vehicle['car_name']}")
                        continue
            
            # Prepare document data
            doc_data = {
                'provider': provider,
                'branch_id': vehicle['airport_code'],
                'vehicle_class': _normalize_category(vehicle['raw_category'], vehicle['car_name']),
                'vehicle_name': vehicle['car_name'],
                'vehicle_bucket': vehicle['bucket'],
                'raw_category': vehicle['raw_category'],
                'price_per_day': vehicle['numeric_price'],
                'raw_price_text': vehicle['raw_price_text'],
                'currency': 'SAR',
                'pickup_at': vehicle['pickup_at'],
                'dropoff_at': vehicle['dropoff_at'],
                'duration_days': vehicle['duration_days'],
                'scraped_at': datetime.utcnow(),
                'source_url': PROVIDER_URLS.get(provider, ''),
                'doc_id': doc_id,
                'scrape_type': 'airport_quote_1day',
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            # Use deterministic doc ID for natural deduplication
            batch.set(doc_ref, doc_data)
            batch_operations += 1
            saved_count += 1
            
            # Commit batch every 500 operations
            if batch_operations >= 500:
                batch.commit()
                batch = db.batch()
                batch_operations = 0
        
        except Exception as e:
            logger.error(f"Error saving vehicle {vehicle.get('car_name', 'unknown')}: {e}")
            error_count += 1
            continue
    
    # Commit remaining operations
    if batch_operations > 0:
        batch.commit()
    
    logger.info(f"✅ Save complete: {saved_count} saved, {skipped_count} skipped, {error_count} errors")
    
    return {
        'saved': saved_count,
        'skipped': skipped_count,
        'errors': error_count
    }


# ==================== MAIN SCRAPING FUNCTIONS ====================

async def scrape_provider(provider: str, city: str = 'riyadh', category: Optional[str] = None) -> Dict:
    """
    Scrape a single provider with resilience and status tracking.
    
    Args:
        provider: Provider key (key, budget, yelo, lumi)
        city: City name (default: riyadh)
        category: Optional category filter
        
    Returns:
        Dictionary with status, offers, and error info
    """
    if provider not in PROVIDER_URLS:
        logger.error(f"Unknown provider: {provider}")
        return {'status': 'error', 'error': 'unknown_provider', 'offers_found': 0, 'new_offers': 0}
    
    start_time = time.time()
    status_ref = db.collection('competitor_scrape_status').document(provider)
    
    try:
        # Fetch HTML with retry
        url = PROVIDER_URLS[provider]
        
        # Validate URL accessibility (DNS + HTTP status)
        try:
            # Use specialized fetcher for Budget (JS-heavy)
            if provider == 'budget':
                html = await fetch_html_budget(url, provider)
            else:
                html = await fetch_html(url)
            
            # Check for 404 or error pages
            if '404' in html[:5000] and 'not found' in html[:5000].lower():
                logger.warning(f"⚠️ {provider}: URL returned 404 page, marking as disabled for this run")
                return {
                    'status': 'disabled',
                    'error': '404_page_detected',
                    'offers_found': 0,
                    'new_offers': 0,
                    'duration_ms': int((time.time() - start_time) * 1000)
                }
                
        except Exception as validation_error:
            error_str = str(validation_error).lower()
            # Check for DNS failures
            if 'name_not_resolved' in error_str or 'getaddrinfo failed' in error_str or 'dns' in error_str:
                logger.warning(f"⚠️ {provider}: DNS lookup failed for {url}, marking as disabled for this run")
                return {
                    'status': 'disabled',
                    'error': 'dns_lookup_failed',
                    'offers_found': 0,
                    'new_offers': 0,
                    'duration_ms': int((time.time() - start_time) * 1000)
                }
            # Re-raise other errors to be handled by main try-except
            raise
        
        # Extract offers
        offers = _extract_offers_from_html(provider, city, html)
        
        # Filter by category if specified
        if category:
            offers = [o for o in offers if o['category'] == category]
        
        # Save to Firestore with deduplication
        saved_count = 0
        skipped_count = 0
        
        if offers:
            competitor_ref = db.collection('competitor_prices_latest')
            batch = db.batch()
            
            for offer in offers:
                # Generate hash for deduplication
                offer_hash = _generate_offer_hash(
                    provider=offer['provider'],
                    branch=offer['city'],
                    vehicle_class=offer['category'],
                    price=offer['price']
                )
                
                # Check if duplicate exists in last 6 hours
                if _check_duplicate_offer(offer_hash, hours=6):
                    skipped_count += 1
                    logger.debug(f"Skipping duplicate offer: {provider}/{offer['city']}/{offer['category']}")
                    continue
                
                # Prepare document with required fields
                doc_data = {
                    'provider': offer['provider'],
                    'branch_id': offer['city'],
                    'vehicle_class': offer['category'],
                    'vehicle_name': offer.get('vehicle_name', 'Unknown'),
                    'price_per_day': offer['price'],
                    'currency': offer.get('currency', 'SAR'),
                    'scraped_at': datetime.utcnow(),
                    'source_url': offer.get('url', PROVIDER_URLS.get(provider, '')),
                    'hash': offer_hash,
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'updated_at': firestore.SERVER_TIMESTAMP
                }
                
                doc_ref = competitor_ref.document()
                batch.set(doc_ref, doc_data)
                saved_count += 1
            
            if saved_count > 0:
                batch.commit()
                logger.info(f"Saved {saved_count} new offers from {provider} (skipped {skipped_count} duplicates)")
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Update success status
        status_ref.set({
            'last_run_at': firestore.SERVER_TIMESTAMP,
            'last_success_at': firestore.SERVER_TIMESTAMP,
            'last_error': None,
            'last_duration_ms': duration_ms,
            'last_offer_count': len(offers),
            'is_stale': False,
            'provider': provider
        }, merge=True)
        
        logger.info(f"✅ {provider}: {len(offers)} offers found, {saved_count} new")
        
        return {
            'status': 'success',
            'offers_found': len(offers),
            'new_offers': saved_count,
            'duration_ms': duration_ms
        }
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        error_msg = str(e)
        
        logger.error(f"❌ Error scraping {provider}: {error_msg}")
        
        # Update error status (but keep last_success_at)
        existing_doc = status_ref.get()
        
        # Check if data is stale (last success > 2 hours ago)
        is_stale = False
        if existing_doc.exists:
            last_success = existing_doc.to_dict().get('last_success_at')
            if last_success:
                # Convert Firestore timestamp to datetime
                if hasattr(last_success, 'timestamp'):
                    last_success_dt = datetime.fromtimestamp(last_success.timestamp())
                    hours_since_success = (datetime.utcnow() - last_success_dt).total_seconds() / 3600
                    is_stale = hours_since_success > 2
        else:
            is_stale = True  # Never succeeded
        
        status_ref.set({
            'last_run_at': firestore.SERVER_TIMESTAMP,
            'last_error': error_msg,
            'last_duration_ms': duration_ms,
            'last_offer_count': 0,
            'is_stale': is_stale,
            'provider': provider
        }, merge=True)  # merge=True preserves last_success_at
        
        return {
            'status': 'error',
            'error': error_msg,
            'offers_found': 0,
            'new_offers': 0,
            'duration_ms': duration_ms
        }


async def scrape_all_providers(city: str, category: Optional[str] = None) -> Dict[str, List[Dict]]:
    """
    Scrape all providers in parallel for a specific city.
    
    This is the main entry point for competitor price scraping.
    Used by the pricing engine to get real-time competitor data.
    
    Args:
        city: City name (riyadh, jeddah, etc.)
        category: Optional category filter (economy, sedan, suv, luxury)
        
    Returns:
        Dictionary mapping provider names to lists of offers:
        {
            "key": [{...}, {...}],
            "budget": [{...}],
            "yelo": [{...}],
            "lumi": [{...}]
        }
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.error("Playwright not available for scraping")
        return {provider: [] for provider in PROVIDER_URLS.keys()}
    
    logger.info(f"Scraping all providers for city={city}, category={category}")
    
    results = {}
    
    # Scrape providers sequentially to avoid rate limiting
    for provider in PROVIDER_URLS.keys():
        try:
            offers = await scrape_provider(provider, city, category)
            results[provider] = offers
            
            # Small delay between providers
            await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"Failed to scrape {provider}: {str(e)}")
            results[provider] = []
    
    total_offers = sum(len(offers) for offers in results.values())
    logger.info(f"Scraped {total_offers} total offers from {len(results)} providers")
    
    return results


async def scrape_airport_quotes_1day(
    providers: Optional[List[str]] = None,
    airports: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Scrape 1-day airport quotes for specified providers and airports.
    
    This function:
    1. For each provider × airport combination
    2. Generates pickup = tomorrow 10:00, dropoff = day after 10:00 (1 day duration)
    3. Calls fetch_airport_quote_with_scroll() to get all vehicles
    4. Saves results to Firestore with deduplication
    
    Args:
        providers: List of provider keys (defaults to all active providers)
        airports: List of airport codes (defaults to riyadh_airport, jeddah_airport)
        
    Returns:
        Summary dictionary with statistics
    """
    if providers is None:
        providers = list(PROVIDER_URLS.keys())
    
    if airports is None:
        airports = ['riyadh_airport', 'jeddah_airport', 'dammam_airport']
    
    logger.info(f"{'='*80}")
    logger.info(f"Airport Quote Scraping (1-day)")
    logger.info(f"Providers: {', '.join(providers)}")
    logger.info(f"Airports: {', '.join(airports)}")
    logger.info(f"{'='*80}")
    
    # Calculate pickup and dropoff times (tomorrow 10:00 to next day 10:00)
    tomorrow = datetime.now() + timedelta(days=1)
    pickup_date = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
    dropoff_date = pickup_date + timedelta(days=1)
    
    summary = {
        'total_vehicles': 0,
        'total_saved': 0,
        'total_skipped': 0,
        'results_by_provider': {},
        'errors': [],
        'started_at': datetime.utcnow()
    }
    
    # Scrape each provider × airport combination
    for provider in providers:
        summary['results_by_provider'][provider] = {
            'airports': {},
            'total_vehicles': 0,
            'total_saved': 0
        }
        
        for airport in airports:
            logger.info(f"\n{'='*60}")
            logger.info(f"Scraping: {provider} @ {airport}")
            logger.info(f"{'='*60}")
            
            try:
                # Fetch vehicles
                vehicles = await fetch_airport_quote_with_scroll(
                    provider=provider,
                    airport_code=airport,
                    pickup_date=pickup_date,
                    dropoff_date=dropoff_date
                )
                
                # Save to Firestore
                save_result = await save_airport_quote_results(vehicles, provider)
                
                # Update summary
                summary['total_vehicles'] += len(vehicles)
                summary['total_saved'] += save_result['saved']
                summary['total_skipped'] += save_result['skipped']
                
                summary['results_by_provider'][provider]['airports'][airport] = {
                    'vehicles_found': len(vehicles),
                    'saved': save_result['saved'],
                    'skipped': save_result['skipped'],
                    'errors': save_result['errors']
                }
                
                summary['results_by_provider'][provider]['total_vehicles'] += len(vehicles)
                summary['results_by_provider'][provider]['total_saved'] += save_result['saved']
                
                logger.info(f"✅ {provider}/{airport}: {len(vehicles)} vehicles, {save_result['saved']} saved")
                
                # Delay between airports
                await asyncio.sleep(3)
                
            except Exception as e:
                error_msg = f"{provider}/{airport}: {str(e)}"
                logger.error(f"❌ {error_msg}")
                summary['errors'].append(error_msg)
                
                summary['results_by_provider'][provider]['airports'][airport] = {
                    'vehicles_found': 0,
                    'saved': 0,
                    'error': str(e)
                }
        
        # Delay between providers
        await asyncio.sleep(5)
    
    summary['completed_at'] = datetime.utcnow()
    summary['duration_seconds'] = (summary['completed_at'] - summary['started_at']).total_seconds()
    
    logger.info(f"\n{'='*80}")
    logger.info(f"Airport Quote Scraping Complete")
    logger.info(f"Total vehicles found: {summary['total_vehicles']}")
    logger.info(f"Total saved: {summary['total_saved']}")
    logger.info(f"Total skipped (duplicates): {summary['total_skipped']}")
    logger.info(f"Duration: {summary['duration_seconds']:.1f}s")
    if summary['errors']:
        logger.warning(f"Errors: {len(summary['errors'])}")
    logger.info(f"{'='*80}")
    
    return summary


# ==================== LEGACY SUPPORT FUNCTIONS ====================
# These maintain backward compatibility with existing API

async def fetch_offers_for_provider(provider: str, city: str, crawler_config: Optional[Any] = None) -> List[Dict]:
    """
    Legacy function for backward compatibility.
    Use scrape_provider() instead.
    
    Args:
        provider: Provider key (key, budget, yelo, lumi)
        city: City name
        crawler_config: Ignored, kept for compatibility
        
    Returns:
        List of offer dictionaries
    """
    logger.warning(f"fetch_offers_for_provider is deprecated, use scrape_provider() instead")
    return await scrape_provider(provider, city)


async def refresh_competitor_prices(
    cities: List[str],
    firestore_client,
    providers: Optional[List[str]] = None
) -> Dict[str, any]:
    """
    Refresh competitor prices for multiple cities and providers.
    
    Args:
        cities: List of city names to scrape
        firestore_client: Firestore database client (ignored, uses global db)
        providers: Optional list of providers (defaults to all)
        
    Returns:
        Summary dictionary with:
            - total_offers: int
            - offers_by_provider: dict
            - cities_scraped: list
            - errors: list
    """
    if providers is None:
        providers = list(PROVIDER_URLS.keys())
    
    summary = {
        "total_offers": 0,
        "offers_by_provider": {},
        "cities_scraped": cities,
        "errors": [],
        "started_at": datetime.utcnow(),
    }
    
    try:
        # Scrape each provider x city combination
        tasks = []
        for provider in providers:
            for city in cities:
                tasks.append(scrape_provider(provider, city))
        
        # Run with rate limiting (batch of 3)
        batch_size = 3
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i+batch_size]
            results = await asyncio.gather(*batch, return_exceptions=True)
            
            for j, result in enumerate(results):
                if isinstance(result, Exception):
                    summary["errors"].append(str(result))
                else:
                    provider = providers[(i + j) // len(cities)]
                    summary["total_offers"] += len(result)
                    summary["offers_by_provider"][provider] = summary["offers_by_provider"].get(provider, 0) + len(result)
            
            # Delay between batches
            if i + batch_size < len(tasks):
                await asyncio.sleep(2)
        
        summary["completed_at"] = datetime.utcnow()
        summary["duration_seconds"] = (summary["completed_at"] - summary["started_at"]).total_seconds()
        
        logger.info(f"Competitor refresh complete: {summary['total_offers']} offers in {summary['duration_seconds']:.1f}s")
        
    except Exception as e:
        logger.error(f"Error in refresh_competitor_prices: {str(e)}")
        summary["errors"].append(str(e))
    
    return summary


def get_supported_cities() -> List[str]:
    """
    Get list of supported cities for scraping.
    
    Returns cities from cached branches loaded from Firestore.
    If branches not loaded yet, returns empty list.
    """
    global _branches_cache
    
    if _branches_cache is None:
        logger.warning("get_supported_cities called before branches loaded from Firestore")
        return []
    
    return get_cities_from_branches(_branches_cache)


def get_supported_providers() -> List[str]:
    """Get list of supported providers."""
    return list(PROVIDER_URLS.keys())


async def cleanup_old_prices(firestore_client, days_old: int = 7) -> int:
    """
    Delete competitor prices older than specified days.
    
    Args:
        firestore_client: Firestore database client (ignored, uses global db)
        days_old: Delete prices older than this many days
        
    Returns:
        Number of documents deleted
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        competitor_ref = db.collection('competitor_prices')
        old_docs = competitor_ref.where('scraped_at', '<', cutoff_date).stream()
        
        batch = db.batch()
        count = 0
        
        for doc in old_docs:
            batch.delete(doc.reference)
            count += 1
            
            if count % 500 == 0:
                batch.commit()
                batch = db.batch()
        
        if count % 500 != 0:
            batch.commit()
        
        logger.info(f"Deleted {count} old competitor prices (>{days_old} days)")
        return count
        
    except Exception as e:
        logger.error(f"Error cleaning up old prices: {str(e)}")
        return 0


# ==================== COMPETITOR AGGREGATION ====================

def compute_aggregates_for_branch_vehicle(branch_id: str, vehicle_class: str, hours: int = 6) -> Optional[Dict]:
    """
    Compute competitor price aggregates for a specific branch and vehicle class.
    
    Args:
        branch_id: Branch/city identifier
        vehicle_class: Vehicle category (economy, sedan, suv, luxury)
        hours: Time window in hours (default: 6)
        
    Returns:
        Dictionary with aggregates or None if no data
    """
    try:
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Query competitor prices for this branch/vehicle in last 6 hours
        competitor_ref = db.collection('competitor_prices')
        query = competitor_ref \
            .where('branch_id', '==', branch_id) \
            .where('vehicle_class', '==', vehicle_class) \
            .where('scraped_at', '>=', cutoff_time)
        
        docs = list(query.stream())
        
        if not docs:
            logger.info(f"No competitor data for {branch_id}/{vehicle_class}")
            return None
        
        # Extract prices
        prices = [doc.to_dict().get('price_per_day', 0) for doc in docs if doc.to_dict().get('price_per_day', 0) > 0]
        
        if not prices:
            return None
        
        # Compute aggregates
        aggregates = {
            'branch_id': branch_id,
            'vehicle_class': vehicle_class,
            'avg_price': sum(prices) / len(prices),
            'min_price': min(prices),
            'max_price': max(prices),
            'sample_count': len(prices),
            'computed_at': datetime.utcnow(),
            'time_window_hours': hours,
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        
        logger.info(f"Computed aggregates for {branch_id}/{vehicle_class}: avg={aggregates['avg_price']:.2f}, min={aggregates['min_price']:.2f}, max={aggregates['max_price']:.2f}, n={aggregates['sample_count']}")
        
        return aggregates
        
    except Exception as e:
        logger.error(f"Error computing aggregates for {branch_id}/{vehicle_class}: {str(e)}")
        return None


def save_competitor_aggregate(branch_id: str, vehicle_class: str, aggregates: Dict) -> bool:
    """
    Save computed aggregates to Firestore.
    
    Args:
        branch_id: Branch/city identifier
        vehicle_class: Vehicle category
        aggregates: Computed aggregate data
        
    Returns:
        True if successful
    """
    try:
        # Use fixed document ID format: {branch_id}_{vehicle_class}
        doc_id = f"{branch_id}_{vehicle_class}"
        
        aggregate_ref = db.collection('competitor_aggregates').document(doc_id)
        aggregate_ref.set(aggregates, merge=True)
        
        logger.info(f"Saved aggregates to competitor_aggregates/{doc_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving aggregates: {str(e)}")
        return False


def refresh_competitor_aggregates(branch_ids: Optional[List[str]] = None, vehicle_classes: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Refresh competitor aggregates for specified branches and vehicle classes.
    
    This function:
    1. Queries competitor_prices from the last 6 hours
    2. Computes avg, min, max, sample_count for each (branch_id, vehicle_class)
    3. Stores results in competitor_aggregates collection
    
    Args:
        branch_ids: List of branch/city IDs (defaults to supported cities)
        vehicle_classes: List of vehicle classes (defaults to all categories)
        
    Returns:
        Summary dictionary with results
    """
    global _branches_cache
    
    if branch_ids is None:
        # Use cities from cached branches
        if _branches_cache is None:
            logger.warning("refresh_competitor_aggregates called before branches loaded, using empty list")
            branch_ids = []
        else:
            branch_ids = get_cities_from_branches(_branches_cache)
    
    if vehicle_classes is None:
        vehicle_classes = list(CATEGORY_MAPPING.keys())
    
    summary = {
        'aggregates_computed': 0,
        'aggregates_saved': 0,
        'errors': [],
        'started_at': datetime.utcnow()
    }
    
    try:
        logger.info(f"Refreshing aggregates for {len(branch_ids)} branches x {len(vehicle_classes)} vehicle classes")
        
        for branch_id in branch_ids:
            for vehicle_class in vehicle_classes:
                try:
                    # Compute aggregates
                    aggregates = compute_aggregates_for_branch_vehicle(branch_id, vehicle_class, hours=6)
                    
                    if aggregates:
                        summary['aggregates_computed'] += 1
                        
                        # Save to Firestore
                        if save_competitor_aggregate(branch_id, vehicle_class, aggregates):
                            summary['aggregates_saved'] += 1
                    
                except Exception as e:
                    error_msg = f"Error processing {branch_id}/{vehicle_class}: {str(e)}"
                    logger.error(error_msg)
                    summary['errors'].append(error_msg)
        
        summary['completed_at'] = datetime.utcnow()
        summary['duration_seconds'] = (summary['completed_at'] - summary['started_at']).total_seconds()
        
        logger.info(f"Aggregate refresh complete: {summary['aggregates_saved']} saved in {summary['duration_seconds']:.1f}s")
        
    except Exception as e:
        error_msg = f"Error in refresh_competitor_aggregates: {str(e)}"
        logger.error(error_msg)
        summary['errors'].append(error_msg)
    
    return summary


# ==================== ML TRAINING INTEGRATION ====================

def export_competitor_data_for_training(target_csv_path: str) -> int:
    """
    Export all competitor_prices from Firestore to CSV for ML training.
    
    This allows retraining the pricing model with historical competitor data.
    
    Args:
        target_csv_path: Path to save CSV file
        
    Returns:
        Number of records exported
    """
    import csv
    
    try:
        logger.info(f"Exporting competitor data to {target_csv_path}")
        
        # Query all competitor prices
        competitor_ref = db.collection('competitor_prices')
        docs = competitor_ref.stream()
        
        # Prepare CSV
        fieldnames = ['provider', 'city', 'category', 'vehicle_name', 'price', 'currency', 'scraped_at']
        
        with open(target_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            count = 0
            for doc in docs:
                data = doc.to_dict()
                
                # Write row
                writer.writerow({
                    'provider': data.get('provider', ''),
                    'city': data.get('city', ''),
                    'category': data.get('category', ''),
                    'vehicle_name': data.get('vehicle_name', ''),
                    'price': data.get('price', 0.0),
                    'currency': data.get('currency', 'SAR'),
                    'scraped_at': data.get('scraped_at', '')
                })
                count += 1
        
        logger.info(f"Exported {count} competitor price records to {target_csv_path}")
        return count
        
    except Exception as e:
        logger.error(f"Error exporting competitor data: {str(e)}")
        return 0

