"""
Check competitor data and pricing functionality
"""
import sys
sys.path.insert(0, '.')

from app.core.firebase import db
from datetime import datetime, timedelta

print("=" * 70)
print("CHECKING COMPETITOR DATA & PRICING")
print("=" * 70)
print()

# Check competitor_prices collection
print("1. Checking competitor_prices collection:")
try:
    competitor_prices = list(db.collection('competitor_prices').limit(5).stream())
    print(f"   ✅ Found {len(competitor_prices)} competitor price entries")
    
    if competitor_prices:
        latest = competitor_prices[0].to_dict()
        print(f"   Latest entry:")
        print(f"      - Provider: {latest.get('provider', 'N/A')}")
        print(f"      - Vehicle Class: {latest.get('vehicle_class', 'N/A')}")
        print(f"      - Price: {latest.get('price_per_day', 'N/A')} SAR/day")
        print(f"      - Scraped at: {latest.get('scraped_at', 'N/A')}")
    else:
        print("   ⚠️  No competitor prices found - scraper hasn't run yet")
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Check vehicles collection for pricing
print("2. Checking vehicles with base prices:")
try:
    vehicles = list(db.collection('vehicles').limit(5).stream())
    print(f"   ✅ Found {len(vehicles)} vehicles")
    
    if vehicles:
        for v in vehicles[:3]:
            data = v.to_dict()
            print(f"   - {data.get('make', 'N/A')} {data.get('model', 'N/A')}")
            print(f"     Base price: {data.get('base_price', 'N/A')} SAR/day")
            print(f"     Category: {data.get('category', 'N/A')}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Check if ONNX model exists
print("3. Checking ONNX pricing model:")
import os
model_path = "./ml/models/model.onnx"
if os.path.exists(model_path):
    print(f"   ✅ ONNX model found at: {model_path}")
    print(f"   Model size: {os.path.getsize(model_path) / 1024:.2f} KB")
else:
    print(f"   ⚠️  ONNX model NOT found at: {model_path}")
    print("   Need to train the model first")

print()

# Check weather collection
print("4. Checking weather data:")
try:
    weather = list(db.collection('weather').limit(3).stream())
    print(f"   ✅ Found {len(weather)} weather entries")
    
    if weather:
        latest_weather = weather[0].to_dict()
        print(f"   Latest: {latest_weather.get('city', 'N/A')} - {latest_weather.get('temperature_c', 'N/A')}°C")
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Test pricing API endpoint
print("5. Testing pricing calculation:")
try:
    from app.services.pricing.feature_builder import build_pricing_features
    from datetime import date
    
    # Test with sample data
    test_request = {
        'vehicle_id': 'test',
        'city': 'riyadh',
        'start_date': date.today() + timedelta(days=1),
        'end_date': date.today() + timedelta(days=4),
    }
    
    print(f"   Testing with: {test_request['city']}, 3 days")
    
    # Try to build features
    try:
        features = build_pricing_features(
            city=test_request['city'],
            start_date=test_request['start_date'],
            end_date=test_request['end_date'],
            vehicle_category='sedan'
        )
        print(f"   ✅ Feature builder working")
        print(f"      - Competitor avg: {features.get('competitor_avg', 'N/A')} SAR")
        print(f"      - Utilization: {features.get('utilization_rate', 'N/A')}")
    except Exception as e:
        print(f"   ⚠️  Feature builder error: {e}")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

print()
print("=" * 70)
print("RECOMMENDATIONS:")
print("=" * 70)

# Provide recommendations
if not competitor_prices:
    print("📌 Run competitor scraper:")
    print("   python -c \"import asyncio; from app.services.competitors.crawler import scrape_all_providers; asyncio.run(scrape_all_providers())\"")
    print()

if not os.path.exists(model_path):
    print("📌 Train ONNX pricing model:")
    print("   python app/ml/training/train_pricing_model.py")
    print()

print("📌 Start backend with scraper worker:")
print("   python -m uvicorn app.main:app --reload --port 8000")
print()
