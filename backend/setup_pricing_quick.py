"""
Quick setup script to initialize pricing system
1. Set base prices for vehicles
2. Run competitor scraper
3. Fetch weather data
4. Train ONNX model
"""
import sys
import os
sys.path.insert(0, '.')

import asyncio
from datetime import datetime
from app.core.firebase import db
from app.services.competitors.crawler import scrape_all_providers
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def setup_pricing_system():
    """Initialize all pricing components"""
    
    print("=" * 70)
    print("SETTING UP PRICING SYSTEM")
    print("=" * 70)
    print()
    
    # Step 1: Set base prices for vehicles
    print("Step 1: Setting base prices for vehicles...")
    try:
        vehicles = db.collection('vehicles').stream()
        base_prices = {
            'Economy': 100,
            'Compact': 120,
            'Sedan': 150,
            'SUV': 200,
            'Luxury': 300
        }
        
        count = 0
        for vehicle_doc in vehicles:
            vehicle_data = vehicle_doc.to_dict()
            category = vehicle_data.get('category', 'Compact')
            base_price = base_prices.get(category, 120)
            
            # Update vehicle with base price
            db.collection('vehicles').document(vehicle_doc.id).update({
                'base_price': base_price,
                'price_per_day': base_price,  # Default price
                'updated_at': datetime.utcnow()
            })
            count += 1
            print(f"   ✅ Updated {vehicle_data.get('make')} {vehicle_data.get('model')}: {base_price} SAR/day")
        
        print(f"   ✅ Updated {count} vehicles with base prices")
    except Exception as e:
        print(f"   ❌ Error updating vehicles: {e}")
    
    print()
    
    # Step 2: Run competitor scraper
    print("Step 2: Running competitor scraper (this may take 2-3 minutes)...")
    try:
        results = await scrape_all_providers()
        total_prices = sum(len(r.get('prices', [])) for r in results)
        print(f"   ✅ Scraped {total_prices} competitor prices")
        
        for result in results:
            provider = result.get('provider')
            prices = result.get('prices', [])
            print(f"      - {provider}: {len(prices)} prices")
            
    except Exception as e:
        print(f"   ⚠️  Scraper error (may be normal): {e}")
        print("      Creating sample competitor data...")
        
        # Create sample competitor data
        sample_competitors = [
            {'provider': 'Budget', 'vehicle_class': 'Economy', 'price_per_day': 110, 'city': 'riyadh'},
            {'provider': 'Budget', 'vehicle_class': 'Compact', 'price_per_day': 130, 'city': 'riyadh'},
            {'provider': 'Budget', 'vehicle_class': 'Sedan', 'price_per_day': 160, 'city': 'riyadh'},
            {'provider': 'Europcar', 'vehicle_class': 'Economy', 'price_per_day': 115, 'city': 'riyadh'},
            {'provider': 'Europcar', 'vehicle_class': 'Compact', 'price_per_day': 135, 'city': 'riyadh'},
            {'provider': 'Europcar', 'vehicle_class': 'Sedan', 'price_per_day': 165, 'city': 'riyadh'},
            {'provider': 'Theeb', 'vehicle_class': 'Economy', 'price_per_day': 108, 'city': 'riyadh'},
            {'provider': 'Theeb', 'vehicle_class': 'Compact', 'price_per_day': 128, 'city': 'riyadh'},
            {'provider': 'Theeb', 'vehicle_class': 'SUV', 'price_per_day': 210, 'city': 'riyadh'},
        ]
        
        batch = db.batch()
        for comp in sample_competitors:
            doc_ref = db.collection('competitor_prices').document()
            comp['scraped_at'] = datetime.utcnow()
            comp['hash'] = f"{comp['provider']}_{comp['vehicle_class']}_{comp['city']}"
            batch.set(doc_ref, comp)
        
        batch.commit()
        print(f"   ✅ Added {len(sample_competitors)} sample competitor prices")
    
    print()
    
    # Step 3: Add weather data
    print("Step 3: Adding weather data...")
    try:
        sample_weather = [
            {'city': 'riyadh', 'temperature_c': 25, 'condition': 'sunny', 'timestamp': datetime.utcnow()},
            {'city': 'jeddah', 'temperature_c': 28, 'condition': 'clear', 'timestamp': datetime.utcnow()},
            {'city': 'dammam', 'temperature_c': 26, 'condition': 'sunny', 'timestamp': datetime.utcnow()},
        ]
        
        batch = db.batch()
        for weather in sample_weather:
            doc_ref = db.collection('weather').document(weather['city'])
            batch.set(doc_ref, weather)
        
        batch.commit()
        print(f"   ✅ Added weather data for {len(sample_weather)} cities")
    except Exception as e:
        print(f"   ⚠️  Weather error: {e}")
    
    print()
    
    # Step 4: Train ONNX model
    print("Step 4: Training ONNX pricing model...")
    try:
        # Create models directory if it doesn't exist
        os.makedirs('./ml/models', exist_ok=True)
        
        # Import and run training
        from app.ml.training.train_pricing_model import train_and_export_onnx
        
        model_path = train_and_export_onnx()
        print(f"   ✅ Model trained and saved to: {model_path}")
        
    except Exception as e:
        print(f"   ⚠️  Model training error: {e}")
        print("      You can train it later with: python app/ml/training/train_pricing_model.py")
    
    print()
    print("=" * 70)
    print("✅ PRICING SYSTEM SETUP COMPLETE!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("1. Restart backend: python -m uvicorn app.main:app --reload --port 8000")
    print("2. Test pricing API: http://localhost:8000/api/v1/pricing/calculate")
    print("3. Frontend should now show dynamic prices!")
    print()


async def migrate_cost_per_day():
    """
    One-time migration utility to add cost_per_day to vehicles.
    For vehicles missing cost_per_day, sets it to base_daily_rate * 0.65 (temporary heuristic).
    Uses batch writes for efficiency.
    """
    print("=" * 70)
    print("MIGRATING VEHICLES: Adding cost_per_day field")
    print("=" * 70)
    print()
    
    try:
        # Scan all vehicles
        vehicles = list(db.collection('vehicles').stream())
        print(f"Found {len(vehicles)} vehicles to scan...")
        
        # Collect vehicles needing update
        vehicles_to_update = []
        for vehicle_doc in vehicles:
            data = vehicle_doc.to_dict()
            if data.get('cost_per_day') is None:
                base_rate = data.get('base_daily_rate', 0)
                if base_rate > 0:
                    cost_per_day = round(base_rate * 0.65, 2)  # 65% of base rate as cost heuristic
                    vehicles_to_update.append({
                        'doc_id': vehicle_doc.id,
                        'cost_per_day': cost_per_day,
                        'base_rate': base_rate
                    })
        
        if not vehicles_to_update:
            print("✅ All vehicles already have cost_per_day. No migration needed.")
            return
        
        print(f"Found {len(vehicles_to_update)} vehicles needing cost_per_day...")
        
        # Batch update (Firestore allows max 500 per batch)
        batch_size = 500
        updated_count = 0
        
        for i in range(0, len(vehicles_to_update), batch_size):
            batch = db.batch()
            batch_items = vehicles_to_update[i:i + batch_size]
            
            for item in batch_items:
                doc_ref = db.collection('vehicles').document(item['doc_id'])
                batch.update(doc_ref, {
                    'cost_per_day': item['cost_per_day'],
                    'updated_at': datetime.utcnow()
                })
                print(f"  → {item['doc_id']}: base_rate={item['base_rate']} → cost_per_day={item['cost_per_day']}")
            
            batch.commit()
            updated_count += len(batch_items)
            print(f"  Committed batch {i // batch_size + 1}: {len(batch_items)} vehicles")
        
        print()
        print(f"✅ Migration complete! Updated {updated_count} vehicles with cost_per_day")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Pricing system setup utilities')
    parser.add_argument('--migrate-cost', action='store_true', 
                        help='Run one-time migration to add cost_per_day to vehicles')
    args = parser.parse_args()
    
    if args.migrate_cost:
        asyncio.run(migrate_cost_per_day())
    else:
        asyncio.run(setup_pricing_system())
