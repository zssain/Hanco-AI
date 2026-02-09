"""Generate mock competitor data for testing when scrapers fail."""

import random
from datetime import datetime
from app.core.firebase import db

# Mock data configuration
CITIES = ['riyadh', 'jeddah', 'dammam']
CATEGORIES = ['sedan', 'suv', 'luxury', 'economy']
PROVIDERS = ['key', 'budget', 'yelo', 'lumi']
VEHICLES = {
    'sedan': ['Hyundai Accent', 'Toyota Corolla', 'Nissan Sunny', 'Kia Cerato'],
    'suv': ['Hyundai Tucson', 'Toyota RAV4', 'Nissan X-Trail', 'Kia Sportage'],
    'luxury': ['BMW 5 Series', 'Mercedes E-Class', 'Audi A6', 'Lexus ES'],
    'economy': ['Hyundai i10', 'Toyota Yaris', 'Nissan Micra', 'Kia Picanto']
}

def generate_mock_offers(count_per_provider=15):
    """Generate mock competitor price data."""
    print(f"🎲 Generating {count_per_provider} offers per provider...")
    
    batch = db.batch()
    total_count = 0
    
    for provider in PROVIDERS:
        for i in range(count_per_provider):
            city = random.choice(CITIES)
            category = random.choice(CATEGORIES)
            vehicle_name = random.choice(VEHICLES[category])
            
            # Generate realistic price range
            base_price = {
                'economy': 80,
                'sedan': 120,
                'suv': 180,
                'luxury': 350
            }[category]
            
            price = base_price + random.randint(-20, 40)
            
            doc_id = f"{provider}_{city}_{category}_{i}"
            doc_ref = db.collection('competitor_prices_latest').document(doc_id)
            
            offer_data = {
                'provider': provider,
                'city': city,
                'category': category,
                'vehicle_name': vehicle_name,
                'price': price,
                'currency': 'SAR',
                'scraped_at': datetime.utcnow(),
                'url': f'https://www.{provider}.com',
                'is_mock': True  # Flag to identify test data
            }
            
            batch.set(doc_ref, offer_data)
            total_count += 1
            
            # Commit in batches of 500
            if total_count % 500 == 0:
                batch.commit()
                batch = db.batch()
                print(f"   Committed {total_count} offers...")
    
    # Commit remaining
    if total_count % 500 != 0:
        batch.commit()
    
    print(f"✅ Generated {total_count} mock offers across {len(PROVIDERS)} providers")
    print(f"   Cities: {', '.join(CITIES)}")
    print(f"   Categories: {', '.join(CATEGORIES)}")
    
    # Update scrape status
    for provider in PROVIDERS:
        status_ref = db.collection('competitor_scrape_status').document(provider)
        status_ref.set({
            'provider': provider,
            'last_run_at': datetime.utcnow(),
            'last_success_at': datetime.utcnow(),
            'last_offer_count': count_per_provider,
            'last_error': None,
            'is_stale': False,
            'last_duration_ms': random.randint(5000, 15000),
            'is_mock': True
        })
    
    print("\n✅ Mock data ready for testing")
    print("   Run: python scripts/smoke_test_pricing.py")


if __name__ == "__main__":
    generate_mock_offers(count_per_provider=15)
