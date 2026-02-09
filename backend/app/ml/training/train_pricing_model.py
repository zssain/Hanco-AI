"""
Train a real pricing model using Saudi car rental dataset and export to ONNX.

This script replaces the dummy ONNX model with a trained GradientBoostingRegressor
while maintaining exact compatibility with the existing pricing engine interfaces.

Run training:
    python app/ml/training/train_pricing_model.py

Requirements:
    - Dataset at: app/ml/data/saudi_car_rental_synthetic.csv
    - Output: app/ml/models/model.onnx (overwrites dummy model)
"""

import os
import sys
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import onnx
import onnxruntime as ort
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
from datetime import datetime, timedelta

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    print("⚠️  Firebase Admin SDK not available - will use default competitor prices")


# Feature order MUST match onnx_runtime.py exactly
FEATURE_ORDER = [
    "rental_length_days",
    "day_of_week",
    "month",
    "base_daily_rate",
    "avg_temp",
    "rain",
    "wind",
    "avg_competitor_price",
    "demand_index",
    "bias",
]

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_PATH = SCRIPT_DIR.parent / "data" / "saudi_car_rental_synthetic.csv"
REAL_DATA_PATH = SCRIPT_DIR.parent / "data" / "pricing_training_real.csv"
MODEL_OUTPUT_PATH = SCRIPT_DIR.parent / "models" / "model.onnx"

# Training source configuration: "real" or "synthetic"
# Set to "real" to use pricing_training_real.csv from Firestore exports
# Set to "synthetic" to use saudi_car_rental_synthetic.csv
TRAINING_SOURCE = "synthetic"  # Change to "real" when sufficient real data available


def initialize_firebase():
    """
    Initialize Firebase Admin SDK if not already initialized.
    
    Returns:
        Firestore client or None if initialization fails
    """
    if not FIREBASE_AVAILABLE:
        return None
    
    try:
        # Check if already initialized
        try:
            app = firebase_admin.get_app()
            return firestore.client()
        except ValueError:
            # Not initialized, try to initialize
            cred_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
            if cred_path and Path(cred_path).exists():
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                return firestore.client()
            else:
                print("   ⚠️  GOOGLE_APPLICATION_CREDENTIALS not set or file not found")
                return None
    except Exception as e:
        print(f"   ⚠️  Firebase initialization failed: {e}")
        return None


def fetch_competitor_prices_from_firestore(db, hours_lookback=168):
    """
    Fetch recent competitor prices from Firestore.
    
    Args:
        db: Firestore client
        hours_lookback: How far back to look (default: 7 days = 168 hours)
        
    Returns:
        Dictionary mapping (branch_id, vehicle_bucket) to avg price
    """
    if db is None:
        return {}
    
    print(f"\n🔍 Fetching competitor prices from Firestore (last {hours_lookback} hours)...")
    
    try:
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_lookback)
        
        # Query competitor_prices_latest collection
        prices_ref = db.collection('competitor_prices_latest')
        
        # Get all documents (no complex query to avoid index requirement)
        docs = prices_ref.stream()
        
        # Aggregate prices by (branch_id, vehicle_bucket)
        price_data = {}
        doc_count = 0
        
        for doc in docs:
            data = doc.to_dict()
            
            # Filter by scraped_at time
            scraped_at = data.get('scraped_at')
            if scraped_at and scraped_at < cutoff_time:
                continue
            
            branch_id = data.get('branch_id', 'unknown')
            bucket = data.get('vehicle_bucket', 'Other')
            price = data.get('price_per_day', 0)
            
            if price > 0:
                key = (branch_id, bucket)
                if key not in price_data:
                    price_data[key] = []
                price_data[key].append(price)
                doc_count += 1
        
        # Calculate averages
        avg_prices = {}
        for key, prices in price_data.items():
            avg_prices[key] = np.mean(prices)
        
        print(f"   ✓ Loaded {doc_count} competitor prices across {len(avg_prices)} (branch, bucket) combinations")
        
        # Show sample
        if avg_prices:
            print("   Sample competitor prices:")
            for i, (key, price) in enumerate(list(avg_prices.items())[:5]):
                branch, bucket = key
                print(f"     {branch}/{bucket}: {price:.2f} SAR")
        
        return avg_prices
        
    except Exception as e:
        print(f"   ⚠️  Error fetching competitor prices: {e}")
        return {}


def export_pricing_decisions_to_csv(db, days_lookback: int = 90) -> str:
    """
    Export pricing decisions from Firestore to CSV for ONNX training.
    
    Fetches pricing_decisions from the last N days and writes to:
    app/ml/data/pricing_training_real.csv
    
    Each row contains:
    - ONNX features: rental_length_days, day_of_week, month, base_daily_rate,
                     avg_temp, rain, wind, avg_competitor_price, demand_index, bias
    - Target: daily_price (from final_price_per_day)
    - Analysis columns: branch_key, class_bucket, durationKey, providers_used_count
    
    Args:
        db: Firestore client
        days_lookback: How many days back to fetch (default: 90)
        
    Returns:
        Path to the exported CSV file
    """
    if db is None:
        print("❌ Firebase not available - cannot export pricing decisions")
        return None
    
    print(f"\n📊 Exporting pricing decisions from Firestore (last {days_lookback} days)...")
    
    try:
        cutoff_time = datetime.utcnow() - timedelta(days=days_lookback)
        
        # Query pricing_decisions collection
        decisions_ref = db.collection('pricing_decisions')
        
        # Fetch all documents (filter by date in code to avoid index issues)
        docs = list(decisions_ref.stream())
        print(f"   Found {len(docs)} total pricing decisions")
        
        # Process documents
        rows = []
        skipped_old = 0
        skipped_missing = 0
        
        for doc in docs:
            data = doc.to_dict()
            
            # Filter by created_at
            created_at = data.get('created_at')
            if created_at:
                # Handle Firestore timestamp
                if hasattr(created_at, 'timestamp'):
                    created_at = datetime.fromtimestamp(created_at.timestamp())
                elif isinstance(created_at, datetime):
                    pass  # Already a datetime
                else:
                    created_at = None
            
            if created_at and created_at < cutoff_time:
                skipped_old += 1
                continue
            
            # Extract ONNX features from onnx_features dict
            onnx_features = data.get('onnx_features', {})
            
            # Get avg_competitor_price - recompute if missing
            avg_competitor_price = onnx_features.get('avg_competitor_price')
            if avg_competitor_price is None or avg_competitor_price == 0:
                # Try to recompute from market_stats
                market_stats = data.get('market_stats', {})
                if market_stats and market_stats.get('median'):
                    avg_competitor_price = market_stats.get('median')
                else:
                    # Fallback: use base_daily_rate if available
                    avg_competitor_price = onnx_features.get('base_daily_rate', 150.0)
            
            # Get final_price_per_day as target
            final_price = data.get('final_price_per_day')
            if final_price is None:
                skipped_missing += 1
                continue
            
            # Get providers_used for Key provider check
            providers_used = data.get('market_stats', {}).get('providers_used', [])
            providers_used_count = len(providers_used) if providers_used else 0
            
            # Ensure 'Key' provider is represented in count (if exists in data)
            # Note: 'Key' is included if it was in the original scrape
            
            # Build row with all required columns
            row = {
                # ONNX features (in FEATURE_ORDER)
                'rental_length_days': onnx_features.get('rental_length_days', data.get('duration_days', 1)),
                'day_of_week': onnx_features.get('day_of_week', 0),
                'month': onnx_features.get('month', 1),
                'base_daily_rate': onnx_features.get('base_daily_rate', data.get('base_daily_rate', 150.0)),
                'avg_temp': onnx_features.get('avg_temp', 25.0),
                'rain': onnx_features.get('rain', 0.0),
                'wind': onnx_features.get('wind', 10.0),
                'avg_competitor_price': avg_competitor_price,
                'demand_index': onnx_features.get('demand_index', 0.5),
                'bias': onnx_features.get('bias', 1.0),
                
                # Target
                'daily_price': final_price,
                
                # Analysis columns
                'branch_key': data.get('branch_key', ''),
                'class_bucket': data.get('class_bucket', ''),
                'durationKey': data.get('durationKey', ''),
                'providers_used_count': providers_used_count,
            }
            
            rows.append(row)
        
        print(f"   Processed {len(rows)} valid decisions (skipped {skipped_old} old, {skipped_missing} missing price)")
        
        if not rows:
            print("   ⚠️  No valid pricing decisions found - cannot create training file")
            return None
        
        # Create DataFrame
        df = pd.DataFrame(rows)
        
        # Ensure column order
        columns = [
            # ONNX features
            'rental_length_days', 'day_of_week', 'month', 'base_daily_rate',
            'avg_temp', 'rain', 'wind', 'avg_competitor_price', 'demand_index', 'bias',
            # Target
            'daily_price',
            # Analysis
            'branch_key', 'class_bucket', 'durationKey', 'providers_used_count'
        ]
        df = df[columns]
        
        # Save to CSV
        REAL_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(REAL_DATA_PATH, index=False)
        
        print(f"\n✅ Exported {len(df)} rows to: {REAL_DATA_PATH}")
        print(f"\n   Feature summary:")
        print(f"     rental_length_days: {df['rental_length_days'].min():.0f} - {df['rental_length_days'].max():.0f} days")
        print(f"     base_daily_rate: {df['base_daily_rate'].min():.0f} - {df['base_daily_rate'].max():.0f} SAR")
        print(f"     avg_competitor_price: {df['avg_competitor_price'].min():.0f} - {df['avg_competitor_price'].max():.0f} SAR")
        print(f"     daily_price (target): {df['daily_price'].min():.0f} - {df['daily_price'].max():.0f} SAR")
        print(f"     unique branches: {df['branch_key'].nunique()}")
        print(f"     unique class_buckets: {df['class_bucket'].nunique()}")
        
        return str(REAL_DATA_PATH)
        
    except Exception as e:
        print(f"   ❌ Error exporting pricing decisions: {e}")
        import traceback
        traceback.print_exc()
        return None


def enrich_with_competitor_prices(df: pd.DataFrame, competitor_prices: dict) -> pd.DataFrame:
    """
    Enrich dataset with real competitor prices from Firestore.
    
    Args:
        df: Training dataset
        competitor_prices: Dictionary mapping (branch_id, bucket) to avg price
        
    Returns:
        Enriched DataFrame with real avg_competitor_price
    """
    if not competitor_prices:
        print("\n   ℹ️  No competitor prices available - using defaults")
        return df
    
    print(f"\n💰 Enriching dataset with real competitor prices...")
    
    # Assume dataset has 'branch_id' and 'vehicle_bucket' columns
    # If not, we'll create synthetic mappings
    
    if 'branch_id' not in df.columns:
        print("   ⚠️  No 'branch_id' column - using default branch mapping")
        # Map to common airports
        branches = ['riyadh_airport', 'jeddah_airport', 'dammam_airport']
        df['branch_id'] = np.random.choice(branches, size=len(df))
    
    if 'vehicle_bucket' not in df.columns:
        print("   ⚠️  No 'vehicle_bucket' column - inferring from category")
        # Try to infer from vehicle_class or category columns
        if 'vehicle_class' in df.columns:
            # Map vehicle classes to buckets
            bucket_map = {
                'economy': 'Compact',
                'compact': 'Compact',
                'sedan': 'Sedan',
                'midsize': 'Sedan',
                'suv': 'SUV',
                'luxury': 'Luxury'
            }
            df['vehicle_bucket'] = df['vehicle_class'].str.lower().map(bucket_map).fillna('Other')
        else:
            # Random assignment
            buckets = ['Compact', 'Sedan', 'SUV', 'Luxury', 'Other']
            df['vehicle_bucket'] = np.random.choice(buckets, size=len(df))
    
    # Create lookup key and fetch competitor prices
    enriched_count = 0
    new_prices = []
    
    for idx, row in df.iterrows():
        branch = row.get('branch_id', 'unknown')
        bucket = row.get('vehicle_bucket', 'Other')
        key = (branch, bucket)
        
        comp_price = competitor_prices.get(key)
        if comp_price:
            new_prices.append(comp_price)
            enriched_count += 1
        else:
            # Fallback: try just bucket (ignore branch)
            bucket_prices = [p for (b, bkt), p in competitor_prices.items() if bkt == bucket]
            if bucket_prices:
                new_prices.append(np.mean(bucket_prices))
                enriched_count += 1
            else:
                # Use default
                new_prices.append(row.get('avg_competitor_price', 100.0))
    
    df['avg_competitor_price'] = new_prices
    
    print(f"   ✓ Enriched {enriched_count}/{len(df)} rows with real competitor prices")
    print(f"   avg_competitor_price range: {df['avg_competitor_price'].min():.2f} - {df['avg_competitor_price'].max():.2f} SAR")
    print(f"   avg_competitor_price mean: {df['avg_competitor_price'].mean():.2f} SAR")
    
    return df


def load_and_preprocess_data(csv_path: Path) -> pd.DataFrame:
    """
    Load dataset and preprocess to ensure all required features exist.
    
    Args:
        csv_path: Path to saudi_car_rental_synthetic.csv
        
    Returns:
        DataFrame with all features and daily_price target
    """
    print(f"📂 Loading dataset from: {csv_path}")
    
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Dataset not found at {csv_path}\n"
            f"Please place saudi_car_rental_synthetic.csv in app/ml/data/"
        )
    
    df = pd.read_csv(csv_path)
    print(f"   Loaded {len(df)} rows, {len(df.columns)} columns")
    print(f"   Columns: {list(df.columns)}")
    
    # ========== DERIVE TARGET: daily_price ==========
    if 'daily_price' in df.columns:
        print("   ✓ Found 'daily_price' column")
    elif 'final_daily_price' in df.columns:
        print("   ✓ Found 'final_daily_price' column (renaming to 'daily_price')")
        df['daily_price'] = df['final_daily_price']
    elif 'total_price' in df.columns and 'rental_length_days' in df.columns:
        print("   Converting total_price → daily_price")
        # Guard against division by zero
        df['rental_length_days'] = df['rental_length_days'].replace(0, 1)
        df['daily_price'] = df['total_price'] / df['rental_length_days']
    else:
        raise ValueError(
            "Dataset must have either 'daily_price', 'final_daily_price', or both 'total_price' and 'rental_length_days'"
        )
    
    # ========== ENSURE ALL 10 FEATURES EXIST ==========
    required_features = FEATURE_ORDER.copy()
    
    # bias is always 1.0
    if 'bias' not in df.columns:
        print("   Adding bias column (constant 1.0)")
        df['bias'] = 1.0
    
    # Check for missing features
    missing = [f for f in required_features if f not in df.columns]
    if missing:
        print(f"   ⚠️  Missing features: {missing}")
        print("   Filling with defaults...")
        
        # Default values for missing features
        defaults = {
            'rental_length_days': 3.0,
            'day_of_week': 3.0,  # Wednesday
            'month': 6.0,  # June
            'base_daily_rate': 150.0,
            'avg_temp': 25.0,
            'rain': 0.0,
            'wind': 10.0,
            'avg_competitor_price': 100.0,
            'demand_index': 0.5,
        }
        
        for feat in missing:
            if feat in defaults:
                df[feat] = defaults[feat]
            else:
                df[feat] = 0.0
    
    # ========== HANDLE MISSING VALUES ==========
    print("\n🧹 Handling missing values...")
    for col in required_features + ['daily_price']:
        if df[col].isnull().sum() > 0:
            median_val = df[col].median()
            df[col].fillna(median_val, inplace=True)
            print(f"   Filled {col} with median: {median_val:.2f}")
    
    # ========== VALIDATE DATA QUALITY ==========
    print("\n✅ Data validation:")
    print(f"   rental_length_days range: {df['rental_length_days'].min():.0f} - {df['rental_length_days'].max():.0f}")
    print(f"   base_daily_rate range: {df['base_daily_rate'].min():.0f} - {df['base_daily_rate'].max():.0f}")
    print(f"   daily_price range: {df['daily_price'].min():.0f} - {df['daily_price'].max():.0f}")
    print(f"   avg_temp range: {df['avg_temp'].min():.1f} - {df['avg_temp'].max():.1f}")
    print(f"   demand_index range: {df['demand_index'].min():.2f} - {df['demand_index'].max():.2f}")
    
    return df


def build_train_test_split(df: pd.DataFrame, test_size=0.2, random_state=42):
    """
    Build X, y and split into train/test sets.
    
    Args:
        df: Preprocessed DataFrame
        test_size: Fraction for test set
        random_state: Random seed for reproducibility
        
    Returns:
        X_train, X_test, y_train, y_test
    """
    print(f"\n📊 Building feature matrix with {len(FEATURE_ORDER)} features...")
    
    # Construct X using exact feature order
    X = df[FEATURE_ORDER].copy()
    y = df['daily_price'].copy()
    
    print(f"   X shape: {X.shape}")
    print(f"   y shape: {y.shape}")
    print(f"   Features in order: {FEATURE_ORDER}")
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )
    
    print(f"\n   Train set: {len(X_train)} samples")
    print(f"   Test set:  {len(X_test)} samples")
    
    return X_train, X_test, y_train, y_test


def train_model(X_train: pd.DataFrame, y_train: pd.Series):
    """
    Train GradientBoostingRegressor on training data.
    
    Args:
        X_train: Training features
        y_train: Training target
        
    Returns:
        Trained model
    """
    print("\n🤖 Training GradientBoostingRegressor...")
    
    model = GradientBoostingRegressor(
        n_estimators=100,
        learning_rate=0.1,
        max_depth=5,
        min_samples_split=5,
        min_samples_leaf=2,
        subsample=0.8,
        random_state=42,
        verbose=0
    )
    
    print("   Hyperparameters:")
    print(f"     n_estimators: {model.n_estimators}")
    print(f"     learning_rate: {model.learning_rate}")
    print(f"     max_depth: {model.max_depth}")
    print(f"     subsample: {model.subsample}")
    
    model.fit(X_train, y_train)
    print("   ✓ Training complete")
    
    # Feature importances
    print("\n   Feature Importances:")
    importances = sorted(
        zip(FEATURE_ORDER, model.feature_importances_),
        key=lambda x: x[1],
        reverse=True
    )
    for feat, imp in importances:
        print(f"     {feat:25s}: {imp:.4f}")
    
    return model


def evaluate_model(model, X_test: pd.DataFrame, y_test: pd.Series) -> dict:
    """
    Evaluate model on test set and return metrics.
    
    Args:
        model: Trained model
        X_test: Test features
        y_test: Test target
        
    Returns:
        Dictionary with mae, rmse, r2 metrics
    """
    print("\n📈 Evaluating model on test set...")
    
    y_pred = model.predict(X_test)
    
    # Compute metrics
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)
    
    metrics = {
        'mae': round(mae, 4),
        'rmse': round(rmse, 4),
        'r2': round(r2, 6)
    }
    
    print(f"\n   Metrics:")
    print(f"     MAE:  {mae:.2f} SAR")
    print(f"     RMSE: {rmse:.2f} SAR")
    print(f"     R²:   {r2:.4f}")
    
    # Show example predictions
    print(f"\n   Example predictions (first 10 rows):")
    print(f"   {'True Price':>12s} | {'Predicted':>12s} | {'Error':>10s}")
    print(f"   {'-'*12}-+-{'-'*12}-+-{'-'*10}")
    
    for i in range(min(10, len(y_test))):
        true_val = y_test.iloc[i]
        pred_val = y_pred[i]
        error = pred_val - true_val
        print(f"   {true_val:12.2f} | {pred_val:12.2f} | {error:+10.2f}")
    
    return metrics


def log_training_metadata(db, source: str, rows_used: int, metrics: dict, model_version: str) -> bool:
    """
    Log training metadata to Firestore ml_models collection.
    
    Args:
        db: Firestore client
        source: "real" or "synthetic"
        rows_used: Number of training rows
        metrics: Dict with mae, rmse, r2
        model_version: Hash or timestamp identifier
        
    Returns:
        True if logging succeeded, False otherwise
    """
    if db is None:
        print("\n⚠️  Firebase not available - skipping metadata logging")
        return False
    
    print("\n📝 Logging training metadata to Firestore...")
    
    try:
        import hashlib
        
        # Generate model version if not provided
        if not model_version:
            model_version = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        metadata = {
            'trained_at': datetime.utcnow(),
            'source': source,
            'rows_used': rows_used,
            'metrics': {
                'mae': metrics.get('mae', 0),
                'rmse': metrics.get('rmse', 0),
                'r2': metrics.get('r2', 0)
            },
            'model_version': model_version,
            'feature_order': FEATURE_ORDER,
            'model_path': str(MODEL_OUTPUT_PATH),
            'updated_at': datetime.utcnow()
        }
        
        # Write to ml_models/latest_training
        db.collection('ml_models').document('latest_training').set(metadata)
        
        # Also write to versioned document for history
        db.collection('ml_models').document(f'training_{model_version}').set(metadata)
        
        print(f"   ✓ Logged to ml_models/latest_training")
        print(f"   ✓ Logged to ml_models/training_{model_version}")
        print(f"   Model version: {model_version}")
        
        return True
        
    except Exception as e:
        print(f"   ⚠️  Error logging metadata: {e}")
        return False

    return y_pred


def export_to_onnx(model, output_path: Path):
    """
    Convert sklearn model to ONNX format.
    
    Args:
        model: Trained sklearn model
        output_path: Path to save model.onnx
    """
    print(f"\n💾 Exporting model to ONNX format...")
    print(f"   Output: {output_path}")
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Define input type: FloatTensor [None, 10]
    initial_type = [("features", FloatTensorType([None, 10]))]
    
    # Convert to ONNX
    onnx_model = convert_sklearn(
        model,
        initial_types=initial_type,
        target_opset=12  # Compatible opset version
    )
    
    # Save ONNX model
    onnx.save_model(onnx_model, str(output_path))
    
    print(f"   ✓ ONNX model saved ({output_path.stat().st_size / 1024:.1f} KB)")
    
    # Validate ONNX model structure
    onnx_model_check = onnx.load(str(output_path))
    onnx.checker.check_model(onnx_model_check)
    print("   ✓ ONNX model structure validated")


def validate_onnx_model(onnx_path: Path, sklearn_model, X_test: pd.DataFrame):
    """
    Validate ONNX model produces same results as sklearn model.
    
    Args:
        onnx_path: Path to ONNX model
        sklearn_model: Original sklearn model
        X_test: Test features
    """
    print("\n🔍 Validating ONNX model compatibility...")
    
    # Load ONNX model
    sess = ort.InferenceSession(str(onnx_path))
    
    # Get test batch (first 5 rows)
    test_batch = X_test.head(5).values.astype(np.float32)
    
    # Sklearn predictions
    sklearn_preds = sklearn_model.predict(test_batch)
    
    # ONNX predictions
    input_name = sess.get_inputs()[0].name
    onnx_preds = sess.run(None, {input_name: test_batch})[0].flatten()
    
    # Compare
    print(f"\n   Comparison (sklearn vs ONNX):")
    print(f"   {'sklearn':>12s} | {'ONNX':>12s} | {'Diff':>10s}")
    print(f"   {'-'*12}-+-{'-'*12}-+-{'-'*10}")
    
    max_diff = 0.0
    for i in range(len(sklearn_preds)):
        sk_val = sklearn_preds[i]
        onnx_val = onnx_preds[i]
        diff = abs(onnx_val - sk_val)
        max_diff = max(max_diff, diff)
        print(f"   {sk_val:12.2f} | {onnx_val:12.2f} | {diff:10.4f}")
    
    print(f"\n   Maximum difference: {max_diff:.6f}")
    
    if max_diff < 0.01:
        print("   ✅ ONNX model is numerically identical to sklearn model")
    elif max_diff < 1.0:
        print("   ✓ ONNX model is very close to sklearn model (acceptable)")
    else:
        print("   ⚠️  Warning: ONNX model differs significantly from sklearn model")
    
    return max_diff < 1.0


def main(source: str = None):
    """
    Unified training pipeline supporting both real and synthetic data.
    
    Args:
        source: "real" or "synthetic" (defaults to TRAINING_SOURCE config)
    """
    # Use provided source or fall back to config
    training_source = source or TRAINING_SOURCE
    
    print("=" * 70)
    print(f"🚀 HANCO AI - Pricing Model Training Pipeline ({training_source.upper()} DATA)")
    print("=" * 70)
    
    try:
        # Step 1: Initialize Firebase
        db = initialize_firebase()
        if db:
            print("✅ Firebase initialized")
        else:
            print("ℹ️  Firebase not available")
        
        # Step 2: Determine data source and load data
        if training_source == "real":
            # Use real Firestore-exported data
            if not REAL_DATA_PATH.exists():
                if db:
                    print("\n📊 Real training data not found - exporting from Firestore...")
                    result = export_pricing_decisions_to_csv(db, days_lookback=90)
                    if not result:
                        print("❌ Failed to export training data - falling back to synthetic")
                        training_source = "synthetic"
                else:
                    print("❌ Real data not found and Firebase unavailable - using synthetic")
                    training_source = "synthetic"
            
            if training_source == "real" and REAL_DATA_PATH.exists():
                print(f"\n📂 Loading real training data from: {REAL_DATA_PATH}")
                df = pd.read_csv(REAL_DATA_PATH)
                print(f"   Loaded {len(df)} rows")
                
                # Validate required columns
                required_cols = FEATURE_ORDER + ['daily_price']
                missing = [c for c in required_cols if c not in df.columns]
                if missing:
                    print(f"❌ Missing required columns: {missing}")
                    print("   Falling back to synthetic data")
                    training_source = "synthetic"
        
        if training_source == "synthetic":
            # Use synthetic data
            print(f"\n📂 Loading synthetic training data from: {DATA_PATH}")
            df = load_and_preprocess_data(DATA_PATH)
            
            # Enrich with real competitor prices if available
            if db:
                competitor_prices = fetch_competitor_prices_from_firestore(db, hours_lookback=168)
                df = enrich_with_competitor_prices(df, competitor_prices)
        
        rows_used = len(df)
        print(f"   Total rows for training: {rows_used}")
        
        # Step 3: Build train/test split
        X_train, X_test, y_train, y_test = build_train_test_split(df)
        
        # Step 4: Train model
        model = train_model(X_train, y_train)
        
        # Step 5: Evaluate model and get metrics
        metrics = evaluate_model(model, X_test, y_test)
        
        # Step 6: Export to ONNX
        export_to_onnx(model, MODEL_OUTPUT_PATH)
        
        # Step 7: Validate ONNX model numerically
        is_valid = validate_onnx_model(MODEL_OUTPUT_PATH, model, X_test)
        
        # Step 8: Generate model version and log metadata
        model_version = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        if db:
            log_training_metadata(
                db=db,
                source=training_source,
                rows_used=rows_used,
                metrics=metrics,
                model_version=model_version
            )
        
        # Final summary
        print("\n" + "=" * 70)
        if is_valid:
            print("✅ SUCCESS: Training complete!")
            print(f"   Data source: {training_source}")
            print(f"   Rows used: {rows_used}")
            print(f"   Model version: {model_version}")
            print(f"   ONNX model saved to: {MODEL_OUTPUT_PATH}")
            print(f"\n   Metrics:")
            print(f"     MAE:  {metrics['mae']:.2f} SAR")
            print(f"     RMSE: {metrics['rmse']:.2f} SAR")
            print(f"     R²:   {metrics['r2']:.4f}")
            print(f"\n   Restart the server to use new model:")
            print(f"   python -m app.main")
        else:
            print("⚠️  WARNING: ONNX validation failed")
            print("   Model was saved but may not produce correct results")
        print("=" * 70)
        
    except FileNotFoundError as e:
        print(f"\n❌ ERROR: {e}")
        print(f"\n   Please ensure dataset exists")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='ONNX Pricing Model Training Pipeline')
    parser.add_argument('--export-data', action='store_true',
                        help='Export pricing decisions from Firestore to CSV (last 90 days)')
    parser.add_argument('--source', choices=['real', 'synthetic'], default=None,
                        help='Training data source: "real" (Firestore) or "synthetic" (default: uses TRAINING_SOURCE config)')
    parser.add_argument('--days', type=int, default=90,
                        help='Number of days to look back for pricing decisions (default: 90)')
    args = parser.parse_args()
    
    if args.export_data:
        # Export only mode
        db = initialize_firebase()
        if db:
            export_pricing_decisions_to_csv(db, days_lookback=args.days)
        else:
            print("❌ Firebase required for export - set GOOGLE_APPLICATION_CREDENTIALS")
            sys.exit(1)
    else:
        # Train with specified source (or default from config)
        main(source=args.source)
