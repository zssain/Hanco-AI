"""Debug tool to inspect HTML from competitor websites and test selectors."""

import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re


PROVIDER_URLS = {
    'key': 'https://www.key.sa/en/rent-a-car',
    'budget': 'https://www.budgetsaudi.com',
    'yelo': 'https://www.iyelo.com',
    'lumi': 'https://www.lumi.com.sa'
}


async def fetch_and_analyze(provider: str):
    """Fetch HTML and analyze structure."""
    url = PROVIDER_URLS.get(provider)
    if not url:
        print(f"❌ Unknown provider: {provider}")
        return
    
    print(f"\n{'='*70}")
    print(f"🔍 Analyzing: {provider.upper()} - {url}")
    print(f"{'='*70}")
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            print(f"📡 Loading page...")
            await page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Wait for content
            await page.wait_for_timeout(3000)
            
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            print(f"✅ Page loaded ({len(html)} bytes)")
            
            # Analyze structure
            print(f"\n📊 HTML Structure Analysis:")
            
            # Check for common vehicle/car patterns
            patterns = [
                ('Vehicle cards (class contains "card")', soup.find_all('div', {'class': re.compile(r'card', re.I)})),
                ('Vehicle cards (class contains "vehicle")', soup.find_all('div', {'class': re.compile(r'vehicle', re.I)})),
                ('Vehicle cards (class contains "car")', soup.find_all('div', {'class': re.compile(r'car', re.I)})),
                ('Price elements (class contains "price")', soup.find_all(class_=re.compile(r'price', re.I))),
                ('Price elements (class contains "rate")', soup.find_all(class_=re.compile(r'rate', re.I))),
                ('Price elements (class contains "cost")', soup.find_all(class_=re.compile(r'cost', re.I))),
                ('Title elements (h1-h6)', soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])),
                ('Images (img tags)', soup.find_all('img')),
            ]
            
            for desc, elements in patterns:
                if elements:
                    print(f"  ✓ {desc}: {len(elements)} found")
                else:
                    print(f"  ✗ {desc}: 0 found")
            
            # Show sample HTML snippet
            print(f"\n📝 Sample HTML (first 3000 chars):")
            print("─" * 70)
            print(html[:3000])
            print("─" * 70)
            
            # Try to find specific provider patterns
            print(f"\n🔎 Looking for {provider}-specific patterns:")
            
            if provider == 'key':
                cards = soup.find_all('div', {'class': re.compile(r'vehicle|car|rental', re.I)})
                print(f"  Vehicle-like divs: {len(cards)}")
                if cards:
                    print(f"\n  Sample card classes: {cards[0].get('class', [])}")
                    print(f"  Sample card content (first 500 chars):\n{str(cards[0])[:500]}")
            
            elif provider == 'budget':
                cards = soup.find_all('div', {'class': re.compile(r'fleet|vehicle|car', re.I)})
                print(f"  Fleet-like divs: {len(cards)}")
                if cards:
                    print(f"\n  Sample card classes: {cards[0].get('class', [])}")
                    print(f"  Sample card content (first 500 chars):\n{str(cards[0])[:500]}")
            
            elif provider == 'yelo':
                cards = soup.find_all('div', {'class': re.compile(r'car|vehicle|item', re.I)})
                print(f"  Item-like divs: {len(cards)}")
                if cards:
                    print(f"\n  Sample card classes: {cards[0].get('class', [])}")
                    print(f"  Sample card content (first 500 chars):\n{str(cards[0])[:500]}")
            
            elif provider == 'lumi':
                # Lumi uses v-card (Vuetify components)
                cards = soup.find_all(class_='v-card')
                print(f"  v-card elements: {len(cards)}")
                if cards:
                    print(f"\n  Sample v-card classes: {cards[0].get('class', [])}")
                    print(f"  Sample v-card content (first 500 chars):\n{str(cards[0])[:500]}")
                else:
                    # Try generic Vue patterns
                    vue_divs = soup.find_all('div', {'class': re.compile(r'^v-', re.I)})
                    print(f"  Vue components (v-*): {len(vue_divs)}")
            
            # Check if page requires JavaScript rendering
            scripts = soup.find_all('script')
            print(f"\n⚙️  JavaScript analysis:")
            print(f"  Script tags: {len(scripts)}")
            
            # Check for SPA frameworks
            body_text = soup.body.get_text() if soup.body else ""
            if len(body_text.strip()) < 100:
                print(f"  ⚠️  Warning: Very little text content - page may be JavaScript-heavy")
                print(f"  Body text length: {len(body_text)} chars")
            
            # Check for common SPA markers
            if any(keyword in html for keyword in ['__NUXT__', 'Vue', 'React', 'Angular', 'ng-app']):
                print(f"  ⚠️  SPA framework detected - may need longer wait times")
            
            await browser.close()
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Debug all providers."""
    providers = ['key', 'budget', 'yelo', 'lumi']
    
    print("🚀 Scraper Debugging Tool")
    print("This will analyze HTML structure from competitor websites")
    print("\nSelect provider to debug:")
    print("  1. key (www.key.sa)")
    print("  2. budget (www.budgetsaudi.com)")
    print("  3. yelo (www.iyelo.com)")
    print("  4. lumi (www.lumi.com.sa)")
    print("  5. All providers")
    
    choice = input("\nEnter choice (1-5): ").strip()
    
    if choice == '5':
        for provider in providers:
            await fetch_and_analyze(provider)
            print("\n" + "="*70 + "\n")
    elif choice in ['1', '2', '3', '4']:
        provider = providers[int(choice) - 1]
        await fetch_and_analyze(provider)
    else:
        print("Invalid choice")


if __name__ == "__main__":
    asyncio.run(main())
