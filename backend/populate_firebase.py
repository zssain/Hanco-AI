"""
Populate Firebase with vehicles and create user accounts with credentials
"""
import sys
import os
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore, auth

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings

def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    try:
        # Use environment variable for credentials path
        import os
        creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 
                               'C:/Users/altaf/Desktop/Hanco-Rent-a-Car-main/hanco-ai-firebase-adminsdk-fbsvc-4c6e1450dc.json')
        cred = credentials.Certificate(creds_path)
        firebase_admin.initialize_app(cred, {
            'projectId': 'hanco-ai',
        })
        print(f"✅ Firebase initialized for project: hanco-ai")
        return firestore.client()
    except Exception as e:
        print(f"❌ Failed to initialize Firebase: {e}")
        raise

def create_user_account(email: str, password: str, display_name: str, role: str):
    """Create a Firebase Auth user and Firestore profile"""
    try:
        # Create Firebase Auth user
        user = auth.create_user(
            email=email,
            password=password,
            display_name=display_name,
            email_verified=True
        )
        
        print(f"✅ Created Firebase Auth user: {email} (UID: {user.uid})")
        
        # Create Firestore user profile
        db = firestore.client()
        user_ref = db.collection('users').document(user.uid)
        user_ref.set({
            'uid': user.uid,
            'email': email,
            'name': display_name,
            'role': role,
            'phone': '+966501234567',
            'subscription_tier': 'premium' if role in ['admin', 'business'] else 'basic',
            'credits_remaining': 1000 if role == 'admin' else 500,
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP,
            'profile_completed': True
        })
        
        print(f"✅ Created Firestore profile for: {email} (Role: {role})")
        return user.uid, None
        
    except auth.EmailAlreadyExistsError:
        print(f"⚠️  User already exists: {email}")
        # Get existing user
        user = auth.get_user_by_email(email)
        return user.uid, "already_exists"
    except KeyboardInterrupt:
        raise
    except Exception as e:
        print(f"❌ Failed to create user {email}: {e}")
        return None, str(e)

def populate_vehicles(db):
    """Populate Firestore with sample vehicles"""
    print("\n📦 Populating vehicles...")
    
    vehicles_data = [
        {
            "id": "compact_001",
            "name": "Toyota Corolla 2024",
            "category": "Compact",
            "make": "Toyota",
            "model": "Corolla",
            "year": 2024,
            "base_daily_rate": 150.0,
            "current_price": 150.0,
            "seats": 5,
            "transmission": "Automatic",
            "fuel_type": "Petrol",
            "mileage": 15000,
            "city": "Riyadh",
            "location": "Riyadh Airport",
            "availability_status": "available",
            "features": ["Air Conditioning", "Bluetooth", "USB Charging", "GPS"],
            "image": "https://images.unsplash.com/photo-1623869675781-80aa31012a5a?w=500",
            "rating": 4.5,
            "total_bookings": 45,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP
        },
        {
            "id": "compact_002",
            "name": "Hyundai Elantra 2024",
            "category": "Compact",
            "make": "Hyundai",
            "model": "Elantra",
            "year": 2024,
            "base_daily_rate": 140.0,
            "current_price": 140.0,
            "seats": 5,
            "transmission": "Automatic",
            "fuel_type": "Petrol",
            "mileage": 12000,
            "city": "Jeddah",
            "location": "Jeddah Airport",
            "availability_status": "available",
            "features": ["Air Conditioning", "Bluetooth", "Backup Camera"],
            "image": "https://images.unsplash.com/photo-1619405399517-d7fce0f13302?w=500",
            "rating": 4.3,
            "total_bookings": 38,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP
        },
        {
            "id": "sedan_001",
            "name": "Honda Accord 2024",
            "category": "Sedan",
            "make": "Honda",
            "model": "Accord",
            "year": 2024,
            "base_daily_rate": 200.0,
            "current_price": 200.0,
            "seats": 5,
            "transmission": "Automatic",
            "fuel_type": "Petrol",
            "mileage": 10000,
            "city": "Riyadh",
            "location": "Riyadh City Center",
            "availability_status": "available",
            "features": ["Air Conditioning", "Bluetooth", "USB Charging", "GPS", "Leather Seats", "Sunroof"],
            "image": "https://images.unsplash.com/photo-1590362891991-f776e747a588?w=500",
            "rating": 4.7,
            "total_bookings": 32,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP
        },
        {
            "id": "sedan_002",
            "name": "Nissan Altima 2024",
            "category": "Sedan",
            "make": "Nissan",
            "model": "Altima",
            "year": 2024,
            "base_daily_rate": 180.0,
            "current_price": 180.0,
            "seats": 5,
            "transmission": "Automatic",
            "fuel_type": "Petrol",
            "mileage": 14000,
            "city": "Dammam",
            "location": "Dammam Airport",
            "availability_status": "available",
            "features": ["Air Conditioning", "Bluetooth", "Apple CarPlay", "Lane Assist"],
            "image": "https://images.unsplash.com/photo-1605559424843-9e4c228bf1c2?w=500",
            "rating": 4.6,
            "total_bookings": 28,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP
        },
        {
            "id": "suv_001",
            "name": "Toyota RAV4 2024",
            "category": "SUV",
            "make": "Toyota",
            "model": "RAV4",
            "year": 2024,
            "base_daily_rate": 280.0,
            "current_price": 280.0,
            "seats": 7,
            "transmission": "Automatic",
            "fuel_type": "Hybrid",
            "mileage": 8000,
            "city": "Riyadh",
            "location": "Riyadh Airport",
            "availability_status": "available",
            "features": ["Air Conditioning", "Bluetooth", "USB Charging", "GPS", "All-Wheel Drive", "Apple CarPlay"],
            "image": "https://images.unsplash.com/photo-1519641471654-76ce0107ad1b?w=500",
            "rating": 4.8,
            "total_bookings": 42,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP
        },
        {
            "id": "suv_002",
            "name": "Honda CR-V 2024",
            "category": "SUV",
            "make": "Honda",
            "model": "CR-V",
            "year": 2024,
            "base_daily_rate": 260.0,
            "current_price": 260.0,
            "seats": 5,
            "transmission": "Automatic",
            "fuel_type": "Petrol",
            "mileage": 9000,
            "city": "Jeddah",
            "location": "Jeddah City Center",
            "availability_status": "available",
            "features": ["Air Conditioning", "Bluetooth", "Panoramic Sunroof", "Heated Seats"],
            "image": "https://images.unsplash.com/photo-1511527844068-006b95d162c8?w=500",
            "rating": 4.7,
            "total_bookings": 35,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP
        },
        {
            "id": "luxury_001",
            "name": "BMW 5 Series 2024",
            "category": "Luxury",
            "make": "BMW",
            "model": "5 Series",
            "year": 2024,
            "base_daily_rate": 450.0,
            "current_price": 450.0,
            "seats": 5,
            "transmission": "Automatic",
            "fuel_type": "Petrol",
            "mileage": 5000,
            "city": "Riyadh",
            "location": "Riyadh Airport",
            "availability_status": "available",
            "features": ["Air Conditioning", "Bluetooth", "USB Charging", "GPS", "Leather Seats", "Premium Sound", "Navigation", "Heated Seats"],
            "image": "https://images.unsplash.com/photo-1555215695-3004980ad54e?w=500",
            "rating": 4.9,
            "total_bookings": 25,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP
        },
        {
            "id": "luxury_002",
            "name": "Mercedes-Benz E-Class 2024",
            "category": "Luxury",
            "make": "Mercedes-Benz",
            "model": "E-Class",
            "year": 2024,
            "base_daily_rate": 500.0,
            "current_price": 500.0,
            "seats": 5,
            "transmission": "Automatic",
            "fuel_type": "Petrol",
            "mileage": 3000,
            "city": "Jeddah",
            "location": "Jeddah Airport",
            "availability_status": "available",
            "features": ["Air Conditioning", "Bluetooth", "Navigation", "Leather Seats", "Massage Seats", "Premium Audio"],
            "image": "https://images.unsplash.com/photo-1618843479313-40f8afb4b4d8?w=500",
            "rating": 5.0,
            "total_bookings": 18,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP
        },
        {
            "id": "luxury_003",
            "name": "Audi A6 2024",
            "category": "Luxury",
            "make": "Audi",
            "model": "A6",
            "year": 2024,
            "base_daily_rate": 480.0,
            "current_price": 480.0,
            "seats": 5,
            "transmission": "Automatic",
            "fuel_type": "Petrol",
            "mileage": 4000,
            "city": "Dammam",
            "location": "Dammam City Center",
            "availability_status": "available",
            "features": ["Air Conditioning", "Bluetooth", "Virtual Cockpit", "Matrix LED", "Bang & Olufsen Sound"],
            "image": "https://images.unsplash.com/photo-1606664515524-ed2f786a0bd6?w=500",
            "rating": 4.8,
            "total_bookings": 22,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP
        },
        {
            "id": "economy_001",
            "name": "Kia Picanto 2024",
            "category": "Economy",
            "make": "Kia",
            "model": "Picanto",
            "year": 2024,
            "base_daily_rate": 100.0,
            "current_price": 100.0,
            "seats": 4,
            "transmission": "Manual",
            "fuel_type": "Petrol",
            "mileage": 20000,
            "city": "Riyadh",
            "location": "Riyadh Airport",
            "availability_status": "available",
            "features": ["Air Conditioning", "USB Charging"],
            "image": "https://images.unsplash.com/photo-1552519507-da3b142c6e3d?w=500",
            "rating": 4.2,
            "total_bookings": 55,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP
        },
        {
            "id": "economy_002",
            "name": "Chevrolet Spark 2024",
            "category": "Economy",
            "make": "Chevrolet",
            "model": "Spark",
            "year": 2024,
            "base_daily_rate": 110.0,
            "current_price": 110.0,
            "seats": 4,
            "transmission": "Automatic",
            "fuel_type": "Petrol",
            "mileage": 18000,
            "city": "Jeddah",
            "location": "Jeddah City Center",
            "availability_status": "available",
            "features": ["Air Conditioning", "Bluetooth", "Backup Camera"],
            "image": "https://images.unsplash.com/photo-1583267746897-c45255fe2b8e?w=500",
            "rating": 4.1,
            "total_bookings": 48,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP
        }
    ]
    
    # Add vehicles to Firestore
    vehicles_collection = db.collection('vehicles')
    count = 0
    
    for vehicle in vehicles_data:
        vehicle_id = vehicle['id']
        vehicle_ref = vehicles_collection.document(vehicle_id)
        vehicle_ref.set(vehicle)
        count += 1
        print(f"  ✅ Added: {vehicle['name']} ({vehicle['category']}) - {vehicle['city']}")
    
    print(f"\n✅ Successfully populated {count} vehicles")

def create_demo_users():
    """Create demo user accounts with credentials"""
    print("\n👥 Creating demo user accounts...")
    
    users = [
        {
            "email": "consumer@hanco.com",
            "password": "Consumer123!",
            "name": "Consumer Demo",
            "role": "consumer"
        },
        {
            "email": "admin@hanco.com",
            "password": "Admin123!",
            "name": "Admin User",
            "role": "admin"
        },
        {
            "email": "business@hanco.com",
            "password": "Business123!",
            "name": "Business Partner",
            "role": "business"
        },
        {
            "email": "support@hanco.com",
            "password": "Support123!",
            "name": "Support Agent",
            "role": "support"
        }
    ]
    
    created_users = []
    for user in users:
        try:
            uid, status = create_user_account(
                email=user['email'],
                password=user['password'],
                display_name=user['name'],
                role=user['role']
            )
            if uid:
                created_users.append(user)
        except KeyboardInterrupt:
            print("\n⚠️  User creation interrupted. Continuing with vehicle population...")
            break
        except Exception as e:
            print(f"Error creating user: {e}")
            continue
    
    return created_users

def main():
    """Main execution"""
    print("=" * 70)
    print("🚀 HANCO Firebase Data Population")
    print("=" * 70)
    
    # Initialize Firebase
    db = initialize_firebase()
    
    # Create demo users
    users = create_demo_users()
    
    # Populate vehicles
    populate_vehicles(db)
    
    # Print summary
    print("\n" + "=" * 70)
    print("✅ Firebase Population Complete!")
    print("=" * 70)
    
    if users:
        print("\n📋 Demo User Credentials:")
        print("-" * 70)
        for user in users:
            print(f"\n{user['role'].upper()}:")
            print(f"  Email:    {user['email']}")
            print(f"  Password: {user['password']}")
            print(f"  Role:     {user['role']}")
    
    print("\n" + "=" * 70)
    print("🔗 Firebase Console:")
    print(f"   https://console.firebase.google.com/project/{settings.FIREBASE_PROJECT_ID}/firestore")
    print("\n💡 You can now use these credentials to login to the application!")
    print("=" * 70)

if __name__ == "__main__":
    main()
