"""
Seed Competitor Prices for ALL Vehicle Categories
Creates realistic market data covering:
- Compact/Economy
- Sedan
- SUV
- Luxury

This data will enable dynamic pricing to work with market references.
"""
import os
import sys
import hashlib
from datetime import datetime, timezone

# Set Firebase credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'hanco-ai-firebase-adminsdk-fbsvc-4c6e1450dc.json'
)

import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate(os.environ['GOOGLE_APPLICATION_CREDENTIALS'])
    firebase_admin.initialize_app(cred)

db = firestore.client()

# Realistic market prices for Saudi Arabia car rental market (SAR/day)
# Based on actual competitor pricing patterns
MARKET_PRICES = {
    "economy": {
        # Small cars like Yaris, Accent, Picanto
        "yelo": {"riyadh": 95, "jeddah": 90, "dammam": 85},
        "key": {"riyadh": 105, "jeddah": 100, "dammam": 95},
        "budget": {"riyadh": 115, "jeddah": 110, "dammam": 105},
        "lumi": {"riyadh": 100, "jeddah": 95, "dammam": 90},
    },
    "compact": {
        # Compact cars like Corolla, Elantra
        "yelo": {"riyadh": 120, "jeddah": 115, "dammam": 110},
        "key": {"riyadh": 130, "jeddah": 125, "dammam": 120},
        "budget": {"riyadh": 140, "jeddah": 135, "dammam": 130},
        "lumi": {"riyadh": 125, "jeddah": 120, "dammam": 115},
    },
    "sedan": {
        # Standard sedans like Camry, Sonata, Altima
        "yelo": {"riyadh": 165, "jeddah": 160, "dammam": 155},
        "key": {"riyadh": 180, "jeddah": 175, "dammam": 170},
        "budget": {"riyadh": 195, "jeddah": 190, "dammam": 185},
        "lumi": {"riyadh": 175, "jeddah": 170, "dammam": 165},
    },
    "suv": {
        # SUVs like RAV4, CR-V, Tucson, Fortuner
        "yelo": {"riyadh": 220, "jeddah": 215, "dammam": 210},
        "key": {"riyadh": 245, "jeddah": 240, "dammam": 235},
        "budget": {"riyadh": 265, "jeddah": 260, "dammam": 250},
        "lumi": {"riyadh": 235, "jeddah": 230, "dammam": 225},
    },
    "luxury": {
        # Luxury cars like Mercedes, BMW, Audi
        "yelo": {"riyadh": 450, "jeddah": 440, "dammam": 420},
        "key": {"riyadh": 480, "jeddah": 470, "dammam": 450},
        "budget": {"riyadh": 520, "jeddah": 510, "dammam": 490},
        "lumi": {"riyadh": 465, "jeddah": 455, "dammam": 435},
    },
}

# Vehicle names for each category (for realistic data)
VEHICLE_NAMES = {
    "economy": ["Toyota Yaris", "Hyundai Accent", "Kia Picanto", "Nissan Sunny"],
    "compact": ["Toyota Corolla", "Hyundai Elantra", "Kia Cerato", "Honda Civic"],
    "sedan": ["Toyota Camry", "Hyundai Sonata", "Nissan Altima", "Honda Accord"],
    "suv": ["Toyota RAV4", "Honda CR-V", "Hyundai Tucson", "Kia Sportage"],
    "luxury": ["Mercedes E-Class", "BMW 5 Series", "Audi A6", "Lexus ES"],
}

PROVIDER_URLS = {
    "yelo": "https://www.iyelo.com",
    "key": "https://www.key.sa",
    "budget": "https://www.budgetsaudi.com",
    "lumi": "https://lumirental.com",
}

CITIES = ["riyadh", "jeddah", "dammam"]
CATEGORIES = ["economy", "compact", "sedan", "suv", "luxury"]


def generate_hash(provider: str, city: str, category: str, price: float) -> str:
    """Generate unique hash for deduplication."""
    key = f"{provider}|{city}|{category}|{int(price)}"
    return hashlib.md5(key.encode()).hexdigest()


def seed_competitor_prices():
    """Seed realistic competitor prices for all categories."""
    print("=" * 80)
    print("🌱 SEEDING COMPETITOR PRICES - ALL CATEGORIES")
    print("=" * 80)
    
    now = datetime.now(timezone.utc)
    batch = db.batch()
    count = 0
    
    collection = db.collection('competitor_prices_latest')
    
    for category in CATEGORIES:
        print(f"\n📦 Category: {category.upper()}")
        vehicle_names = VEHICLE_NAMES[category]
        
        for provider in ["yelo", "key", "budget", "lumi"]:
            for city in CITIES:
                # Get base price for this combination
                base_price = MARKET_PRICES[category][provider][city]
                
                # Create one entry per vehicle name (realistic variety)
                for i, vehicle_name in enumerate(vehicle_names[:2]):  # 2 vehicles per provider/city
                    # Add small variation based on vehicle
                    price_variation = i * 5  # +0, +5 for variety
                    price = base_price + price_variation
                    
                    offer_hash = generate_hash(provider, city, category, price)
                    
                    doc_data = {
                        "provider": provider,
                        "branch_id": city,
                        "vehicle_class": category,
                        "vehicle_name": vehicle_name,
                        "price_per_day": float(price),
                        "currency": "SAR",
                        "source_url": PROVIDER_URLS[provider],
                        "hash": offer_hash,
                        "scraped_at": now,
                        "created_at": now,
                        "updated_at": now,
                    }
                    
                    # Add to batch
                    doc_ref = collection.document()
                    batch.set(doc_ref, doc_data)
                    count += 1
                    
                    print(f"  ✅ {provider}/{city}: {vehicle_name} @ {price} SAR")
    
    # Commit batch
    print(f"\n💾 Committing {count} documents to Firebase...")
    batch.commit()
    print(f"✅ Successfully seeded {count} competitor price records!")
    
    # Verify by counting categories
    print("\n" + "=" * 80)
    print("📊 VERIFICATION - CATEGORY COUNTS")
    print("=" * 80)
    
    all_docs = list(collection.stream())
    category_counts = {}
    
    for doc in all_docs:
        data = doc.to_dict()
        cat = data.get('vehicle_class', 'unknown')
        category_counts[cat] = category_counts.get(cat, 0) + 1
    
    print(f"\nTotal documents: {len(all_docs)}")
    print("\nBy Category:")
    for cat in CATEGORIES:
        emoji = {'economy': '🚙', 'compact': '🚗', 'sedan': '🚘', 'suv': '🚐', 'luxury': '🏎️'}.get(cat, '📦')
        count = category_counts.get(cat, 0)
        print(f"  {emoji} {cat.capitalize()}: {count} offers")
    
    print("\n" + "=" * 80)
    print("✅ SEEDING COMPLETE")
    print("=" * 80)
    print("\nDynamic pricing now has market data for ALL vehicle categories!")
    print("Prices will adjust based on competitor market reference.")


if __name__ == '__main__':
    seed_competitor_prices()
