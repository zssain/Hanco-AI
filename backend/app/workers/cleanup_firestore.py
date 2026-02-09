"""
Firestore Data Cleanup Worker
Removes old documents to maintain data retention policies
"""
import logging
from datetime import datetime, timedelta
from typing import Dict
import sys

from app.core.firebase import db, Collections
from app.core.monitoring import track_job, validate_environment, log_job_skipped

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def delete_old_competitor_prices(days: int = 14, dry_run: bool = False) -> Dict:
    """
    Delete competitor_prices documents older than specified days
    
    Args:
        days: Delete documents older than this many days (default: 14)
        dry_run: If True, only count documents without deleting
        
    Returns:
        Dictionary with deletion statistics
    """
    logger.info(f"{'[DRY RUN] ' if dry_run else ''}Cleaning competitor_prices older than {days} days...")
    
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Query old documents
        competitor_ref = db.collection(Collections.COMPETITORS)
        old_docs_query = competitor_ref.where('scraped_at', '<', cutoff_date)
        old_docs = list(old_docs_query.stream())
        
        count = len(old_docs)
        
        if count == 0:
            logger.info(f"  No documents to delete (all are newer than {days} days)")
            return {
                'collection': 'competitor_prices',
                'cutoff_date': cutoff_date.isoformat(),
                'documents_deleted': 0,
                'dry_run': dry_run
            }
        
        if dry_run:
            logger.info(f"  [DRY RUN] Would delete {count} competitor_prices documents")
        else:
            # Delete in batches of 500 (Firestore limit)
            batch = db.batch()
            deleted = 0
            
            for doc in old_docs:
                batch.delete(doc.reference)
                deleted += 1
                
                # Commit every 500 docs
                if deleted % 500 == 0:
                    batch.commit()
                    batch = db.batch()
                    logger.info(f"  Deleted {deleted}/{count} documents...")
            
            # Commit remaining
            if deleted % 500 != 0:
                batch.commit()
            
            logger.info(f"  ✅ Deleted {deleted} competitor_prices documents")
        
        return {
            'collection': 'competitor_prices',
            'cutoff_date': cutoff_date.isoformat(),
            'documents_deleted': count if not dry_run else 0,
            'documents_found': count,
            'dry_run': dry_run
        }
        
    except Exception as e:
        logger.error(f"  ❌ Error cleaning competitor_prices: {str(e)}")
        return {
            'collection': 'competitor_prices',
            'error': str(e),
            'documents_deleted': 0,
            'dry_run': dry_run
        }


def delete_old_price_quotes(days: int = 180, dry_run: bool = False) -> Dict:
    """
    Delete price_quotes documents older than specified days
    
    Args:
        days: Delete documents older than this many days (default: 180)
        dry_run: If True, only count documents without deleting
        
    Returns:
        Dictionary with deletion statistics
    """
    logger.info(f"{'[DRY RUN] ' if dry_run else ''}Cleaning price_quotes older than {days} days...")
    
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Query old documents
        quotes_ref = db.collection(Collections.PRICE_QUOTES)
        old_docs_query = quotes_ref.where('created_at', '<', cutoff_date)
        old_docs = list(old_docs_query.stream())
        
        count = len(old_docs)
        
        if count == 0:
            logger.info(f"  No documents to delete (all are newer than {days} days)")
            return {
                'collection': 'price_quotes',
                'cutoff_date': cutoff_date.isoformat(),
                'documents_deleted': 0,
                'dry_run': dry_run
            }
        
        if dry_run:
            logger.info(f"  [DRY RUN] Would delete {count} price_quotes documents")
        else:
            # Delete in batches of 500 (Firestore limit)
            batch = db.batch()
            deleted = 0
            
            for doc in old_docs:
                batch.delete(doc.reference)
                deleted += 1
                
                # Commit every 500 docs
                if deleted % 500 == 0:
                    batch.commit()
                    batch = db.batch()
                    logger.info(f"  Deleted {deleted}/{count} documents...")
            
            # Commit remaining
            if deleted % 500 != 0:
                batch.commit()
            
            logger.info(f"  ✅ Deleted {deleted} price_quotes documents")
        
        return {
            'collection': 'price_quotes',
            'cutoff_date': cutoff_date.isoformat(),
            'documents_deleted': count if not dry_run else 0,
            'documents_found': count,
            'dry_run': dry_run
        }
        
    except Exception as e:
        logger.error(f"  ❌ Error cleaning price_quotes: {str(e)}")
        return {
            'collection': 'price_quotes',
            'error': str(e),
            'documents_deleted': 0,
            'dry_run': dry_run
        }


def delete_old_pricing_history(days: int = 180, dry_run: bool = False) -> Dict:
    """
    Delete pricing_history documents older than specified days
    
    Args:
        days: Delete documents older than this many days (default: 180)
        dry_run: If True, only count documents without deleting
        
    Returns:
        Dictionary with deletion statistics
    """
    logger.info(f"{'[DRY RUN] ' if dry_run else ''}Cleaning pricing_history older than {days} days...")
    
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Query old documents
        history_ref = db.collection(Collections.PRICING_HISTORY)
        old_docs_query = history_ref.where('timestamp', '<', cutoff_date)
        old_docs = list(old_docs_query.stream())
        
        count = len(old_docs)
        
        if count == 0:
            logger.info(f"  No documents to delete (all are newer than {days} days)")
            return {
                'collection': 'pricing_history',
                'cutoff_date': cutoff_date.isoformat(),
                'documents_deleted': 0,
                'dry_run': dry_run
            }
        
        if dry_run:
            logger.info(f"  [DRY RUN] Would delete {count} pricing_history documents")
        else:
            # Delete in batches of 500 (Firestore limit)
            batch = db.batch()
            deleted = 0
            
            for doc in old_docs:
                batch.delete(doc.reference)
                deleted += 1
                
                # Commit every 500 docs
                if deleted % 500 == 0:
                    batch.commit()
                    batch = db.batch()
                    logger.info(f"  Deleted {deleted}/{count} documents...")
            
            # Commit remaining
            if deleted % 500 != 0:
                batch.commit()
            
            logger.info(f"  ✅ Deleted {deleted} pricing_history documents")
        
        return {
            'collection': 'pricing_history',
            'cutoff_date': cutoff_date.isoformat(),
            'documents_deleted': count if not dry_run else 0,
            'documents_found': count,
            'dry_run': dry_run
        }
        
    except Exception as e:
        logger.error(f"  ❌ Error cleaning pricing_history: {str(e)}")
        return {
            'collection': 'pricing_history',
            'error': str(e),
            'documents_deleted': 0,
            'dry_run': dry_run
        }


def run_cleanup_job(
    competitor_days: int = 14,
    quote_days: int = 180,
    history_days: int = 180,
    dry_run: bool = False
) -> Dict:
    """
    Main cleanup job function that orchestrates all cleanup operations
    
    Args:
        competitor_days: Days to keep competitor_prices (default: 14)
        quote_days: Days to keep price_quotes (default: 180)
        history_days: Days to keep pricing_history (default: 180)
        dry_run: If True, only report what would be deleted
        
    Returns:
        Dictionary with cleanup summary
    """
    logger.info("=" * 80)
    logger.info(f"{'[DRY RUN MODE] ' if dry_run else ''}Starting Firestore Cleanup Job")
    logger.info("=" * 80)
    logger.info(f"Retention policies:")
    logger.info(f"  - competitor_prices: {competitor_days} days")
    logger.info(f"  - price_quotes: {quote_days} days")
    logger.info(f"  - pricing_history: {history_days} days")
    logger.info("=" * 80)
    
    counts = {'inserted': 0, 'updated': 0, 'deleted': 0}
    
    with track_job('cleanup_firestore', counts):
        results = {}
        total_deleted = 0
        total_found = 0
        errors = []
        
        # Cleanup competitor_prices
        competitor_result = delete_old_competitor_prices(days=competitor_days, dry_run=dry_run)
        results['competitor_prices'] = competitor_result
        total_deleted += competitor_result.get('documents_deleted', 0)
        total_found += competitor_result.get('documents_found', 0)
        if 'error' in competitor_result:
            errors.append(f"competitor_prices: {competitor_result['error']}")
        
        # Cleanup price_quotes
        quote_result = delete_old_price_quotes(days=quote_days, dry_run=dry_run)
        results['price_quotes'] = quote_result
        total_deleted += quote_result.get('documents_deleted', 0)
        total_found += quote_result.get('documents_found', 0)
        if 'error' in quote_result:
            errors.append(f"price_quotes: {quote_result['error']}")
        
        # Cleanup pricing_history
        history_result = delete_old_pricing_history(days=history_days, dry_run=dry_run)
        results['pricing_history'] = history_result
        total_deleted += history_result.get('documents_deleted', 0)
        total_found += history_result.get('documents_found', 0)
        if 'error' in history_result:
            errors.append(f"pricing_history: {history_result['error']}")
        
        counts['deleted'] = total_deleted
        
        # Summary
        logger.info("=" * 80)
        logger.info("Cleanup Job Summary")
        logger.info("=" * 80)
        logger.info(f"Total documents found: {total_found}")
        if dry_run:
            logger.info(f"[DRY RUN] Would delete: {total_found} documents")
        else:
            logger.info(f"Total documents deleted: {total_deleted}")
        
        if errors:
            logger.warning(f"Errors encountered: {len(errors)}")
            for error in errors:
                logger.warning(f"  - {error}")
        logger.info("=" * 80)
        
        return {
            'status': 'success' if not errors else 'partial_success',
            'dry_run': dry_run,
            'total_documents_found': total_found,
            'total_documents_deleted': total_deleted,
            'results': results,
            'errors': errors
        }


def main():
    """
    Run Firestore cleanup worker
    
    Usage:
        python3 -m app.workers.cleanup_firestore [OPTIONS]
    
    Requirements:
        - GOOGLE_APPLICATION_CREDENTIALS must be set
        - Points to Firebase service account JSON file
    
    Examples:
        # Dry run (default settings)
        export GOOGLE_APPLICATION_CREDENTIALS=/path/to/firebase-key.json
        python3 -m app.workers.cleanup_firestore --dry-run
        
        # Actual cleanup with default settings
        python3 -m app.workers.cleanup_firestore
        
        # Custom retention periods
        python3 -m app.workers.cleanup_firestore --competitor-days 7 --quote-days 90
        
        # Dry run with custom settings
        python3 -m app.workers.cleanup_firestore --dry-run --competitor-days 30
    
    Environment Variables:
        GOOGLE_APPLICATION_CREDENTIALS - Path to Firebase service account JSON
        DRY_RUN=true - Enable dry run mode
    """
    import argparse
    import os
    import time
    from pathlib import Path
    
    # Validate environment
    validate_environment()
    
    # Lock file configuration
    LOCK_FILE = Path('/tmp/hanco_cleanup.lock')
    MAX_LOCK_AGE_SECONDS = 2 * 60 * 60  # 2 hours
    
    # Parse arguments
    parser = argparse.ArgumentParser(description='Firestore data cleanup worker')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Perform a dry run without deleting documents'
    )
    parser.add_argument(
        '--competitor-days',
        type=int,
        default=14,
        help='Days to keep competitor_prices (default: 14)'
    )
    parser.add_argument(
        '--quote-days',
        type=int,
        default=180,
        help='Days to keep price_quotes (default: 180)'
    )
    parser.add_argument(
        '--history-days',
        type=int,
        default=180,
        help='Days to keep pricing_history (default: 180)'
    )
    
    args = parser.parse_args()
    
    # Check environment variable for dry-run
    dry_run = args.dry_run or os.environ.get('DRY_RUN', '').lower() == 'true'
    
    if dry_run:
        logger.info("🔍 DRY RUN MODE - No documents will be deleted")
    
    # Check for existing lock
    if LOCK_FILE.exists():
        try:
            lock_age = time.time() - LOCK_FILE.stat().st_mtime
            
            if lock_age < MAX_LOCK_AGE_SECONDS:
                logger.info(f"Lock file exists and is recent ({lock_age/60:.1f} minutes old)")
                logger.info("Another cleanup job may be running. Skipping this run.")
                log_job_skipped('cleanup_firestore', reason=f"Lock exists ({lock_age/60:.1f} min old)")
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
        result = run_cleanup_job(
            competitor_days=args.competitor_days,
            quote_days=args.quote_days,
            history_days=args.history_days,
            dry_run=dry_run
        )
        
        if result['status'] == 'success':
            logger.info("✅ Cleanup job completed successfully")
            exit_code = 0
        elif result['status'] == 'partial_success':
            logger.warning("⚠️  Cleanup job completed with some errors")
            exit_code = 0
        else:
            logger.error("❌ Cleanup job failed")
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
