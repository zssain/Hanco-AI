"""
Check bookings in Firebase
"""
import sys
sys.path.insert(0, '.')

from app.core.firebase import db, Collections

print("🔍 Checking recent bookings in Firebase...\n")

docs = db.collection(Collections.BOOKINGS).order_by('created_at', direction='DESCENDING').limit(5).stream()

count = 0
for doc in docs:
    count += 1
    data = doc.to_dict()
    print(f"Booking ID: {doc.id}")
    print(f"  Guest ID: {data.get('guest_id')}")
    print(f"  Vehicle ID: {data.get('vehicle_id')}")
    print(f"  Status: {data.get('status')}")
    print(f"  Total Price: {data.get('total_price')}")
    print(f"  Start Date: {data.get('start_date')}")
    print(f"  End Date: {data.get('end_date')}")
    print(f"  Created: {data.get('created_at')}")
    print()

if count == 0:
    print("No bookings found in Firebase!")
