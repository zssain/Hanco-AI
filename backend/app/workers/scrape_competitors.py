"""
Competitor Scraping Worker
Scrapes competitor prices and stores in Firestore with deduplication
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict

from app.core.firebase import db
from app.core.monitoring import track_job, validate_environment, log_job_skipped
from app.services.competitors.crawler import (
    scrape_provider, 
    get_branches_cached, 
    get_cities_from_branches
)
from app.services.competitors import compute_aggregates_for_branch_vehicle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_scrape_grid_config(mode: str = 'FAST_GRID') -> Dict[str, List]:
    """
    Generate scrape grid configuration based on mode.
    
    Args:
        mode: Either 'FAST_GRID' or 'FULL_GRID'
        
    Returns:
        Dictionary with pickup_dates, durations, and pickup_times
    """
    tomorrow = datetime.now() + timedelta(days=1)
    
    if mode == 'FULL_GRID':
        # FULL_GRID: Comprehensive scraping (runs once daily)
        pickup_dates = [
            tomorrow,  # Tomorrow
            datetime.now() + timedelta(days=3),  # +3 days
            datetime.now() + timedelta(days=7),  # +7 days
            datetime.now() + timedelta(days=14),  # +14 days
            _get_next_friday()  # Next Friday
        ]
        durations = [1, 3, 7, 30]
        pickup_times = ['10:00', '18:00']
        
        logger.info(f"Using FULL_GRID mode: {len(pickup_dates)} dates x {len(durations)} durations x {len(pickup_times)} times = {len(pickup_dates) * len(durations) * len(pickup_times)} combinations per city")
    else:
        # FAST_GRID: Quick scraping (runs every 30-60 minutes)
        pickup_dates = [tomorrow]
        durations = [3, 7]
        pickup_times = ['10:00']
        
        logger.info(f"Using FAST_GRID mode: {len(pickup_dates)} dates x {len(durations)} durations x {len(pickup_times)} times = {len(pickup_dates) * len(durations) * len(pickup_times)} combinations per city")
    
    return {
        'pickup_dates': pickup_dates,
        'durations': durations,
        'pickup_times': pickup_times
    }


def _get_next_friday() -> datetime:
    """
    Calculate the date of the next Friday.
    
    Returns:
        datetime object representing next Friday
    """
    today = datetime.now()
    # 4 = Friday (0 = Monday, 6 = Sunday)
    days_until_friday = (4 - today.weekday()) % 7
    
    # If today is Friday, get next Friday
    if days_until_friday == 0:
        days_until_friday = 7
    
    return today + timedelta(days=days_until_friday)


async def scrape_all_competitors() -> Dict[str, int]:
    """
    Execute quote-grid scraping for all competitors using loaded branches.
    
    Returns:
        Dictionary with scraping statistics
    """
    # Get scrape mode from environment variable
    scrape_mode = os.getenv('COMPETITOR_SCRAPE_MODE', 'FAST_GRID').upper()
    
    if scrape_mode not in ['FAST_GRID', 'FULL_GRID']:
        logger.warning(f"Invalid COMPETITOR_SCRAPE_MODE='{scrape_mode}', defaulting to FAST_GRID")
        scrape_mode = 'FAST_GRID'
    
    logger.info("=" * 80)
    logger.info(f"Starting {scrape_mode} Competitor Scraping")
    logger.info("=" * 80)
    
    # Load branches from Firestore
    branches = await get_branches_cached(db)
    
    if not branches:
        logger.error("No branches loaded from Firestore, aborting scrape")
        return {
            'total_offers': 0,
            'total_new': 0,
            'providers_scraped': 0,
            'errors': ['No branches loaded from Firestore']
        }
    
    # Get cities from branches
    cities = get_cities_from_branches(branches)
    logger.info(f"Loaded {len(branches)} branches covering {len(cities)} cities: {', '.join(cities)}")
    
    # Get grid configuration based on mode
    grid_config = get_scrape_grid_config(scrape_mode)
    
    # Execute scraping for each city using grid configuration
    total_offers = 0
    total_new = 0
    providers_scraped = set()
    errors = []
    
    for city in cities:
        logger.info(f"\n{'='*60}")
        logger.info(f"Scraping {city.upper()}")
        logger.info(f"{'='*60}")
        
        # For now, we scrape providers without grid parameters
        # Grid parameters (pickup_dates, durations, times) will be used
        # when individual provider scrapers support them
        from app.services.competitors.crawler import get_supported_providers
        
        for provider in get_supported_providers():
            try:
                result = await scrape_provider(provider, city)
                
                if result['status'] == 'success':
                    total_offers += result.get('offers_found', 0)
                    total_new += result.get('new_offers', 0)
                    providers_scraped.add(provider)
                    logger.info(f"  ✅ {provider}: {result.get('offers_found', 0)} offers, {result.get('new_offers', 0)} new")
                elif result['status'] == 'disabled':
                    logger.warning(f"  ⚠️ {provider}: Disabled - {result.get('error', 'unknown')}")
                else:
                    error_msg = f"{provider}/{city}: {result.get('error', 'unknown')}"
                    errors.append(error_msg)
                    logger.error(f"  ❌ {provider}: {result.get('error', 'unknown')}")
                    
                # Small delay between providers
                await asyncio.sleep(1)
                
            except Exception as e:
                error_msg = f"{provider}/{city}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"  ❌ {provider}: {str(e)}")
    
    logger.info("\n" + "=" * 80)
    logger.info(f"{scrape_mode} scraping complete:")
    logger.info(f"  Mode: {scrape_mode}")
    logger.info(f"  Grid config: {len(grid_config['pickup_dates'])} dates x {len(grid_config['durations'])} durations x {len(grid_config['pickup_times'])} times")
    logger.info(f"  Cities scraped: {len(cities)}")
    logger.info(f"  Providers successful: {len(providers_scraped)}")
    logger.info(f"  Total offers: {total_offers} ({total_new} new)")
    if errors:
        logger.warning(f"  Errors: {len(errors)}")
    logger.info("=" * 80)
    
    return {
        'total_offers': total_offers,
        'total_new': total_new,
        'providers_scraped': len(providers_scraped),
        'errors': errors,
        'scrape_mode': scrape_mode,
        'grid_config': grid_config
    }


async def refresh_competitor_aggregates() -> Dict[str, int]:
    """
    Refresh competitor price aggregates for all branch/vehicle combinations
    
    Returns:
        Dictionary with refresh statistics
    """
    logger.info("=" * 80)
    logger.info("Refreshing Competitor Aggregates")
    logger.info("=" * 80)
    
    # Load branches from Firestore to get current branch/vehicle combinations
    branches = await get_branches_cached(db)
    
    if not branches:
        logger.error("No branches loaded from Firestore, skipping aggregate refresh")
        return {
            'combinations_found': 0,
            'aggregates_updated': 0,
            'errors': ['No branches loaded from Firestore']
        }
    
    # Get unique cities from branches
    cities = get_cities_from_branches(branches)
    logger.info(f"Found {len(cities)} cities from {len(branches)} branches")
    
    # Get all unique branch/vehicle combinations from recent competitor data
    cutoff = datetime.utcnow()
    competitor_docs = db.collection('competitor_prices').where('scraped_at', '>=', cutoff).stream()
    
    # Collect unique combinations
    combinations = set()
    for doc in competitor_docs:
        data = doc.to_dict()
        branch_id = data.get('branch_id')
        vehicle_class = data.get('vehicle_class')
        
        if branch_id and vehicle_class:
            combinations.add((branch_id, vehicle_class))
    
    logger.info(f"Found {len(combinations)} branch/vehicle combinations to refresh")
    
    aggregated = 0
    errors = []
    
    for branch_id, vehicle_class in combinations:
        try:
            result = await compute_aggregates_for_branch_vehicle(branch_id, vehicle_class)
            
            if result:
                aggregated += 1
                logger.info(f"  ✅ {branch_id}/{vehicle_class}: avg={result.get('avg_price_6h'):.2f}")
            else:
                logger.warning(f"  ⚠️ {branch_id}/{vehicle_class}: no data")
                
        except Exception as e:
            error_msg = f"{branch_id}/{vehicle_class}: {str(e)}"
            errors.append(error_msg)
            logger.error(f"  ❌ {error_msg}")
    
    logger.info("=" * 80)
    logger.info(f"Aggregation complete: {aggregated} updated")
    if errors:
        logger.warning(f"Errors encountered: {len(errors)}")
    logger.info("=" * 80)
    
    return {
        'combinations_found': len(combinations),
        'aggregates_updated': aggregated,
        'errors': errors
    }


async def scrape_airport_quotes() -> Dict[str, any]:
    """
    Execute 1-day airport quote scraping for all providers.
    
    Returns:
        Dictionary with scraping statistics
    """
    logger.info("=" * 80)
    logger.info("Starting 1-Day Airport Quote Scraping")
    logger.info("=" * 80)
    
    # Import here to avoid circular dependency
    from app.services.competitors import scrape_airport_quotes_1day
    
    # Execute airport quote scraping
    result = await scrape_airport_quotes_1day()
    
    logger.info("=" * 80)
    logger.info(f"Airport quote scraping complete:")
    logger.info(f"  Total vehicles: {result.get('total_vehicles', 0)}")
    logger.info(f"  Total saved: {result.get('total_saved', 0)}")
    logger.info(f"  Total skipped: {result.get('total_skipped', 0)}")
    logger.info(f"  Duration: {result.get('duration_seconds', 0):.1f}s")
    if result.get('errors'):
        logger.warning(f"  Errors: {len(result.get('errors', []))}")
    logger.info("=" * 80)
    
    return result



async def run_competitor_scraping_job():
    """
    Main job function that orchestrates scraping and aggregation
    """
    logger.info(f"Competitor scraping job started at {datetime.utcnow().isoformat()}")
    
    # Check for airport quote mode
    scrape_mode = os.getenv('COMPETITOR_SCRAPE_MODE', 'FAST_GRID').upper()
    
    if scrape_mode == 'AIRPORT_QUOTE':
        logger.info("Running in AIRPORT_QUOTE mode")
        counts = {'inserted': 0, 'updated': 0, 'deleted': 0}
        
        with track_job('scrape_airport_quotes', counts):
            airport_result = await scrape_airport_quotes()
            counts['inserted'] = airport_result.get('total_saved', 0)
            
            return {
                'status': 'success',
                'airport_result': airport_result
            }
    
    # Default: Regular competitor scraping
    counts = {'inserted': 0, 'updated': 0, 'deleted': 0}
    
    with track_job('scrape_competitors', counts):
        # Step 0: Load branches from Firestore
        logger.info("Loading branches from Firestore...")
        branches = await get_branches_cached(db)
        
        if not branches:
            logger.error("Failed to load branches from Firestore, aborting job")
            return {
                'status': 'error',
                'error': 'Failed to load branches from Firestore',
                'scrape_result': {'total_offers': 0, 'total_new': 0, 'errors': ['No branches']},
                'aggregate_result': {'aggregates_updated': 0, 'errors': ['No branches']}
            }
        
        cities = get_cities_from_branches(branches)
        logger.info(f"Loaded {len(branches)} branches covering {len(cities)} cities: {', '.join(cities)}")
        
        # Step 1: Scrape competitors
        scrape_result = await scrape_all_competitors()
        counts['inserted'] = scrape_result['total_new']
        
        # Step 2: Refresh aggregates
        aggregate_result = await refresh_competitor_aggregates()
        counts['updated'] = aggregate_result['aggregates_updated']
        
        # Summary
        logger.info("=" * 80)
        logger.info("Job Summary")
        logger.info("=" * 80)
        logger.info(f"Scrape mode: {scrape_result.get('scrape_mode', 'FAST_GRID')}")
        logger.info(f"Offers scraped: {scrape_result['total_offers']} ({scrape_result['total_new']} new)")
        logger.info(f"Aggregates updated: {aggregate_result['aggregates_updated']}")
        logger.info(f"Total errors: {len(scrape_result['errors']) + len(aggregate_result['errors'])}")
        logger.info("=" * 80)
        
        return {
            'status': 'success',
            'scrape_result': scrape_result,
            'aggregate_result': aggregate_result
        }


def main():
    """
    Run competitor scraping worker
    
    Usage:
        python3 -m app.workers.scrape_competitors
    
    Environment Variables:
        GOOGLE_APPLICATION_CREDENTIALS: Path to Firebase service account JSON (required)
        COMPETITOR_SCRAPE_MODE: Scrape mode (default: FAST_GRID)
            - FAST_GRID: Runs every 30-60 min, pickup=tomorrow, durations=[3,7], time=10:00
            - FULL_GRID: Runs daily, pickup=[tomorrow,+3d,+7d,+14d,nextFri], durations=[1,3,7,30], times=[10:00,18:00]
            - AIRPORT_QUOTE: 1-day airport quote scraping (pickup=tomorrow 10:00, duration=1 day, all airports)
    
    Example:
        export GOOGLE_APPLICATION_CREDENTIALS=/path/to/firebase-key.json
        export COMPETITOR_SCRAPE_MODE=AIRPORT_QUOTE
        python3 -m app.workers.scrape_competitors
    """
    import sys
    import os
    import time
    import tempfile
    from pathlib import Path
    
    # Validate environment
    validate_environment()
    
    # Lock file configuration (cross-platform temp directory)
    temp_dir = Path(tempfile.gettempdir())
    LOCK_FILE = temp_dir / 'hanco_scrape.lock'
    MAX_LOCK_AGE_SECONDS = 2 * 60 * 60  # 2 hours
    
    # Check for existing lock
    if LOCK_FILE.exists():
        try:
            lock_age = time.time() - LOCK_FILE.stat().st_mtime
            
            if lock_age < MAX_LOCK_AGE_SECONDS:
                logger.info(f"Lock file exists and is recent ({lock_age/60:.1f} minutes old)")
                logger.info("Another scraping job may be running. Skipping this run.")
                log_job_skipped('scrape_competitors', reason=f"Lock exists ({lock_age/60:.1f} min old)")
                sys.exit(0)  # Graceful skip
            else:
                logger.warning(f"Lock file is stale ({lock_age/3600:.1f} hours old). Overwriting.")
                LOCK_FILE.unlink()
        except Exception as e:
            logger.warning(f"Error checking lock file: {e}. Removing it.")
            LOCK_FILE.unlink()
    
    # Create lock file
    try:
        LOCK_FILE.write_text(str(os.getpid()))
        logger.info(f"Lock acquired: {LOCK_FILE}")
    except Exception as e:
        logger.error(f"Failed to create lock file: {e}")
        sys.exit(1)
    
    try:
        result = asyncio.run(run_competitor_scraping_job())
        
        if result['status'] == 'success':
            logger.info("✅ Competitor scraping job completed successfully")
            exit_code = 0
        else:
            logger.error("❌ Competitor scraping job failed")
            exit_code = 1
            
    except KeyboardInterrupt:
        logger.info("Job interrupted by user")
        exit_code = 130
    except Exception as e:
        logger.error(f"Job failed with error: {str(e)}")
        exit_code = 1
    finally:
        # Always remove lock file
        try:
            if LOCK_FILE.exists():
                LOCK_FILE.unlink()
                logger.info(f"Lock released: {LOCK_FILE}")
        except Exception as e:
            logger.error(f"Failed to remove lock file: {e}")
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
