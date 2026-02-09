"""
Worker: Release Expired Vehicle Reservations
Runs every 1-5 minutes to release vehicles with expired reservation TTLs.

Prevents vehicles from being stuck in "reserved" status if:
- User never completes payment
- Booking confirmation times out
- Session is abandoned

Usage:
    python3 -m app.workers.release_reservations [--dry-run]
"""

import argparse
import logging
import sys
from datetime import datetime, timezone

from app.core.firebase import db, Collections
from app.core.monitoring import validate_environment, track_job

logger = logging.getLogger(__name__)


def release_expired_reservations(dry_run: bool = False) -> dict:
    """
    Release vehicles with expired reservations.
    
    Args:
        dry_run: If True, only report what would be released without making changes
        
    Returns:
        dict with counts: released, failed, total
    """
    now = datetime.now(tz=timezone.utc)
    released_count = 0
    failed_count = 0
    
    try:
        # Query vehicles with expired reservations
        vehicles_ref = db.collection(Collections.VEHICLES)
        query = vehicles_ref.where("availability_status", "==", "reserved")
        
        docs = list(query.stream())
        total_reserved = len(docs)
        
        logger.info(f"Found {total_reserved} reserved vehicles")
        
        for doc in docs:
            vehicle = doc.to_dict()
            vehicle_id = doc.id
            
            # Check if reservation has expired
            expires_at = vehicle.get("reservation_expires_at")
            if not expires_at:
                # No expiration set - skip (shouldn't happen with new code)
                logger.warning(f"Vehicle {vehicle_id} reserved but no expiration set")
                continue
            
            # Compare timestamps
            if expires_at < now:
                # Reservation expired - release vehicle
                booking_id = vehicle.get("reserved_booking_id")
                reserved_at = vehicle.get("reserved_at")
                
                logger.info(
                    f"Releasing vehicle {vehicle_id} "
                    f"(booking: {booking_id}, reserved_at: {reserved_at}, expires_at: {expires_at})"
                )
                
                if not dry_run:
                    try:
                        # Release vehicle back to available
                        db.collection(Collections.VEHICLES).document(vehicle_id).update({
                            "availability_status": "available",
                            "reserved_booking_id": None,
                            "reserved_at": None,
                            "reservation_expires_at": None,
                            "updated_at": now,
                        })
                        released_count += 1
                        
                        # Optional: Update booking status to "expired" if still pending
                        if booking_id:
                            booking_ref = db.collection(Collections.BOOKINGS).document(booking_id)
                            booking_doc = booking_ref.get()
                            if booking_doc.exists:
                                booking_data = booking_doc.to_dict()
                                if booking_data.get("status") == "pending":
                                    booking_ref.update({
                                        "status": "expired",
                                        "updated_at": now,
                                    })
                                    logger.info(f"Marked booking {booking_id} as expired")
                        
                    except Exception as e:
                        logger.error(f"Failed to release vehicle {vehicle_id}: {e}")
                        failed_count += 1
                else:
                    released_count += 1
                    logger.info(f"[DRY RUN] Would release vehicle {vehicle_id}")
        
        result = {
            "total_reserved": total_reserved,
            "expired_found": released_count + failed_count,
            "released": released_count,
            "failed": failed_count,
        }
        
        logger.info(
            f"Release summary: {released_count} released, {failed_count} failed, "
            f"{total_reserved} total reserved"
        )
        
        return result
        
    except Exception as e:
        logger.exception(f"Error in release_expired_reservations: {e}")
        raise


def main():
    """Main entry point"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    parser = argparse.ArgumentParser(
        description="Release expired vehicle reservations"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate release without making changes"
    )
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("RELEASE EXPIRED RESERVATIONS JOB")
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
    logger.info("=" * 60)
    
    # Validate environment
    try:
        validate_environment()
    except EnvironmentError as e:
        logger.error(f"Environment validation failed: {e}")
        return 1
    
    # Run with job tracking
    try:
        with track_job(job_name="release_reservations"):
            result = release_expired_reservations(dry_run=args.dry_run)
            
            logger.info("=" * 60)
            logger.info("RELEASE JOB COMPLETED SUCCESSFULLY")
            logger.info(f"Total reserved: {result['total_reserved']}")
            logger.info(f"Expired found: {result['expired_found']}")
            logger.info(f"Released: {result['released']}")
            logger.info(f"Failed: {result['failed']}")
            logger.info("=" * 60)
            
            return 0
            
    except KeyboardInterrupt:
        logger.warning("Job interrupted by user")
        return 130
    except Exception as e:
        logger.exception(f"Job failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
