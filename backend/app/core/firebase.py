"""
Firebase integration for Hanco-AI
Firestore database and Firebase Authentication
"""
import firebase_admin
from firebase_admin import credentials, firestore, auth
from typing import Optional, Dict, Any, List
import logging
from functools import lru_cache
import os

logger = logging.getLogger(__name__)


class MockFirestoreClient:
    """Mock Firestore client for development without Firebase credentials"""
    
    def __init__(self):
        self._data = {}
        self._initialize_mock_data()
        logger.info("🔧 Using Mock Firestore Client for development")
    
    def _initialize_mock_data(self):
        """Initialize with sample vehicle data for development"""
        from datetime import datetime
        
        # Sample vehicles data
        self._data['vehicles'] = {
            'toyota-camry-2024': {
                'name': 'Toyota Camry 2024',
                'brand': 'Toyota',
                'make': 'Toyota',
                'model': 'Camry',
                'year': 2024,
                'type': 'Sedan',
                'category': 'Sedan',
                'transmission': 'Automatic',
                'fuel_type': 'Gasoline',
                'seats': 5,
                'daily_rate': 150.0,
                'base_daily_rate': 150.0,
                'available': True,
                'location': 'Riyadh',
                'branch': 'riyadh',
                'image': 'https://images.unsplash.com/photo-1621007947382-bb3c3994e3fb?w=800',
                'features': ['Bluetooth', 'Backup Camera', 'Cruise Control', 'GPS'],
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            },
            'honda-accord-2024': {
                'name': 'Honda Accord 2024',
                'brand': 'Honda',
                'make': 'Honda',
                'model': 'Accord',
                'year': 2024,
                'type': 'Sedan',
                'category': 'Sedan',
                'transmission': 'Automatic',
                'fuel_type': 'Gasoline',
                'seats': 5,
                'daily_rate': 160.0,
                'base_daily_rate': 160.0,
                'available': True,
                'location': 'Riyadh',
                'branch': 'riyadh',
                'image': 'https://images.unsplash.com/photo-1590362891991-f776e747a588?w=800',
                'features': ['Sunroof', 'Leather Seats', 'Apple CarPlay', 'Lane Assist'],
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            },
            'nissan-altima-2023': {
                'name': 'Nissan Altima 2023',
                'brand': 'Nissan',
                'make': 'Nissan',
                'model': 'Altima',
                'year': 2023,
                'type': 'Sedan',
                'category': 'Sedan',
                'transmission': 'Automatic',
                'fuel_type': 'Gasoline',
                'seats': 5,
                'daily_rate': 140.0,
                'base_daily_rate': 140.0,
                'available': True,
                'location': 'Jeddah',
                'branch': 'jeddah',
                'image': 'https://images.unsplash.com/photo-1605559424843-9e4c228bf1c2?w=800',
                'features': ['Bluetooth', 'USB Ports', 'Keyless Entry'],
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            },
            'toyota-rav4-2024': {
                'name': 'Toyota RAV4 2024',
                'brand': 'Toyota',
                'make': 'Toyota',
                'model': 'RAV4',
                'year': 2024,
                'type': 'SUV',
                'category': 'SUV',
                'transmission': 'Automatic',
                'fuel_type': 'Hybrid',
                'seats': 7,
                'daily_rate': 200.0,
                'base_daily_rate': 200.0,
                'available': True,
                'location': 'Riyadh',
                'branch': 'riyadh',
                'image': 'https://images.unsplash.com/photo-1519641471654-76ce0107ad1b?w=800',
                'features': ['AWD', 'Third Row', 'Safety Package', '360 Camera'],
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            },
            'hyundai-tucson-2024': {
                'name': 'Hyundai Tucson 2024',
                'brand': 'Hyundai',
                'make': 'Hyundai',
                'model': 'Tucson',
                'year': 2024,
                'type': 'SUV',
                'category': 'SUV',
                'transmission': 'Automatic',
                'fuel_type': 'Gasoline',
                'seats': 5,
                'daily_rate': 180.0,
                'base_daily_rate': 180.0,
                'available': True,
                'location': 'Dammam',
                'branch': 'dammam',
                'image': 'https://images.unsplash.com/photo-1548354643-3322f0d7482c?w=800',
                'features': ['Panoramic Sunroof', 'Heated Seats', 'Wireless Charging'],
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
        }
    
    def collection(self, name: str):
        """Return a mock collection"""
        return MockCollection(name, self._data)
    
    def document(self, path: str):
        """Return a mock document"""
        return MockDocument(path, self._data)


class MockCollection:
    """Mock Firestore collection"""
    
    def __init__(self, name: str, data_store: dict):
        self.name = name
        self._data = data_store
        if name not in self._data:
            self._data[name] = {}
    
    def document(self, doc_id: str):
        """Return a mock document"""
        return MockDocument(f"{self.name}/{doc_id}", self._data)
    
    def stream(self):
        """Return all documents in collection"""
        if self.name not in self._data:
            return []
        
        # Return mock document snapshots for all documents in collection
        docs = []
        for doc_id, doc_data in self._data[self.name].items():
            docs.append(MockDocumentSnapshot(f"{self.name}/{doc_id}", doc_data, doc_id))
        return docs
    
    def get(self):
        """Get all documents in collection"""
        return self.stream()
    
    def add(self, data: dict):
        """Add a document to collection"""
        import uuid
        doc_id = str(uuid.uuid4())
        path = f"{self.name}/{doc_id}"
        if self.name not in self._data:
            self._data[self.name] = {}
        self._data[self.name][doc_id] = data
        return (None, MockDocumentReference(path))
    
    def where(self, *args, **kwargs):
        """Mock where query"""
        return self
    
    def limit(self, count: int):
        """Mock limit query"""
        return self
    
    def order_by(self, field: str, **kwargs):
        """Mock order_by query"""
        return self
    
    def offset(self, count: int):
        """Mock offset query"""
        return self


class MockDocument:
    """Mock Firestore document"""
    
    def __init__(self, path: str, data_store: dict):
        self.path = path
        self._data = data_store
        parts = path.split('/')
        self.collection_name = parts[0] if len(parts) > 0 else None
        self.doc_id = parts[1] if len(parts) > 1 else None
    
    def get(self):
        """Get document data"""
        if self.collection_name and self.doc_id:
            if self.collection_name in self._data and self.doc_id in self._data[self.collection_name]:
                return MockDocumentSnapshot(self.path, self._data[self.collection_name][self.doc_id])
        return MockDocumentSnapshot(self.path, None)
    
    def set(self, data: dict, merge: bool = False):
        """Set document data"""
        if self.collection_name not in self._data:
            self._data[self.collection_name] = {}
        if merge and self.doc_id in self._data[self.collection_name]:
            self._data[self.collection_name][self.doc_id].update(data)
        else:
            self._data[self.collection_name][self.doc_id] = data
    
    def update(self, data: dict):
        """Update document data"""
        if self.collection_name not in self._data:
            self._data[self.collection_name] = {}
        if self.doc_id in self._data[self.collection_name]:
            self._data[self.collection_name][self.doc_id].update(data)
    
    def delete(self):
        """Delete document"""
        if self.collection_name in self._data and self.doc_id in self._data[self.collection_name]:
            del self._data[self.collection_name][self.doc_id]
    
    def collection(self, name: str):
        """Return subcollection"""
        return MockCollection(f"{self.path}/{name}", self._data)


class MockDocumentSnapshot:
    """Mock document snapshot"""
    
    def __init__(self, path: str, data: Optional[dict], doc_id: Optional[str] = None):
        self.id = doc_id or (path.split('/')[-1] if path else None)
        self._data = data
    
    def exists(self):
        """Check if document exists"""
        return self._data is not None
    
    def to_dict(self):
        """Get document data as dict"""
        return self._data or {}


class MockDocumentReference:
    """Mock document reference"""
    
    def __init__(self, path: str):
        self.id = path.split('/')[-1] if path else None
        self.path = path


class MockAuth:
    """Mock Firebase Auth for development"""
    
    @staticmethod
    def verify_id_token(token: str):
        """Mock token verification - always returns a test user"""
        logger.warning("🔧 Using mock auth - accepting all tokens in development mode")
        return {
            'uid': 'mock-user-id',
            'email': 'test@example.com',
            'name': 'Test User'
        }


class FirebaseClient:
    """Firebase Admin SDK client singleton"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FirebaseClient, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._initialize_firebase()
            self._initialized = True
    
    def _initialize_firebase(self):
        """
        Initialize Firebase Admin SDK
        Supports three modes:
        1. Mock mode (USE_MOCK_FIREBASE=True) - for development without credentials
        2. GOOGLE_APPLICATION_CREDENTIALS env var pointing to JSON file (production recommended)
        3. FIREBASE_CREDENTIALS_JSON env var with inline JSON string (alternative)
        """
        import json
        from dotenv import load_dotenv
        
        # Load .env file for development
        load_dotenv()
        
        # Check if mock mode is enabled
        use_mock = os.getenv('USE_MOCK_FIREBASE', 'False').lower() == 'true'
        
        if use_mock:
            logger.warning("🔧 Running in MOCK mode - using in-memory database (no real Firebase)")
            self._db = MockFirestoreClient()
            self._auth_client = MockAuth()
            self._mock_mode = True
            return
        
        try:
            # Method 1: Try GOOGLE_APPLICATION_CREDENTIALS (standard for GCP/AWS)
            google_creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            
            if google_creds_path:
                logger.info(f"Loading Firebase credentials from GOOGLE_APPLICATION_CREDENTIALS: {google_creds_path}")
                cred = credentials.Certificate(google_creds_path)
            else:
                # Method 2: Try inline JSON from FIREBASE_CREDENTIALS_JSON
                firebase_creds_json = os.getenv('FIREBASE_CREDENTIALS_JSON')
                
                if firebase_creds_json:
                    logger.info("Loading Firebase credentials from FIREBASE_CREDENTIALS_JSON environment variable")
                    cred_dict = json.loads(firebase_creds_json)
                    cred = credentials.Certificate(cred_dict)
                else:
                    # No credentials found - fail with clear message
                    raise ValueError(
                        "Firebase credentials not found. Please set either:\n"
                        "  - USE_MOCK_FIREBASE=True (for development), or\n"
                        "  - GOOGLE_APPLICATION_CREDENTIALS=/path/to/firebase-key.json (recommended for AWS), or\n"
                        "  - FIREBASE_CREDENTIALS_JSON='{...}' (inline JSON string)"
                    )
            
            # Initialize Firebase app
            firebase_admin.initialize_app(cred)
            
            # Initialize Firestore client
            self._db = firestore.client()
            self._auth_client = auth
            self._mock_mode = False
            
            logger.info(f"✅ Firebase initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Firebase: {e}")
            raise
    
    @property
    def db(self) -> firestore.Client:
        """Get Firestore client instance"""
        return self._db
    
    @property
    def auth_client(self):
        """Get Firebase Auth client"""
        return self._auth_client if hasattr(self, '_auth_client') else auth


# Global Firebase client instance
firebase_client = FirebaseClient()
db = firebase_client.db
auth_client = firebase_client.auth_client


# ==================== Collection References ====================
class Collections:
    """Firestore collection names"""
    USERS = "users"
    VEHICLES = "vehicles"
    BOOKINGS = "bookings"
    BRANCHES = "branches"
    CHAT_SESSIONS = "chat_sessions"
    CHAT_MESSAGES = "chat_messages"
    PAYMENTS = "payments"
    COMPETITORS = "competitor_prices"
    PRICING_LOGS = "pricing_logs"
    
    # Dynamic Pricing System Collections
    COMPETITOR_AGGREGATES = "competitor_aggregates"
    UTILIZATION_SNAPSHOTS = "utilization_snapshots"
    DEMAND_SIGNALS = "demand_signals"
    PRICE_QUOTES = "price_quotes"
    PRICING_HISTORY = "pricing_history"
    PRICING_DECISIONS = "pricing_decisions"
    ML_MODELS = "ml_models"
    
    # Audit Trail Collections
    VEHICLE_HISTORY = "vehicle_history"


# ==================== Authentication Functions ====================

def verify_id_token(token: str) -> Dict[str, Any]:
    """
    Verify Firebase ID token and return decoded claims.
    
    Args:
        token: Firebase ID token from client
        
    Returns:
        Decoded token claims including uid, email, etc.
        
    Raises:
        ValueError: If token is invalid or expired
    """
    try:
        decoded_token = auth_client.verify_id_token(token)
        return decoded_token
    except auth.InvalidIdTokenError:
        raise ValueError("Invalid ID token")
    except auth.ExpiredIdTokenError:
        raise ValueError("Token has expired")
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise ValueError(f"Token verification failed: {str(e)}")


def get_user(uid: str) -> Optional[Dict[str, Any]]:
    """
    Get user data from Firestore by UID.
    
    Args:
        uid: Firebase user UID
        
    Returns:
        User document data or None if not found
    """
    try:
        user_ref = db.collection(Collections.USERS).document(uid)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            return user_doc.to_dict()
        return None
    except Exception as e:
        logger.error(f"Error fetching user {uid}: {e}")
        return None


def create_user(email: str, password: str, **kwargs) -> Dict[str, Any]:
    """
    Create a new Firebase user and store in Firestore.
    
    Args:
        email: User email
        password: User password
        **kwargs: Additional user data (name, phone, role, etc.)
        
    Returns:
        Created user data including uid
        
    Raises:
        ValueError: If user creation fails
    """
    try:
        # Create Firebase Auth user
        user_record = auth_client.create_user(
            email=email,
            password=password,
            email_verified=False
        )
        
        # Prepare user document data
        user_data = {
            'uid': user_record.uid,
            'email': email,
            'name': kwargs.get('name', ''),
            'phone': kwargs.get('phone', ''),
            'role': kwargs.get('role', 'consumer'),
            'is_active': True,
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        
        # Store in Firestore
        db.collection(Collections.USERS).document(user_record.uid).set(user_data)
        
        # Set custom claims for role-based access
        auth_client.set_custom_user_claims(user_record.uid, {'role': user_data['role']})
        
        logger.info(f"✅ User created successfully: {email}")
        
        return user_data
        
    except auth.EmailAlreadyExistsError:
        raise ValueError("Email already exists")
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise ValueError(f"User creation failed: {str(e)}")


def update_user(uid: str, data: Dict[str, Any]) -> bool:
    """
    Update user data in Firestore.
    
    Args:
        uid: User UID
        data: Dictionary of fields to update
        
    Returns:
        True if successful
    """
    try:
        data['updated_at'] = firestore.SERVER_TIMESTAMP
        db.collection(Collections.USERS).document(uid).update(data)
        return True
    except Exception as e:
        logger.error(f"Error updating user {uid}: {e}")
        return False


def delete_user(uid: str) -> bool:
    """
    Delete user from Firebase Auth and Firestore.
    
    Args:
        uid: User UID
        
    Returns:
        True if successful
    """
    try:
        # Delete from Firebase Auth
        auth_client.delete_user(uid)
        
        # Delete from Firestore
        db.collection(Collections.USERS).document(uid).delete()
        
        logger.info(f"✅ User deleted: {uid}")
        return True
    except Exception as e:
        logger.error(f"Error deleting user {uid}: {e}")
        return False


# ==================== Firestore Helper Functions ====================

def get_document(collection: str, doc_id: str) -> Optional[Dict[str, Any]]:
    """Get a document from Firestore by ID"""
    try:
        doc_ref = db.collection(collection).document(doc_id)
        doc = doc_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None
    except Exception as e:
        logger.error(f"Error getting document {collection}/{doc_id}: {e}")
        return None


def create_document(collection: str, data: Dict[str, Any], doc_id: Optional[str] = None) -> Optional[str]:
    """
    Create a new document in Firestore.
    
    Returns:
        Document ID if successful, None otherwise
    """
    try:
        data['created_at'] = firestore.SERVER_TIMESTAMP
        data['updated_at'] = firestore.SERVER_TIMESTAMP
        
        if doc_id:
            db.collection(collection).document(doc_id).set(data)
            return doc_id
        else:
            doc_ref = db.collection(collection).add(data)
            return doc_ref[1].id
    except Exception as e:
        logger.error(f"Error creating document in {collection}: {e}")
        return None


def update_document(collection: str, doc_id: str, data: Dict[str, Any]) -> bool:
    """Update a document in Firestore"""
    try:
        data['updated_at'] = firestore.SERVER_TIMESTAMP
        db.collection(collection).document(doc_id).update(data)
        return True
    except Exception as e:
        logger.error(f"Error updating document {collection}/{doc_id}: {e}")
        return False


def delete_document(collection: str, doc_id: str) -> bool:
    """Delete a document from Firestore"""
    try:
        db.collection(collection).document(doc_id).delete()
        return True
    except Exception as e:
        logger.error(f"Error deleting document {collection}/{doc_id}: {e}")
        return False


def query_documents(
    collection: str,
    filters: Optional[List[tuple]] = None,
    order_by: Optional[str] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Query documents from Firestore with filters.
    
    Args:
        collection: Collection name
        filters: List of tuples (field, operator, value)
        order_by: Field to order by
        limit: Maximum number of results
        
    Returns:
        List of documents
    """
    try:
        query = db.collection(collection)
        
        # Apply filters
        if filters:
            for field, operator, value in filters:
                query = query.where(field, operator, value)
        
        # Apply ordering
        if order_by:
            query = query.order_by(order_by)
        
        # Apply limit
        if limit:
            query = query.limit(limit)
        
        # Execute query
        docs = query.stream()
        
        results = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            results.append(data)
        
        return results
    except Exception as e:
        logger.error(f"Error querying {collection}: {e}")
        return []


# ==================== Vehicle Base Rate Update (Atomic) ====================

def update_vehicle_base_rate(
    vehicle_id: str,
    new_base_daily_rate: float,
    reason: str,
    triggered_by: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Atomically update a vehicle's base_daily_rate with audit trail.
    
    Uses Firestore batched write to guarantee:
    - vehicle_history doc is written
    - vehicle doc is updated
    Both happen together or neither happens.
    
    Args:
        vehicle_id: Vehicle document ID
        new_base_daily_rate: New base daily rate (must be float > 0)
        reason: Reason for change (manual_update, apply_recommendation, migration, etc.)
        triggered_by: Optional dict with uid and email of user who triggered change
        context: Optional traceability context (pricing_decision_id, model_version, competitor_snapshot)
        
    Returns:
        dict with:
            - status: "no_change" | "updated" | "error"
            - vehicle_id: str
            - old_base_daily_rate: float (if updated)
            - new_base_daily_rate: float (if updated)
            - history_id: str (if updated)
            - error: str (if error)
    """
    try:
        # Validate input
        new_base_daily_rate = float(new_base_daily_rate)
        if new_base_daily_rate <= 0:
            return {
                'status': 'error',
                'vehicle_id': vehicle_id,
                'error': 'new_base_daily_rate must be > 0'
            }
        
        # Read existing vehicle document
        vehicle_ref = db.collection(Collections.VEHICLES).document(vehicle_id)
        vehicle_doc = vehicle_ref.get()
        
        if not vehicle_doc.exists:
            logger.warning(f"Vehicle {vehicle_id} not found for base rate update")
            return {
                'status': 'error',
                'vehicle_id': vehicle_id,
                'error': f'Vehicle {vehicle_id} not found'
            }
        
        vehicle_data = vehicle_doc.to_dict()
        old_base_daily_rate = vehicle_data.get('base_daily_rate')
        
        # Ensure old rate is float for comparison
        if old_base_daily_rate is not None:
            old_base_daily_rate = float(old_base_daily_rate)
        
        # Check if rate actually changed
        if old_base_daily_rate == new_base_daily_rate:
            logger.info(f"Vehicle {vehicle_id}: base_daily_rate unchanged at {new_base_daily_rate}")
            return {
                'status': 'no_change',
                'vehicle_id': vehicle_id,
                'base_daily_rate': new_base_daily_rate
            }
        
        # Calculate delta
        delta_amount = float(new_base_daily_rate - (old_base_daily_rate or 0))
        
        # Guard against division by zero
        if old_base_daily_rate and old_base_daily_rate > 0:
            delta_percent = float((new_base_daily_rate - old_base_daily_rate) / old_base_daily_rate)
        else:
            delta_percent = None
        
        # Build history record
        history_record = {
            'created_at': firestore.SERVER_TIMESTAMP,
            'vehicle_id': vehicle_id,
            'branch_key': vehicle_data.get('branch_key'),
            'change_type': 'base_daily_rate_change',
            'old_base_daily_rate': float(old_base_daily_rate) if old_base_daily_rate else None,
            'new_base_daily_rate': float(new_base_daily_rate),
            'delta_amount': delta_amount,
            'delta_percent': delta_percent,
            'currency': 'SAR',
            'reason': reason or 'manual_update',
            'triggered_by': triggered_by,
            'request_context': context,
            # Additional context
            'vehicle_name': vehicle_data.get('name'),
            'vehicle_brand': vehicle_data.get('brand'),
            'vehicle_category': vehicle_data.get('category')
        }
        
        # Use batched write for atomicity
        batch = db.batch()
        
        # 1. Create history document (auto-generated ID)
        history_ref = db.collection(Collections.VEHICLE_HISTORY).document()
        batch.set(history_ref, history_record)
        
        # 2. Update vehicle document
        batch.update(vehicle_ref, {
            'base_daily_rate': float(new_base_daily_rate),
            'updated_at': firestore.SERVER_TIMESTAMP
        })
        
        # Commit both writes atomically
        batch.commit()
        
        logger.info(
            f"Vehicle {vehicle_id}: base_daily_rate updated "
            f"{old_base_daily_rate} -> {new_base_daily_rate} "
            f"(delta: {delta_amount:+.2f}, reason: {reason})"
        )
        
        return {
            'status': 'updated',
            'vehicle_id': vehicle_id,
            'old_base_daily_rate': old_base_daily_rate,
            'new_base_daily_rate': new_base_daily_rate,
            'delta_amount': delta_amount,
            'delta_percent': delta_percent,
            'history_id': history_ref.id,
            'reason': reason
        }
        
    except Exception as e:
        logger.error(f"Error updating vehicle {vehicle_id} base rate: {e}")
        return {
            'status': 'error',
            'vehicle_id': vehicle_id,
            'error': str(e)
        }
