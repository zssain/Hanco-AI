"""
Test Pricing Engine
"""
import asyncio
from datetime import date, timedelta
from app.services.pricing.onnx_runtime import predict_price
from app.services.pricing.rule_engine import PricingRuleEngine
from app.services.pricing.feature_builder import build_pricing_features
from app.core.firebase import db

async def test_pricing():
    print("=" * 60)
    print("PRICING ENGINE TEST")
    print("=" * 60)

    # Create mock vehicle doc
    vehicle_doc = {
        "base_daily_rate": 150.0,
        "category": "sedan",
        "name": "Toyota Camry"
    }

    # Test feature building
    print("\n1. Feature Building:")
    try:
        features = await build_pricing_features(
            vehicle_doc=vehicle_doc,
            start_date=date.today() + timedelta(days=3),
            end_date=date.today() + timedelta(days=6),
            city="Riyadh",
            firestore_client=db
        )
        print(f"   Features built: {list(features.keys())}")
        print(f"   Base rate: {features.get('base_daily_rate')}")
        print(f"   Competitor avg: {features.get('avg_competitor_price')}")
        print(f"   Demand index: {features.get('demand_index')}")
        print("   ✅ Feature building OK")
    except Exception as e:
        print(f"   Error: {e}")
        # Use fallback features
        features = {
            'rental_length_days': 3.0,
            'day_of_week': 2.0,
            'month': 1.0,
            'base_daily_rate': 150.0,
            'avg_temp': 25.0,
            'rain': 0.0,
            'wind': 10.0,
            'avg_competitor_price': 160.0,
            'demand_index': 0.5,
            'bias': 1.0
        }
        print(f"   Using fallback features")

    # Test ML prediction
    print("\n2. ML Prediction:")
    try:
        ml_price = predict_price(features)
        print(f"   ML Predicted Price: {ml_price}")
        print("   ✅ ML prediction OK")
    except Exception as e:
        print(f"   ML prediction error: {e}")

    # Test rule engine
    print("\n3. Rule Engine:")
    try:
        rule_engine = PricingRuleEngine()
        print(f"   Rule engine loaded")
        print("   ✅ Rule engine OK")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "=" * 60)
    print("PRICING ENGINE TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_pricing())
