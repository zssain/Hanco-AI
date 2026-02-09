"""
Update Firestore Security Rules to allow public read access for vehicles
This script updates the rules to fix the "Missing or insufficient permissions" error
"""
import os
import sys
from google.cloud import firestore_admin_v1
from google.oauth2 import service_account

# Path to your service account key
SERVICE_ACCOUNT_PATH = r"C:\Users\altaf\Desktop\Hanco-Rent-a-Car-main\hanco-ai-firebase-adminsdk-fbsvc-4c6e1450dc.json"

# Your Firebase project ID
PROJECT_ID = "hanco-ai"

# Firestore rules with public read access for vehicles, branches, etc.
FIRESTORE_RULES = """rules_version = '2';

service cloud.firestore {
  match /databases/{database}/documents {
    
    // ==================== PUBLIC READ ACCESS ====================
    // Vehicles - PUBLIC READ for browsing, write restricted
    match /vehicles/{vehicleId} {
      allow read: if true;  // Public read access for vehicle browsing
      allow write: if request.auth != null && get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'admin';
    }
    
    // Branches - PUBLIC READ for location info
    match /branches/{branchId} {
      allow read: if true;  // Public read access for branch information
      allow write: if request.auth != null && get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'admin';
    }
    
    // Competitor data - PUBLIC READ (for price comparison feature)
    match /competitors/{competitorId} {
      allow read: if true;  // Public read for price comparisons
      allow write: if request.auth != null && get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'admin';
    }
    
    // Weather data - PUBLIC READ
    match /weather/{weatherId} {
      allow read: if true;
      allow write: if request.auth != null;
    }
    
    // ==================== USER DATA ====================
    // Users - Read own profile, admins can read all
    match /users/{userId} {
      allow read: if request.auth != null && (request.auth.uid == userId || get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'admin');
      allow create: if request.auth != null;
      allow update: if request.auth != null && (request.auth.uid == userId || get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'admin');
      allow delete: if request.auth != null && get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'admin';
    }
    
    // ==================== BOOKINGS ====================
    // Bookings - Users can read/create own bookings, admins can access all
    match /bookings/{bookingId} {
      allow read: if request.auth != null && (resource.data.user_id == request.auth.uid || get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'admin');
      allow create: if request.auth != null;
      allow update: if request.auth != null && (resource.data.user_id == request.auth.uid || get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'admin');
      allow delete: if request.auth != null && get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'admin';
    }
    
    // ==================== PAYMENTS ====================
    match /payments/{paymentId} {
      allow read: if request.auth != null && (resource.data.user_id == request.auth.uid || get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'admin');
      allow write: if request.auth != null;
    }
    
    // ==================== CHAT HISTORY ====================
    match /chat_history/{chatId} {
      allow read: if request.auth != null && (resource.data.user_id == request.auth.uid || get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'admin');
      allow create: if request.auth != null;
      allow update: if request.auth != null && (resource.data.user_id == request.auth.uid || get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'admin');
      allow delete: if request.auth != null && get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'admin';
    }
    
    // ==================== PRICING LOGS ====================
    match /pricing_logs/{logId} {
      allow read: if request.auth != null && get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'admin';
      allow write: if request.auth != null && get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'admin';
    }
    
    // Deny all other access by default
    match /{document=**} {
      allow read, write: if false;
    }
  }
}"""

def update_firestore_rules():
    """Update Firestore security rules via API"""
    try:
        print("🔧 Attempting to update Firestore rules...")
        print(f"📁 Using service account: {SERVICE_ACCOUNT_PATH}")
        print(f"🎯 Project ID: {PROJECT_ID}")
        print("")
        
        # Note: The Firestore Admin API doesn't support updating rules programmatically
        # through the Python SDK. Rules must be updated via:
        # 1. Firebase Console (recommended)
        # 2. Firebase CLI: firebase deploy --only firestore:rules
        # 3. REST API (complex)
        
        print("❌ Cannot update Firestore rules programmatically via Python SDK")
        print("")
        print("=" * 70)
        print("📋 MANUAL FIX REQUIRED - Follow these steps:")
        print("=" * 70)
        print("")
        print("1. Open Firebase Console: https://console.firebase.google.com/")
        print(f"2. Select your project: {PROJECT_ID}")
        print("3. Go to: Firestore Database → Rules tab")
        print("4. Copy the rules from 'firestore.rules' file")
        print("5. Paste into the editor and click 'Publish'")
        print("")
        print("=" * 70)
        print("🚀 QUICK FIX (Development Only):")
        print("=" * 70)
        print("")
        print("For testing, use these permissive rules:")
        print("")
        print("rules_version = '2';")
        print("service cloud.firestore {")
        print("  match /databases/{database}/documents {")
        print("    match /{document=**} {")
        print("      allow read, write: if true;")
        print("    }")
        print("  }")
        print("}")
        print("")
        print("⚠️  WARNING: Only use for local development!")
        print("")
        
        # Save the rules to file for easy access
        rules_file = os.path.join(os.path.dirname(__file__), "..", "firestore.rules")
        with open(rules_file, "w") as f:
            f.write(FIRESTORE_RULES)
        print(f"✅ Rules saved to: {rules_file}")
        print("")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    update_firestore_rules()
