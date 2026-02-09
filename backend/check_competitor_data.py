"""Quick script to check what's in competitor_prices_latest collection."""

import asyncio
from app.core.firebase import db


def main():
    print("Checking competitor_prices_latest collection...")
    
    docs = list(db.collection('competitor_prices_latest').limit(10).stream())
    
    print(f"\n📊 Total documents: {len(docs)}")
    
    if len(docs) == 0:
        print("❌ Collection is EMPTY - no competitor data scraped!")
    else:
        print("\n✅ Sample documents:")
        for doc in docs[:5]:
            data = doc.to_dict()
            print(f"\n  ID: {doc.id}")
            print(f"  Provider: {data.get('provider')}")
            print(f"  City: {data.get('city')}")
            print(f"  Category: {data.get('category')}")
            print(f"  Price: {data.get('price')} {data.get('currency')}")
            print(f"  Vehicle: {data.get('vehicle_name')}")


if __name__ == "__main__":
    main()
