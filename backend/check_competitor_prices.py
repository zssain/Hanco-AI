"""Check competitor prices in Firestore"""
from app.core.firebase import db

print("=" * 60)
print("COMPETITOR PRICES DATA CHECK")
print("=" * 60)

# Check competitor_prices collection (raw scraped data)
print("\n1. competitor_prices (raw scraped):")
try:
    prices = list(db.collection("competitor_prices").limit(10).stream())
    print(f"   Found: {len(prices)} prices")
    for p in prices[:5]:
        d = p.to_dict()
        provider = d.get("provider", "N/A")
        vehicle_class = d.get("vehicle_class", "N/A")
        city = d.get("city", "N/A")
        daily_rate = d.get("daily_rate", "N/A")
        print(f"   - {provider}: {vehicle_class} @ {city} = {daily_rate} SAR")
except Exception as e:
    print(f"   Error: {e}")

# Check competitor_prices_latest (aggregated)
print("\n2. competitor_prices_latest (aggregated):")
try:
    latest = list(db.collection("competitor_prices_latest").limit(10).stream())
    print(f"   Found: {len(latest)} aggregates")
    for l in latest[:5]:
        d = l.to_dict()
        avg_price = d.get("avg_price", "N/A")
        min_price = d.get("min_price", "N/A")
        max_price = d.get("max_price", "N/A")
        print(f"   - {l.id}: avg={avg_price}, min={min_price}, max={max_price}")
except Exception as e:
    print(f"   Error: {e}")

# Check fleet_prices_cache
print("\n3. fleet_prices_cache:")
try:
    cache = list(db.collection("fleet_prices_cache").limit(5).stream())
    print(f"   Found: {len(cache)} cache entries")
    for c in cache[:3]:
        d = c.to_dict()
        print(f"   - {c.id}: {d.keys()}")
except Exception as e:
    print(f"   Error: {e}")

print("\n" + "=" * 60)
