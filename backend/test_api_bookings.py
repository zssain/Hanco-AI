"""
Test backend API bookings endpoint
"""
import requests
import json

# Your guest ID from the booking
guest_id = "545b5ad4-2578-4cdc-8e0d-69ad8c393ac9"

print(f"🔍 Testing API with guest_id: {guest_id}\n")

try:
    response = requests.get(
        'http://localhost:8000/api/v1/bookings',
        headers={'X-Guest-Id': guest_id}
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"\nResponse:")
    print(json.dumps(response.json(), indent=2))
    
except Exception as e:
    print(f"❌ Error: {e}")
