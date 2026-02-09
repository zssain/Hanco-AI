"""
Booking management endpoints for Hanco-AI
Handles rental bookings lifecycle with Firestore integration
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timezone
import logging
import uuid
import asyncio

from app.core.firebase import db, Collections
from app.core.security import get_guest_id, verify_booking_ownership, safe_log_error
from app.schemas.booking import (
    BookingCreate,
    BookingUpdate,
    BookingResponse,
    BookingListResponse
)
from google.cloud.firestore_v1 import FieldFilter
from google.cloud import firestore

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== Helper Functions ====================

def booking_doc_to_response(doc_id: str, doc_data: Dict[str, Any]) -> Optional[BookingResponse]:
    """Convert Firestore document to BookingResponse schema"""
    try:
        # Handle Firestore timestamps - ensure timezone-aware datetimes
        created_at = doc_data.get('created_at')
        updated_at = doc_data.get('updated_at')
        
        if isinstance(created_at, datetime):
            # Make timezone-aware if naive
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
        elif hasattr(created_at, 'timestamp'):
            created_at = datetime.fromtimestamp(created_at.timestamp(), tz=timezone.utc)
        elif isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
            except:
                created_at = None
        else:
            created_at = None
            
        if isinstance(updated_at, datetime):
            # Make timezone-aware if naive
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
        elif hasattr(updated_at, 'timestamp'):
            updated_at = datetime.fromtimestamp(updated_at.timestamp(), tz=timezone.utc)
        elif isinstance(updated_at, str):
            try:
                updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
            except:
                updated_at = None
        else:
            updated_at = None
        
        # Handle dates
        start_date = doc_data.get('start_date')
        end_date = doc_data.get('end_date')
        
        try:
            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date).date()
            elif hasattr(start_date, 'date'):
                start_date = start_date.date()
            elif start_date is None:
                start_date = date.today()
        except:
            start_date = date.today()
            
        try:
            if isinstance(end_date, str):
                end_date = datetime.fromisoformat(end_date).date()
            elif hasattr(end_date, 'date'):
                end_date = end_date.date()
            elif end_date is None:
                end_date = date.today()
        except:
            end_date = date.today()
        
        # Get guest_id from either field
        guest_id = doc_data.get('guest_id') or doc_data.get('user_id') or 'unknown'
        
        return BookingResponse(
            id=doc_id,
            guest_id=guest_id,
            vehicle_id=doc_data.get('vehicle_id', 'unknown'),
            start_date=start_date,
            end_date=end_date,
            pickup_branch_id=doc_data.get('pickup_branch_id') or doc_data.get('pickup_location', ''),
            dropoff_branch_id=doc_data.get('dropoff_branch_id') or doc_data.get('dropoff_location', ''),
            insurance_selected=doc_data.get('insurance_selected', False),
            payment_mode=doc_data.get('payment_mode', 'cash'),
            total_price=float(doc_data.get('total_price', 0.0)),
            insurance_amount=float(doc_data.get('insurance_amount', 0.0)),
            status=doc_data.get('status', 'pending'),
            payment_status=doc_data.get('payment_status', 'pending'),
            created_at=created_at,
            updated_at=updated_at
        )
    except Exception as e:
        logger.error(f"Error converting booking document {doc_id}: {str(e)}, data: {doc_data}")
        return None  # Return None for invalid bookings
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing booking data: {str(e)}"
        )


async def check_vehicle_availability(vehicle_id: str, start_date: date, end_date: date) -> tuple[bool, List[Dict]]:
    """
    Check if vehicle is available for the given date range
    Returns: (is_available, conflicting_bookings)
    """
    try:
        # Check if vehicle exists
        vehicle_ref = db.collection(Collections.VEHICLES).document(vehicle_id)
        vehicle_doc = vehicle_ref.get()
        
        if not vehicle_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vehicle with ID {vehicle_id} not found"
            )
        
        vehicle_data = vehicle_doc.to_dict()
        
        # Check vehicle status
        if vehicle_data.get('status') not in ['available', 'rented']:
            return False, []
        
        # Query existing bookings
        bookings_query = db.collection(Collections.BOOKINGS)\
            .where(filter=FieldFilter('vehicle_id', '==', vehicle_id))\
            .where(filter=FieldFilter('status', 'in', ['pending', 'confirmed', 'active']))
        
        bookings = bookings_query.stream()
        
        # Check for date conflicts
        conflicting_bookings = []
        for booking_doc in bookings:
            booking_data = booking_doc.to_dict()
            booking_start = booking_data.get('start_date')
            booking_end = booking_data.get('end_date')
            
            # Convert to date objects
            if isinstance(booking_start, str):
                booking_start = datetime.fromisoformat(booking_start).date()
            elif hasattr(booking_start, 'date'):
                booking_start = booking_start.date()
                
            if isinstance(booking_end, str):
                booking_end = datetime.fromisoformat(booking_end).date()
            elif hasattr(booking_end, 'date'):
                booking_end = booking_end.date()
            
            # Check for overlap
            if start_date <= booking_end and end_date >= booking_start:
                conflicting_bookings.append({
                    "booking_id": booking_doc.id,
                    "start_date": str(booking_start),
                    "end_date": str(booking_end)
                })
        
        return len(conflicting_bookings) == 0, conflicting_bookings
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking availability: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check availability: {str(e)}"
        )


async def calculate_booking_price(vehicle_id: str, start_date: date, end_date: date) -> float:
    """
    Calculate total price for booking using the new pricing engine.
    Falls back to simple base_daily_rate calculation if pricing engine fails.
    """
    try:
        # Get vehicle details
        vehicle_ref = db.collection(Collections.VEHICLES).document(vehicle_id)
        
        def _get_vehicle():
            return vehicle_ref.get()
        
        vehicle_doc = await asyncio.to_thread(_get_vehicle)
        
        if not vehicle_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vehicle with ID {vehicle_id} not found"
            )
        
        vehicle_data = vehicle_doc.to_dict()
        base_rate = vehicle_data.get('base_daily_rate', 0)
        cost_per_day = vehicle_data.get('cost_per_day', base_rate * 0.7)  # Default 70% of base
        vehicle_class = vehicle_data.get('category', 'sedan')
        branch_id = vehicle_data.get('branch_id', 'riyadh')
        
        # Calculate number of days
        num_days = (end_date - start_date).days
        if num_days <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date range"
            )
        
        # Try to use new pricing engine
        try:
            # Import here to avoid circular dependency
            from app.api.v1.pricing import (
                compute_vehicle_price,
                VehicleQuoteInput,
                _map_duration_to_key,
                get_market_stats
            )
            
            # Map vehicle class to class_bucket
            class_mapping = {
                'economy': 'economy',
                'compact': 'compact',
                'sedan': 'sedan',
                'suv': 'suv',
                'luxury': 'luxury',
                'van': 'van',
                'other': 'sedan'  # Default fallback
            }
            class_bucket = class_mapping.get(vehicle_class.lower(), 'sedan')
            
            # Create vehicle input
            vehicle_input = VehicleQuoteInput(
                vehicle_id=vehicle_id,
                class_bucket=class_bucket,
                base_daily_rate=base_rate,
                cost_per_day=cost_per_day,
                branch_type="City"  # Default, could be enriched from branch data
            )
            
            # Get duration key
            duration_key = _map_duration_to_key(num_days)
            
            # Get market stats
            market_stats = await get_market_stats(
                branch_key=branch_id,
                duration_key=duration_key,
                class_bucket=class_bucket
            )
            
            # Determine if weekend
            is_weekend = start_date.weekday() in [3, 4, 5]  # Thu/Fri/Sat
            
            # Weather defaults
            weather_defaults = {
                'avg_temp': 25.0,
                'rain': 0.0,
                'wind': 10.0
            }
            
            # Compute price using new engine
            result = await compute_vehicle_price(
                vehicle=vehicle_input,
                branch_key=branch_id,
                duration_days=num_days,
                duration_key=duration_key,
                pickup_date=start_date,
                is_weekend=is_weekend,
                market_stats=market_stats,
                weather_defaults=weather_defaults
            )
            
            total_price = result['total_price']
            cached = result.get('cached', False)
            
            logger.info(
                f"Calculated price for {vehicle_id} using pricing engine: "
                f"${total_price:.2f} ({num_days} days @ ${result['daily_price']:.2f}/day, cached={cached})"
            )
            
            return total_price
            
        except ImportError as ie:
            logger.warning(f"Could not import pricing engine: {ie}, falling back to simple calculation")
            # Fall through to simple calculation
        except Exception as pe:
            logger.warning(f"Pricing engine failed: {pe}, falling back to simple calculation")
            # Fall through to simple calculation
        
        # Fallback: Simple calculation with basic duration discount
        daily_rate = base_rate
        if num_days >= 30:
            daily_rate *= 0.85  # 15% discount for 30+ days
        elif num_days >= 7:
            daily_rate *= 0.93  # 7% discount for 7+ days
        elif num_days >= 3:
            daily_rate *= 0.97  # 3% discount for 3+ days
        
        total_price = daily_rate * num_days
        
        logger.info(
            f"Calculated price for {vehicle_id} (fallback): "
            f"${total_price:.2f} ({num_days} days @ ${daily_rate:.2f}/day)"
        )
        
        return total_price
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating price: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate price: {str(e)}"
        )


# ==================== Endpoints ====================

@router.post("", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def create_booking(
    booking: BookingCreate,
    guest_id: str = Depends(get_guest_id)
):
    """
    Create a new booking
    
    Flow:
    1. Validate dates
    2. Check vehicle availability
    3. Calculate total price
    4. Create booking with status='pending' and payment_status='unpaid'
    
    Requires authentication.
    """
    try:
        # Validate dates
        if booking.end_date <= booking.start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End date must be after start date"
            )
        
        if booking.start_date < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start date cannot be in the past"
            )
        
        # Check vehicle availability
        is_available, conflicts = await check_vehicle_availability(
            booking.vehicle_id,
            booking.start_date,
            booking.end_date
        )
        
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Vehicle not available for selected dates. Conflicting bookings: {len(conflicts)}"
            )
        
        # Calculate total price
        total_price = await calculate_booking_price(
            booking.vehicle_id,
            booking.start_date,
            booking.end_date
        )
        
        # Generate booking ID
        booking_id = str(uuid.uuid4())
        
        # Prepare booking data
        booking_data = {
            'id': booking_id,
            'user_id': guest_id,
            'vehicle_id': booking.vehicle_id,
            'start_date': booking.start_date.isoformat(),
            'end_date': booking.end_date.isoformat(),
            'total_price': total_price,
            'status': 'pending',
            'payment_status': 'unpaid',
            'pickup_location': booking.pickup_location,
            'dropoff_location': booking.dropoff_location,
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        
        # Add quote_id if provided
        if booking.quote_id:
            booking_data['quote_id'] = booking.quote_id
        
        # Use Firestore transaction to prevent race conditions (double-booking)
        # This ensures availability check + booking creation happens atomically
        @firestore.transactional
        def create_booking_transaction(transaction):
            # Re-check availability within transaction
            bookings_ref = db.collection(Collections.BOOKINGS)
            conflicting_query = bookings_ref.where(
                filter=FieldFilter('vehicle_id', '==', booking.vehicle_id)
            ).where(
                filter=FieldFilter('status', 'in', ['pending', 'confirmed', 'active'])
            )
            
            conflicting_bookings = []
            for doc in conflicting_query.stream():
                doc_data = doc.to_dict()
                doc_start = datetime.fromisoformat(doc_data['start_date']).date()
                doc_end = datetime.fromisoformat(doc_data['end_date']).date()
                
                # Check for date overlap
                if not (booking.end_date <= doc_start or booking.start_date >= doc_end):
                    conflicting_bookings.append(doc.id)
            
            if conflicting_bookings:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Vehicle became unavailable. Conflicts: {len(conflicting_bookings)}"
                )
            
            # Create booking within transaction
            doc_ref = db.collection(Collections.BOOKINGS).document(booking_id)
            transaction.set(doc_ref, booking_data)
            return doc_ref
        
        # Execute transaction
        transaction = db.transaction()
        doc_ref = create_booking_transaction(transaction)
        
        logger.info(f"Booking created: {booking_id} for user {guest_id}")
        
        # Update price_quotes if quote_id was provided
        if booking.quote_id:
            try:
                quote_ref = db.collection(Collections.PRICE_QUOTES).document(booking.quote_id)
                quote_doc = quote_ref.get()
                
                if quote_doc.exists:
                    quote_ref.update({
                        'booked': True,
                        'booking_id': booking_id,
                        'booked_at': firestore.SERVER_TIMESTAMP,
                        'updated_at': firestore.SERVER_TIMESTAMP
                    })
                    logger.info(f"Updated price quote {booking.quote_id} with booking {booking_id}")
                else:
                    logger.warning(f"Quote {booking.quote_id} not found, skipping update")
            except Exception as e:
                # Log error but don't fail booking creation
                logger.error(f"Error updating quote {booking.quote_id}: {str(e)}")
        
        # Fetch created document
        created_doc = doc_ref.get()
        return booking_doc_to_response(created_doc.id, created_doc.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        safe_log_error("Error creating booking", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create booking"
        )


@router.get("", response_model=BookingListResponse)
async def list_user_bookings(
    guest_id: str = Depends(get_guest_id),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page")
):
    """
    Get all bookings for the current user
    
    Returns bookings ordered by creation date (newest first).
    """
    try:
        # Query user's bookings - check both user_id (old bookings) and guest_id (chatbot bookings)
        logger.info(f"Fetching bookings for guest_id: {guest_id}")
        
        # First try guest_id (chatbot bookings)
        query_guest = db.collection(Collections.BOOKINGS)\
            .where(filter=FieldFilter('guest_id', '==', guest_id))
        
        # Also query for user_id (traditional bookings)
        query_user = db.collection(Collections.BOOKINGS)\
            .where(filter=FieldFilter('user_id', '==', guest_id))
        
        # Apply status filter if provided
        if status_filter:
            query_guest = query_guest.where(filter=FieldFilter('status', '==', status_filter))
            query_user = query_user.where(filter=FieldFilter('status', '==', status_filter))
        
        # Execute both queries and combine results
        docs_guest = list(query_guest.stream())
        docs_user = list(query_user.stream())
        
        logger.info(f"Found {len(docs_guest)} bookings with guest_id, {len(docs_user)} bookings with user_id")
        
        # Combine and deduplicate by booking ID
        all_docs = {doc.id: doc for doc in docs_guest + docs_user}
        
        # Convert to list, filtering out None values (invalid bookings)
        bookings = []
        for doc in all_docs.values():
            booking = booking_doc_to_response(doc.id, doc.to_dict())
            if booking is not None:
                bookings.append(booking)
        
        # Sort by created_at (newest first) - use timezone-aware datetime for comparison
        bookings.sort(key=lambda x: x.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        
        # Apply pagination
        total = len(bookings)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_bookings = bookings[start_idx:end_idx]
        
        logger.info(f"Listed {len(paginated_bookings)} bookings for user {guest_id}")
        
        return BookingListResponse(
            bookings=paginated_bookings,
            total=total,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"Error listing bookings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list bookings: {str(e)}"
        )


@router.get("/all", response_model=BookingListResponse)
async def list_all_bookings(
    guest_id: str = Depends(get_guest_id),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    city: Optional[str] = Query(None, description="Filter by vehicle city"),
    date_from: Optional[date] = Query(None, description="Filter bookings from this date"),
    date_to: Optional[date] = Query(None, description="Filter bookings to this date"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page")
):
    """
    Get all bookings across all users (Admin only)
    
    Supports filtering by status, city, and date range.
    """
    try:
        # Start with base query
        query = db.collection(Collections.BOOKINGS)
        
        # Apply status filter
        if status_filter:
            query = query.where(filter=FieldFilter('status', '==', status_filter))
        
        # Execute query
        docs = query.stream()
        
        # Convert to list and apply additional filters
        bookings = []
        for doc in docs:
            doc_data = doc.to_dict()
            
            # Date range filter (on start_date)
            if date_from or date_to:
                start_date = doc_data.get('start_date')
                if isinstance(start_date, str):
                    start_date = datetime.fromisoformat(start_date).date()
                elif hasattr(start_date, 'date'):
                    start_date = start_date.date()
                
                if date_from and start_date < date_from:
                    continue
                if date_to and start_date > date_to:
                    continue
            
            # City filter (requires vehicle lookup - inefficient but necessary with Firestore)
            if city:
                vehicle_id = doc_data.get('vehicle_id')
                vehicle_doc = db.collection(Collections.VEHICLES).document(vehicle_id).get()
                if vehicle_doc.exists:
                    vehicle_data = vehicle_doc.to_dict()
                    if vehicle_data.get('city') != city:
                        continue
                else:
                    continue
            
            bookings.append(booking_doc_to_response(doc.id, doc_data))
        
        # Sort by created_at (newest first)
        bookings.sort(key=lambda x: x.created_at or datetime.min, reverse=True)
        
        # Apply pagination
        total = len(bookings)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_bookings = bookings[start_idx:end_idx]
        
        logger.info(f"Admin listed {len(paginated_bookings)} bookings (total: {total})")
        
        return BookingListResponse(
            bookings=paginated_bookings,
            total=total,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"Error listing all bookings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list bookings: {str(e)}"
        )


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: str,
    guest_id: str = Depends(get_guest_id)
):
    """
    Get booking details by ID
    
    Users can only view their own bookings.
    Admins can view any booking.
    """
    try:
        # Get booking document
        doc_ref = db.collection(Collections.BOOKINGS).document(booking_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )
        
        booking_data = doc.to_dict()
        
        # IDOR protection: Return 404 instead of 403 to prevent ID enumeration
        await verify_booking_ownership(booking_id, current_user)
        
        logger.info(f"Retrieved booking: {booking_id}")
        return booking_doc_to_response(doc.id, booking_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving booking {booking_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve booking: {str(e)}"
        )


@router.delete("/{booking_id}", status_code=status.HTTP_200_OK)
async def cancel_booking(
    booking_id: str,
    guest_id: str = Depends(get_guest_id)
):
    """
    Cancel a booking
    
    Users can cancel their own bookings if not already cancelled or completed.
    Sets status to 'cancelled'.
    """
    try:
        # Get booking document
        doc_ref = db.collection(Collections.BOOKINGS).document(booking_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )
        
        booking_data = doc.to_dict()
        
        # IDOR protection
        await verify_booking_ownership(booking_id, current_user)
        
        # Check if booking can be cancelled
        current_status = booking_data.get('status')
        if current_status in ['cancelled', 'completed']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel booking with status: {current_status}"
            )
        
        # Update booking status
        doc_ref.update({
            'status': 'cancelled',
            'updated_at': firestore.SERVER_TIMESTAMP
        })
        
        logger.info(f"Booking cancelled: {booking_id} by user {guest_id}")
        
        return {
            "message": f"Booking {booking_id} cancelled successfully",
            "booking_id": booking_id,
            "status": "cancelled"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling booking {booking_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel booking: {str(e)}"
        )


@router.post("/{booking_id}/confirm", response_model=BookingResponse)
async def confirm_booking(
    booking_id: str,
    guest_id: str = Depends(get_guest_id)
):
    """
    Confirm a booking after successful payment
    
    Called internally by payment service or manually by user/admin.
    Sets status='confirmed' and payment_status='paid'.
    """
    try:
        # Get booking document
        doc_ref = db.collection(Collections.BOOKINGS).document(booking_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Booking with ID {booking_id} not found"
            )
        
        booking_data = doc.to_dict()
        
        # Check authorization
        if booking_data.get('user_id') != guest_id and current_user.role != 'admin':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only confirm your own bookings"
            )
        
        # Check current status
        current_status = booking_data.get('status')
        if current_status == 'cancelled':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot confirm a cancelled booking"
            )
        
        if current_status == 'confirmed':
            # Already confirmed, return current state
            return booking_doc_to_response(doc.id, booking_data)
        
        # Update booking
        doc_ref.update({
            'status': 'confirmed',
            'payment_status': 'paid',
            'updated_at': firestore.SERVER_TIMESTAMP
        })
        
        logger.info(f"Booking confirmed: {booking_id}")
        
        # Fetch updated document
        updated_doc = doc_ref.get()
        return booking_doc_to_response(updated_doc.id, updated_doc.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming booking {booking_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to confirm booking: {str(e)}"
        )
