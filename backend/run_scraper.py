"""
Run competitor scraper to populate pricing data.

This script runs the competitor crawler to fetch pricing data from
various providers and stores it in Firestore for use by the pricing engine.

Usage:
    python run_scraper.py
"""

import asyncio
import sys
from datetime import datetime

# Import scraping functions
from app.services.competitors.crawler import (
    refresh_competitor_prices,
    get_branches_cached,
    get_cities_from_branches
)
from app.core.firebase import db


async def main():
    """Run the competitor scraper."""
    print("=" * 80)
    print("🕷️  HANCO AI - Competitor Price Scraper")
    print("=" * 80)
    print()
    
    try:
        # Load branches
        print("📍 Loading branch configuration...")
        branches = await get_branches_cached(db, force_reload=True)
        cities = get_cities_from_branches(branches)
        print(f"   Found {len(branches)} branches in {len(cities)} cities")
        print(f"   Cities: {', '.join(cities)}")
        print()
        
        # Run scraper for all cities
        print("🔄 Starting competitor scraping...")
        print(f"   Cities: {', '.join(cities)}")
        print()
        
        result = await refresh_competitor_prices(
            cities=cities,
            firestore_client=db
        )
        
        total_offers = result.get('total_offers', 0)
        total_errors = len(result.get('errors', []))
        offers_by_provider = result.get('offers_by_provider', {})
        
        print("📊 Scraping Results:")
        for provider, count in offers_by_provider.items():
            print(f"   {provider:12s}: {count:3d} offers")
        print()
        
        # Summary
        print("=" * 80)
        print("📈 SCRAPING COMPLETE")
        print("=" * 80)
        print(f"Total offers scraped: {total_offers}")
        print(f"Total errors: {total_errors}")
        print()
        
        if total_offers > 0:
            print("✅ Competitor data is now available for pricing engine")
            print()
            print("Next steps:")
            print("  - Run smoke test: python scripts/smoke_test_pricing.py")
            print("  - Test pricing API: python test_quote_pricing.py")
        else:
            print("⚠️  No offers were scraped - check errors above")
            sys.exit(1)
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
