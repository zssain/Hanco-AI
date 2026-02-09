"""Quick script to check Audi A6 vehicle data."""
from app.core.firebase import db

docs = list(db.collection('vehicles').stream())
for d in docs:
    data = d.to_dict()
    name = data.get('name', '')
    if 'audi' in name.lower():
        print(f"Vehicle: {name}")
        print(f"  Category: {data.get('category')}")
        print(f"  Daily Rate: {data.get('daily_rate')} SAR")
        print(f"  ID: {d.id}")

# Also show competitor data for luxury/sedan
print("\n--- Competitor Prices ---")
sedan_docs = list(db.collection('competitor_prices_latest').where('vehicle_class', '==', 'sedan').limit(10).stream())
print(f"Sedan prices: {[d.to_dict().get('price_per_day') for d in sedan_docs]}")
