"""
Fix Data Consistency - Update vehicles with proper branch_ids
"""
from datetime import datetime
from app.core.firebase import db, Collections

def fix_vehicle_branch_ids():
    """Map vehicle locations to branch_ids"""
    
    # Location to branch_id mapping
    location_to_branch = {
        "Riyadh Airport": "riyadh_airport",
        "Riyadh Olaya": "riyadh_olaya",
        "Riyadh Malaz": "riyadh_malaz",
        "Riyadh City Center": "riyadh_olaya",  # Map to Olaya
        "Jeddah Airport": "jeddah_airport",
        "Jeddah Corniche": "jeddah_corniche",
        "Jeddah City Center": "jeddah_corniche",  # Map to corniche
        "Jeddah Red Sea Mall": "jeddah_redsea",
        "Dammam Airport": "dammam_airport",
        "Dammam Corniche": "dammam_corniche",
        "Dammam City Center": "dammam_corniche",  # Map to corniche
    }
    
    print("=" * 60)
    print("FIXING VEHICLE BRANCH_IDs")
    print("=" * 60)
    
    vehicles = db.collection(Collections.VEHICLES).stream()
    updated_count = 0
    
    for v in vehicles:
        data = v.to_dict()
        location = data.get("location")
        current_branch = data.get("branch_id")
        
        if current_branch is None and location:
            # Find matching branch
            new_branch_id = location_to_branch.get(location)
            
            if not new_branch_id:
                # Try partial match
                for loc_key, branch_id in location_to_branch.items():
                    if loc_key.lower() in location.lower() or location.lower() in loc_key.lower():
                        new_branch_id = branch_id
                        break
            
            if new_branch_id:
                print(f"  Updating {v.id}: location='{location}' -> branch_id='{new_branch_id}'")
                db.collection(Collections.VEHICLES).document(v.id).update({
                    "branch_id": new_branch_id
                })
                updated_count += 1
            else:
                print(f"  ⚠️ No match for {v.id}: location='{location}'")
    
    print(f"\n✅ Updated {updated_count} vehicles with branch_ids")
    return updated_count


def fix_ml_model_registry():
    """Ensure baseline_pricing_model has active_version set"""
    
    print("\n" + "=" * 60)
    print("FIXING ML MODEL REGISTRY")
    print("=" * 60)
    
    # Check if baseline_pricing_model exists
    model_ref = db.collection(Collections.ML_MODELS).document("baseline_pricing_model")
    model_doc = model_ref.get()
    
    if not model_doc.exists:
        print("  Creating baseline_pricing_model registry entry...")
        model_ref.set({
            "model_name": "baseline_pricing_model",
            "description": "Baseline pricing model for vehicle rentals",
            "created_at": datetime.utcnow().isoformat(),
            "active_version": {
                "version": "1.0.0",
                "storage_path": None,  # Will use local fallback
                "deployed_at": datetime.utcnow().isoformat()
            }
        })
        print("  ✅ Created baseline_pricing_model registry")
    else:
        data = model_doc.to_dict()
        if not data.get("active_version") or not data["active_version"].get("version"):
            print("  Updating active_version...")
            model_ref.update({
                "active_version": {
                    "version": "1.0.0",
                    "storage_path": None,
                    "deployed_at": datetime.utcnow().isoformat()
                }
            })
            print("  ✅ Updated active_version")
        else:
            print(f"  ✅ Model already has active_version: {data['active_version'].get('version')}")


if __name__ == "__main__":
    fix_vehicle_branch_ids()
    fix_ml_model_registry()
    print("\n" + "=" * 60)
    print("DATA FIX COMPLETE")
    print("=" * 60)
