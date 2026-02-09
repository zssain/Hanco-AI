"""
Monitoring utilities for job runs and performance tracking
"""
import logging
import time
import os
import sys
from datetime import datetime
from typing import Dict, Optional, Any
from contextlib import contextmanager
from pathlib import Path

from app.core.firebase import db
from google.cloud import firestore as fs

logger = logging.getLogger(__name__)


def validate_environment():
    """
    Validate required environment variables for production deployment
    
    Raises:
        SystemExit: If GOOGLE_APPLICATION_CREDENTIALS is not set
    """
    creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    
    if not creds_path:
        logger.error("GOOGLE_APPLICATION_CREDENTIALS environment variable is not set")
        logger.error("Set it to point to your Firebase service account JSON file:")
        logger.error("  export GOOGLE_APPLICATION_CREDENTIALS=/path/to/firebase-key.json")
        sys.exit(1)
    
    if not os.path.exists(creds_path):
        logger.error(f"Firebase credentials file not found: {creds_path}")
        logger.error("Verify GOOGLE_APPLICATION_CREDENTIALS points to a valid file")
        sys.exit(1)
    
    logger.info(f"Firebase credentials loaded from: {creds_path}")


@contextmanager
def acquire_lock(job_name: str, lock_dir: str = "/tmp"):
    """
    Acquire a file lock to prevent concurrent job execution
    
    Args:
        job_name: Name of the job (used for lock filename)
        lock_dir: Directory to store lock files (default: /tmp)
        
    Raises:
        RuntimeError: If lock cannot be acquired (job already running)
    """
    lock_file = Path(lock_dir) / f"{job_name}.lock"
    
    # Check if lock exists
    if lock_file.exists():
        try:
            # Read PID from lock file
            with open(lock_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process is still running
            try:
                os.kill(pid, 0)  # Signal 0 checks if process exists
                # Process exists - lock is valid
                raise RuntimeError(
                    f"Job {job_name} is already running (PID: {pid}). "
                    f"Lock file: {lock_file}"
                )
            except OSError:
                # Process doesn't exist - stale lock file
                logger.warning(f"Removing stale lock file: {lock_file} (PID {pid} not found)")
                lock_file.unlink()
        except Exception as e:
            logger.warning(f"Error checking lock file: {e}. Removing it.")
            lock_file.unlink()
    
    # Acquire lock
    try:
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))
        logger.info(f"Lock acquired: {lock_file}")
        
        yield
        
    finally:
        # Release lock
        if lock_file.exists():
            lock_file.unlink()
            logger.info(f"Lock released: {lock_file}")


def log_job_run(
    job_name: str,
    status: str,
    started_at: datetime,
    finished_at: datetime,
    counts: Optional[Dict[str, int]] = None,
    error: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Log job execution to Firestore job_runs collection
    
    Args:
        job_name: Name of the job (e.g., 'scrape_competitors', 'train_model', 'cleanup_firestore')
        status: 'success', 'fail', or 'skipped'
        started_at: Job start timestamp
        finished_at: Job completion timestamp
        counts: Dictionary with counts like {inserted: 10, updated: 5, deleted: 0}
        error: Error message if status is 'fail'
        metadata: Additional job-specific metadata
        
    Returns:
        Document ID of created job_run
    """
    duration_ms = int((finished_at - started_at).total_seconds() * 1000)
    
    job_run = {
        'job_name': job_name,
        'started_at': started_at,
        'finished_at': finished_at,
        'status': status,
        'duration_ms': duration_ms,
        'counts': counts or {},
        'error': error,
        'metadata': metadata or {},
        'created_at': fs.SERVER_TIMESTAMP
    }
    
    # Auto-generate document ID
    doc_ref = db.collection('job_runs').document()
    doc_ref.set(job_run)
    
    log_msg = f"Job run logged: {job_name} [{status}] duration={duration_ms}ms"
    if counts:
        log_msg += f" counts={counts}"
    if error:
        log_msg += f" error={error}"
    
    logger.info(log_msg)
    
    return doc_ref.id


def log_job_skipped(job_name: str, reason: str = "Lock file exists"):
    """
    Log a skipped job run (quick helper for early exit scenarios)
    
    Args:
        job_name: Name of the job
        reason: Reason for skipping
    """
    now = datetime.utcnow()
    return log_job_run(
        job_name=job_name,
        status='skipped',
        started_at=now,
        finished_at=now,
        counts={},
        error=None,
        metadata={'skip_reason': reason}
    )


@contextmanager
def track_job(job_name: str, counts: Optional[Dict[str, int]] = None):
    """
    Context manager to automatically track job execution
    
    Usage:
        with track_job('scrape_competitors', counts={'inserted': 0, 'updated': 0}):
            # do work
            counts['inserted'] += 10
    
    Args:
        job_name: Name of the job
        counts: Dictionary to track counts (mutated by caller)
    """
    started_at = datetime.utcnow()
    error_msg = None
    status = 'success'
    
    try:
        yield counts or {}
    except Exception as e:
        status = 'fail'
        error_msg = str(e)
        logger.error(f"Job {job_name} failed: {error_msg}")
        raise
    finally:
        finished_at = datetime.utcnow()
        log_job_run(
            job_name=job_name,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            counts=counts,
            error=error_msg
        )
