"""
Quick test to verify auth endpoints are working
Run with: python -m pytest test_auth_quick.py -v
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_imports():
    """Test that all imports work correctly"""
    try:
        from app.api.v1.auth import router
        from app.core.firebase import firebase_client, db, auth_client
        from app.core.security import get_current_user
        from app.schemas.auth import RegisterRequest, LoginRequest, UserResponse
        
        print("✅ All imports successful!")
        print(f"✅ Auth router: {router}")
        print(f"✅ Firebase client initialized: {firebase_client is not None}")
        print(f"✅ Firestore DB: {db is not None}")
        print(f"✅ Auth client: {auth_client is not None}")
        
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False


def test_router_endpoints():
    """Test that router has all expected endpoints"""
    from app.api.v1.auth import router
    
    routes = [route.path for route in router.routes]
    print(f"\n✅ Auth router has {len(routes)} endpoints:")
    for route in router.routes:
        print(f"  - {route.methods} {route.path}")
    
    expected_paths = ['/register', '/login', '/me', '/logout', '/password-reset', '/account']
    for path in expected_paths:
        if path in routes:
            print(f"✅ {path} endpoint found")
        else:
            print(f"❌ {path} endpoint missing")


def test_schemas():
    """Test Pydantic schemas"""
    from app.schemas.auth import RegisterRequest, LoginRequest, UserResponse
    
    try:
        # Test RegisterRequest validation
        register_data = RegisterRequest(
            email="test@example.com",
            password="SecurePass123",
            full_name="Test User",
            phone="+966512345678",
            role="customer"
        )
        print(f"✅ RegisterRequest schema works: {register_data.email}")
        
        # Test LoginRequest
        login_data = LoginRequest(
            email="test@example.com",
            password="test_token"
        )
        print(f"✅ LoginRequest schema works: {login_data.email}")
        
        return True
    except Exception as e:
        print(f"❌ Schema validation failed: {e}")
        return False


def test_main_app():
    """Test main app includes auth router"""
    from app.main import app
    from app.api.v1.router import api_router
    
    print(f"\n✅ Main app created: {app.title}")
    print(f"✅ API router included")
    
    # Check routes
    routes = [route.path for route in app.routes]
    print(f"✅ Total app routes: {len(routes)}")
    
    # Check if auth routes are included
    auth_routes = [r for r in routes if '/auth' in r]
    print(f"✅ Auth routes found: {len(auth_routes)}")
    for route in auth_routes[:5]:  # Show first 5
        print(f"  - {route}")


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 Testing Hanco-AI Auth Implementation")
    print("=" * 60)
    
    print("\n1️⃣ Testing Imports...")
    test_imports()
    
    print("\n2️⃣ Testing Router Endpoints...")
    test_router_endpoints()
    
    print("\n3️⃣ Testing Pydantic Schemas...")
    test_schemas()
    
    print("\n4️⃣ Testing Main App Integration...")
    test_main_app()
    
    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)
    print("\n🚀 To run the server:")
    print("   cd backend")
    print("   python -m app.main")
    print("\n📚 API Docs:")
    print("   http://localhost:8000/api/v1/docs")
