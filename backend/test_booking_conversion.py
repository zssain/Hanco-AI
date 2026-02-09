"""
Test the full booking conversion flow
"""
import sys
sys.path.insert(0, '.')

from app.core.firebase import db, Collections
from app.api.v1.bookings import booking_doc_to_response
from google.cloud.firestore_v1 import FieldFilter

guest_id = "545b5ad4-2578-4cdc-8e0d-69ad8c393ac9"

print(f"🔍 Testing full booking flow for guest_id: {guest_id}\n")

# Query bookings
query = db.collection(Collections.BOOKINGS).where(filter=FieldFilter('guest_id', '==', guest_id))
docs = list(query.stream())

print(f"Found {len(docs)} bookings in query")

for doc in docs:
    print(f"\nBooking ID: {doc.id}")
    data = doc.to_dict()
    
    try:
        booking_response = booking_doc_to_response(doc.id, data)
        if booking_response:
            print(f"✅ Successfully converted")
            print(f"   Guest ID: {booking_response.guest_id}")
            print(f"   Vehicle ID: {booking_response.vehicle_id}")
            print(f"   Total: {booking_response.total_price}")
        else:
            print(f"❌ Conversion returned None")
    except Exception as e:
        print(f"❌ Error converting: {e}")
        import traceback
        traceback.print_exc()
