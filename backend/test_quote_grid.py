"""
Test script to verify quote-grid scraping implementation
"""
import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.firebase import db
from app.services.competitors.crawler import (
    generate_run_id,
    calculate_quote_dates,
    scrape_quote_grid,
    get_branches_cached,
    PROVIDER_URLS,
    QUOTE_TEMPLATES
)

async def test_quote_grid():
    """Test quote-grid scraping setup"""
    print("=" * 80)
    print("🧪 Testing Quote-Grid Scraping Implementation")
    print("=" * 80)
    
    # Test 1: Run ID generation
    print("\n1️⃣ Testing generate_run_id()...")
    run_id = generate_run_id()
    print(f"   ✅ Generated run_id: {run_id}")
    
    # Test 2: Date calculation
    print("\n2️⃣ Testing calculate_quote_dates()...")
    for template in QUOTE_TEMPLATES:
        dates = calculate_quote_dates(template)
        print(f"   • {template['name']}:")
        print(f"     Pickup: {dates['pickup_date']} {dates['pickup_time']}")
        print(f"     Drop:   {dates['dropoff_date']} {dates['drop_time']}")
    
    # Test 3: Provider configuration
    print(f"\n3️⃣ Competitor Providers ({len(PROVIDER_URLS)}):")
    for provider, url in PROVIDER_URLS.items():
        print(f"   • {provider}: {url}")
    
    # Test 4: Quote templates
    print(f"\n4️⃣ Quote Templates ({len(QUOTE_TEMPLATES)}):")
    for template in QUOTE_TEMPLATES:
        print(f"   • {template['name']} - {template['booking_mode']}")
    
    # Test 5: Load branches
    print("\n5️⃣ Loading branches from Firestore...")
    branches = await get_branches_cached(db)
    
    if branches:
        print(f"   ✅ Loaded {len(branches)} branches")
        for branch in branches:
            print(f"      • {branch['city']}/{branch['branch_key']} - {branch['label']}")
    else:
        print("   ❌ No branches loaded")
        return
    
    # Test 6: Calculate total combinations
    total_combinations = len(PROVIDER_URLS) * len(branches) * len(QUOTE_TEMPLATES)
    print(f"\n6️⃣ Total Combinations:")
    print(f"   {len(PROVIDER_URLS)} competitors × {len(branches)} branches × {len(QUOTE_TEMPLATES)} templates")
    print(f"   = {total_combinations} scraping operations per run")
    
    # Test 7: Concurrency settings
    from app.core.config import settings
    print(f"\n7️⃣ Concurrency Configuration:")
    print(f"   COMPETITOR_SCRAPE_CONCURRENCY: {settings.COMPETITOR_SCRAPE_CONCURRENCY}")
    print(f"   Estimated batches: {(total_combinations + settings.COMPETITOR_SCRAPE_CONCURRENCY - 1) // settings.COMPETITOR_SCRAPE_CONCURRENCY}")
    
    print("\n" + "=" * 80)
    print("✅ Quote-Grid Setup Verification Complete!")
    print("=" * 80)
    
    # Optional: Ask if user wants to run a test scrape
    print("\n⚠️  To run actual scraping, use:")
    print("   python -m app.workers.scrape_competitors")
    print("\n💡 The quote-grid will scrape all combinations automatically.")

if __name__ == "__main__":
    asyncio.run(test_quote_grid())
