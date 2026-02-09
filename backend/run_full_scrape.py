"""
Full Competitor Scrape Script
Runs a comprehensive scrape covering ALL vehicle categories:
- Compact/Economy
- Sedan  
- SUV
- Luxury

This script directly invokes the scraper without going through the API.
"""
import asyncio
import os
import sys
import logging
from datetime import datetime, timezone

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set Firebase credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'hanco-ai-firebase-adminsdk-fbsvc-4c6e1450dc.json'
)

# Set to FULL_GRID for comprehensive scraping
os.environ['COMPETITOR_SCRAPE_MODE'] = 'FULL_GRID'


async def run_full_scrape():
    """Execute full competitor scraping job."""
    from app.workers.scrape_competitors import run_competitor_scraping_job
    from app.core.firebase import db
    
    print("=" * 80)
    print("🚀 FULL COMPETITOR SCRAPE - ALL CATEGORIES")
    print("=" * 80)
    print(f"Started at: {datetime.now(timezone.utc).isoformat()}")
    print("Categories to scrape: Compact, Economy, Sedan, SUV, Luxury")
    print("=" * 80)
    
    try:
        # Run the scraping job
        result = await run_competitor_scraping_job()
        
        print("\n" + "=" * 80)
        print("📊 SCRAPE RESULTS")
        print("=" * 80)
        
        if result.get('status') == 'success':
            scrape_result = result.get('scrape_result', {})
            print(f"✅ Status: SUCCESS")
            print(f"📦 Total offers scraped: {scrape_result.get('total_offers', 0)}")
            print(f"🆕 New offers stored: {scrape_result.get('total_new', 0)}")
            print(f"🏢 Providers scraped: {scrape_result.get('providers_scraped', 0)}")
            
            if scrape_result.get('errors'):
                print(f"\n⚠️ Errors encountered:")
                for error in scrape_result.get('errors', []):
                    print(f"   - {error}")
        else:
            print(f"❌ Status: {result.get('status', 'unknown')}")
            print(f"Error: {result.get('error', 'Unknown error')}")
        
        # Check what categories we now have
        print("\n" + "=" * 80)
        print("📊 CATEGORY BREAKDOWN IN FIREBASE")
        print("=" * 80)
        
        # Query competitor_prices_latest to get category counts
        docs = list(db.collection('competitor_prices_latest').stream())
        
        category_counts = {}
        provider_counts = {}
        latest_scraped = None
        
        for doc in docs:
            data = doc.to_dict()
            cat = data.get('vehicle_class', 'unknown')
            provider = data.get('provider', 'unknown')
            scraped_at = data.get('scraped_at')
            
            category_counts[cat] = category_counts.get(cat, 0) + 1
            provider_counts[provider] = provider_counts.get(provider, 0) + 1
            
            if scraped_at:
                if not latest_scraped or scraped_at > latest_scraped:
                    latest_scraped = scraped_at
        
        print(f"\nTotal documents: {len(docs)}")
        print(f"\nBy Category:")
        for cat, count in sorted(category_counts.items()):
            emoji = {
                'compact': '🚗',
                'economy': '🚙',
                'sedan': '🚘',
                'suv': '🚐',
                'luxury': '🏎️'
            }.get(cat, '📦')
            print(f"  {emoji} {cat.capitalize()}: {count} offers")
        
        print(f"\nBy Provider:")
        for provider, count in sorted(provider_counts.items()):
            print(f"  🏢 {provider}: {count} offers")
        
        if latest_scraped:
            print(f"\n🕐 Latest scrape timestamp: {latest_scraped}")
        
        print("\n" + "=" * 80)
        print("✅ SCRAPE COMPLETE")
        print("=" * 80)
        
        return result
        
    except Exception as e:
        logger.error(f"Scrape failed: {e}")
        import traceback
        traceback.print_exc()
        return {'status': 'error', 'error': str(e)}


if __name__ == '__main__':
    print("\n🔄 Initializing scraper...")
    result = asyncio.run(run_full_scrape())
