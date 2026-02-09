"""Extract sample vehicle cards from Yelo to understand the structure."""

import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re
import json


async def analyze_yelo_cards():
    """Analyze actual card structure from iYelo.com."""
    url = 'https://www.iyelo.com'
    
    print("🔍 Analyzing Yelo Card Structure...")
    print(f"URL: {url}\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto(url, wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(3000)
        
        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')
        
        # Try different card selectors
        selectors_to_try = [
            ('product-card', soup.find_all(class_='product-card')),
            ('vehicle-card', soup.find_all(class_=re.compile(r'vehicle.*card', re.I))),
            ('car-card', soup.find_all(class_=re.compile(r'car.*card', re.I))),
            ('fleet-card', soup.find_all(class_=re.compile(r'fleet.*card', re.I))),
            ('item-card', soup.find_all(class_=re.compile(r'item.*card', re.I))),
            ('div with "card" and "price"', [
                div for div in soup.find_all('div', class_=re.compile(r'card', re.I))
                if div.find(class_=re.compile(r'price', re.I))
            ]),
        ]
        
        print("Testing selectors:")
        print("=" * 70)
        
        for name, elements in selectors_to_try:
            print(f"\n{name}: {len(elements)} elements")
            
            if elements and len(elements) > 0:
                # Show first card
                card = elements[0]
                print(f"\n  First card structure:")
                print(f"  Classes: {card.get('class', [])}")
                
                # Look for price elements
                price_elems = card.find_all(class_=re.compile(r'price', re.I))
                print(f"  Price elements: {len(price_elems)}")
                if price_elems:
                    print(f"    Price text: {price_elems[0].get_text(strip=True)[:100]}")
                    print(f"    Price classes: {price_elems[0].get('class', [])}")
                
                # Look for title elements
                titles = card.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                print(f"  Title elements: {len(titles)}")
                if titles:
                    print(f"    Title text: {titles[0].get_text(strip=True)[:100]}")
                
                # Show full HTML of first card (truncated)
                card_html = str(card)[:1500]
                print(f"\n  Sample HTML (first 1500 chars):")
                print("  " + "-" * 66)
                for line in card_html.split('\n')[:30]:
                    print(f"  {line}")
                print("  " + "-" * 66)
        
        # Try to find the main vehicle listing section
        print("\n" + "=" * 70)
        print("Looking for main vehicle listing container...")
        
        # Common patterns for vehicle listings
        container_patterns = [
            'fleet',
            'vehicles',
            'cars',
            'products',
            'listings',
            'gallery',
            'grid'
        ]
        
        for pattern in container_patterns:
            containers = soup.find_all(class_=re.compile(pattern, re.I))
            if containers:
                print(f"\n{pattern}: {len(containers)} containers")
                if containers:
                    # Check if this container has price children
                    prices_inside = containers[0].find_all(class_=re.compile(r'price', re.I))
                    print(f"  Prices inside first container: {len(prices_inside)}")
                    if prices_inside:
                        print(f"  ✓ This looks promising!")
                        print(f"  Container classes: {containers[0].get('class', [])}")
        
        await browser.close()


async def main():
    await analyze_yelo_cards()


if __name__ == "__main__":
    asyncio.run(main())
