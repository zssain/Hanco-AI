"""
ML Model Training Worker
Trains booking probability model from price quote data and deploys to Firebase
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, log_loss
import lightgbm as lgb
import onnx
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
import firebase_admin
from firebase_admin import storage, firestore
from google.cloud import firestore as fs

from app.core.firebase import db
from app.core.monitoring import track_job, validate_environment, log_job_skipped

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BookingProbabilityTrainer:
    """
    Trains booking probability model from historical price quotes
    """
    
    def __init__(
        self,
        lookback_days: int = 30,
        test_size: float = 0.2,
        random_state: int = 42
    ):
        self.lookback_days = lookback_days
        self.test_size = test_size
        self.random_state = random_state
        self.model = None
        self.feature_names = None
        self.metrics = {}
        
    def load_quote_data(self) -> pd.DataFrame:
        """
        Load price quotes from Firestore for the last N days
        
        Returns:
            DataFrame with quote data
        """
        logger.info(f"Loading price quotes from last {self.lookback_days} days...")
        
        cutoff_date = datetime.utcnow() - timedelta(days=self.lookback_days)
        
        # Query price_quotes collection
        quotes_ref = db.collection('price_quotes')
        query = quotes_ref.where('created_at', '>=', cutoff_date)
        
        docs = query.stream()
        
        quotes_data = []
        for doc in docs:
            doc_data = doc.to_dict()
            quotes_data.append({
                'quote_id': doc.id,
                'vehicle_id': doc_data.get('vehicle_id'),
                'branch_id': doc_data.get('branch_id'),
                'vehicle_class': doc_data.get('vehicle_class'),
                'city': doc_data.get('city'),
                'rental_length_days': doc_data.get('rental_length_days'),
                'lead_time_days': doc_data.get('lead_time_days'),
                'baseline_price_ml': doc_data.get('baseline_price_ml'),
                'daily_price': doc_data.get('daily_price'),
                'total_price': doc_data.get('total_price'),
                'booked': doc_data.get('booked', False),
                'feature_snapshot': doc_data.get('feature_snapshot', {}),
                'factors_applied': doc_data.get('factors_applied', {}),
                'created_at': doc_data.get('created_at')
            })
        
        df = pd.DataFrame(quotes_data)
        logger.info(f"Loaded {len(df)} price quotes")
        logger.info(f"Conversion rate: {df['booked'].mean():.2%}")
        
        return df
    
    def build_dataset(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Build training dataset from quote data
        
        Args:
            df: Raw quote DataFrame
            
        Returns:
            Tuple of (X, y) where X is features and y is target (booked)
        """
        logger.info("Building training dataset...")
        
        features_list = []
        
        for idx, row in df.iterrows():
            feature_snapshot = row['feature_snapshot']
            factors_applied = row['factors_applied']
            
            # Extract ML features
            ml_features = feature_snapshot.get('ml_features', {})
            
            # Build feature vector
            features = {
                # Temporal features
                'rental_length_days': ml_features.get('rental_length_days', row['rental_length_days']),
                'day_of_week': ml_features.get('day_of_week', 0),
                'month': ml_features.get('month', 1),
                'lead_time_days': feature_snapshot.get('lead_time_days', row['lead_time_days']),
                
                # Vehicle features
                'base_daily_rate': ml_features.get('base_daily_rate', 100.0),
                
                # Weather features
                'avg_temp': ml_features.get('avg_temp', 25.0),
                'rain': ml_features.get('rain', 0.0),
                'wind': ml_features.get('wind', 10.0),
                
                # Competitor features
                'avg_competitor_price': ml_features.get('avg_competitor_price', 100.0),
                
                # Demand features
                'demand_index': ml_features.get('demand_index', 0.5),
                'utilization_rate': feature_snapshot.get('utilization_rate', 0.5),
                
                # Pricing features
                'baseline_price_ml': row['baseline_price_ml'],
                'daily_price': row['daily_price'],
                'price_premium_pct': ((row['daily_price'] - row['baseline_price_ml']) / row['baseline_price_ml'] * 100) if row['baseline_price_ml'] > 0 else 0,
                
                # Factors applied (binary flags)
                'factor_utilization': factors_applied.get('utilization', 1.0),
                'factor_lead_time': factors_applied.get('lead_time', 1.0),
                'factor_duration': factors_applied.get('duration', 1.0),
                'factor_weekend': factors_applied.get('weekend', 1.0),
                'factor_season': factors_applied.get('season', 1.0),
                'factor_demand': factors_applied.get('demand', 1.0),
                
                # Categorical features (one-hot encoded)
                'vehicle_class_economy': 1 if row['vehicle_class'] == 'economy' else 0,
                'vehicle_class_sedan': 1 if row['vehicle_class'] == 'sedan' else 0,
                'vehicle_class_suv': 1 if row['vehicle_class'] == 'suv' else 0,
                'vehicle_class_luxury': 1 if row['vehicle_class'] == 'luxury' else 0,
            }
            
            features_list.append(features)
        
        X = pd.DataFrame(features_list)
        y = df['booked'].astype(int)
        
        # Store feature names
        self.feature_names = list(X.columns)
        
        logger.info(f"Dataset built: {X.shape[0]} samples, {X.shape[1]} features")
        logger.info(f"Features: {self.feature_names}")
        
        return X, y
    
    def train_model(self, X: pd.DataFrame, y: pd.Series) -> Dict:
        """
        Train LightGBM booking probability model
        
        Args:
            X: Feature matrix
            y: Target variable (booked)
            
        Returns:
            Dictionary with training metrics
        """
        logger.info("Training LightGBM model...")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=self.test_size, random_state=self.random_state, stratify=y
        )
        
        logger.info(f"Train size: {len(X_train)}, Test size: {len(X_test)}")
        logger.info(f"Train conversion: {y_train.mean():.2%}, Test conversion: {y_test.mean():.2%}")
        
        # Configure LightGBM
        train_data = lgb.Dataset(X_train, label=y_train)
        test_data = lgb.Dataset(X_test, label=y_test, reference=train_data)
        
        params = {
            'objective': 'binary',
            'metric': ['binary_logloss', 'auc'],
            'boosting_type': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1,
            'seed': self.random_state
        }
        
        # Train model
        self.model = lgb.train(
            params,
            train_data,
            num_boost_round=100,
            valid_sets=[train_data, test_data],
            valid_names=['train', 'test'],
            callbacks=[lgb.early_stopping(stopping_rounds=10), lgb.log_evaluation(10)]
        )
        
        # Evaluate
        y_train_pred = self.model.predict(X_train, num_iteration=self.model.best_iteration)
        y_test_pred = self.model.predict(X_test, num_iteration=self.model.best_iteration)
        
        train_auc = roc_auc_score(y_train, y_train_pred)
        test_auc = roc_auc_score(y_test, y_test_pred)
        train_logloss = log_loss(y_train, y_train_pred)
        test_logloss = log_loss(y_test, y_test_pred)
        
        self.metrics = {
            'train_auc': float(train_auc),
            'test_auc': float(test_auc),
            'train_logloss': float(train_logloss),
            'test_logloss': float(test_logloss),
            'train_samples': int(len(X_train)),
            'test_samples': int(len(X_test)),
            'train_conversion_rate': float(y_train.mean()),
            'test_conversion_rate': float(y_test.mean()),
            'num_features': int(X.shape[1]),
            'best_iteration': int(self.model.best_iteration)
        }
        
        logger.info(f"Training complete!")
        logger.info(f"  Train AUC: {train_auc:.4f}, Test AUC: {test_auc:.4f}")
        logger.info(f"  Train LogLoss: {train_logloss:.4f}, Test LogLoss: {test_logloss:.4f}")
        
        # Feature importance
        feature_importance = pd.DataFrame({
            'feature': self.feature_names,
            'importance': self.model.feature_importance(importance_type='gain')
        }).sort_values('importance', ascending=False)
        
        logger.info(f"Top 10 features:")
        for idx, row in feature_importance.head(10).iterrows():
            logger.info(f"  {row['feature']}: {row['importance']:.2f}")
        
        return self.metrics
    
    def run_sanity_checks(self, X_test: pd.DataFrame) -> Tuple[bool, Dict]:
        """
        Run sanity checks on model predictions
        
        Args:
            X_test: Test feature matrix
            
        Returns:
            Tuple of (passed, check_results)
        """
        logger.info("Running sanity checks...")
        
        # Generate predictions
        test_predictions = self.model.predict(X_test, num_iteration=self.model.best_iteration)
        
        mean_pred = float(np.mean(test_predictions))
        std_pred = float(np.std(test_predictions))
        
        checks = {
            'mean_prediction': mean_pred,
            'std_prediction': std_pred,
            'mean_in_range': 0.01 <= mean_pred <= 0.50,
            'std_not_zero': std_pred > 0.01,
            'all_checks_passed': False
        }
        
        checks['all_checks_passed'] = checks['mean_in_range'] and checks['std_not_zero']
        
        logger.info(f"  Mean prediction: {mean_pred:.4f} (expected: 0.01-0.50)")
        logger.info(f"  Std prediction: {std_pred:.4f} (expected: >0.01)")
        logger.info(f"  Sanity checks: {'PASSED' if checks['all_checks_passed'] else 'FAILED'}")
        
        return checks['all_checks_passed'], checks
    
    def should_promote(self, new_metrics: Dict, current_metrics: Optional[Dict], sanity_passed: bool) -> Tuple[bool, str]:
        """
        Evaluate if new model should be promoted based on gates
        
        Args:
            new_metrics: Metrics from newly trained model
            current_metrics: Metrics from current active model (None if first model)
            sanity_passed: Whether sanity checks passed
            
        Returns:
            Tuple of (should_promote, reason)
        """
        # Gate 1: Sanity checks must pass
        if not sanity_passed:
            return False, "Sanity checks failed"
        
        # First model always promotes if sanity passes
        if current_metrics is None:
            return True, "First model deployment (sanity passed)"
        
        # Gate 2: Metric improvements
        current_logloss = current_metrics.get('test_logloss', float('inf'))
        current_auc = current_metrics.get('test_auc', 0.0)
        
        new_logloss = new_metrics['test_logloss']
        new_auc = new_metrics['test_auc']
        
        # Calculate improvements
        logloss_improvement = (current_logloss - new_logloss) / current_logloss * 100  # positive = better
        auc_improvement = (new_auc - current_auc) * 100  # positive = better
        
        logger.info(f"  Current model - AUC: {current_auc:.4f}, LogLoss: {current_logloss:.4f}")
        logger.info(f"  New model - AUC: {new_auc:.4f}, LogLoss: {new_logloss:.4f}")
        logger.info(f"  LogLoss improvement: {logloss_improvement:+.2f}%")
        logger.info(f"  AUC improvement: {auc_improvement:+.2f}%")
        
        # Check thresholds: logloss improves by 1% OR AUC improves by 0.5%
        if logloss_improvement >= 1.0:
            return True, f"LogLoss improved by {logloss_improvement:.2f}%"
        elif auc_improvement >= 0.5:
            return True, f"AUC improved by {auc_improvement:.2f}%"
        else:
            return False, f"Insufficient improvement (LogLoss: {logloss_improvement:+.2f}%, AUC: {auc_improvement:+.2f}%)"
    
    def export_to_onnx(self, output_path: str) -> str:
        """
        Export LightGBM model to ONNX format
        
        Args:
            output_path: Path to save ONNX model
            
        Returns:
            Path to saved ONNX model
        """
        logger.info(f"Exporting model to ONNX: {output_path}")
        
        # Create directory if needed
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Convert to ONNX using lightgbm's built-in converter
        # Note: LightGBM has native ONNX export
        import lightgbm as lgb
        
        # Save as LightGBM text format first
        temp_model_path = output_path.replace('.onnx', '.txt')
        self.model.save_model(temp_model_path)
        
        # Convert to ONNX using onnxmltools
        try:
            import onnxmltools
            from onnxmltools.convert import convert_lightgbm
            
            # Define initial types for ONNX conversion
            initial_types = [('input', FloatTensorType([None, len(self.feature_names)]))]
            
            # Convert
            onnx_model = convert_lightgbm(
                self.model,
                initial_types=initial_types,
                target_opset=12
            )
            
            # Save ONNX
            onnx.save_model(onnx_model, output_path)
            
            # Clean up temp file
            if os.path.exists(temp_model_path):
                os.remove(temp_model_path)
            
            logger.info(f"ONNX model saved: {output_path}")
            
        except ImportError:
            logger.error("onnxmltools not installed. Install with: pip install onnxmltools")
            raise
        
        return output_path
    
    def upload_to_firebase_storage(self, local_path: str, storage_path: str) -> str:
        """
        Upload ONNX model to Firebase Storage
        
        Args:
            local_path: Local file path
            storage_path: Firebase Storage path
            
        Returns:
            Public URL of uploaded file
        """
        logger.info(f"Uploading to Firebase Storage: {storage_path}")
        
        try:
            # Get storage bucket
            bucket = storage.bucket()
            
            # Upload file
            blob = bucket.blob(storage_path)
            blob.upload_from_filename(local_path)
            
            # Make public (optional - adjust based on security requirements)
            blob.make_public()
            
            public_url = blob.public_url
            logger.info(f"Model uploaded successfully: {public_url}")
            
            return public_url
            
        except Exception as e:
            logger.error(f"Error uploading to Firebase Storage: {str(e)}")
            raise
    
    def update_model_registry(
        self,
        model_name: str,
        version: str,
        storage_path: str,
        metrics: Dict,
        promote: bool = True,
        gate_reason: str = "",
        sanity_checks: Optional[Dict] = None
    ) -> None:
        """
        Update Firestore ml_models collection with new model version
        Implements versioning with rollback support
        
        Args:
            model_name: Name of the model (e.g., 'booking_probability_model')
            version: Version string (e.g., 'v1.0.0_20260102')
            storage_path: Firebase Storage path
            metrics: Model performance metrics
            promote: Whether to promote to active (True) or just log failed run (False)
            gate_reason: Reason for promotion decision
            sanity_checks: Results from sanity check validation
        """
        model_ref = db.collection('ml_models').document(model_name)
        model_doc = model_ref.get()
        
        if promote:
            logger.info(f"Updating model registry: {model_name} -> {version} [PROMOTING]")
            logger.info(f"  Reason: {gate_reason}")
            
            new_version_data = {
                'version': version,
                'storage_path': storage_path,
                'metrics': metrics,
                'feature_names': self.feature_names,
                'deployed_at': fs.SERVER_TIMESTAMP,
                'deployed_by': 'training_worker',
                'status': 'active',
                'gate_reason': gate_reason,
                'sanity_checks': sanity_checks or {}
            }
            
            if model_doc.exists:
                # Model exists - move current active to previous_versions
                current_data = model_doc.to_dict()
                current_active = current_data.get('active_version')
                previous_versions = current_data.get('previous_versions', [])
                
                if current_active:
                    # Archive current active version
                    current_active['status'] = 'archived'
                    current_active['archived_at'] = datetime.utcnow().isoformat()
                    previous_versions.insert(0, current_active)
                    
                    # Keep only last 5 versions
                    previous_versions = previous_versions[:5]
                    
                    logger.info(f"Archived previous version: {current_active.get('version')}")
                
                # Update with new active version
                model_ref.update({
                    'active_version': new_version_data,
                    'previous_versions': previous_versions,
                    'updated_at': fs.SERVER_TIMESTAMP
                })
                
            else:
                # First model deployment
                model_ref.set({
                    'model_name': model_name,
                    'active_version': new_version_data,
                    'previous_versions': [],
                    'created_at': fs.SERVER_TIMESTAMP,
                    'updated_at': fs.SERVER_TIMESTAMP
                })
            
            logger.info(f"Model registry updated successfully - Model PROMOTED")
        
        else:
            # Gate failed - log failed run without promoting
            logger.warning(f"Model gate FAILED: {model_name} -> {version}")
            logger.warning(f"  Reason: {gate_reason}")
            
            failed_run = {
                'version': version,
                'storage_path': storage_path,
                'metrics': metrics,
                'feature_names': self.feature_names,
                'trained_at': datetime.utcnow().isoformat(),
                'gate_reason': gate_reason,
                'sanity_checks': sanity_checks or {},
                'status': 'rejected'
            }
            
            if model_doc.exists:
                # Update last_failed_run in existing doc
                model_ref.update({
                    'last_failed_run': failed_run,
                    'updated_at': fs.SERVER_TIMESTAMP
                })
            else:
                # Create doc with failed run (no active version)
                model_ref.set({
                    'model_name': model_name,
                    'active_version': None,
                    'previous_versions': [],
                    'last_failed_run': failed_run,
                    'created_at': fs.SERVER_TIMESTAMP,
                    'updated_at': fs.SERVER_TIMESTAMP
                })
            
            logger.warning(f"Failed training run logged - Model NOT promoted")
    
    def rollback_to_version(self, model_name: str, version: str) -> bool:
        """
        Rollback to a previous model version
        
        Args:
            model_name: Name of the model
            version: Version to rollback to
            
        Returns:
            True if successful
        """
        logger.info(f"Rolling back {model_name} to version {version}")
        
        model_ref = db.collection('ml_models').document(model_name)
        model_doc = model_ref.get()
        
        if not model_doc.exists:
            logger.error(f"Model {model_name} not found")
            return False
        
        current_data = model_doc.to_dict()
        previous_versions = current_data.get('previous_versions', [])
        
        # Find target version
        target_version = None
        remaining_versions = []
        
        for prev_version in previous_versions:
            if prev_version.get('version') == version:
                target_version = prev_version
            else:
                remaining_versions.append(prev_version)
        
        if not target_version:
            logger.error(f"Version {version} not found in previous versions")
            return False
        
        # Move current active to previous versions
        current_active = current_data.get('active_version')
        if current_active:
            current_active['status'] = 'archived'
            current_active['archived_at'] = datetime.utcnow().isoformat()
            remaining_versions.insert(0, current_active)
        
        # Restore target version as active
        target_version['status'] = 'active'
        target_version['restored_at'] = datetime.utcnow().isoformat()
        
        model_ref.update({
            'active_version': target_version,
            'previous_versions': remaining_versions[:5],
            'updated_at': fs.SERVER_TIMESTAMP
        })
        
        logger.info(f"Successfully rolled back to version {version}")
        return True


def train_booking_probability_model(
    lookback_days: int = 30,
    model_name: str = 'booking_probability_model',
    output_dir: str = './models'
) -> Dict:
    """
    Main training function with promotion gates
    
    Args:
        lookback_days: Days of historical data to use
        model_name: Name for model registry
        output_dir: Local directory for model files
        
    Returns:
        Dictionary with training summary
    """
    logger.info("=" * 80)
    logger.info("Starting Booking Probability Model Training")
    logger.info("=" * 80)
    
    counts = {'inserted': 0, 'updated': 0, 'deleted': 0}
    
    with track_job('train_model', counts):
        trainer = BookingProbabilityTrainer(lookback_days=lookback_days)
        
        # Step 1: Load data
        df = trainer.load_quote_data()
        
        if len(df) < 100:
            logger.error(f"Insufficient data: {len(df)} quotes. Need at least 100.")
            raise ValueError('insufficient_data')
        
        if df['booked'].sum() < 10:
            logger.error(f"Insufficient positive samples: {df['booked'].sum()}. Need at least 10.")
            raise ValueError('insufficient_positive_samples')
        
        # Step 2: Build dataset
        X, y = trainer.build_dataset(df)
        
        # Step 3: Train model
        from sklearn.model_selection import train_test_split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=trainer.test_size, random_state=trainer.random_state, stratify=y
        )
        metrics = trainer.train_model(X, y)
        
        # Step 4: Run sanity checks
        sanity_passed, sanity_checks = trainer.run_sanity_checks(X_test)
        
        # Step 5: Get current model metrics for comparison
        model_ref = db.collection('ml_models').document(model_name)
        model_doc = model_ref.get()
        current_metrics = None
        if model_doc.exists:
            current_data = model_doc.to_dict()
            active_version = current_data.get('active_version')
            if active_version:
                current_metrics = active_version.get('metrics')
        
        # Step 6: Evaluate promotion gates
        should_promote, gate_reason = trainer.should_promote(metrics, current_metrics, sanity_passed)
        
        logger.info("=" * 80)
        logger.info("PROMOTION GATE EVALUATION")
        logger.info(f"  Decision: {'PROMOTE' if should_promote else 'REJECT'}")
        logger.info(f"  Reason: {gate_reason}")
        logger.info("=" * 80)
        
        # Step 7: Export to ONNX
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        version = f"v1.0.0_{timestamp}"
        local_model_path = os.path.join(output_dir, f"{model_name}_{version}.onnx")
        
        trainer.export_to_onnx(local_model_path)
        
        # Step 8: Upload to Firebase Storage (optional if not promoting)
        storage_path = f"ml_models/{model_name}/{version}.onnx"
        if should_promote:
            storage_url = trainer.upload_to_firebase_storage(local_model_path, storage_path)
            counts['updated'] = 1  # Model promoted
        else:
            logger.info("Skipping Firebase Storage upload (gate failed)")
            storage_url = None
        
        # Step 9: Update model registry (promote or log failed run)
        trainer.update_model_registry(
            model_name=model_name,
            version=version,
            storage_path=storage_path,
            metrics=metrics,
            promote=should_promote,
            gate_reason=gate_reason,
            sanity_checks=sanity_checks
        )
        
        logger.info("=" * 80)
        logger.info(f"Training {'Complete' if should_promote else 'Complete (NOT PROMOTED)'}!")
        logger.info(f"  Version: {version}")
        logger.info(f"  Test AUC: {metrics['test_auc']:.4f}")
        logger.info(f"  Test LogLoss: {metrics['test_logloss']:.4f}")
        logger.info(f"  Sanity Checks: {'PASSED' if sanity_passed else 'FAILED'}")
        logger.info(f"  Promoted: {'YES' if should_promote else 'NO'}")
        if storage_url:
            logger.info(f"  Storage: {storage_path}")
        logger.info("=" * 80)
        
        return {
            'status': 'success' if should_promote else 'gate_rejected',
            'version': version,
            'metrics': metrics,
            'sanity_checks': sanity_checks,
            'promoted': should_promote,
            'gate_reason': gate_reason,
            'storage_path': storage_path if should_promote else None,
            'storage_url': storage_url
        }
    }


def main():
    """
    Run training worker with promotion gates or rollback
    
    Usage:
        python3 -m app.workers.train_models [lookback_days]
    
    Requirements:
        - GOOGLE_APPLICATION_CREDENTIALS must be set
        - Points to Firebase service account JSON file
    
    Examples:
        # Default (30 days lookback)
        export GOOGLE_APPLICATION_CREDENTIALS=/path/to/firebase-key.json
        python3 -m app.workers.train_models
        
        # Custom lookback period
        python3 -m app.workers.train_models 60
        
        # Rollback to specific version
        FORCE_ROLLBACK_VERSION=v1.0.0_20260101_120000 python3 -m app.workers.train_models
    """
    import sys
    import time
    from pathlib import Path
    
    # Validate environment
    validate_environment()
    
    # Lock file configuration
    LOCK_FILE = Path('/tmp/hanco_train.lock')
    MAX_LOCK_AGE_SECONDS = 8 * 60 * 60  # 8 hours
    
    # Check for rollback command (skip lock check for rollback)
    force_rollback_version = os.environ.get('FORCE_ROLLBACK_VERSION')
    
    if force_rollback_version:
        logger.info("=" * 80)
        logger.info("ROLLBACK COMMAND DETECTED")
        logger.info(f"  Target Version: {force_rollback_version}")
        logger.info("=" * 80)
        
        try:
            trainer = BookingProbabilityTrainer()
            success = trainer.rollback_to_version(
                model_name='booking_probability_model',
                version=force_rollback_version
            )
            
            if success:
                logger.info("Rollback succeeded!")
                sys.exit(0)
            else:
                logger.error("Rollback failed!")
                sys.exit(1)
        except Exception as e:
            logger.error(f"Rollback failed: {str(e)}")
            sys.exit(1)
    
    # Check for existing lock (normal training mode)
    if LOCK_FILE.exists():
        try:
            lock_age = time.time() - LOCK_FILE.stat().st_mtime
            
            if lock_age < MAX_LOCK_AGE_SECONDS:
                logger.info(f"Lock file exists and is recent ({lock_age/3600:.1f} hours old)")
                logger.info("Another training job may be running. Skipping this run.")
                log_job_skipped('train_models', reason=f"Lock exists ({lock_age/3600:.1f} hours old)")
                sys.exit(0)  # Graceful skip
            else:
                logger.warning(f"Lock file is stale ({lock_age/3600:.1f} hours old). Overwriting.")
                LOCK_FILE.unlink()
        except Exception as e:
            logger.warning(f"Error checking lock file: {e}. Removing it.")
            LOCK_FILE.unlink()
    
    # Create lock file
    try:
        LOCK_FILE.write_text(str(os.getpid()))
        logger.info(f"Lock acquired: {LOCK_FILE}")
    except Exception as e:
        logger.error(f"Failed to create lock file: {e}")
        sys.exit(1)
    
    # Parse arguments for training
    lookback_days = 30
    if len(sys.argv) > 1:
        lookback_days = int(sys.argv[1])
    
    # Run training with lock
    try:
        result = train_booking_probability_model(lookback_days=lookback_days)
        
        if result['status'] == 'success':
            logger.info("Training succeeded and model PROMOTED!")
            exit_code = 0
        elif result['status'] == 'gate_rejected':
            logger.warning(f"Training succeeded but promotion gate REJECTED: {result.get('gate_reason')}")
            exit_code = 2  # Exit code 2 = gate rejected
        else:
            logger.error("Training failed")
            exit_code = 1
            
    except ValueError as e:
        logger.error(f"Training failed: {str(e)}")
        exit_code = 1
    except KeyboardInterrupt:
        logger.info("Training interrupted by user")
        exit_code = 130
    except Exception as e:
        logger.error(f"Training failed with unexpected error: {str(e)}")
        exit_code = 1
    finally:
        # Always remove lock file
        try:
            if LOCK_FILE.exists():
                LOCK_FILE.unlink()
                logger.info(f"Lock released: {LOCK_FILE}")
        except Exception as e:
            logger.error(f"Failed to remove lock file: {e}")
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
