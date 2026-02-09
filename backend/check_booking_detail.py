"""
Check specific booking data structure
"""
import sys
sys.path.insert(0, '.')

from app.core.firebase import db, Collections

booking_id = "3adc83e4-a60d-448d-8835-f41d704db39c"
guest_id = "545b5ad4-2578-4cdc-8e0d-69ad8c393ac9"

print(f"🔍 Checking booking: {booking_id}\n")

# Get booking directly
doc = db.collection(Collections.BOOKINGS).document(booking_id).get()

if doc.exists:
    data = doc.to_dict()
    print("Booking data:")
    for key, value in data.items():
        print(f"  {key}: {value} (type: {type(value).__name__})")
    print()
    
    # Check what guest_id field contains
    print(f"guest_id field: '{data.get('guest_id')}'")
    print(f"user_id field: '{data.get('user_id')}'")
    print(f"Expected guest_id: '{guest_id}'")
    print(f"Match: {data.get('guest_id') == guest_id}")
    
    # Now test the query
    print("\n🔍 Testing Firestore query...")
    from google.cloud.firestore_v1 import FieldFilter
    
    query = db.collection(Collections.BOOKINGS).where(filter=FieldFilter('guest_id', '==', guest_id))
    docs = list(query.stream())
    print(f"Query found {len(docs)} bookings")
    
else:
    print("❌ Booking not found!")
