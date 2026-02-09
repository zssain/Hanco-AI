"""
ONNX Runtime Inference Service with Model Caching and Hot-Reload
Loads ONNX models with automatic version tracking and Firebase Storage integration
"""
import numpy as np
from typing import Dict, Optional
import os
import logging
import tempfile
from datetime import datetime, timedelta

# Try to import onnxruntime, but make it optional
try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("⚠️ onnxruntime not available - ML predictions will be disabled")
    ONNX_AVAILABLE = False
    ort = None

try:
    from firebase_admin import storage
    STORAGE_AVAILABLE = True
except Exception:
    STORAGE_AVAILABLE = False

from app.core.firebase import db, Collections

logger = logging.getLogger(__name__)

# Feature order (must match training)
FEATURE_ORDER = [
    'rental_length_days',
    'day_of_week',
    'month',
    'base_daily_rate',
    'avg_temp',
    'rain',
    'wind',
    'avg_competitor_price',
    'demand_index',
    'bias'
]


class ModelCache:
    """
    Global cache for ONNX model sessions with hot-reload support
    
    Features:
    - Caches model sessions in memory to avoid re-loading
    - Tracks model versions from Firestore ml_models collection
    - Auto-reloads when new version is detected
    - TTL on version checks (60s) to reduce Firestore reads
    - Downloads models from Firebase Storage when needed
    """
    
    def __init__(self, registry_ttl_seconds: int = 60):
        if ONNX_AVAILABLE and ort:
            self.sessions: Dict[str, ort.InferenceSession] = {}
        else:
            self.sessions: Dict[str, None] = {}
        self.versions: Dict[str, str] = {}
        self.last_check: Dict[str, datetime] = {}
        self.registry_ttl = timedelta(seconds=registry_ttl_seconds)
        self.temp_dir = tempfile.mkdtemp(prefix="onnx_models_")
        logger.info(f"Model cache initialized with {registry_ttl_seconds}s TTL")
    
    def _should_check_registry(self, model_name: str) -> bool:
        """Check if we should query Firestore registry (respects TTL)"""
        if model_name not in self.last_check:
            return True
        
        elapsed = datetime.utcnow() - self.last_check[model_name]
        return elapsed > self.registry_ttl
    
    def _get_model_registry(self, model_name: str) -> Optional[Dict]:
        """
        Get model metadata from Firestore ml_models collection
        
        Returns active_version metadata including version string and storage_path
        """
        try:
            model_ref = db.collection(Collections.ML_MODELS).document(model_name)
            model_doc = model_ref.get()
            
            if not model_doc.exists:
                logger.warning(f"Model {model_name} not found in ml_models registry")
                return None
            
            model_data = model_doc.to_dict()
            active_version = model_data.get('active_version')
            
            if not active_version:
                logger.warning(f"No active_version for model {model_name}")
                return None
            
            self.last_check[model_name] = datetime.utcnow()
            return active_version
            
        except Exception as e:
            logger.error(f"Error reading model registry for {model_name}: {str(e)}")
            return None
    
    def _download_model_from_storage(self, storage_path: str, local_path: str) -> bool:
        """
        Download model file from Firebase Storage
        
        Args:
            storage_path: Path in Firebase Storage (e.g., ml_models/model_name/v1.0.0.onnx)
            local_path: Local file path to save to
            
        Returns:
            True if successful
        """
        try:
            logger.info(f"Downloading model from Firebase Storage: {storage_path}")
            
            bucket = storage.bucket()
            blob = bucket.blob(storage_path)
            blob.download_to_filename(local_path)
            
            logger.info(f"Model downloaded successfully to {local_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading model from storage: {str(e)}")
            return False
    
    def _load_local_fallback(self, model_name: str) -> Optional[str]:
        """
        Try to load model from local filesystem as fallback
        
        Returns local path if found
        """
        # Try standard local paths
        current_dir = os.path.dirname(os.path.abspath(__file__))
        local_paths = [
            os.path.join(current_dir, '..', '..', 'ml', 'models', 'model.onnx'),
            os.path.join(current_dir, '..', '..', 'ml', 'models', f'{model_name}.onnx'),
            f'./ml/models/{model_name}.onnx',
            f'./models/{model_name}.onnx'
        ]
        
        for path in local_paths:
            if os.path.exists(path):
                logger.info(f"Found local model at {path}")
                return path
        
        return None
    
    def get_session(self, model_name: str = 'baseline_pricing_model') -> ort.InferenceSession:
        """
        Get cached ONNX session or load/reload if needed
        
        Args:
            model_name: Name of model in ml_models collection
            
        Returns:
            ONNX InferenceSession ready for inference
            
        Raises:
            FileNotFoundError: If model cannot be found/loaded
        """
        # Check if we should query registry (respects TTL)
        should_check = self._should_check_registry(model_name)
        
        if should_check:
            registry_data = self._get_model_registry(model_name)
            
            if registry_data:
                new_version = registry_data.get('version')
                storage_path = registry_data.get('storage_path')
                cached_version = self.versions.get(model_name)
                
                # Check if version changed (or first load)
                if new_version != cached_version:
                    logger.info(
                        f"Model version changed for {model_name}: "
                        f"{cached_version} -> {new_version}"
                    )
                    
                    # Download and load new version
                    if storage_path:
                        local_path = os.path.join(
                            self.temp_dir,
                            f"{model_name}_{new_version}.onnx"
                        )
                        
                        # Download from Firebase Storage
                        if self._download_model_from_storage(storage_path, local_path):
                            try:
                                # Load ONNX session
                                session = ort.InferenceSession(local_path)
                                
                                # Update cache
                                self.sessions[model_name] = session
                                self.versions[model_name] = new_version
                                
                                logger.info(
                                    f"✅ Model {model_name} v{new_version} loaded successfully"
                                )
                                return session
                                
                            except Exception as e:
                                logger.error(f"Error loading ONNX session: {str(e)}")
                        else:
                            logger.warning(f"Failed to download model from {storage_path}")
        
        # Return cached session if available
        if model_name in self.sessions:
            return self.sessions[model_name]
        
        # Fallback: try to load from local filesystem
        logger.warning(
            f"No cached session for {model_name}, attempting local fallback"
        )
        
        local_path = self._load_local_fallback(model_name)
        
        if local_path:
            try:
                session = ort.InferenceSession(local_path)
                self.sessions[model_name] = session
                self.versions[model_name] = 'local_fallback'
                logger.info(f"✅ Loaded {model_name} from local fallback: {local_path}")
                return session
                
            except Exception as e:
                logger.error(f"Error loading local fallback: {str(e)}")
        
        # No model available
        raise FileNotFoundError(
            f"Model {model_name} not found in cache, registry, or local filesystem. "
            f"Train a model first using: python -m app.workers.train_models"
        )
    
    def clear_cache(self, model_name: Optional[str] = None):
        """Clear cached sessions (useful for testing or manual reload)"""
        if model_name:
            self.sessions.pop(model_name, None)
            self.versions.pop(model_name, None)
            self.last_check.pop(model_name, None)
            logger.info(f"Cleared cache for {model_name}")
        else:
            self.sessions.clear()
            self.versions.clear()
            self.last_check.clear()
            logger.info("Cleared all model caches")


# Global singleton cache
_model_cache = ModelCache(registry_ttl_seconds=60)


def get_model_cache() -> ModelCache:
    """Get the global model cache instance"""
    return _model_cache


def predict_price(
    features: Dict[str, float],
    model_name: str = 'baseline_pricing_model'
) -> float:
    """
    Predict price using cached ONNX model with hot-reload support
    
    Args:
        features: Dictionary with keys:
            - rental_length_days
            - day_of_week
            - month
            - base_daily_rate
            - avg_temp
            - rain
            - wind
            - avg_competitor_price
            - demand_index
            - bias
        model_name: Name of model in ml_models registry (default: 'baseline_pricing_model')
    
    Returns:
        Predicted daily price as float
        
    Raises:
        ValueError: If required features are missing
        FileNotFoundError: If model cannot be loaded
    """
    # If ONNX is not available, return a simple baseline prediction
    if not ONNX_AVAILABLE:
        logger.warning("ONNX not available, using fallback pricing")
        base_rate = features.get('base_daily_rate', 100.0)
        rental_days = features.get('rental_length_days', 1)
        demand = features.get('demand_index', 1.0)
        competitor_price = features.get('avg_competitor_price', base_rate)
        
        # Simple fallback formula
        price = base_rate * (1.0 - 0.05 * min(rental_days - 1, 10)) * demand
        price = (price + competitor_price) / 2  # Average with competitor
        return max(price, base_rate * 0.5)  # At least 50% of base rate
    
    try:
        # Validate features
        missing_features = [f for f in FEATURE_ORDER if f not in features]
        if missing_features:
            raise ValueError(f"Missing features: {missing_features}")
        
        # Get cached session (with auto-reload)
        cache = get_model_cache()
        session = cache.get_session(model_name)
        
        # Convert dict to ordered numpy array
        feature_vector = np.array([
            [features[f] for f in FEATURE_ORDER]
        ], dtype=np.float32)
        
        # Run inference
        result = session.run(None, {'features': feature_vector})
        predicted_price = float(result[0][0][0])
        
        logger.debug(f"Predicted price: ${predicted_price:.2f} (model: {model_name})")
        
        return predicted_price
        
    except Exception as e:
        logger.error(f"Error predicting price: {str(e)}")
        raise


def predict_booking_probability(
    features: Dict[str, float],
    model_name: str = 'booking_probability_model'
) -> float:
    """
    Predict booking probability using cached ONNX model
    
    Args:
        features: Dictionary of feature name -> value
        model_name: Name of model in ml_models registry
    
    Returns:
        Predicted booking probability (0.0 to 1.0)
    """
    try:
        # Get cached session
        cache = get_model_cache()
        session = cache.get_session(model_name)
        
        # Prepare features (feature order must match training)
        # This is model-specific - adjust based on your training
        feature_vector = np.array([[
            features.get('rental_length_days', 1),
            features.get('day_of_week', 0),
            features.get('month', 1),
            features.get('lead_time_days', 7),
            features.get('base_daily_rate', 100.0),
            features.get('avg_temp', 25.0),
            features.get('rain', 0.0),
            features.get('wind', 10.0),
            features.get('avg_competitor_price', 100.0),
            features.get('demand_index', 0.5),
            features.get('utilization_rate', 0.5),
            features.get('baseline_price_ml', 100.0),
            features.get('daily_price', 100.0),
            features.get('price_premium_pct', 0.0),
        ]], dtype=np.float32)
        
        # Run inference
        result = session.run(None, {'input': feature_vector})
        probability = float(result[0][0][0])
        
        logger.debug(f"Predicted booking probability: {probability:.2%}")
        
        return probability
        
    except FileNotFoundError:
        # Model doesn't exist yet - return default
        logger.warning(f"Booking probability model not found, returning default 0.5")
        return 0.5
    except Exception as e:
        logger.error(f"Error predicting booking probability: {str(e)}")
        return 0.5
