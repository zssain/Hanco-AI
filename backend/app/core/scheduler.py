"""
Background Scheduler for Hanco AI
Handles scheduled tasks: competitor scraping, pricing updates, model training
"""
import asyncio
import hashlib
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import pytz

from app.core.config import settings
from app.core.firebase import db, Collections, update_vehicle_base_rate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: Optional[AsyncIOScheduler] = None

# Timezone for Saudi Arabia
SCHEDULER_TIMEZONE = pytz.timezone('Asia/Riyadh')

# Lock TTL in minutes (how long to hold the lock)
SCHEDULER_LOCK_TTL_MINUTES = 30


async def acquire_scheduler_lock(job_name: str, ttl_minutes: int = SCHEDULER_LOCK_TTL_MINUTES) -> bool:
    """
    Acquire distributed lock to prevent duplicate job runs across multiple workers.
    
    Uses Firestore document as lock mechanism.
    
    Args:
        job_name: Name of the job to lock
        ttl_minutes: How long the lock should be held
        
    Returns:
        True if lock acquired, False if another worker holds it
    """
    try:
        lock_ref = db.collection('scheduler_locks').document(job_name)
        now = datetime.utcnow()
        worker_id = f"{os.getpid()}_{hashlib.md5(str(now.timestamp()).encode()).hexdigest()[:8]}"
        
        # Use Firestore transaction for atomic read-write
        @db.transaction
        def try_acquire_lock(transaction):
            doc = lock_ref.get(transaction=transaction)
            
            if doc.exists:
                lock_data = doc.to_dict()
                expires_at = lock_data.get('expires_at')
                
                # Check if lock is still valid
                if expires_at:
                    # Handle timezone-aware datetime
                    if hasattr(expires_at, 'tzinfo') and expires_at.tzinfo:
                        expires_at = expires_at.replace(tzinfo=None)
                    if expires_at > now:
                        logger.info(f"🔒 Lock held by worker {lock_data.get('worker_id')}, expires at {expires_at}")
                        return False
            
            # Acquire the lock
            transaction.set(lock_ref, {
                'acquired_at': now,
                'expires_at': now + timedelta(minutes=ttl_minutes),
                'worker_id': worker_id,
                'job_name': job_name
            })
            return True
        
        result = try_acquire_lock()
        if result:
            logger.info(f"🔓 Lock acquired for job '{job_name}' by worker {worker_id}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to acquire lock: {e}")
        # On error, allow job to proceed (fail-open)
        return True


async def release_scheduler_lock(job_name: str):
    """Release the scheduler lock after job completion."""
    try:
        lock_ref = db.collection('scheduler_locks').document(job_name)
        lock_ref.delete()
        logger.info(f"🔓 Lock released for job '{job_name}'")
    except Exception as e:
        logger.warning(f"Failed to release lock: {e}")


async def scrape_and_update_prices() -> Dict[str, Any]:
    """
    Main scheduled job (Full Grid) that:
    1. Acquires distributed lock to prevent duplicate runs
    2. Scrapes all competitor prices (all cities × durations × categories)
    3. Validates vehicle prices and flags anomalies (but does NOT auto-adjust)
    
    PROFIT-FIRST STRATEGY:
    - Competitor data is used for guardrails + analytics, NOT as a pricing target
    - We do NOT chase competitors (removed: target_price = avg * 0.95)
    - Base rates stay stable until manually adjusted
    
    Returns:
        Dictionary with job results
    """
    job_name = 'scrape_and_update_prices'
    
    # Try to acquire lock (prevents duplicate runs across workers)
    if not await acquire_scheduler_lock(job_name):
        logger.info("⏭️ Skipping job - another worker is running it")
        return {'status': 'skipped', 'reason': 'lock_held_by_another_worker'}
    
    job_start = datetime.utcnow()
    logger.info("=" * 80)
    logger.info(f"🕐 Scheduled Job Started: {job_start.isoformat()}Z")
    logger.info("=" * 80)
    
    results = {
        'started_at': job_start.isoformat() + 'Z',
        'scrape_result': None,
        'pricing_updates': None,
        'errors': []
    }
    
    try:
        # Step 1: Run competitor scraping
        logger.info("\n📡 Step 1: Scraping competitor prices...")
        from app.workers.scrape_competitors import run_competitor_scraping_job
        
        scrape_result = await run_competitor_scraping_job()
        results['scrape_result'] = scrape_result
        
        if scrape_result.get('status') == 'success':
            total_offers = scrape_result.get('scrape_result', {}).get('total_offers', 0)
            new_offers = scrape_result.get('scrape_result', {}).get('total_new', 0)
            logger.info(f"   ✅ Scraping complete: {total_offers} offers ({new_offers} new)")
        else:
            error = scrape_result.get('error', 'Unknown scraping error')
            results['errors'].append(f"Scraping failed: {error}")
            logger.error(f"   ❌ Scraping failed: {error}")
        
        # Step 2: Validate vehicle prices (does NOT auto-update, just checks for anomalies)
        logger.info("\n🔍 Step 2: Validating vehicle prices against market data...")
        pricing_result = await update_vehicle_prices_from_competitors()
        results['pricing_updates'] = pricing_result
        
        if pricing_result.get('anomalies_detected', 0) > 0:
            logger.info(f"   ⚠️ Found {pricing_result['anomalies_detected']} pricing anomalies to review")
        else:
            logger.info(f"   ✅ All vehicles within expected market range")
        
    except Exception as e:
        error_msg = f"Scheduled job error: {str(e)}"
        results['errors'].append(error_msg)
        logger.error(f"❌ {error_msg}")
    
    finally:
        # Always release the lock when done
        await release_scheduler_lock(job_name)
    
    # Job summary
    job_end = datetime.utcnow()
    duration = (job_end - job_start).total_seconds()
    results['completed_at'] = job_end.isoformat() + 'Z'
    results['duration_seconds'] = duration
    
    logger.info("\n" + "=" * 80)
    logger.info(f"✅ Scheduled Job Complete: {duration:.1f}s")
    logger.info("=" * 80)
    
    # Log to Firestore for audit (using UTC timestamps)
    try:
        db.collection('scheduled_job_logs').add({
            'job_type': 'scrape_and_update_prices',
            'started_at': job_start,  # UTC
            'completed_at': job_end,  # UTC
            'duration_seconds': duration,
            'scrape_offers': results.get('scrape_result', {}).get('scrape_result', {}).get('total_offers', 0),
            'prices_updated': results.get('pricing_updates', {}).get('updated', 0),
            'errors': results['errors'],
            'status': 'success' if not results['errors'] else 'partial'
        })
    except Exception as e:
        logger.warning(f"Failed to log job to Firestore: {e}")
    
    return results


async def update_vehicle_prices_from_competitors() -> Dict[str, Any]:
    """
    Validate vehicle base prices against competitor data.
    
    PROFIT-FIRST STRATEGY (no competitor-chasing):
    - We do NOT adjust base_daily_rate to match competitors
    - Base rates are set by management based on cost, positioning, demand
    - Competitors are ONLY used for guardrails during real-time pricing
    - This job now just validates data and logs anomalies
    
    Previous behavior (REMOVED):
    - target_price = avg_competitor * 0.95 (chased market)
    - Auto-adjusted vehicle prices to undercut competitors
    
    New behavior:
    - Logs competitor aggregates for monitoring
    - Flags vehicles with potential pricing issues (too high/low vs market)
    - Does NOT auto-update prices
    
    Returns:
        Dictionary with validation statistics
    """
    from app.services.competitors import get_competitor_price_aggregates
    
    result = {
        'vehicles_checked': 0,
        'anomalies_detected': 0,
        'skipped': 0,
        'errors': [],
        'anomalies': []  # List of vehicles with pricing concerns
    }
    
    # Thresholds for anomaly detection (for monitoring, not auto-correction)
    FLOOR_RATIO = 0.50  # Flag if our price is <50% of market avg (too cheap?)
    CEILING_RATIO = 2.00  # Flag if our price is >200% of market avg (too expensive?)
    
    try:
        # Get all vehicles
        vehicles_ref = db.collection(Collections.VEHICLES)
        vehicles = vehicles_ref.stream()
        
        # Get latest competitor aggregates by category
        competitor_aggregates = await get_competitor_price_aggregates()
        
        logger.info(f"   📊 Competitor aggregates (for monitoring): {competitor_aggregates}")
        
        for vehicle_doc in vehicles:
            result['vehicles_checked'] += 1
            vehicle_id = vehicle_doc.id
            vehicle_data = vehicle_doc.to_dict()
            
            try:
                vehicle_category = vehicle_data.get('category', 'sedan').lower()
                current_rate = vehicle_data.get('base_daily_rate', 0)
                cost_per_day = vehicle_data.get('cost_per_day', 0)
                vehicle_name = vehicle_data.get('name', 'Unknown')
                
                # Skip if no current rate
                if not current_rate or current_rate <= 0:
                    result['skipped'] += 1
                    continue
                
                # Get competitor average for this category
                category_data = competitor_aggregates.get(vehicle_category, {})
                avg_competitor_price = category_data.get('avg_price', 0)
                
                if not avg_competitor_price or avg_competitor_price <= 0:
                    # No competitor data, skip validation
                    result['skipped'] += 1
                    continue
                
                # Calculate ratio of our price to market
                price_ratio = current_rate / avg_competitor_price
                
                # Check for anomalies (flag but don't auto-correct)
                if price_ratio < FLOOR_RATIO:
                    anomaly = {
                        'vehicle_id': vehicle_id,
                        'vehicle_name': vehicle_name,
                        'current_rate': current_rate,
                        'market_avg': avg_competitor_price,
                        'ratio': round(price_ratio, 2),
                        'issue': 'potentially_underpriced',
                        'suggestion': f'Consider raising to ~{round(avg_competitor_price * 0.9, 2)} SAR'
                    }
                    result['anomalies'].append(anomaly)
                    result['anomalies_detected'] += 1
                    logger.warning(f"   ⚠️ UNDERPRICED: {vehicle_name} at {current_rate} SAR vs market avg {avg_competitor_price} SAR")
                    
                elif price_ratio > CEILING_RATIO:
                    anomaly = {
                        'vehicle_id': vehicle_id,
                        'vehicle_name': vehicle_name,
                        'current_rate': current_rate,
                        'market_avg': avg_competitor_price,
                        'ratio': round(price_ratio, 2),
                        'issue': 'potentially_overpriced',
                        'suggestion': f'Consider reviewing pricing strategy'
                    }
                    result['anomalies'].append(anomaly)
                    result['anomalies_detected'] += 1
                    logger.warning(f"   ⚠️ OVERPRICED: {vehicle_name} at {current_rate} SAR vs market avg {avg_competitor_price} SAR")
                else:
                    # Price is within reasonable range - no action needed
                    logger.debug(f"   ✓ {vehicle_name}: {current_rate} SAR (market avg: {avg_competitor_price}, ratio: {price_ratio:.2f})")
                    
            except Exception as e:
                error_msg = f"Error validating {vehicle_id}: {str(e)}"
                result['errors'].append(error_msg)
                logger.warning(f"   ⚠️ {error_msg}")
        
        # Log summary
        if result['anomalies_detected'] > 0:
            logger.info(f"   📋 Found {result['anomalies_detected']} pricing anomalies to review")
        else:
            logger.info(f"   ✅ All {result['vehicles_checked']} vehicles within expected market range")
                
    except Exception as e:
        error_msg = f"Failed to validate prices: {str(e)}"
        result['errors'].append(error_msg)
        logger.error(f"   ❌ {error_msg}")
    
    # Note: We removed 'updated' from result since we no longer auto-update
    result['updated'] = 0  # Kept for API compatibility
    
    return result


async def get_competitor_price_aggregates() -> Dict[str, Dict[str, float]]:
    """
    Get average competitor prices by vehicle category.
    
    Returns:
        Dict mapping category to {avg_price, min_price, max_price, count}
    """
    from datetime import datetime, timedelta
    
    aggregates = {}
    
    try:
        # Get prices from last 24 hours
        cutoff = datetime.utcnow() - timedelta(hours=24)
        
        prices_ref = db.collection('competitor_prices_latest')
        prices_docs = prices_ref.stream()
        
        # Group by category
        category_prices = {}
        
        for doc in prices_docs:
            data = doc.to_dict()
            category = data.get('vehicle_class', 'sedan').lower()
            price = data.get('price_per_day', 0)
            
            if price and price > 0:
                if category not in category_prices:
                    category_prices[category] = []
                category_prices[category].append(price)
        
        # Calculate aggregates
        for category, prices in category_prices.items():
            if prices:
                aggregates[category] = {
                    'avg_price': round(sum(prices) / len(prices), 2),
                    'min_price': min(prices),
                    'max_price': max(prices),
                    'count': len(prices)
                }
                
        logger.info(f"   Aggregates calculated for {len(aggregates)} categories")
        
    except Exception as e:
        logger.error(f"Error calculating aggregates: {e}")
    
    return aggregates


async def lite_refresh_prices() -> Dict[str, Any]:
    """
    Lite Refresh job - runs every 6 hours to keep key market data fresh.
    
    Focuses on high-priority combinations only:
    - Branches: airports (highest margin locations)
    - Durations: D1, D3, D7 (most common rentals)
    - Categories: economy, sedan, suv (main segments)
    
    This keeps guardrail percentiles fresh without the heavy load of full scraping.
    
    Returns:
        Dictionary with job results
    """
    job_name = 'lite_refresh_prices'
    
    # Try to acquire lock (prevents duplicate runs across workers)
    if not await acquire_scheduler_lock(job_name, ttl_minutes=15):  # Shorter TTL for lite job
        logger.info("⏭️ Skipping lite refresh - another worker is running it")
        return {'status': 'skipped', 'reason': 'lock_held_by_another_worker'}
    
    job_start = datetime.utcnow()
    logger.info("=" * 60)
    logger.info(f"⚡ Lite Refresh Started: {job_start.isoformat()}Z")
    logger.info("=" * 60)
    
    # Key combinations to refresh (high priority only)
    LITE_BRANCHES = ['riyadh_airport', 'jeddah_airport', 'dammam_airport']
    LITE_DURATIONS = ['D1', 'D3', 'D7']
    LITE_CATEGORIES = ['economy', 'sedan', 'suv']
    
    results = {
        'started_at': job_start.isoformat() + 'Z',
        'mode': 'lite',
        'branches_checked': LITE_BRANCHES,
        'durations_checked': LITE_DURATIONS,
        'categories_checked': LITE_CATEGORIES,
        'scrape_result': None,
        'errors': []
    }
    
    try:
        # Run competitor scraping in lite mode
        logger.info("📡 Scraping key competitors (lite mode)...")
        from app.workers.scrape_competitors import run_competitor_scraping_job
        
        # Pass lite mode parameters
        scrape_result = await run_competitor_scraping_job(
            branches=LITE_BRANCHES,
            durations=LITE_DURATIONS,
            categories=LITE_CATEGORIES,
            mode='lite'
        )
        results['scrape_result'] = scrape_result
        
        if scrape_result.get('status') == 'success':
            total_offers = scrape_result.get('scrape_result', {}).get('total_offers', 0)
            logger.info(f"   ✅ Lite refresh complete: {total_offers} key offers refreshed")
        else:
            error = scrape_result.get('error', 'Unknown error')
            results['errors'].append(f"Lite refresh failed: {error}")
            logger.error(f"   ❌ Lite refresh failed: {error}")
            
    except TypeError as te:
        # Fallback if run_competitor_scraping_job doesn't support lite params yet
        logger.warning(f"   ⚠️ Lite mode not supported, running standard refresh: {te}")
        try:
            from app.workers.scrape_competitors import run_competitor_scraping_job
            scrape_result = await run_competitor_scraping_job()
            results['scrape_result'] = scrape_result
            results['mode'] = 'full_fallback'
        except Exception as e2:
            results['errors'].append(f"Fallback refresh failed: {str(e2)}")
            
    except Exception as e:
        error_msg = f"Lite refresh error: {str(e)}"
        results['errors'].append(error_msg)
        logger.error(f"❌ {error_msg}")
    
    finally:
        await release_scheduler_lock(job_name)
    
    # Job summary
    job_end = datetime.utcnow()
    duration = (job_end - job_start).total_seconds()
    results['completed_at'] = job_end.isoformat() + 'Z'
    results['duration_seconds'] = duration
    
    logger.info("=" * 60)
    logger.info(f"⚡ Lite Refresh Complete: {duration:.1f}s")
    logger.info("=" * 60)
    
    # Log to Firestore
    try:
        db.collection('scheduled_job_logs').add({
            'job_type': 'lite_refresh_prices',
            'started_at': job_start,
            'completed_at': job_end,
            'duration_seconds': duration,
            'mode': results['mode'],
            'scrape_offers': results.get('scrape_result', {}).get('scrape_result', {}).get('total_offers', 0),
            'errors': results['errors'],
            'status': 'success' if not results['errors'] else 'partial'
        })
    except Exception as e:
        logger.warning(f"Failed to log lite refresh to Firestore: {e}")
    
    return results


def init_scheduler() -> AsyncIOScheduler:
    """
    Initialize and configure the background scheduler.
    
    Uses Asia/Riyadh timezone for Saudi Arabia.
    Implements distributed locking to prevent duplicate runs across workers.
    
    Returns:
        Configured AsyncIOScheduler instance
    """
    global scheduler
    
    if scheduler is not None:
        logger.info("Scheduler already initialized")
        return scheduler
    
    # Initialize with explicit timezone for Saudi Arabia
    scheduler = AsyncIOScheduler(timezone=SCHEDULER_TIMEZONE)
    
    # Get schedule configuration from environment
    scrape_interval_hours = int(os.getenv('SCRAPE_INTERVAL_HOURS', '24'))
    scrape_hour = int(os.getenv('SCRAPE_HOUR', '3'))  # Default: 3 AM Riyadh time
    scrape_minute = int(os.getenv('SCRAPE_MINUTE', '0'))
    
    # Lite refresh configuration (optional, every 6 hours by default)
    lite_refresh_enabled = os.getenv('LITE_REFRESH_ENABLED', 'true').lower() == 'true'
    lite_refresh_interval_hours = int(os.getenv('LITE_REFRESH_INTERVAL_HOURS', '6'))
    
    # Schedule the main job (Full Grid - daily at 3 AM)
    if scrape_interval_hours == 24:
        # Run daily at specific time (default 3 AM Riyadh time)
        scheduler.add_job(
            scrape_and_update_prices,
            CronTrigger(hour=scrape_hour, minute=scrape_minute, timezone=SCHEDULER_TIMEZONE),
            id='scrape_and_update_prices',
            name='Daily Full Grid Scraping & Validation',
            replace_existing=True
        )
        logger.info(f"📅 Scheduled FULL scraping at {scrape_hour:02d}:{scrape_minute:02d} ({SCHEDULER_TIMEZONE})")
    else:
        # Run at interval
        scheduler.add_job(
            scrape_and_update_prices,
            IntervalTrigger(hours=scrape_interval_hours),
            id='scrape_and_update_prices',
            name=f'Full Grid Scraping (every {scrape_interval_hours}h)',
            replace_existing=True
        )
        logger.info(f"📅 Scheduled FULL scraping every {scrape_interval_hours} hours")
    
    # Schedule Lite Refresh job (keeps guardrail percentiles fresh)
    if lite_refresh_enabled:
        scheduler.add_job(
            lite_refresh_prices,
            IntervalTrigger(hours=lite_refresh_interval_hours),
            id='lite_refresh_prices',
            name=f'Lite Refresh (every {lite_refresh_interval_hours}h)',
            replace_existing=True
        )
        logger.info(f"⚡ Scheduled LITE refresh every {lite_refresh_interval_hours} hours")
    else:
        logger.info("⚡ Lite refresh DISABLED (set LITE_REFRESH_ENABLED=true to enable)")
    
    return scheduler


def start_scheduler():
    """Start the scheduler if not already running."""
    global scheduler
    
    if scheduler is None:
        scheduler = init_scheduler()
    
    if not scheduler.running:
        scheduler.start()
        logger.info("🚀 Background scheduler started")
        
        # Log next run time
        jobs = scheduler.get_jobs()
        for job in jobs:
            next_run = job.next_run_time
            if next_run:
                logger.info(f"   Next '{job.name}': {next_run.isoformat()}")
    else:
        logger.info("Scheduler already running")


def stop_scheduler():
    """Stop the scheduler gracefully."""
    global scheduler
    
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("🛑 Background scheduler stopped")


async def trigger_scrape_now() -> Dict[str, Any]:
    """
    Manually trigger a scrape and price update.
    Used by admin endpoints for on-demand scraping.
    
    Returns:
        Job results
    """
    logger.info("🔧 Manual scrape triggered")
    return await scrape_and_update_prices()


def get_scheduler_status() -> Dict[str, Any]:
    """
    Get current scheduler status and job info.
    
    Returns:
        Dictionary with scheduler status including timezone info
    """
    global scheduler
    
    if scheduler is None:
        return {'status': 'not_initialized', 'timezone': str(SCHEDULER_TIMEZONE), 'jobs': []}
    
    jobs_info = []
    for job in scheduler.get_jobs():
        next_run = job.next_run_time
        next_run_utc = None
        next_run_local = None
        
        if next_run:
            # Convert to UTC for consistent API response
            next_run_utc = next_run.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
            next_run_local = next_run.strftime('%Y-%m-%dT%H:%M:%S%z')
        
        jobs_info.append({
            'id': job.id,
            'name': job.name,
            'next_run_utc': next_run_utc,
            'next_run_local': next_run_local,
            'trigger': str(job.trigger)
        })
    
    return {
        'status': 'running' if scheduler.running else 'stopped',
        'timezone': str(SCHEDULER_TIMEZONE),
        'jobs': jobs_info
    }
