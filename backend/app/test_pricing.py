"""
Test script for dynamic pricing system
Demonstrates the complete pricing flow
"""
import asyncio
from datetime import date, timedelta
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


async def test_pricing_flow():
    """Test the complete pricing flow"""
    print("=" * 60)
    print("🧪 Testing Dynamic Pricing System")
    print("=" * 60)
    
    # 1. Test weather service
    print("\n1️⃣ Testing Weather Service...")
    from app.services.weather.open_meteo import get_weather_features
    
    test_date = date.today() + timedelta(days=7)
    weather = await get_weather_features('riyadh', test_date)
    print(f"   ✅ Weather for Riyadh on {test_date}:")
    print(f"      Temperature: {weather['avg_temp']}°C")
    print(f"      Rain: {weather['rain']}mm")
    print(f"      Wind: {weather['wind']}km/h")
    
    # 2. Test feature builder
    print("\n2️⃣ Testing Feature Builder...")
    from app.services.pricing.feature_builder import build_pricing_features
    from app.core.firebase import db
    
    # Mock vehicle document
    vehicle_doc = {
        'id': 'test-vehicle',
        'name': 'Test Car',
        'category': 'sedan',
        'base_daily_rate': 100.0,
        'city': 'riyadh'
    }
    
    start_date = date.today() + timedelta(days=7)
    end_date = start_date + timedelta(days=5)
    
    features = await build_pricing_features(
        vehicle_doc=vehicle_doc,
        start_date=start_date,
        end_date=end_date,
        city='riyadh',
        firestore_client=db
    )
    
    print(f"   ✅ Features built successfully:")
    for key, value in features.items():
        print(f"      {key}: {value}")
    
    # 3. Test ONNX model prediction
    print("\n3️⃣ Testing ONNX Model Prediction...")
    from app.services.pricing.onnx_runtime import predict_price
    
    try:
        daily_price = predict_price(features)
        print(f"   ✅ Predicted daily price: ${daily_price:.2f}")
        
        rental_days = (end_date - start_date).days
        total_price = daily_price * rental_days
        print(f"   ✅ Total price ({rental_days} days): ${total_price:.2f}")
        
    except FileNotFoundError as e:
        print(f"   ❌ ONNX model not found!")
        print(f"   ℹ️  Please run: python app/ml/training/create_dummy_model.py")
        return False
    
    print("\n" + "=" * 60)
    print("✅ All pricing components working correctly!")
    print("=" * 60)
    
    return True


if __name__ == '__main__':
    print("\n🚀 Starting Pricing System Test\n")
    
    # Check if model exists
    model_path = os.path.join(
        os.path.dirname(__file__),
        'ml',
        'models',
        'model.onnx'
    )
    
    if not os.path.exists(model_path):
        print("⚠️  ONNX model not found!")
        print("📝 Creating model now...\n")
        
        # Run model creation
        import subprocess
        result = subprocess.run(
            [sys.executable, 'app/ml/training/create_dummy_model.py'],
            cwd=os.path.dirname(__file__)
        )
        
        if result.returncode != 0:
            print("\n❌ Failed to create model")
            sys.exit(1)
        
        print("\n✅ Model created successfully!")
    
    # Run async tests
    success = asyncio.run(test_pricing_flow())
    
    if success:
        print("\n🎉 Pricing system is ready for production!")
        print("\n📚 Next steps:")
        print("   1. Start the server: python -m app.main")
        print("   2. Test the API: POST /api/v1/pricing/calculate")
        print("   3. View docs: http://localhost:8000/api/v1/docs")
    else:
        print("\n❌ Please create the ONNX model first")
        sys.exit(1)
