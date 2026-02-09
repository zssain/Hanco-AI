"""Feature engineering for pricing model
Builds feature vectors for ONNX model input

Required Firestore Composite Indexes:
1. price_quotes:
   - branch_id (ASC) + vehicle_class (ASC) + created_at (DESC)
   - booked (ASC) + created_at (DESC)
   - vehicle_id (ASC) + created_at (DESC)

2. pricing_history:
   - vehicle_id (ASC) + timestamp (DESC)
   - city (ASC) + timestamp (DESC)

3. bookings (for overlap queries):
   - vehicle_id (ASC) + status (ASC) + start_date (ASC)
   - vehicle_id (ASC) + status (ASC) + end_date (ASC)
"""
from datetime import date
from typing import Dict
import logging
from google.cloud.firestore_v1 import FieldFilter

from app.services.weather.open_meteo import get_weather_features
# from app.services.competitors.crawler import scrape_all_providers  # Disabled due to dependency conflicts

logger = logging.getLogger(__name__)


async def build_pricing_features(
    vehicle_doc: Dict,
    start_date: date,
    end_date: date,
    city: str,
    firestore_client
) -> Dict[str, float]:
    """
    Build all features required for pricing prediction
    
    Args:
        vehicle_doc: Vehicle document from Firestore
        start_date: Rental start date
        end_date: Rental end date
        city: City name
        firestore_client: Firestore database client
        
    Returns:
        Dictionary of numeric features for ONNX model
    """
    try:
        # 1. Temporal features
        rental_length_days = (end_date - start_date).days
        day_of_week = start_date.weekday()  # 0=Monday, 6=Sunday
        month = start_date.month  # 1-12
        
        # 2. Vehicle features
        base_daily_rate = vehicle_doc.get('base_daily_rate', 100.0)
        category = vehicle_doc.get('category', 'sedan')
        
        # 3. Weather features
        weather = await get_weather_features(city, start_date)
        avg_temp = weather.get('avg_temp', 25.0)
        rain = weather.get('rain', 0.0)
        wind = weather.get('wind', 10.0)
        
        # 4. Competitor pricing features
        avg_competitor_price = await get_avg_competitor_price(
            firestore_client,
            city,
            category
        )
        
        # 5. Demand features
        demand_index = await calculate_demand_index(
            firestore_client,
            city,
            start_date,
            end_date
        )
        
        # 6. Bias term
        bias = 1.0
        
        features = {
            'rental_length_days': float(rental_length_days),
            'day_of_week': float(day_of_week),
            'month': float(month),
            'base_daily_rate': float(base_daily_rate),
            'avg_temp': float(avg_temp),
            'rain': float(rain),
            'wind': float(wind),
            'avg_competitor_price': float(avg_competitor_price),
            'demand_index': float(demand_index),
            'bias': float(bias)
        }
        
        logger.info(f"Built pricing features: {features}")
        
        return features
        
    except Exception as e:
        logger.error(f"Error building features: {str(e)}")
        raise


async def get_avg_competitor_price(
    firestore_client,
    city: str,
    category: str,
    use_realtime: bool = False
) -> float:
    """
    Get average competitor price for same city and category
    
    Args:
        firestore_client: Firestore database
        city: City name
        category: Vehicle category
        use_realtime: If True, scrape live prices instead of using cached data
        
    Returns:
        Average competitor price (or base fallback)
    """
    try:
        prices = []
        
        # Option 1: Real-time scraping (fresh data)
        if use_realtime:
            logger.warning(f"Real-time competitor scraping requested but crawl4ai is disabled")
            # Scraping disabled - fall back to historical data
            # scraped_data = await scrape_all_providers(city, category)
            # [Scraping code removed]
        
        # Option 2: Historical data from Firestore (cached)
        else:
            logger.info(f"Fetching cached competitor prices for {city}/{category}")
            
            # Query competitor_prices collection
            competitor_ref = firestore_client.collection('competitor_prices')
            
            # Filter by city and category
            query = competitor_ref\
                .where(filter=FieldFilter('city', '==', city))\
                .where(filter=FieldFilter('category', '==', category))\
                .limit(20)
            
            docs = query.stream()
            
            # Extract prices
            for doc in docs:
                doc_data = doc.to_dict()
                price = doc_data.get('price', 0)
                if price > 0:
                    prices.append(price)
        
        # Calculate average
        if prices:
            avg_price = sum(prices) / len(prices)
            logger.info(f"Found {len(prices)} competitor prices, avg: {avg_price:.2f} SAR")
            return avg_price
        else:
            # No competitor data, return a reasonable default
            logger.warning(f"No competitor prices for {city}/{category}, using default")
            return 100.0
            
    except Exception as e:
        logger.error(f"Error fetching competitor prices: {str(e)}")
        return 100.0


async def calculate_demand_index(
    firestore_client,
    city: str,
    start_date: date,
    end_date: date
) -> float:
    """
    Calculate demand index based on existing bookings
    
    Args:
        firestore_client: Firestore database
        city: City name
        start_date: Rental start date
        end_date: Rental end date
        
    Returns:
        Demand index (0.0 - 2.0, where 1.0 is normal)
    """
    try:
        # Query bookings in the same city and date range
        bookings_ref = firestore_client.collection('bookings')
        
        # Get all active bookings
        query = bookings_ref.where(
            filter=FieldFilter('status', 'in', ['pending', 'confirmed', 'active'])
        )
        
        docs = query.stream()
        
        # Count overlapping bookings
        overlap_count = 0
        for doc in docs:
            doc_data = doc.to_dict()
            
            # Check if booking overlaps with requested dates
            booking_start = doc_data.get('start_date')
            booking_end = doc_data.get('end_date')
            
            # Convert to date if string
            if isinstance(booking_start, str):
                from datetime import datetime
                booking_start = datetime.fromisoformat(booking_start).date()
            if isinstance(booking_end, str):
                from datetime import datetime
                booking_end = datetime.fromisoformat(booking_end).date()
            
            # Check overlap
            if hasattr(booking_start, 'date'):
                booking_start = booking_start.date()
            if hasattr(booking_end, 'date'):
                booking_end = booking_end.date()
                
            if start_date <= booking_end and end_date >= booking_start:
                overlap_count += 1
        
        # Normalize to 0-2 range (0=no demand, 1=normal, 2=high demand)
        # Assume 5 overlapping bookings = normal demand
        demand_index = min(overlap_count / 5.0, 2.0)
        
        logger.info(f"Demand index for {city}: {demand_index:.2f} ({overlap_count} overlapping bookings)")
        
        return demand_index
        
    except Exception as e:
        logger.error(f"Error calculating demand: {str(e)}")
        return 0.5  # Default to low demand on error


# ==================== UTILIZATION SNAPSHOTS ====================

def compute_utilization_snapshot(
    firestore_client,
    branch_id: str,
    vehicle_class: str,
    target_date: date = None
) -> Dict:
    """
    Compute utilization snapshot for a specific branch and vehicle class.
    
    Args:
        firestore_client: Firestore database client
        branch_id: Branch/city identifier
        vehicle_class: Vehicle category (economy, sedan, suv, luxury)
        target_date: Date to compute utilization for (defaults to today)
        
    Returns:
        Dictionary with utilization metrics
    """
    if target_date is None:
        target_date = date.today()
    
    try:
        # 1. Count total fleet for this branch and vehicle class
        vehicles_ref = firestore_client.collection('vehicles')
        vehicle_query = vehicles_ref \
            .where(filter=FieldFilter('city', '==', branch_id)) \
            .where(filter=FieldFilter('category', '==', vehicle_class))
        
        vehicle_docs = list(vehicle_query.stream())
        total_fleet = len(vehicle_docs)
        
        if total_fleet == 0:
            logger.info(f"No vehicles found for {branch_id}/{vehicle_class}")
            return None
        
        # Get vehicle IDs for booking check
        vehicle_ids = [doc.id for doc in vehicle_docs]
        
        # 2. Count active bookings overlapping today for these vehicles
        bookings_ref = firestore_client.collection('bookings')
        
        # Query bookings with active statuses
        booking_query = bookings_ref.where(
            filter=FieldFilter('status', 'in', ['confirmed', 'active'])
        )
        
        booking_docs = list(booking_query.stream())
        
        # Filter bookings that overlap with target_date and match our vehicles
        booked_count = 0
        for doc in booking_docs:
            doc_data = doc.to_dict()
            vehicle_id = doc_data.get('vehicle_id')
            
            # Skip if not in our vehicle list
            if vehicle_id not in vehicle_ids:
                continue
            
            # Check date overlap
            booking_start = doc_data.get('start_date')
            booking_end = doc_data.get('end_date')
            
            # Convert to date objects
            if isinstance(booking_start, str):
                from datetime import datetime
                booking_start = datetime.fromisoformat(booking_start).date()
            elif hasattr(booking_start, 'date'):
                booking_start = booking_start.date()
            
            if isinstance(booking_end, str):
                from datetime import datetime
                booking_end = datetime.fromisoformat(booking_end).date()
            elif hasattr(booking_end, 'date'):
                booking_end = booking_end.date()
            
            # Check if booking overlaps with target_date
            if booking_start <= target_date <= booking_end:
                booked_count += 1
        
        # 3. Calculate utilization rate
        utilization_rate = booked_count / total_fleet if total_fleet > 0 else 0.0
        
        snapshot = {
            'branch_id': branch_id,
            'vehicle_class': vehicle_class,
            'snapshot_date': target_date,
            'total_fleet': total_fleet,
            'booked': booked_count,
            'available': total_fleet - booked_count,
            'utilization_rate': utilization_rate,
            'computed_at': date.today()  # Will be converted to timestamp in Firestore
        }
        
        logger.info(
            f"Utilization for {branch_id}/{vehicle_class} on {target_date}: "
            f"{booked_count}/{total_fleet} = {utilization_rate:.2%}"
        )
        
        return snapshot
        
    except Exception as e:
        logger.error(f"Error computing utilization snapshot: {str(e)}")
        return None


def save_utilization_snapshot(
    firestore_client,
    branch_id: str,
    vehicle_class: str,
    snapshot: Dict
) -> bool:
    """
    Save utilization snapshot to Firestore.
    
    Args:
        firestore_client: Firestore database client
        branch_id: Branch/city identifier
        vehicle_class: Vehicle category
        snapshot: Computed snapshot data
        
    Returns:
        True if successful
    """
    try:
        from google.cloud import firestore as fs
        
        # Use fixed document ID format: {branch_id}_{vehicle_class}_{date}
        snapshot_date = snapshot.get('snapshot_date')
        date_str = snapshot_date.isoformat() if hasattr(snapshot_date, 'isoformat') else str(snapshot_date)
        doc_id = f"{branch_id}_{vehicle_class}_{date_str}"
        
        # Prepare document with timestamp
        doc_data = {
            **snapshot,
            'snapshot_date': snapshot_date,  # Store as date
            'computed_at': fs.SERVER_TIMESTAMP,
            'updated_at': fs.SERVER_TIMESTAMP
        }
        
        snapshot_ref = firestore_client.collection('utilization_snapshots').document(doc_id)
        snapshot_ref.set(doc_data, merge=True)
        
        logger.info(f"Saved utilization snapshot to utilization_snapshots/{doc_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving utilization snapshot: {str(e)}")
        return False


def refresh_utilization_snapshots(
    firestore_client,
    branch_ids: list = None,
    vehicle_classes: list = None,
    target_date: date = None
) -> Dict:
    """
    Refresh utilization snapshots for multiple branches and vehicle classes.
    
    Args:
        firestore_client: Firestore database client
        branch_ids: List of branch/city IDs (defaults to all active branches)
        vehicle_classes: List of vehicle classes (defaults to common categories)
        target_date: Date to compute utilization for (defaults to today)
        
    Returns:
        Summary dictionary with results
    """
    from datetime import datetime
    
    if branch_ids is None:
        # Default to common Saudi cities
        branch_ids = ['riyadh', 'jeddah', 'dammam', 'mecca', 'medina']
    
    if vehicle_classes is None:
        # Default to common vehicle categories
        vehicle_classes = ['economy', 'sedan', 'suv', 'luxury']
    
    if target_date is None:
        target_date = date.today()
    
    summary = {
        'snapshots_computed': 0,
        'snapshots_saved': 0,
        'errors': [],
        'target_date': target_date,
        'started_at': datetime.utcnow()
    }
    
    try:
        logger.info(
            f"Refreshing utilization snapshots for {len(branch_ids)} branches x "
            f"{len(vehicle_classes)} vehicle classes on {target_date}"
        )
        
        for branch_id in branch_ids:
            for vehicle_class in vehicle_classes:
                try:
                    # Compute snapshot
                    snapshot = compute_utilization_snapshot(
                        firestore_client,
                        branch_id,
                        vehicle_class,
                        target_date
                    )
                    
                    if snapshot:
                        summary['snapshots_computed'] += 1
                        
                        # Save to Firestore
                        if save_utilization_snapshot(firestore_client, branch_id, vehicle_class, snapshot):
                            summary['snapshots_saved'] += 1
                    
                except Exception as e:
                    error_msg = f"Error processing {branch_id}/{vehicle_class}: {str(e)}"
                    logger.error(error_msg)
                    summary['errors'].append(error_msg)
        
        summary['completed_at'] = datetime.utcnow()
        summary['duration_seconds'] = (summary['completed_at'] - summary['started_at']).total_seconds()
        
        logger.info(
            f"Utilization snapshot refresh complete: {summary['snapshots_saved']} saved in "
            f"{summary['duration_seconds']:.1f}s"
        )
        
    except Exception as e:
        error_msg = f"Error in refresh_utilization_snapshots: {str(e)}"
        logger.error(error_msg)
        summary['errors'].append(error_msg)
    
    return summary


# ==================== DEMAND SIGNALS ====================

def compute_demand_signal(
    firestore_client,
    branch_id: str,
    vehicle_class: str,
    hour_bucket: str = None
) -> Dict:
    """
    Compute demand signal for a specific branch, vehicle class, and hour bucket.
    
    Args:
        firestore_client: Firestore database client
        branch_id: Branch/city identifier
        vehicle_class: Vehicle category (economy, sedan, suv, luxury)
        hour_bucket: Hour bucket in format 'YYYY-MM-DD-HH' (defaults to current hour)
        
    Returns:
        Dictionary with demand signal metrics
    """
    from datetime import datetime, timedelta
    
    if hour_bucket is None:
        # Default to current hour bucket
        now = datetime.utcnow()
        hour_bucket = now.strftime('%Y-%m-%d-%H')
    
    try:
        # Parse hour bucket to get time range
        bucket_dt = datetime.strptime(hour_bucket, '%Y-%m-%d-%H')
        start_time = bucket_dt
        end_time = bucket_dt + timedelta(hours=1)
        
        # 1. Count price quotes in this hour bucket
        quotes_ref = firestore_client.collection('price_quotes')
        quote_query = quotes_ref \
            .where(filter=FieldFilter('branch_id', '==', branch_id)) \
            .where(filter=FieldFilter('vehicle_class', '==', vehicle_class)) \
            .where(filter=FieldFilter('created_at', '>=', start_time)) \
            .where(filter=FieldFilter('created_at', '<', end_time))
        
        quote_docs = list(quote_query.stream())
        quote_count = len(quote_docs)
        
        # 2. Count bookings in this hour bucket
        bookings_ref = firestore_client.collection('bookings')
        booking_query = bookings_ref \
            .where(filter=FieldFilter('pickup_branch_id', '==', branch_id)) \
            .where(filter=FieldFilter('created_at', '>=', start_time)) \
            .where(filter=FieldFilter('created_at', '<', end_time))
        
        booking_docs = list(booking_query.stream())
        
        # Filter bookings by vehicle class (match vehicle category)
        booking_count = 0
        for doc in booking_docs:
            doc_data = doc.to_dict()
            vehicle_id = doc_data.get('vehicle_id')
            
            # Get vehicle to check category
            if vehicle_id:
                vehicle_ref = firestore_client.collection('vehicles').document(vehicle_id)
                vehicle_doc = vehicle_ref.get()
                if vehicle_doc.exists:
                    vehicle_data = vehicle_doc.to_dict()
                    if vehicle_data.get('category') == vehicle_class:
                        booking_count += 1
        
        # 3. Calculate conversion rate
        conversion_rate = booking_count / quote_count if quote_count > 0 else 0.0
        
        # 4. Calculate demand index (normalized 0-1)
        # Formula: weighted combination of quote volume and conversion rate
        # High quotes = high interest, high conversion = high demand
        
        # Normalize quote_count (assume 10 quotes per hour is high demand)
        quote_score = min(quote_count / 10.0, 1.0)
        
        # Conversion rate is already 0-1
        conversion_score = conversion_rate
        
        # Weighted average: 40% quote volume, 60% conversion rate
        demand_index = (0.4 * quote_score) + (0.6 * conversion_score)
        
        signal = {
            'branch_id': branch_id,
            'vehicle_class': vehicle_class,
            'hour_bucket': hour_bucket,
            'quote_count': quote_count,
            'booking_count': booking_count,
            'conversion_rate': conversion_rate,
            'demand_index': demand_index,
            'start_time': start_time,
            'end_time': end_time,
            'computed_at': datetime.utcnow()
        }
        
        logger.info(
            f"Demand signal for {branch_id}/{vehicle_class} at {hour_bucket}: "
            f"quotes={quote_count}, bookings={booking_count}, "
            f"conversion={conversion_rate:.2%}, demand_index={demand_index:.3f}"
        )
        
        return signal
        
    except Exception as e:
        logger.error(f"Error computing demand signal: {str(e)}")
        return None


def save_demand_signal(
    firestore_client,
    branch_id: str,
    vehicle_class: str,
    signal: Dict
) -> bool:
    """
    Save demand signal to Firestore.
    
    Args:
        firestore_client: Firestore database client
        branch_id: Branch/city identifier
        vehicle_class: Vehicle category
        signal: Computed signal data
        
    Returns:
        True if successful
    """
    try:
        from google.cloud import firestore as fs
        
        # Use fixed document ID format: {branch_id}_{vehicle_class}_{hour_bucket}
        hour_bucket = signal.get('hour_bucket')
        doc_id = f"{branch_id}_{vehicle_class}_{hour_bucket}"
        
        # Prepare document with timestamp
        doc_data = {
            **signal,
            'computed_at': fs.SERVER_TIMESTAMP,
            'updated_at': fs.SERVER_TIMESTAMP
        }
        
        signal_ref = firestore_client.collection('demand_signals').document(doc_id)
        signal_ref.set(doc_data, merge=True)
        
        logger.info(f"Saved demand signal to demand_signals/{doc_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving demand signal: {str(e)}")
        return False


def refresh_demand_signals(
    firestore_client,
    branch_ids: list = None,
    vehicle_classes: list = None,
    hour_bucket: str = None
) -> Dict:
    """
    Refresh demand signals for multiple branches and vehicle classes.
    
    Args:
        firestore_client: Firestore database client
        branch_ids: List of branch/city IDs (defaults to all active branches)
        vehicle_classes: List of vehicle classes (defaults to common categories)
        hour_bucket: Hour bucket in format 'YYYY-MM-DD-HH' (defaults to current hour)
        
    Returns:
        Summary dictionary with results
    """
    from datetime import datetime
    
    if branch_ids is None:
        # Default to common Saudi cities
        branch_ids = ['riyadh', 'jeddah', 'dammam', 'mecca', 'medina']
    
    if vehicle_classes is None:
        # Default to common vehicle categories
        vehicle_classes = ['economy', 'sedan', 'suv', 'luxury']
    
    if hour_bucket is None:
        # Default to current hour
        now = datetime.utcnow()
        hour_bucket = now.strftime('%Y-%m-%d-%H')
    
    summary = {
        'signals_computed': 0,
        'signals_saved': 0,
        'errors': [],
        'hour_bucket': hour_bucket,
        'started_at': datetime.utcnow()
    }
    
    try:
        logger.info(
            f"Refreshing demand signals for {len(branch_ids)} branches x "
            f"{len(vehicle_classes)} vehicle classes for hour {hour_bucket}"
        )
        
        for branch_id in branch_ids:
            for vehicle_class in vehicle_classes:
                try:
                    # Compute signal
                    signal = compute_demand_signal(
                        firestore_client,
                        branch_id,
                        vehicle_class,
                        hour_bucket
                    )
                    
                    if signal:
                        summary['signals_computed'] += 1
                        
                        # Save to Firestore
                        if save_demand_signal(firestore_client, branch_id, vehicle_class, signal):
                            summary['signals_saved'] += 1
                    
                except Exception as e:
                    error_msg = f"Error processing {branch_id}/{vehicle_class}: {str(e)}"
                    logger.error(error_msg)
                    summary['errors'].append(error_msg)
        
        summary['completed_at'] = datetime.utcnow()
        summary['duration_seconds'] = (summary['completed_at'] - summary['started_at']).total_seconds()
        
        logger.info(
            f"Demand signal refresh complete: {summary['signals_saved']} saved in "
            f"{summary['duration_seconds']:.1f}s"
        )
        
    except Exception as e:
        error_msg = f"Error in refresh_demand_signals: {str(e)}"
        logger.error(error_msg)
        summary['errors'].append(error_msg)
    
    return summary
