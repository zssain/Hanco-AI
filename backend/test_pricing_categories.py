"""Test dynamic pricing with new market data for all categories."""
import requests
import json

API_URL = 'http://localhost:8000/api/v1/pricing/unified-price'

# Test vehicles from each category
test_vehicles = [
    ('economy_001', 'economy'),
    ('compact_001', 'compact'),
    ('sedan_001', 'sedan'),
    ('suv_001', 'suv'),
    ('luxury_001', 'luxury'),
]

print('=' * 80)
print('TESTING DYNAMIC PRICING WITH NEW MARKET DATA')
print('=' * 80)

for vehicle_id, category in test_vehicles:
    try:
        response = requests.post(API_URL, json={
            'vehicle_id': vehicle_id,
            'branch_key': 'riyadh',
            'pickup_date': '2026-01-15',
            'dropoff_date': '2026-01-18',
            'include_insurance': False
        }, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            vehicle_name = data.get('vehicle_name', 'Unknown')
            daily_rate = data.get('daily_rate', 0)
            market_ref = data.get('market_ref', 0)
            breakdown = data.get('breakdown', {})
            market_used = breakdown.get('market_data_used', False)
            
            emoji = {'economy': '🚙', 'compact': '🚗', 'sedan': '🚘', 'suv': '🚐', 'luxury': '🏎️'}.get(category, '📦')
            status = "YES" if market_used else "NO"
            
            print(f'{emoji} {category.upper()}: {vehicle_name}')
            print(f'   Daily Rate: {daily_rate} SAR')
            print(f'   Market Ref: {market_ref} SAR')
            print(f'   Market Data Used: {status}')
            print()
        else:
            print(f'{category}: Error {response.status_code} - {response.text[:100]}')
            print()
    except Exception as e:
        print(f'{category}: Failed - {str(e)[:100]}')
        print()

print('=' * 80)
print('DONE')
print('=' * 80)
