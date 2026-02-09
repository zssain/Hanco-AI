"""
Check Payment Routes
"""
import sys
sys.path.insert(0, '.')

from app.api.v1.router import api_router

print("=" * 60)
print("PAYMENT API ROUTES")
print("=" * 60)
print()

routes = [r.path for r in api_router.routes]
payment_routes = [r for r in routes if 'payment' in r.lower()]

if payment_routes:
    print("✅ Payment routes registered:")
    for route in payment_routes:
        print(f"   {route}")
else:
    print("❌ No payment routes found")

print()
print("All API Routes:")
print("-" * 60)
for route in sorted(routes):
    print(f"  {route}")
