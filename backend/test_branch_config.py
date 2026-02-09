"""
Test script to verify branch configuration loading from Firestore
"""
import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.firebase import db
from app.services.competitors.crawler import (
    load_branches_from_firestore,
    get_branches_cached,
    get_cities_from_branches,
    get_supported_cities
)

async def test_branch_loading():
    """Test branch configuration loading"""
    print("=" * 70)
    print("🔍 Testing Branch Configuration Loading")
    print("=" * 70)
    
    # Test 1: Load branches directly
    print("\n1️⃣ Testing load_branches_from_firestore()...")
    branches = await load_branches_from_firestore(db)
    
    if branches:
        print(f"   ✅ Loaded {len(branches)} branches")
        for branch in branches:
            print(f"      • {branch['city']} - {branch['label']} ({branch['type']})")
    else:
        print("   ❌ Failed to load branches")
        return
    
    # Test 2: Test caching
    print("\n2️⃣ Testing get_branches_cached()...")
    cached_branches = await get_branches_cached(db)
    
    if cached_branches:
        print(f"   ✅ Cache working: {len(cached_branches)} branches")
    else:
        print("   ❌ Cache failed")
    
    # Test 3: Derive cities
    print("\n3️⃣ Testing get_cities_from_branches()...")
    cities = get_cities_from_branches(cached_branches)
    
    if cities:
        print(f"   ✅ Derived {len(cities)} unique cities: {', '.join(cities)}")
    else:
        print("   ❌ No cities derived")
    
    # Test 4: Test get_supported_cities
    print("\n4️⃣ Testing get_supported_cities()...")
    supported_cities = get_supported_cities()
    
    if supported_cities:
        print(f"   ✅ Supported cities: {', '.join(supported_cities)}")
    else:
        print("   ⚠️ No supported cities (branches not cached yet)")
    
    print("\n" + "=" * 70)
    print("✅ All tests completed!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test_branch_loading())
