"""
Create test data to populate Firebase Firestore collections
"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def register_user():
    """Register a test user"""
    print("📝 Registering test user...")
    
    payload = {
        "email": "test@hanco.com",
        "password": "Test123!@#",
        "full_name": "Test User",
        "phone": "+1234567890"
    }
    
    response = requests.post(f"{BASE_URL}/auth/register", json=payload)
    
    if response.status_code == 200:
        print("✅ User registered successfully!")
        print(json.dumps(response.json(), indent=2))
        return response.json()
    else:
        print(f"❌ Registration failed: {response.status_code}")
        print(response.text)
        return None

def login_user():
    """Login with test user"""
    print("\n🔐 Logging in...")
    
    # Note: In real scenario, you'd get the ID token from Firebase client SDK
    # For now, we'll just show the registration creates the Firestore document
    print("ℹ️  Login requires Firebase ID token from client SDK")
    print("ℹ️  Check Firebase Console - users collection should now exist!")

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Creating Test Data for Hanco-AI")
    print("=" * 60)
    
    user = register_user()
    
    if user:
        login_user()
        print("\n" + "=" * 60)
        print("✅ Test data creation complete!")
        print("=" * 60)
        print("\n📊 Check Firebase Console:")
        print("   - Go to Firestore Database")
        print("   - You should see 'users' collection")
        print(f"   - With document ID: {user['uid']}")
        print("\n🔗 Firebase Console:")
        print("   https://console.firebase.google.com/u/1/project/hanco-ai/firestore/databases/-default-/data")
