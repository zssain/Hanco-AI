"""
Test quote-time pricing engine

Tests the new /api/v1/pricing/quote endpoint that prices all available vehicles.

Usage:
    python test_quote_pricing.py
"""

import requests
from datetime import datetime, timedelta
import json

# API endpoint
BASE_URL = "http://localhost:8000"
QUOTE_ENDPOINT = f"{BASE_URL}/api/v1/pricing/quote"


def test_quote_pricing():
    """Test quote-time pricing with sample vehicles"""
    
    # Sample request
    pickup = datetime.now() + timedelta(days=3)
    dropoff = pickup + timedelta(days=5)  # 5-day rental
    
    request_data = {
        "branch_key": "riyadh",
        "pickup_at": pickup.isoformat(),
        "dropoff_at": dropoff.isoformat(),
        "vehicles": [
            {
                "vehicle_id": "vehicle_001",
                "class_bucket": "economy",
                "base_daily_rate": 120.0,
                "cost_per_day": 80.0,
                "branch_type": "City"
            },
            {
                "vehicle_id": "vehicle_002",
                "class_bucket": "sedan",
                "base_daily_rate": 180.0,
                "cost_per_day": 120.0,
                "branch_type": "City"
            },
            {
                "vehicle_id": "vehicle_003",
                "class_bucket": "suv",
                "base_daily_rate": 250.0,
                "cost_per_day": 170.0,
                "branch_type": "Airport"
            },
            {
                "vehicle_id": "vehicle_004",
                "class_bucket": "luxury",
                "base_daily_rate": 450.0,
                "cost_per_day": 300.0,
                "branch_type": "City"
            }
        ]
    }
    
    print("=" * 70)
    print("🚗 Testing Quote-Time Pricing Engine")
    print("=" * 70)
    print(f"\n📍 Branch: {request_data['branch_key']}")
    print(f"📅 Pickup: {pickup.strftime('%Y-%m-%d %H:%M')}")
    print(f"📅 Dropoff: {dropoff.strftime('%Y-%m-%d %H:%M')}")
    print(f"🔢 Vehicles: {len(request_data['vehicles'])}")
    print(f"\n{'Vehicle ID':<15} {'Class':<12} {'Base Rate':<12} {'Cost/Day':<12} {'Type':<10}")
    print("-" * 70)
    
    for v in request_data['vehicles']:
        print(f"{v['vehicle_id']:<15} {v['class_bucket']:<12} {v['base_daily_rate']:<12.2f} {v['cost_per_day']:<12.2f} {v['branch_type']:<10}")
    
    print("\n" + "=" * 70)
    print("🔄 Sending request to API...")
    print("=" * 70)
    
    try:
        response = requests.post(QUOTE_ENDPOINT, json=request_data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            
            print("\n✅ SUCCESS - Quote Generated")
            print("=" * 70)
            print(f"Quote ID: {result['quote_id']}")
            print(f"Duration: {result['duration_days']} days ({result['duration_key']})")
            print(f"Market Stats Available: {'Yes' if result['market_stats_available'] else 'No'}")
            print(f"Timestamp: {result['timestamp']}")
            
            print("\n💰 Pricing Results:")
            print("=" * 70)
            print(f"{'Vehicle ID':<15} {'Daily':<12} {'Total':<12} {'Cached':<10} {'Breakdown'}")
            print("-" * 70)
            
            for vehicle in result['vehicles']:
                cached_flag = "✓" if vehicle['cached'] else "✗"
                print(f"{vehicle['vehicle_id']:<15} {vehicle['daily_price']:<12.2f} {vehicle['total_price']:<12.2f} {cached_flag:<10} ", end="")
                
                if 'breakdown' in vehicle:
                    breakdown = vehicle['breakdown']
                    if 'ml_price' in breakdown:
                        print(f"ML:{breakdown['ml_price']:.0f} Rule:{breakdown['rule_price']:.0f} Final:{breakdown['final']:.0f}")
                    else:
                        print(json.dumps(breakdown))
                else:
                    print("N/A")
            
            # Show detailed breakdown for first vehicle
            if result['vehicles']:
                first = result['vehicles'][0]
                if 'breakdown' in first:
                    print("\n📊 Detailed Breakdown (First Vehicle):")
                    print("-" * 70)
                    breakdown = first['breakdown']
                    
                    if 'ml_price' in breakdown:
                        print(f"  ML Price:        {breakdown['ml_price']:.2f} SAR/day")
                        print(f"  Rule Price:      {breakdown['rule_price']:.2f} SAR/day")
                        print(f"  Blended (60/40): {breakdown['blended']:.2f} SAR/day")
                        print(f"  Floor:           {breakdown['floor']:.2f} SAR/day")
                        print(f"  Ceiling:         {breakdown['ceiling']:.2f} SAR/day")
                        print(f"  Final (rounded): {breakdown['final']:.2f} SAR/day")
                        
                        if breakdown.get('discounts'):
                            print(f"\n  Discounts Applied:")
                            for key, val in breakdown['discounts'].items():
                                print(f"    - {key}: {val*100:.0f}%")
                        
                        if breakdown.get('premiums'):
                            print(f"\n  Premiums Applied:")
                            for key, val in breakdown['premiums'].items():
                                print(f"    - {key}: {val*100:.0f}%")
            
            print("\n" + "=" * 70)
            print("✅ Test completed successfully")
            print("=" * 70)
            
        else:
            print(f"\n❌ ERROR: API returned status {response.status_code}")
            print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to API")
        print("Make sure the backend server is running:")
        print("  python -m uvicorn app.main:app --reload --port 8000")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")


def test_cache_behavior():
    """Test that caching works on second request"""
    
    print("\n\n" + "=" * 70)
    print("🔄 Testing Cache Behavior (2nd Request)")
    print("=" * 70)
    
    pickup = datetime.now() + timedelta(days=3)
    dropoff = pickup + timedelta(days=5)
    
    request_data = {
        "branch_key": "riyadh",
        "pickup_at": pickup.isoformat(),
        "dropoff_at": dropoff.isoformat(),
        "vehicles": [
            {
                "vehicle_id": "vehicle_001",
                "class_bucket": "economy",
                "base_daily_rate": 120.0,
                "cost_per_day": 80.0,
                "branch_type": "City"
            }
        ]
    }
    
    try:
        # First request
        print("\n1️⃣  First request (should compute)...")
        response1 = requests.post(QUOTE_ENDPOINT, json=request_data, timeout=30)
        result1 = response1.json()
        
        if result1['vehicles']:
            cached1 = result1['vehicles'][0]['cached']
            price1 = result1['vehicles'][0]['daily_price']
            print(f"   Cached: {cached1}, Price: {price1:.2f} SAR")
        
        # Second request (should use cache)
        print("\n2️⃣  Second request (should use cache)...")
        response2 = requests.post(QUOTE_ENDPOINT, json=request_data, timeout=30)
        result2 = response2.json()
        
        if result2['vehicles']:
            cached2 = result2['vehicles'][0]['cached']
            price2 = result2['vehicles'][0]['daily_price']
            print(f"   Cached: {cached2}, Price: {price2:.2f} SAR")
        
        # Verify caching worked
        if cached1 == False and cached2 == True and price1 == price2:
            print("\n✅ Cache is working correctly!")
        else:
            print(f"\n⚠️  Cache behavior unexpected: cached1={cached1}, cached2={cached2}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")


if __name__ == "__main__":
    # Run basic test
    test_quote_pricing()
    
    # Test caching
    test_cache_behavior()
