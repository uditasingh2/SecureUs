"""
Predictive Monitoring System with Explainability
ML-based inference for missing data with evidence-based reasoning
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, mean_squared_error
import joblib
from loguru import logger

from .config import PREDICTION_CONFIG, CAMPUS_LOCATIONS, ENTITY_TYPES
from .timeline_generator import TimelineEvent
from .multimodal_fusion import FusionRecord


@dataclass
class Prediction:
    """Represents a prediction with explanation"""
    entity_id: str
    timestamp: datetime
    predicted_location: str
    predicted_activity: str
    confidence: float
    explanation: Dict[str, Any]
    evidence: List[str]
    alternative_predictions: List[Tuple[str, float]]


@dataclass
class AnomalyAlert:
    """Represents an anomaly detection alert"""
    entity_id: str
    alert_type: str
    severity: str
    timestamp: datetime
    description: str
    evidence: Dict[str, Any]
    recommended_actions: List[str]


class PredictiveMonitor:
    """
    Advanced predictive monitoring system that:
    - Predicts missing data using ML models
    - Provides explainable predictions with evidence
    - Detects anomalies and generates alerts
    - Monitors entity absence patterns
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or PREDICTION_CONFIG
        self.location_predictor = None
        self.activity_predictor = None
        self.anomaly_detector = None
        self.label_encoders = {}
        self.feature_scaler = StandardScaler()
        self.is_trained = False
        
    def train_predictive_models(self, 
                               training_data: List[FusionRecord],
                               entity_profiles: pd.DataFrame) -> Dict[str, float]:
        """
        Train ML models for prediction and anomaly detection
        Returns training performance metrics
        """
        logger.info("Training predictive models...")
        
        if not training_data:
            logger.error("No training data provided")
            return {}
        
        # Prepare training features and targets
        features, location_targets, activity_targets = self._prepare_training_data(
            training_data, entity_profiles
        )
        
        if len(features) == 0:
            logger.error("No valid training features extracted")
            return {}
        
        # Split data
        X_train, X_test, y_loc_train, y_loc_test, y_act_train, y_act_test = train_test_split(
            features, location_targets, activity_targets, test_size=0.2, random_state=42
        )
        
        # Scale features
        X_train_scaled = self.feature_scaler.fit_transform(X_train)
        X_test_scaled = self.feature_scaler.transform(X_test)
        
        # Train location predictor
        self.location_predictor = RandomForestClassifier(
            n_estimators=100, random_state=42, max_depth=10
        )
        self.location_predictor.fit(X_train_scaled, y_loc_train)
        
        # Train activity predictor
        self.activity_predictor = RandomForestClassifier(
            n_estimators=100, random_state=42, max_depth=10
        )
        self.activity_predictor.fit(X_train_scaled, y_act_train)
        
        # Train anomaly detector (using isolation forest approach)
        from sklearn.ensemble import IsolationForest
        self.anomaly_detector = IsolationForest(
            contamination=0.1, random_state=42
        )
        self.anomaly_detector.fit(X_train_scaled)
        
        # Evaluate models
        loc_pred = self.location_predictor.predict(X_test_scaled)
        act_pred = self.activity_predictor.predict(X_test_scaled)
        
        loc_accuracy = accuracy_score(y_loc_test, loc_pred)
        act_accuracy = accuracy_score(y_act_test, act_pred)
        
        # Anomaly detection evaluation
        anomaly_scores = self.anomaly_detector.decision_function(X_test_scaled)
        anomaly_threshold = np.percentile(anomaly_scores, 10)  # Bottom 10% as anomalies
        
        self.is_trained = True
        
        performance = {
            'location_accuracy': loc_accuracy,
            'activity_accuracy': act_accuracy,
            'training_samples': len(X_train),
            'test_samples': len(X_test),
            'anomaly_threshold': anomaly_threshold
        }
        
        logger.info(f"Model training completed. Location accuracy: {loc_accuracy:.3f}, Activity accuracy: {act_accuracy:.3f}")
        return performance
    
    def _prepare_training_data(self, 
                              training_data: List[FusionRecord],
                              entity_profiles: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Prepare features and targets for training"""
        features = []
        location_targets = []
        activity_targets = []
        
        # Create entity profile lookup
        profile_lookup = entity_profiles.set_index('entity_id').to_dict('index')
        
        for record in training_data:
            # Extract features
            feature_vector = self._extract_features(record, profile_lookup)
            if feature_vector is not None:
                features.append(feature_vector)
                location_targets.append(record.location)
                activity_targets.append(record.activity_type)
        
        if not features:
            return np.array([]), np.array([]), np.array([])
        
        # Encode categorical targets
        if 'location' not in self.label_encoders:
            self.label_encoders['location'] = LabelEncoder()
            location_targets_encoded = self.label_encoders['location'].fit_transform(location_targets)
        else:
            location_targets_encoded = self.label_encoders['location'].transform(location_targets)
        
        if 'activity' not in self.label_encoders:
            self.label_encoders['activity'] = LabelEncoder()
            activity_targets_encoded = self.label_encoders['activity'].fit_transform(activity_targets)
        else:
            activity_targets_encoded = self.label_encoders['activity'].transform(activity_targets)
        
        return np.array(features), location_targets_encoded, activity_targets_encoded
    
    def _extract_features(self, 
                         record: FusionRecord, 
                         profile_lookup: Dict) -> Optional[np.ndarray]:
        """Extract feature vector from a fusion record"""
        try:
            # Get entity profile
            entity_profile = profile_lookup.get(record.unified_entity_id, {})
            
            features = []
            
            # Temporal features
            features.extend([
                record.timestamp.hour,
                record.timestamp.weekday(),
                record.timestamp.day,
                record.timestamp.month
            ])
            
            # Entity features
            role_encoding = {'student': 0, 'staff': 1, 'faculty': 2}
            features.append(role_encoding.get(entity_profile.get('role', 'student'), 0))
            
            # Department encoding
            dept_encoding = {
                'Physics': 0, 'MECH': 1, 'ECE': 2, 'CIVIL': 3, 'BIO': 4,
                'Chemistry': 5, 'Admin': 6, 'Maths': 7, 'Computer Science': 8
            }
            features.append(dept_encoding.get(entity_profile.get('department', 'Unknown'), -1))
            
            # Historical pattern features (simplified)
            features.extend([
                len(record.source_records),  # Number of data sources
                record.confidence,  # Fusion confidence
                len(record.evidence)  # Amount of evidence
            ])
            
            # Location features
            location_encoding = {loc: i for i, loc in enumerate(CAMPUS_LOCATIONS.keys())}
            features.append(location_encoding.get(record.location, -1))
            
            # Activity pattern features
            activity_counts = {}
            for source_record in record.source_records:
                dataset = source_record['dataset']
                activity_counts[dataset] = activity_counts.get(dataset, 0) + 1
            
            # Binary features for data source presence
            for source in ['card_swipes', 'cctv_frames', 'wifi_logs', 'lab_bookings', 'library_checkouts', 'notes']:
                features.append(1 if source in activity_counts else 0)
            
            return np.array(features, dtype=float)
            
        except Exception as e:
            logger.warning(f"Failed to extract features from record: {e}")
            return None
    
    def predict_missing_data(self, 
                           entity_id: str,
                           timestamp: datetime,
                           context_records: List[FusionRecord],
                           entity_profile: Dict) -> Optional[Prediction]:
        """
        Predict most likely location and activity for missing data point
        """
        if not self.is_trained:
            logger.error("Models not trained. Call train_predictive_models first.")
            return None
        
        # Create synthetic record for feature extraction
        synthetic_record = FusionRecord(
            unified_entity_id=entity_id,
            timestamp=timestamp,
            location='UNKNOWN',
            activity_type='unknown',
            confidence=0.0,
            source_records=[],
            provenance={},
            evidence={}
        )
        
        # Extract features
        profile_lookup = {entity_id: entity_profile}
        features = self._extract_features(synthetic_record, profile_lookup)
        
        if features is None:
            return None
        
        # Scale features
        features_scaled = self.feature_scaler.transform([features])
        
        # Make predictions
        location_probs = self.location_predictor.predict_proba(features_scaled)[0]
        activity_probs = self.activity_predictor.predict_proba(features_scaled)[0]
        
        # Get top predictions
        location_classes = self.location_predictor.classes_
        activity_classes = self.activity_predictor.classes_
        
        # Decode predictions
        top_location_idx = np.argmax(location_probs)
        top_activity_idx = np.argmax(activity_probs)
        
        predicted_location = self.label_encoders['location'].inverse_transform([location_classes[top_location_idx]])[0]
        predicted_activity = self.label_encoders['activity'].inverse_transform([activity_classes[top_activity_idx]])[0]
        
        location_confidence = location_probs[top_location_idx]
        activity_confidence = activity_probs[top_activity_idx]
        overall_confidence = (location_confidence + activity_confidence) / 2
        
        # Generate explanation
        explanation = self._generate_prediction_explanation(
            entity_id, timestamp, predicted_location, predicted_activity,
            context_records, entity_profile, features
        )
        
        # Generate evidence
        evidence = self._generate_prediction_evidence(
            entity_id, timestamp, context_records, entity_profile
        )
        
        # Get alternative predictions
        alternatives = self._get_alternative_predictions(
            location_probs, activity_probs, location_classes, activity_classes
        )
        
        return Prediction(
            entity_id=entity_id,
            timestamp=timestamp,
            predicted_location=predicted_location,
            predicted_activity=predicted_activity,
            confidence=overall_confidence,
            explanation=explanation,
            evidence=evidence,
            alternative_predictions=alternatives
        )
    
    def _generate_prediction_explanation(self, 
                                       entity_id: str,
                                       timestamp: datetime,
                                       location: str,
                                       activity: str,
                                       context_records: List[FusionRecord],
                                       entity_profile: Dict,
                                       features: np.ndarray) -> Dict[str, Any]:
        """Generate human-readable explanation for prediction"""
        explanation = {
            'reasoning': [],
            'confidence_factors': {},
            'temporal_patterns': {},
            'behavioral_patterns': {}
        }
        
        # Temporal reasoning
        hour = timestamp.hour
        weekday = timestamp.weekday()
        
        if 8 <= hour <= 17:
            explanation['reasoning'].append("Predicted during typical working hours")
            explanation['confidence_factors']['working_hours'] = 0.8
        elif 18 <= hour <= 22:
            explanation['reasoning'].append("Predicted during evening hours")
            explanation['confidence_factors']['evening_hours'] = 0.6
        else:
            explanation['reasoning'].append("Predicted during off-hours")
            explanation['confidence_factors']['off_hours'] = 0.3
        
        # Role-based reasoning
        role = entity_profile.get('role', 'student')
        if role == 'faculty' and location.startswith('LAB'):
            explanation['reasoning'].append("Faculty members often use lab facilities")
            explanation['confidence_factors']['role_location_match'] = 0.7
        elif role == 'student' and activity == 'library_checkout':
            explanation['reasoning'].append("Students frequently use library services")
            explanation['confidence_factors']['role_activity_match'] = 0.8
        
        # Historical pattern reasoning
        if context_records:
            recent_locations = [r.location for r in context_records[-5:]]  # Last 5 records
            if location in recent_locations:
                explanation['reasoning'].append(f"Entity recently visited {location}")
                explanation['confidence_factors']['location_history'] = 0.9
        
        # Department-based reasoning
        department = entity_profile.get('department', '')
        if department == 'MECH' and location == 'LAB_101':
            explanation['reasoning'].append("Mechanical engineering students often use Lab 101")
            explanation['confidence_factors']['department_location'] = 0.7
        
        return explanation
    
    def _generate_prediction_evidence(self, 
                                    entity_id: str,
                                    timestamp: datetime,
                                    context_records: List[FusionRecord],
                                    entity_profile: Dict) -> List[str]:
        """Generate evidence supporting the prediction"""
        evidence = []
        
        # Recent activity evidence
        if context_records:
            last_record = context_records[-1]
            time_diff = (timestamp - last_record.timestamp).total_seconds() / 60
            
            if time_diff < 60:  # Within last hour
                evidence.append(f"Last seen {int(time_diff)} minutes ago at {last_record.location}")
            
            # Pattern evidence
            recent_locations = [r.location for r in context_records[-10:]]
            location_counts = pd.Series(recent_locations).value_counts()
            most_frequent = location_counts.index[0]
            
            evidence.append(f"Most frequently visits {most_frequent} ({location_counts[most_frequent]} times recently)")
        
        # Schedule evidence
        hour = timestamp.hour
        weekday = timestamp.weekday()
        
        if weekday < 5 and 9 <= hour <= 17:
            evidence.append("Prediction made during typical campus hours")
        
        # Role evidence
        role = entity_profile.get('role', 'student')
        evidence.append(f"Entity role: {role}")
        
        return evidence
    
    def _get_alternative_predictions(self, 
                                   location_probs: np.ndarray,
                                   activity_probs: np.ndarray,
                                   location_classes: np.ndarray,
                                   activity_classes: np.ndarray) -> List[Tuple[str, float]]:
        """Get alternative predictions with confidence scores"""
        alternatives = []
        
        # Top 3 location alternatives
        top_location_indices = np.argsort(location_probs)[-3:][::-1]
        for idx in top_location_indices[1:]:  # Skip the top prediction
            location = self.label_encoders['location'].inverse_transform([location_classes[idx]])[0]
            confidence = location_probs[idx]
            alternatives.append((f"Location: {location}", confidence))
        
        # Top 3 activity alternatives
        top_activity_indices = np.argsort(activity_probs)[-3:][::-1]
        for idx in top_activity_indices[1:]:  # Skip the top prediction
            activity = self.label_encoders['activity'].inverse_transform([activity_classes[idx]])[0]
            confidence = activity_probs[idx]
            alternatives.append((f"Activity: {activity}", confidence))
        
        return sorted(alternatives, key=lambda x: x[1], reverse=True)[:3]
    
    def detect_anomalies(self, 
                        entity_records: List[FusionRecord],
                        entity_profile: Dict) -> List[AnomalyAlert]:
        """Detect anomalies in entity behavior"""
        if not self.is_trained or not entity_records:
            return []
        
        alerts = []
        profile_lookup = {entity_records[0].unified_entity_id: entity_profile}
        
        # Check for absence anomalies
        absence_alert = self._check_absence_anomaly(entity_records, entity_profile)
        if absence_alert:
            alerts.append(absence_alert)
        
        # Check for behavioral anomalies
        for record in entity_records[-10:]:  # Check last 10 records
            features = self._extract_features(record, profile_lookup)
            if features is not None:
                features_scaled = self.feature_scaler.transform([features])
                anomaly_score = self.anomaly_detector.decision_function(features_scaled)[0]
                
                if anomaly_score < -0.5:  # Threshold for anomaly
                    behavioral_alert = self._create_behavioral_anomaly_alert(
                        record, anomaly_score, entity_profile
                    )
                    alerts.append(behavioral_alert)
        
        return alerts
    
    def _check_absence_anomaly(self, 
                              entity_records: List[FusionRecord],
                              entity_profile: Dict) -> Optional[AnomalyAlert]:
        """Check for unusual absence patterns"""
        if not entity_records:
            return None
        
        # Check time since last activity
        last_record = max(entity_records, key=lambda x: x.timestamp)
        time_since_last = datetime.now() - last_record.timestamp
        
        absence_threshold_hours = self.config['alert_absence_hours']
        
        if time_since_last > timedelta(hours=absence_threshold_hours):
            severity = 'high' if time_since_last > timedelta(hours=24) else 'medium'
            
            return AnomalyAlert(
                entity_id=last_record.unified_entity_id,
                alert_type='absence',
                severity=severity,
                timestamp=datetime.now(),
                description=f"No activity detected for {time_since_last.total_seconds() / 3600:.1f} hours",
                evidence={
                    'last_seen': last_record.timestamp,
                    'last_location': last_record.location,
                    'absence_duration_hours': time_since_last.total_seconds() / 3600,
                    'entity_role': entity_profile.get('role', 'unknown')
                },
                recommended_actions=[
                    "Contact entity directly",
                    "Check with department/supervisor",
                    "Review recent access logs",
                    "Verify if planned absence"
                ]
            )
        
        return None
    
    def _create_behavioral_anomaly_alert(self, 
                                       record: FusionRecord,
                                       anomaly_score: float,
                                       entity_profile: Dict) -> AnomalyAlert:
        """Create alert for behavioral anomaly"""
        severity = 'high' if anomaly_score < -0.8 else 'medium'
        
        return AnomalyAlert(
            entity_id=record.unified_entity_id,
            alert_type='behavioral',
            severity=severity,
            timestamp=record.timestamp,
            description=f"Unusual activity pattern detected at {record.location}",
            evidence={
                'anomaly_score': anomaly_score,
                'location': record.location,
                'activity': record.activity_type,
                'confidence': record.confidence,
                'sources': [sr['dataset'] for sr in record.source_records],
                'entity_role': entity_profile.get('role', 'unknown')
            },
            recommended_actions=[
                "Review activity details",
                "Check for data quality issues",
                "Verify entity authorization for location",
                "Investigate if security concern"
            ]
        )
    
    def save_models(self, model_path: str):
        """Save trained models to disk"""
        if not self.is_trained:
            logger.error("No trained models to save")
            return
        
        model_data = {
            'location_predictor': self.location_predictor,
            'activity_predictor': self.activity_predictor,
            'anomaly_detector': self.anomaly_detector,
            'label_encoders': self.label_encoders,
            'feature_scaler': self.feature_scaler,
            'config': self.config
        }
        
        joblib.dump(model_data, model_path)
        logger.info(f"Models saved to {model_path}")
    
    def load_models(self, model_path: str):
        """Load trained models from disk"""
        try:
            model_data = joblib.load(model_path)
            
            self.location_predictor = model_data['location_predictor']
            self.activity_predictor = model_data['activity_predictor']
            self.anomaly_detector = model_data['anomaly_detector']
            self.label_encoders = model_data['label_encoders']
            self.feature_scaler = model_data['feature_scaler']
            self.config = model_data.get('config', self.config)
            
            self.is_trained = True
            logger.info(f"Models loaded from {model_path}")
            
        except Exception as e:
            logger.error(f"Failed to load models: {e}")
    
    def get_prediction_statistics(self, predictions: List[Prediction]) -> Dict[str, Any]:
        """Get statistics about predictions"""
        if not predictions:
            return {}
        
        confidences = [p.confidence for p in predictions]
        locations = [p.predicted_location for p in predictions]
        activities = [p.predicted_activity for p in predictions]
        
        return {
            'total_predictions': len(predictions),
            'average_confidence': np.mean(confidences),
            'confidence_std': np.std(confidences),
            'high_confidence_predictions': sum(1 for c in confidences if c > 0.8),
            'location_distribution': pd.Series(locations).value_counts().to_dict(),
            'activity_distribution': pd.Series(activities).value_counts().to_dict(),
            'prediction_coverage': len(set(locations)) / len(CAMPUS_LOCATIONS) if CAMPUS_LOCATIONS else 0
        }
