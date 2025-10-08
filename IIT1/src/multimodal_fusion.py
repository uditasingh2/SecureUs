"""
Multi-Modal Fusion System for Campus Entity Resolution
Integrates structured data, text notes, and visual inputs with confidence scoring
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import cv2
from sklearn.metrics.pairwise import cosine_similarity
from loguru import logger
import re

from .config import FUSION_CONFIG, CAMPUS_LOCATIONS
from .entity_resolver import ResolvedEntity


@dataclass
class FusionRecord:
    """Represents a fused record from multiple data sources"""
    unified_entity_id: str
    timestamp: datetime
    location: str
    activity_type: str
    confidence: float
    source_records: List[Dict[str, Any]]
    provenance: Dict[str, str]
    evidence: Dict[str, Any]


@dataclass
class ActivityEvent:
    """Represents a single activity event"""
    entity_id: str
    timestamp: datetime
    location: str
    event_type: str
    source_dataset: str
    raw_data: Dict[str, Any]
    confidence: float = 1.0


class MultiModalFusion:
    """
    Advanced multi-modal fusion system that integrates:
    - Structured data (card swipes, WiFi, bookings)
    - Text data (notes, helpdesk tickets)
    - Visual data (CCTV, face recognition)
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or FUSION_CONFIG
        self.fused_records = []
        self.activity_timeline = {}
        
    def fuse_entity_data(self, 
                        entity: ResolvedEntity, 
                        entity_data: Dict[str, pd.DataFrame],
                        face_embeddings: Optional[pd.DataFrame] = None) -> List[FusionRecord]:
        """
        Fuse all data sources for a specific entity
        Returns chronologically ordered fusion records
        """
        logger.info(f"Fusing data for entity {entity.unified_id}")
        
        # Step 1: Extract all activity events
        activity_events = self._extract_activity_events(entity, entity_data)
        logger.debug(f"Extracted {len(activity_events)} activity events")
        
        # Step 2: Temporal clustering of events
        event_clusters = self._cluster_temporal_events(activity_events)
        logger.debug(f"Created {len(event_clusters)} temporal clusters")
        
        # Step 3: Cross-source correlation within clusters
        fused_records = []
        for cluster in event_clusters:
            fused_record = self._fuse_event_cluster(cluster, face_embeddings)
            if fused_record:
                fused_records.append(fused_record)
        
        # Step 4: Sort by timestamp and validate
        fused_records.sort(key=lambda x: x.timestamp)
        validated_records = self._validate_fusion_records(fused_records)
        
        logger.info(f"Generated {len(validated_records)} fused records for entity {entity.unified_id}")
        return validated_records
    
    def _extract_activity_events(self, 
                                entity: ResolvedEntity, 
                                entity_data: Dict[str, pd.DataFrame]) -> List[ActivityEvent]:
        """Extract all activity events from entity data"""
        events = []
        
        # Card swipe events
        if 'card_swipes' in entity_data and not entity_data['card_swipes'].empty:
            for _, row in entity_data['card_swipes'].iterrows():
                events.append(ActivityEvent(
                    entity_id=entity.unified_id,
                    timestamp=pd.to_datetime(row['timestamp']),
                    location=row['location_id'],
                    event_type='card_swipe',
                    source_dataset='card_swipes',
                    raw_data=row.to_dict(),
                    confidence=0.95  # High confidence for physical access
                ))
        
        # CCTV detection events
        if 'cctv_frames' in entity_data and not entity_data['cctv_frames'].empty:
            for _, row in entity_data['cctv_frames'].iterrows():
                events.append(ActivityEvent(
                    entity_id=entity.unified_id,
                    timestamp=pd.to_datetime(row['timestamp']),
                    location=row['location_id'],
                    event_type='cctv_detection',
                    source_dataset='cctv_frames',
                    raw_data=row.to_dict(),
                    confidence=0.85  # Good confidence for face detection
                ))
        
        # WiFi connection events
        if 'wifi_logs' in entity_data and not entity_data['wifi_logs'].empty:
            for _, row in entity_data['wifi_logs'].iterrows():
                # Infer location from AP ID
                location = self._infer_location_from_ap(row['ap_id'])
                events.append(ActivityEvent(
                    entity_id=entity.unified_id,
                    timestamp=pd.to_datetime(row['timestamp']),
                    location=location,
                    event_type='wifi_connection',
                    source_dataset='wifi_logs',
                    raw_data=row.to_dict(),
                    confidence=0.75  # Medium confidence for location inference
                ))
        
        # Lab booking events
        if 'lab_bookings' in entity_data and not entity_data['lab_bookings'].empty:
            for _, row in entity_data['lab_bookings'].iterrows():
                # Start event
                events.append(ActivityEvent(
                    entity_id=entity.unified_id,
                    timestamp=pd.to_datetime(row['start_time']),
                    location=row['room_id'],
                    event_type='lab_booking_start',
                    source_dataset='lab_bookings',
                    raw_data=row.to_dict(),
                    confidence=0.90 if row.get('attended') else 0.60
                ))
                
                # End event
                events.append(ActivityEvent(
                    entity_id=entity.unified_id,
                    timestamp=pd.to_datetime(row['end_time']),
                    location=row['room_id'],
                    event_type='lab_booking_end',
                    source_dataset='lab_bookings',
                    raw_data=row.to_dict(),
                    confidence=0.90 if row.get('attended') else 0.60
                ))
        
        # Library checkout events
        if 'library_checkouts' in entity_data and not entity_data['library_checkouts'].empty:
            for _, row in entity_data['library_checkouts'].iterrows():
                events.append(ActivityEvent(
                    entity_id=entity.unified_id,
                    timestamp=pd.to_datetime(row['timestamp']),
                    location='LIB_ENT',  # Assume library entrance
                    event_type='library_checkout',
                    source_dataset='library_checkouts',
                    raw_data=row.to_dict(),
                    confidence=0.85
                ))
        
        # Note/helpdesk events
        if 'notes' in entity_data and not entity_data['notes'].empty:
            for _, row in entity_data['notes'].iterrows():
                # Try to infer location from note text
                location = self._infer_location_from_text(row['text'])
                events.append(ActivityEvent(
                    entity_id=entity.unified_id,
                    timestamp=pd.to_datetime(row['timestamp']),
                    location=location or 'UNKNOWN',
                    event_type=f"note_{row['category']}",
                    source_dataset='notes',
                    raw_data=row.to_dict(),
                    confidence=0.70  # Lower confidence for text inference
                ))
        
        return events
    
    def _infer_location_from_ap(self, ap_id: str) -> str:
        """Infer location from WiFi access point ID"""
        # Extract location pattern from AP ID (e.g., AP_LAB_1 -> LAB)
        match = re.search(r'AP_([A-Z]+)_\d+', ap_id)
        if match:
            location_prefix = match.group(1)
            
            # Map to known locations
            location_mapping = {
                'LAB': 'LAB_101',  # Default lab
                'LIB': 'LIB_ENT',
                'CAF': 'CAF_01',
                'AUD': 'AUDITORIUM',
                'ENG': 'LAB_101',
                'HOSTEL': 'HOSTEL_GATE'
            }
            
            return location_mapping.get(location_prefix, f"{location_prefix}_AREA")
        
        return 'UNKNOWN'
    
    def _infer_location_from_text(self, text: str) -> Optional[str]:
        """Infer location from text content"""
        text_lower = text.lower()
        
        # Location keywords mapping
        location_keywords = {
            'library': 'LIB_ENT',
            'lab': 'LAB_101',
            'gym': 'GYM',
            'cafeteria': 'CAF_01',
            'hostel': 'HOSTEL_GATE',
            'auditorium': 'AUDITORIUM',
            'seminar': 'SEM_01',
            'admin': 'ADMIN_LOBBY'
        }
        
        for keyword, location in location_keywords.items():
            if keyword in text_lower:
                return location
        
        return None
    
    def _cluster_temporal_events(self, events: List[ActivityEvent]) -> List[List[ActivityEvent]]:
        """Cluster events that occur within the same time window"""
        if not events:
            return []
        
        # Sort events by timestamp
        events.sort(key=lambda x: x.timestamp)
        
        clusters = []
        current_cluster = [events[0]]
        
        for event in events[1:]:
            time_diff = (event.timestamp - current_cluster[-1].timestamp).total_seconds() / 60
            
            if time_diff <= self.config['max_time_gap_minutes']:
                current_cluster.append(event)
            else:
                clusters.append(current_cluster)
                current_cluster = [event]
        
        if current_cluster:
            clusters.append(current_cluster)
        
        return clusters
    
    def _fuse_event_cluster(self, 
                           events: List[ActivityEvent], 
                           face_embeddings: Optional[pd.DataFrame] = None) -> Optional[FusionRecord]:
        """Fuse a cluster of temporally related events"""
        if not events:
            return None
        
        # Use the earliest timestamp as the cluster timestamp
        cluster_timestamp = min(event.timestamp for event in events)
        
        # Determine primary location (most confident or most frequent)
        location_scores = {}
        for event in events:
            if event.location not in location_scores:
                location_scores[event.location] = []
            location_scores[event.location].append(event.confidence)
        
        # Calculate weighted location scores
        primary_location = max(location_scores.keys(), 
                             key=lambda loc: np.mean(location_scores[loc]) * len(location_scores[loc]))
        
        # Determine primary activity type
        activity_types = [event.event_type for event in events]
        primary_activity = max(set(activity_types), key=activity_types.count)
        
        # Calculate fusion confidence
        fusion_confidence = self._calculate_fusion_confidence(events, face_embeddings)
        
        # Build provenance information
        provenance = {}
        source_records = []
        evidence = {}
        
        for event in events:
            provenance[event.source_dataset] = f"{event.event_type} at {event.timestamp}"
            source_records.append({
                'dataset': event.source_dataset,
                'event_type': event.event_type,
                'timestamp': event.timestamp,
                'confidence': event.confidence,
                'raw_data': event.raw_data
            })
        
        # Cross-source validation evidence
        evidence.update(self._generate_cross_source_evidence(events))
        
        # Face recognition evidence if available
        if face_embeddings is not None:
            face_evidence = self._validate_face_recognition(events, face_embeddings)
            if face_evidence:
                evidence['face_recognition'] = face_evidence
        
        return FusionRecord(
            unified_entity_id=events[0].entity_id,
            timestamp=cluster_timestamp,
            location=primary_location,
            activity_type=primary_activity,
            confidence=fusion_confidence,
            source_records=source_records,
            provenance=provenance,
            evidence=evidence
        )
    
    def _calculate_fusion_confidence(self, 
                                   events: List[ActivityEvent], 
                                   face_embeddings: Optional[pd.DataFrame] = None) -> float:
        """Calculate confidence score for fused record"""
        if not events:
            return 0.0
        
        # Base confidence from individual events
        base_confidence = np.mean([event.confidence for event in events])
        
        # Multi-source bonus (more sources = higher confidence)
        unique_sources = len(set(event.source_dataset for event in events))
        source_bonus = min(0.2, unique_sources * 0.05)
        
        # Location consistency bonus
        locations = [event.location for event in events if event.location != 'UNKNOWN']
        location_consistency = 1.0 if len(set(locations)) <= 1 else 0.8
        
        # Temporal consistency (events close in time)
        if len(events) > 1:
            time_span = (max(event.timestamp for event in events) - 
                        min(event.timestamp for event in events)).total_seconds() / 60
            temporal_consistency = max(0.5, 1.0 - (time_span / self.config['max_time_gap_minutes']))
        else:
            temporal_consistency = 1.0
        
        # Face recognition validation bonus
        face_bonus = 0.0
        if face_embeddings is not None:
            face_validation = self._validate_face_recognition(events, face_embeddings)
            if face_validation and face_validation.get('similarity', 0) > self.config['face_similarity_threshold']:
                face_bonus = 0.1
        
        # Calculate final confidence
        final_confidence = (base_confidence + source_bonus) * location_consistency * temporal_consistency + face_bonus
        
        return min(1.0, final_confidence)
    
    def _generate_cross_source_evidence(self, events: List[ActivityEvent]) -> Dict[str, Any]:
        """Generate evidence for cross-source validation"""
        evidence = {}
        
        # Time correlation evidence
        if len(events) > 1:
            timestamps = [event.timestamp for event in events]
            time_span = (max(timestamps) - min(timestamps)).total_seconds() / 60
            evidence['temporal_correlation'] = {
                'time_span_minutes': time_span,
                'events_count': len(events),
                'correlation_strength': 'high' if time_span <= 5 else 'medium' if time_span <= 15 else 'low'
            }
        
        # Location correlation evidence
        locations = [event.location for event in events if event.location != 'UNKNOWN']
        if locations:
            unique_locations = set(locations)
            evidence['location_correlation'] = {
                'locations': list(unique_locations),
                'consistency': 'high' if len(unique_locations) == 1 else 'medium' if len(unique_locations) <= 2 else 'low'
            }
        
        # Source diversity evidence
        sources = [event.source_dataset for event in events]
        evidence['source_diversity'] = {
            'sources': list(set(sources)),
            'diversity_score': len(set(sources)) / len(sources) if sources else 0
        }
        
        # Activity pattern evidence
        activity_types = [event.event_type for event in events]
        evidence['activity_pattern'] = {
            'types': activity_types,
            'primary_activity': max(set(activity_types), key=activity_types.count) if activity_types else None
        }
        
        return evidence
    
    def _validate_face_recognition(self, 
                                 events: List[ActivityEvent], 
                                 face_embeddings: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """Validate events using face recognition data"""
        # Find CCTV events in the cluster
        cctv_events = [event for event in events if event.event_type == 'cctv_detection']
        
        if not cctv_events or face_embeddings.empty:
            return None
        
        face_validation = {}
        
        for cctv_event in cctv_events:
            face_id = cctv_event.raw_data.get('face_id')
            if not face_id:
                continue
            
            # Find corresponding face embedding
            face_embedding_row = face_embeddings[face_embeddings['face_id'] == face_id]
            if face_embedding_row.empty:
                continue
            
            embedding_vector = face_embedding_row.iloc[0]['embedding_vector']
            
            # For now, we'll assume high similarity if we have the embedding
            # In a real implementation, this would compare against known face embeddings
            face_validation[face_id] = {
                'similarity': 0.9,  # Placeholder - would be actual similarity score
                'embedding_quality': len(embedding_vector) if hasattr(embedding_vector, '__len__') else 0,
                'detection_confidence': cctv_event.confidence
            }
        
        return face_validation if face_validation else None
    
    def _validate_fusion_records(self, records: List[FusionRecord]) -> List[FusionRecord]:
        """Validate and filter fusion records"""
        validated_records = []
        
        for record in records:
            # Filter by minimum confidence threshold
            if record.confidence >= self.config['confidence_threshold']:
                validated_records.append(record)
            else:
                logger.debug(f"Filtered record with low confidence: {record.confidence}")
        
        return validated_records
    
    def generate_activity_summary(self, fused_records: List[FusionRecord]) -> Dict[str, Any]:
        """Generate summary statistics for fused activity data"""
        if not fused_records:
            return {}
        
        # Time range
        timestamps = [record.timestamp for record in fused_records]
        time_range = {
            'start': min(timestamps),
            'end': max(timestamps),
            'duration_hours': (max(timestamps) - min(timestamps)).total_seconds() / 3600
        }
        
        # Location analysis
        locations = [record.location for record in fused_records]
        location_counts = pd.Series(locations).value_counts().to_dict()
        
        # Activity analysis
        activities = [record.activity_type for record in fused_records]
        activity_counts = pd.Series(activities).value_counts().to_dict()
        
        # Confidence analysis
        confidences = [record.confidence for record in fused_records]
        confidence_stats = {
            'mean': np.mean(confidences),
            'min': np.min(confidences),
            'max': np.max(confidences),
            'std': np.std(confidences)
        }
        
        # Source diversity
        all_sources = []
        for record in fused_records:
            all_sources.extend([sr['dataset'] for sr in record.source_records])
        source_counts = pd.Series(all_sources).value_counts().to_dict()
        
        return {
            'total_records': len(fused_records),
            'time_range': time_range,
            'location_distribution': location_counts,
            'activity_distribution': activity_counts,
            'confidence_statistics': confidence_stats,
            'source_distribution': source_counts,
            'average_sources_per_record': np.mean([len(record.source_records) for record in fused_records])
        }
    
    def export_fusion_results(self, fused_records: List[FusionRecord]) -> pd.DataFrame:
        """Export fusion results to a structured DataFrame"""
        if not fused_records:
            return pd.DataFrame()
        
        export_data = []
        
        for record in fused_records:
            row = {
                'unified_entity_id': record.unified_entity_id,
                'timestamp': record.timestamp,
                'location': record.location,
                'activity_type': record.activity_type,
                'confidence': record.confidence,
                'source_count': len(record.source_records),
                'sources': ','.join([sr['dataset'] for sr in record.source_records]),
                'evidence_score': len(record.evidence),
                'provenance': str(record.provenance)
            }
            export_data.append(row)
        
        return pd.DataFrame(export_data)
