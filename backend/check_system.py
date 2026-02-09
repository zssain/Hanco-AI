"""
System Check Script - Verifies all components are working
"""
from app.core.firebase import db, Collections
import os

def check_firebase():
    print("=" * 60)
    print("FIREBASE CONNECTIVITY CHECK")
    print("=" * 60)
    
    # 1. Branches
    print("\n1. BRANCHES COLLECTION:")
    branches = list(db.collection(Collections.BRANCHES).limit(10).stream())
    print(f"   Found: {len(branches)} branches")
    branch_cities = set()
    branch_ids = set()
    for b in branches:
        data = b.to_dict()
        branch_cities.add(data.get("city"))
        branch_ids.add(b.id)
        print(f"   - {b.id}: {data.get('name')}, City: {data.get('city')}")
    
    # 2. Vehicles
    print("\n2. VEHICLES COLLECTION:")
    vehicles = list(db.collection(Collections.VEHICLES).limit(15).stream())
    print(f"   Found: {len(vehicles)} vehicles")
    vehicle_locations = set()
    vehicle_branches = set()
    for v in vehicles[:5]:
        data = v.to_dict()
        vehicle_locations.add(data.get("location"))
        vehicle_branches.add(data.get("branch_id"))
        print(f"   - {v.id}: {data.get('name')}, Location: {data.get('location')}, Branch: {data.get('branch_id')}")
    
    # 3. Competitor Prices
    print("\n3. COMPETITOR_PRICES_LATEST COLLECTION:")
    try:
        prices = list(db.collection("competitor_prices_latest").limit(5).stream())
        print(f"   Found: {len(prices)} cached competitor prices")
        for p in prices[:3]:
            data = p.to_dict()
            print(f"   - Branch: {data.get('branch_id')}, Class: {data.get('vehicle_class')}, Avg: {data.get('avg_price')}")
    except Exception as e:
        print(f"   Warning: {e}")
    
    # 4. ML Models Registry
    print("\n4. ML_MODELS COLLECTION:")
    try:
        models = list(db.collection(Collections.ML_MODELS).stream())
        print(f"   Found: {len(models)} models registered")
        for m in models:
            data = m.to_dict()
            active = data.get("active_version", {})
            print(f"   - {m.id}: Version {active.get('version', 'N/A')}, Path: {active.get('storage_path', 'N/A')}")
    except Exception as e:
        print(f"   Warning: {e}")
    
    # 5. Bookings
    print("\n5. BOOKINGS COLLECTION:")
    bookings = list(db.collection(Collections.BOOKINGS).limit(5).stream())
    print(f"   Found: {len(bookings)} bookings")
    
    # 6. Pricing Decisions
    print("\n6. PRICING_DECISIONS COLLECTION (Audit Log):")
    try:
        decisions = list(db.collection("pricing_decisions").limit(3).stream())
        print(f"   Found: {len(decisions)} pricing decisions logged")
    except Exception as e:
        print(f"   Warning: {e}")
    
    # 7. Data Consistency Check
    print("\n" + "=" * 60)
    print("DATA CONSISTENCY CHECK")
    print("=" * 60)
    
    print(f"\nBranch Cities: {sorted(branch_cities)}")
    print(f"Branch IDs: {sorted(branch_ids)}")
    print(f"Vehicle Locations: {sorted(vehicle_locations)}")
    print(f"Vehicle Branch IDs: {sorted(vehicle_branches)}")
    
    # Check if vehicle branch_ids match actual branch IDs
    orphan_branches = vehicle_branches - branch_ids - {None}
    if orphan_branches:
        print(f"\n⚠️  WARNING: Vehicles reference non-existent branches: {orphan_branches}")
    else:
        print(f"\n✅ All vehicle branch_ids match existing branches")
    
    return len(branches), len(vehicles)


def check_workers():
    print("\n" + "=" * 60)
    print("WORKER SCRIPTS CHECK")
    print("=" * 60)
    
    workers = [
        "app/workers/scrape_competitors.py",
        "app/workers/train_models.py",
        "app/workers/release_reservations.py",
        "app/workers/cleanup_firestore.py"
    ]
    
    for worker in workers:
        exists = os.path.exists(worker)
        status = "✅" if exists else "❌"
        print(f"   {status} {worker}")


def check_pricing_engine():
    print("\n" + "=" * 60)
    print("PRICING ENGINE CHECK")
    print("=" * 60)
    
    try:
        from app.services.pricing.onnx_runtime import predict_price, get_model_cache
        from app.services.pricing.rule_engine import PricingRuleEngine
        from app.services.pricing.feature_builder import build_pricing_features
        
        print("   ✅ ONNX Runtime imported successfully")
        print("   ✅ Rule Engine imported successfully")
        print("   ✅ Feature Builder imported successfully")
        
        # Check if model exists locally
        import os
        model_paths = [
            "app/ml/models/model.onnx",
            "ml/models/model.onnx"
        ]
        for path in model_paths:
            if os.path.exists(path):
                print(f"   ✅ Local ONNX model found: {path}")
                break
        else:
            print("   ⚠️  No local ONNX model found (will use Firebase Storage)")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")


def check_chatbot():
    print("\n" + "=" * 60)
    print("CHATBOT CHECK")
    print("=" * 60)
    
    try:
        from app.services.chatbot.orchestrator import ChatbotOrchestrator
        print("   ✅ ChatbotOrchestrator imported successfully")
        
        from app.core.config import settings
        if settings.GEMINI_API_KEY:
            print("   ✅ Gemini API Key configured")
        else:
            print("   ⚠️  Gemini API Key NOT configured")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")


if __name__ == "__main__":
    check_firebase()
    check_workers()
    check_pricing_engine()
    check_chatbot()
    
    print("\n" + "=" * 60)
    print("SYSTEM CHECK COMPLETE")
    print("=" * 60)
