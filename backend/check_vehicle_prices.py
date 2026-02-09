"""
Quick test to check if vehicles have prices in Firebase
"""
import sys
sys.path.insert(0, '.')

from app.core.firebase import db, Collections

print("🔍 Checking vehicles in Firebase...\n")

docs = db.collection(Collections.VEHICLES).where('category', '==', 'Luxury').limit(3).stream()

for doc in docs:
    data = doc.to_dict()
    print(f"Vehicle ID: {doc.id}")
    print(f"  Name: {data.get('make')} {data.get('model')}")
    print(f"  Category: {data.get('category')}")
    print(f"  base_daily_rate: {data.get('base_daily_rate')}")
    print(f"  current_price: {data.get('current_price')}")
    print(f"  Status: {data.get('availability_status')}")
    print()
