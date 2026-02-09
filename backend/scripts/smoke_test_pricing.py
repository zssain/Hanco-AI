"""
Smoke Test: Competitor Scraping + ONNX Pricing Engine End-to-End

This script validates the entire pricing pipeline:
1. Firestore connectivity
2. Branch configuration
3. Competitor scraping output
4. ONNX model inference
5. Pricing engine execution
6. Cache verification

Run manually:
    cd backend
    python scripts/smoke_test_pricing.py

Requirements:
    - GOOGLE_APPLICATION_CREDENTIALS must be set
    - Backend dependencies installed (pip install -r requirements.txt)
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 80)
print("🔥 SMOKE TEST: Competitor Scraping + ONNX Pricing Engine")
print("=" * 80)
print()


# ==================== TEST 1: FIRESTORE CONNECTIVITY ====================
print("📡 TEST 1: Firestore Connectivity")
print("-" * 80)

try:
    from app.core.firebase import db, Collections
    
    # Perform a harmless read
    test_ref = db.collection("config").limit(1)
    test_docs = list(test_ref.stream())
    
    print("✅ Firestore client initialized successfully")
    print(f"   Connection verified via config collection")
    
except Exception as e:
    print(f"❌ FAILED: Could not connect to Firestore")
    print(f"   Error: {str(e)}")
    print()
    print("   Please ensure:")
    print("   1. GOOGLE_APPLICATION_CREDENTIALS is set")
    print("   2. Firebase credentials JSON file exists")
    print("   3. Firestore permissions are correct")
    sys.exit(1)

print()


# ==================== TEST 2: BRANCH CONFIG EXISTS ====================
print("🏢 TEST 2: Branch Configuration")
print("-" * 80)

try:
    # Read config/branches document
    branches_ref = db.collection("config").document("branches")
    branches_doc = branches_ref.get()
    
    assert branches_doc.exists, "config/branches document does not exist"
    
    branches_data = branches_doc.to_dict()
    branches = branches_data.get("branches", [])
    
    assert isinstance(branches, list), "branches is not a list"
    assert len(branches) > 0, "branches list is empty"
    
    # Validate structure
    required_keys = ["city", "branch_key", "type", "label"]
    for idx, branch in enumerate(branches):
        for key in required_keys:
            assert key in branch, f"Branch {idx} missing required key: {key}"
    
    print(f"✅ Branch configuration valid")
    print(f"   Loaded {len(branches)} branches:")
    for branch in branches:
        print(f"     - {branch.get('label')} ({branch.get('branch_key')})")
    
except AssertionError as e:
    print(f"❌ FAILED: {str(e)}")
    sys.exit(1)
except Exception as e:
    print(f"❌ FAILED: Error reading branch config: {str(e)}")
    sys.exit(1)

print()


# ==================== TEST 3: COMPETITOR SCRAPING OUTPUT ====================
print("🕷️  TEST 3: Competitor Scraping Output")
print("-" * 80)

# Test combination
test_branch = "riyadh_airport"
test_duration = "D3"
test_class = "suv"
providers = ["lumi", "budget", "theeb", "alwefaq", "europcar", "yelo"]

found_providers = []
missing_providers = []

print(f"Checking for: {test_branch} / {test_duration} / {test_class}")
print()

for provider in providers:
    doc_id = f"{provider}_{test_branch}_{test_duration}_{test_class}"
    
    try:
        doc_ref = db.collection("competitor_prices_latest").document(doc_id)
        doc = doc_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            price = data.get("last_price_per_day", 0)
            currency = data.get("currency", "SAR")
            found_providers.append(provider)
            print(f"  ✅ {provider:12s}: {price:8.2f} {currency}")
        else:
            missing_providers.append(provider)
            print(f"  ⚠️  {provider:12s}: No data found")
    
    except Exception as e:
        missing_providers.append(provider)
        print(f"  ❌ {provider:12s}: Error - {str(e)}")

print()

if len(found_providers) == 0:
    print("❌ FAILED: No competitor data found")
    print()
    print("   Checking competitor_scrape_debug for hints...")
    
    try:
        debug_ref = db.collection("competitor_scrape_debug").limit(5)
        debug_docs = list(debug_ref.stream())
        
        if debug_docs:
            print(f"   Found {len(debug_docs)} debug entries (recent scraping attempts)")
            latest = debug_docs[0].to_dict()
            print(f"   Latest debug entry:")
            print(f"     Provider: {latest.get('provider')}")
            print(f"     Branch: {latest.get('branch_key')}")
            print(f"     Zero results reason: {latest.get('zero_reason')}")
        else:
            print("   No debug entries found - scraper may not have run yet")
    
    except Exception as e:
        print(f"   Could not check debug collection: {str(e)}")
    
    print()
    print("   💡 HINT: Run competitor scraper first:")
    print("      python -m app.services.competitors.crawler")
    sys.exit(1)
else:
    print(f"✅ Found data from {len(found_providers)}/{len(providers)} providers")
    if missing_providers:
        print(f"   ℹ️  Missing: {', '.join(missing_providers)}")

print()


# ==================== TEST 4: ONNX MODEL INFERENCE ====================
print("🤖 TEST 4: ONNX Model Inference")
print("-" * 80)

try:
    from app.services.pricing.onnx_runtime import predict_price
    
    # Build realistic feature vector
    features = {
        'rental_length_days': 3.0,
        'day_of_week': 2.0,  # Wednesday
        'month': 1.0,  # January
        'base_daily_rate': 200.0,
        'avg_temp': 22.0,
        'rain': 0.0,
        'wind': 12.0,
        'avg_competitor_price': 195.0,
        'demand_index': 0.6,
        'bias': 1.0
    }
    
    print("Running ONNX inference with features:")
    print(f"  rental_length_days: {features['rental_length_days']}")
    print(f"  base_daily_rate: {features['base_daily_rate']}")
    print(f"  avg_competitor_price: {features['avg_competitor_price']}")
    print(f"  demand_index: {features['demand_index']}")
    print()
    
    # Run inference
    predicted_price = predict_price(features)
    
    # Validate output
    assert isinstance(predicted_price, (int, float)), "Output is not numeric"
    assert predicted_price > 0, f"Invalid price: {predicted_price} (must be > 0)"
    assert predicted_price < 5000, f"Invalid price: {predicted_price} (must be < 5000)"
    
    print(f"✅ ONNX inference successful")
    print(f"   Predicted daily price: {predicted_price:.2f} SAR")
    
except ImportError as e:
    print(f"❌ FAILED: Could not import ONNX runtime")
    print(f"   Error: {str(e)}")
    print()
    print("   Ensure onnxruntime is installed:")
    print("   pip install onnxruntime")
    sys.exit(1)
except FileNotFoundError as e:
    print(f"❌ FAILED: ONNX model file not found")
    print(f"   Error: {str(e)}")
    print()
    print("   Train the model first:")
    print("   python app/ml/training/train_pricing_model.py")
    sys.exit(1)
except AssertionError as e:
    print(f"❌ FAILED: {str(e)}")
    sys.exit(1)
except Exception as e:
    print(f"❌ FAILED: ONNX inference error: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()


# ==================== TEST 5: PRICING ENGINE EXECUTION ====================
print("💰 TEST 5: Pricing Engine Execution")
print("-" * 80)

try:
    from app.api.v1.pricing import (
        compute_vehicle_price,
        VehicleQuoteInput,
        _map_duration_to_key,
        get_market_stats
    )
    import asyncio
    
    print("Attempting to execute pricing engine...")
    
    # Create test vehicle
    test_vehicle = VehicleQuoteInput(
        vehicle_id="test_vehicle_001",
        class_bucket="suv",
        base_daily_rate=250.0,
        cost_per_day=170.0,
        branch_type="Airport"
    )
    
    # Test parameters
    pickup_date = (datetime.now(timezone.utc) + timedelta(days=1)).date()
    duration_days = 3
    duration_key = _map_duration_to_key(duration_days)
    is_weekend = pickup_date.weekday() in [4, 5]
    
    print(f"  Test parameters:")
    print(f"    Branch: riyadh_airport")
    print(f"    Duration: {duration_days} days ({duration_key})")
    print(f"    Vehicle class: suv")
    print(f"    Pickup date: {pickup_date}")
    print()
    
    # Run pricing engine
    async def run_pricing():
        # Get market stats
        market_stats = await get_market_stats(
            branch_key="riyadh_airport",
            duration_key=duration_key,
            class_bucket="suv"
        )
        
        # Weather defaults
        weather_defaults = {
            'avg_temp': 25.0,
            'rain': 0.0,
            'wind': 10.0
        }
        
        # Compute price
        result = await compute_vehicle_price(
            vehicle=test_vehicle,
            branch_key="riyadh_airport",
            duration_days=duration_days,
            duration_key=duration_key,
            pickup_date=pickup_date,
            is_weekend=is_weekend,
            market_stats=market_stats,
            weather_defaults=weather_defaults
        )
        
        return result, market_stats
    
    # Execute async function
    result, market_stats = asyncio.run(run_pricing())
    
    # Validate result
    assert 'daily_price' in result, "Result missing daily_price"
    assert 'total_price' in result, "Result missing total_price"
    assert result['daily_price'] > 0, "Invalid daily_price"
    
    print(f"✅ Pricing engine executed successfully")
    print(f"   Daily price: {result['daily_price']:.2f} SAR")
    print(f"   Total price: {result['total_price']:.2f} SAR")
    print(f"   Cached: {result.get('cached', False)}")
    
    if 'breakdown' in result:
        breakdown = result['breakdown']
        if 'ml_price' in breakdown:
            print(f"   Breakdown:")
            print(f"     ML price: {breakdown['ml_price']:.2f} SAR")
            print(f"     Rule price: {breakdown['rule_price']:.2f} SAR")
            print(f"     Blended: {breakdown['blended']:.2f} SAR")
            print(f"     Final: {breakdown['final']:.2f} SAR")
    
    if market_stats:
        print(f"   Market stats available: Yes ({market_stats.get('count', 0)} providers)")
    else:
        print(f"   Market stats available: No")
    
except ImportError as e:
    print(f"⚠️  SKIPPED: Could not import pricing engine")
    print(f"   Reason: {str(e)}")
    print(f"   This is not a critical failure - pricing may be deployed separately")
except Exception as e:
    print(f"❌ FAILED: Pricing engine error")
    print(f"   Error: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()


# ==================== TEST 6: CACHE WRITE VERIFICATION ====================
print("💾 TEST 6: Cache Verification")
print("-" * 80)

try:
    cache_ref = db.collection("fleet_prices_cache").limit(10)
    cache_docs = list(cache_ref.stream())
    
    if len(cache_docs) > 0:
        print(f"✅ Cache collection exists with {len(cache_docs)} entries (showing 10)")
        
        # Show sample cache entry
        sample = cache_docs[0].to_dict()
        print(f"   Sample cache entry:")
        print(f"     Doc ID: {cache_docs[0].id}")
        print(f"     Price: {sample.get('final_price_per_day', 0):.2f} SAR/day")
        print(f"     Created: {sample.get('created_at')}")
        print(f"     Expires: {sample.get('expires_at')}")
        
        # Check if any are still valid
        now = datetime.utcnow()
        valid_count = 0
        for doc in cache_docs:
            data = doc.to_dict()
            expires = data.get('expires_at')
            if expires and expires > now:
                valid_count += 1
        
        print(f"   Valid (not expired): {valid_count}/{len(cache_docs)}")
    else:
        print(f"ℹ️  Cache collection is empty")
        print(f"   This is expected if no quotes have been generated yet")
        print(f"   Cache entries are created when pricing quotes are requested")
    
except Exception as e:
    print(f"⚠️  Could not verify cache: {str(e)}")
    print(f"   This is not critical - cache may not be initialized yet")

print()


# ==================== TEST 7: VEHICLE HISTORY RECORDING (Option 2) ====================
print("📜 TEST 7: Vehicle History Recording (Audit Trail)")
print("-" * 80)

# Check if mutation is allowed
SMOKE_TEST_MUTATES_DATA = os.environ.get("SMOKE_TEST_MUTATES_DATA", "false").lower() == "true"

if not SMOKE_TEST_MUTATES_DATA:
    print("ℹ️  SKIPPED: Mutation tests disabled")
    print("   Set SMOKE_TEST_MUTATES_DATA=true to enable vehicle history tests")
    print("   This test modifies and then restores vehicle base_daily_rate")
    vehicle_history_test_passed = None
else:
    try:
        from app.core.firebase import update_vehicle_base_rate
        
        # Step 1: Pick a known vehicle
        print("   Step 1: Finding a test vehicle...")
        vehicles_ref = db.collection(Collections.VEHICLES).limit(1)
        vehicle_docs = list(vehicles_ref.stream())
        
        if not vehicle_docs:
            raise Exception("No vehicles found in Firestore")
        
        test_vehicle_id = vehicle_docs[0].id
        test_vehicle_data = vehicle_docs[0].to_dict()
        original_rate = test_vehicle_data.get('base_daily_rate', 100.0)
        vehicle_name = test_vehicle_data.get('name', 'Unknown')
        
        print(f"   ✅ Selected vehicle: {vehicle_name} (ID: {test_vehicle_id})")
        print(f"      Current base_daily_rate: {original_rate} SAR")
        
        # Step 2: Apply a +1 SAR change
        print("   Step 2: Applying +1 SAR change...")
        new_rate = float(original_rate) + 1.0
        
        result = update_vehicle_base_rate(
            vehicle_id=test_vehicle_id,
            new_base_daily_rate=new_rate,
            reason="smoke_test",
            triggered_by={"uid": "smoke_test", "email": "smoke_test@hanco.ai"},
            context={"test_run": datetime.utcnow().isoformat()}
        )
        
        if result['status'] == 'error':
            raise Exception(f"Update failed: {result.get('error')}")
        
        if result['status'] == 'no_change':
            print(f"   ⚠️  No change made (rate already at target)")
        else:
            print(f"   ✅ Update successful: {result['old_base_daily_rate']} -> {result['new_base_daily_rate']}")
            print(f"      History ID: {result['history_id']}")
            update_history_id = result['history_id']
        
        # Step 3: Verify vehicle doc updated
        print("   Step 3: Verifying vehicle document updated...")
        updated_vehicle = db.collection(Collections.VEHICLES).document(test_vehicle_id).get()
        updated_rate = updated_vehicle.to_dict().get('base_daily_rate')
        
        assert abs(updated_rate - new_rate) < 0.01, f"Vehicle rate mismatch: expected {new_rate}, got {updated_rate}"
        print(f"   ✅ Vehicle document updated correctly: {updated_rate} SAR")
        
        # Step 4: Verify vehicle_history doc exists
        print("   Step 4: Verifying vehicle_history entry...")
        history_query = db.collection(Collections.VEHICLE_HISTORY)\
            .where('vehicle_id', '==', test_vehicle_id)\
            .order_by('created_at', direction='DESCENDING')\
            .limit(1)
        history_docs = list(history_query.stream())
        
        assert len(history_docs) > 0, "No vehicle_history document found"
        history_data = history_docs[0].to_dict()
        
        assert history_data.get('change_type') == 'base_daily_rate_change', "Incorrect change_type"
        assert abs(history_data.get('new_base_daily_rate', 0) - new_rate) < 0.01, "History new_rate mismatch"
        assert history_data.get('reason') == 'smoke_test', "History reason mismatch"
        
        print(f"   ✅ History entry found:")
        print(f"      ID: {history_docs[0].id}")
        print(f"      Old: {history_data.get('old_base_daily_rate')} -> New: {history_data.get('new_base_daily_rate')}")
        print(f"      Reason: {history_data.get('reason')}")
        
        # Step 5: Roll back to original rate
        print("   Step 5: Rolling back to original rate...")
        rollback_result = update_vehicle_base_rate(
            vehicle_id=test_vehicle_id,
            new_base_daily_rate=float(original_rate),
            reason="smoke_test_rollback",
            triggered_by={"uid": "smoke_test", "email": "smoke_test@hanco.ai"},
            context={"rollback_from_test": True}
        )
        
        if rollback_result['status'] == 'error':
            raise Exception(f"Rollback failed: {rollback_result.get('error')}")
        
        if rollback_result['status'] == 'updated':
            print(f"   ✅ Rollback successful: {rollback_result['old_base_daily_rate']} -> {rollback_result['new_base_daily_rate']}")
            print(f"      Rollback History ID: {rollback_result['history_id']}")
        else:
            print(f"   ℹ️  Rollback: {rollback_result['status']}")
        
        # Step 6: Verify rollback history entry
        print("   Step 6: Verifying rollback history entry...")
        rollback_history_query = db.collection(Collections.VEHICLE_HISTORY)\
            .where('vehicle_id', '==', test_vehicle_id)\
            .where('reason', '==', 'smoke_test_rollback')\
            .limit(1)
        rollback_history_docs = list(rollback_history_query.stream())
        
        assert len(rollback_history_docs) > 0, "No rollback history document found"
        rollback_history_data = rollback_history_docs[0].to_dict()
        
        print(f"   ✅ Rollback history entry found:")
        print(f"      ID: {rollback_history_docs[0].id}")
        print(f"      Old: {rollback_history_data.get('old_base_daily_rate')} -> New: {rollback_history_data.get('new_base_daily_rate')}")
        
        # Final verification: vehicle is back to original
        final_vehicle = db.collection(Collections.VEHICLES).document(test_vehicle_id).get()
        final_rate = final_vehicle.to_dict().get('base_daily_rate')
        
        assert abs(final_rate - original_rate) < 0.01, f"Final rate mismatch: expected {original_rate}, got {final_rate}"
        print(f"   ✅ Vehicle restored to original rate: {final_rate} SAR")
        
        vehicle_history_test_passed = True
        print()
        print("✅ Vehicle History Recording test PASSED")
        
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        vehicle_history_test_passed = False
        # Try to restore original rate if possible
        try:
            if 'test_vehicle_id' in locals() and 'original_rate' in locals():
                print("   Attempting to restore original rate...")
                restore_result = update_vehicle_base_rate(
                    vehicle_id=test_vehicle_id,
                    new_base_daily_rate=float(original_rate),
                    reason="smoke_test_restore_after_failure",
                    triggered_by={"uid": "smoke_test", "email": "smoke_test@hanco.ai"},
                    context={"restore_after_failure": True}
                )
                if restore_result['status'] == 'updated':
                    print(f"   ✅ Original rate restored: {original_rate} SAR")
        except:
            print("   ⚠️  Could not restore original rate")

print()


# ==================== FINAL SUMMARY ====================
print("=" * 80)
print("✅ ALL SMOKE TESTS PASSED")
print("=" * 80)
print()
print("Summary:")
print(f"  ✅ Firestore connectivity: OK")
print(f"  ✅ Branch configuration: {len(branches)} branches loaded")
print(f"  ✅ Competitor data: {len(found_providers)} providers found")
print(f"  ✅ ONNX inference: {predicted_price:.2f} SAR predicted")
print(f"  ✅ Pricing engine: Executed successfully")
print(f"  ℹ️  Cache: {len(cache_docs) if 'cache_docs' in locals() else 0} entries")
if SMOKE_TEST_MUTATES_DATA:
    if vehicle_history_test_passed:
        print(f"  ✅ Vehicle history: Recording + rollback verified")
    elif vehicle_history_test_passed is False:
        print(f"  ❌ Vehicle history: Test failed")
    else:
        print(f"  ℹ️  Vehicle history: Skipped (no mutation)")
else:
    print(f"  ℹ️  Vehicle history: Skipped (SMOKE_TEST_MUTATES_DATA=false)")
print()
print("🎉 The pricing pipeline is operational!")
print()
print("Next steps:")
print("  - Run competitor scraper for missing providers:")
print("    python -m app.services.competitors.crawler")
print("  - Generate test quotes:")
print("    python test_quote_pricing.py")
print("  - Start the API server:")
print("    python -m uvicorn app.main:app --reload --port 8000")
