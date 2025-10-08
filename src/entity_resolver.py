"""
Entity Resolution Engine for Campus Entity Resolution System
Core component for linking entities across heterogeneous datasets
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from fuzzywuzzy import fuzz, process
import networkx as nx
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_similarity
from loguru import logger
import re

from .config import ENTITY_RESOLUTION_CONFIG


@dataclass
class EntityMatch:
    """Represents a potential entity match between records"""
    source_id: str
    target_id: str
    source_dataset: str
    target_dataset: str
    confidence: float
    match_type: str
    evidence: Dict[str, any]


@dataclass
class ResolvedEntity:
    """Represents a resolved entity with unified identifiers"""
    unified_id: str
    entity_ids: Set[str]
    names: Set[str]
    identifiers: Dict[str, Set[str]]
    confidence: float
    primary_profile: Dict[str, any]


class EntityResolver:
    """
    Advanced entity resolution system for campus data
    Uses fuzzy matching, graph clustering, and confidence scoring
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or ENTITY_RESOLUTION_CONFIG
        self.entity_graph = nx.Graph()
        self.resolved_entities = {}
        self.match_cache = {}
        
    def resolve_entities(self, data: Dict[str, pd.DataFrame]) -> Dict[str, ResolvedEntity]:
        """
        Main entity resolution pipeline
        Returns dictionary of unified entities
        """
        logger.info("Starting entity resolution process...")
        
        # Step 1: Extract all potential entity records
        entity_records = self._extract_entity_records(data)
        logger.info(f"Extracted {len(entity_records)} entity records")
        
        # Step 2: Find potential matches using multiple strategies
        matches = self._find_entity_matches(entity_records)
        logger.info(f"Found {len(matches)} potential matches")
        
        # Step 3: Build entity graph
        self._build_entity_graph(matches)
        logger.info(f"Built entity graph with {self.entity_graph.number_of_nodes()} nodes")
        
        # Step 4: Cluster entities using graph analysis
        entity_clusters = self._cluster_entities()
        logger.info(f"Identified {len(entity_clusters)} entity clusters")
        
        # Step 5: Create resolved entities
        self.resolved_entities = self._create_resolved_entities(entity_clusters, entity_records)
        logger.info(f"Resolved {len(self.resolved_entities)} unique entities")
        
        return self.resolved_entities
    
    def _extract_entity_records(self, data: Dict[str, pd.DataFrame]) -> List[Dict]:
        """Extract all records that could represent entities"""
        entity_records = []
        
        # Primary source: profiles
        if 'profiles' in data:
            for _, row in data['profiles'].iterrows():
                record = {
                    'record_id': f"profile_{row['entity_id']}",
                    'dataset': 'profiles',
                    'entity_id': row['entity_id'],
                    'name': row['name'],
                    'email': row['email'],
                    'role': row['role'],
                    'department': row['department'],
                    'student_id': row.get('student_id'),
                    'staff_id': row.get('staff_id'),
                    'card_id': row['card_id'],
                    'device_hash': row['device_hash'],
                    'face_id': row['face_id']
                }
                entity_records.append(record)
        
        # Secondary sources: infer entities from other datasets
        entity_records.extend(self._extract_from_card_swipes(data.get('card_swipes')))
        entity_records.extend(self._extract_from_wifi_logs(data.get('wifi_logs')))
        entity_records.extend(self._extract_from_cctv_frames(data.get('cctv_frames')))
        entity_records.extend(self._extract_from_notes(data.get('notes')))
        
        return entity_records
    
    def _extract_from_card_swipes(self, df: Optional[pd.DataFrame]) -> List[Dict]:
        """Extract entity records from card swipe data"""
        if df is None or df.empty:
            return []
        
        records = []
        unique_cards = df['card_id'].unique()
        
        for card_id in unique_cards:
            card_data = df[df['card_id'] == card_id]
            record = {
                'record_id': f"card_{card_id}",
                'dataset': 'card_swipes',
                'card_id': card_id,
                'first_seen': card_data['timestamp'].min(),
                'last_seen': card_data['timestamp'].max(),
                'locations_visited': card_data['location_id'].unique().tolist(),
                'total_swipes': len(card_data)
            }
            records.append(record)
        
        return records
    
    def _extract_from_wifi_logs(self, df: Optional[pd.DataFrame]) -> List[Dict]:
        """Extract entity records from WiFi logs"""
        if df is None or df.empty:
            return []
        
        records = []
        unique_devices = df['device_hash'].unique()
        
        for device_hash in unique_devices:
            device_data = df[df['device_hash'] == device_hash]
            record = {
                'record_id': f"wifi_{device_hash}",
                'dataset': 'wifi_logs',
                'device_hash': device_hash,
                'first_seen': device_data['timestamp'].min(),
                'last_seen': device_data['timestamp'].max(),
                'access_points': device_data['ap_id'].unique().tolist(),
                'total_connections': len(device_data)
            }
            records.append(record)
        
        return records
    
    def _extract_from_cctv_frames(self, df: Optional[pd.DataFrame]) -> List[Dict]:
        """Extract entity records from CCTV frames"""
        if df is None or df.empty:
            return []
        
        records = []
        unique_faces = df[df['face_id'].notna()]['face_id'].unique()
        
        for face_id in unique_faces:
            face_data = df[df['face_id'] == face_id]
            record = {
                'record_id': f"face_{face_id}",
                'dataset': 'cctv_frames',
                'face_id': face_id,
                'first_seen': face_data['timestamp'].min(),
                'last_seen': face_data['timestamp'].max(),
                'locations_detected': face_data['location_id'].unique().tolist(),
                'total_detections': len(face_data)
            }
            records.append(record)
        
        return records
    
    def _extract_from_notes(self, df: Optional[pd.DataFrame]) -> List[Dict]:
        """Extract entity records from text notes"""
        if df is None or df.empty:
            return []
        
        records = []
        unique_entities = df['entity_id'].unique()
        
        for entity_id in unique_entities:
            entity_data = df[df['entity_id'] == entity_id]
            record = {
                'record_id': f"notes_{entity_id}",
                'dataset': 'notes',
                'entity_id': entity_id,
                'note_categories': entity_data['category'].unique().tolist(),
                'total_notes': len(entity_data),
                'first_note': entity_data['timestamp'].min(),
                'last_note': entity_data['timestamp'].max()
            }
            records.append(record)
        
        return records
    
    def _find_entity_matches(self, entity_records: List[Dict]) -> List[EntityMatch]:
        """Find potential matches between entity records"""
        matches = []
        
        # Limit comparison for performance - only compare first 1000 records
        limited_records = entity_records[:1000]
        
        for i, record1 in enumerate(limited_records):
            for j, record2 in enumerate(limited_records[i+1:], i+1):
                match = self._compare_records(record1, record2)
                if match and match.confidence >= self.config['fuzzy_match_threshold']:
                    matches.append(match)
        
        return matches
    
    def _compare_records(self, record1: Dict, record2: Dict) -> Optional[EntityMatch]:
        """Compare two records and determine if they might represent the same entity"""
        evidence = {}
        confidence_scores = []
        
        # Direct identifier matches (highest confidence)
        if self._check_direct_match(record1, record2, 'entity_id'):
            return EntityMatch(
                source_id=record1['record_id'],
                target_id=record2['record_id'],
                source_dataset=record1['dataset'],
                target_dataset=record2['dataset'],
                confidence=1.0,
                match_type='direct_entity_id',
                evidence={'entity_id': record1.get('entity_id')}
            )
        
        # Card ID matches
        if self._check_direct_match(record1, record2, 'card_id'):
            confidence_scores.append(0.95)
            evidence['card_id_match'] = True
        
        # Device hash matches
        if self._check_direct_match(record1, record2, 'device_hash'):
            confidence_scores.append(0.90)
            evidence['device_hash_match'] = True
        
        # Face ID matches
        if self._check_direct_match(record1, record2, 'face_id'):
            confidence_scores.append(0.85)
            evidence['face_id_match'] = True
        
        # Name similarity (fuzzy matching)
        name_similarity = self._calculate_name_similarity(record1, record2)
        if name_similarity > self.config['name_similarity_threshold']:
            confidence_scores.append(name_similarity * 0.8)
            evidence['name_similarity'] = name_similarity
        
        # Email similarity
        email_similarity = self._calculate_email_similarity(record1, record2)
        if email_similarity > 0.8:
            confidence_scores.append(email_similarity * 0.7)
            evidence['email_similarity'] = email_similarity
        
        # Temporal correlation
        temporal_score = self._calculate_temporal_correlation(record1, record2)
        if temporal_score > 0.5:
            confidence_scores.append(temporal_score * 0.6)
            evidence['temporal_correlation'] = temporal_score
        
        # Location correlation
        location_score = self._calculate_location_correlation(record1, record2)
        if location_score > 0.5:
            confidence_scores.append(location_score * 0.5)
            evidence['location_correlation'] = location_score
        
        # Calculate overall confidence
        if confidence_scores:
            overall_confidence = max(confidence_scores)  # Take the highest confidence indicator
            
            if overall_confidence >= self.config['fuzzy_match_threshold']:
                return EntityMatch(
                    source_id=record1['record_id'],
                    target_id=record2['record_id'],
                    source_dataset=record1['dataset'],
                    target_dataset=record2['dataset'],
                    confidence=overall_confidence,
                    match_type='fuzzy_match',
                    evidence=evidence
                )
        
        return None
    
    def _check_direct_match(self, record1: Dict, record2: Dict, field: str) -> bool:
        """Check if two records have matching values for a specific field"""
        val1 = record1.get(field)
        val2 = record2.get(field)
        return val1 is not None and val2 is not None and val1 == val2
    
    def _calculate_name_similarity(self, record1: Dict, record2: Dict) -> float:
        """Calculate name similarity between two records"""
        name1 = record1.get('name', '').strip().lower()
        name2 = record2.get('name', '').strip().lower()
        
        if not name1 or not name2:
            return 0.0
        
        # Use multiple fuzzy matching strategies
        ratio = fuzz.ratio(name1, name2) / 100.0
        token_sort_ratio = fuzz.token_sort_ratio(name1, name2) / 100.0
        token_set_ratio = fuzz.token_set_ratio(name1, name2) / 100.0
        
        return max(ratio, token_sort_ratio, token_set_ratio)
    
    def _calculate_email_similarity(self, record1: Dict, record2: Dict) -> float:
        """Calculate email similarity between two records"""
        email1 = record1.get('email', '').strip().lower()
        email2 = record2.get('email', '').strip().lower()
        
        if not email1 or not email2:
            return 0.0
        
        return fuzz.ratio(email1, email2) / 100.0
    
    def _calculate_temporal_correlation(self, record1: Dict, record2: Dict) -> float:
        """Calculate temporal correlation between records"""
        # Look for overlapping time periods
        times1 = self._extract_timestamps(record1)
        times2 = self._extract_timestamps(record2)
        
        if not times1 or not times2:
            return 0.0
        
        # Calculate overlap in active periods
        overlap_score = 0.0
        for t1 in times1:
            for t2 in times2:
                time_diff = abs((t1 - t2).total_seconds()) / 60  # minutes
                if time_diff <= self.config['time_window_minutes']:
                    overlap_score = max(overlap_score, 1.0 - (time_diff / self.config['time_window_minutes']))
        
        return overlap_score
    
    def _calculate_location_correlation(self, record1: Dict, record2: Dict) -> float:
        """Calculate location correlation between records"""
        locations1 = self._extract_locations(record1)
        locations2 = self._extract_locations(record2)
        
        if not locations1 or not locations2:
            return 0.0
        
        # Calculate Jaccard similarity
        intersection = len(locations1.intersection(locations2))
        union = len(locations1.union(locations2))
        
        return intersection / union if union > 0 else 0.0
    
    def _extract_timestamps(self, record: Dict) -> List:
        """Extract timestamps from a record"""
        timestamps = []
        
        for key in ['first_seen', 'last_seen', 'first_note', 'last_note']:
            if key in record and record[key] is not None:
                timestamps.append(pd.to_datetime(record[key]))
        
        return timestamps
    
    def _extract_locations(self, record: Dict) -> Set[str]:
        """Extract locations from a record"""
        locations = set()
        
        for key in ['locations_visited', 'locations_detected', 'access_points']:
            if key in record and record[key]:
                if isinstance(record[key], list):
                    locations.update(record[key])
                else:
                    locations.add(record[key])
        
        return locations
    
    def _build_entity_graph(self, matches: List[EntityMatch]):
        """Build a graph of entity relationships"""
        self.entity_graph.clear()
        
        # Add all matches as edges
        for match in matches:
            self.entity_graph.add_edge(
                match.source_id,
                match.target_id,
                weight=match.confidence,
                match_type=match.match_type,
                evidence=match.evidence
            )
    
    def _cluster_entities(self) -> List[Set[str]]:
        """Cluster entities using graph-based community detection"""
        if self.entity_graph.number_of_nodes() == 0:
            return []
        
        # Use connected components for clustering
        clusters = list(nx.connected_components(self.entity_graph))
        
        # Filter clusters by minimum confidence
        filtered_clusters = []
        for cluster in clusters:
            if len(cluster) > 1:  # Only consider clusters with multiple nodes
                # Calculate cluster confidence
                subgraph = self.entity_graph.subgraph(cluster)
                avg_confidence = np.mean([data['weight'] for _, _, data in subgraph.edges(data=True)])
                
                if avg_confidence >= self.config['fuzzy_match_threshold']:
                    filtered_clusters.append(cluster)
            else:
                # Single node clusters are always valid
                filtered_clusters.append(cluster)
        
        return filtered_clusters
    
    def _create_resolved_entities(self, clusters: List[Set[str]], entity_records: List[Dict]) -> Dict[str, ResolvedEntity]:
        """Create resolved entities from clusters"""
        resolved_entities = {}
        record_lookup = {record['record_id']: record for record in entity_records}
        
        for i, cluster in enumerate(clusters):
            unified_id = f"unified_entity_{i:06d}"
            
            # Collect all information from cluster members
            entity_ids = set()
            names = set()
            identifiers = {
                'card_ids': set(),
                'device_hashes': set(),
                'face_ids': set(),
                'student_ids': set(),
                'staff_ids': set(),
                'emails': set()
            }
            
            primary_profile = None
            cluster_confidence = 1.0
            
            for record_id in cluster:
                record = record_lookup.get(record_id, {})
                
                # Collect entity IDs
                if 'entity_id' in record and record['entity_id']:
                    entity_ids.add(record['entity_id'])
                
                # Collect names
                if 'name' in record and record['name']:
                    names.add(record['name'])
                
                # Collect identifiers
                for id_type, id_key in [
                    ('card_ids', 'card_id'),
                    ('device_hashes', 'device_hash'),
                    ('face_ids', 'face_id'),
                    ('student_ids', 'student_id'),
                    ('staff_ids', 'staff_id'),
                    ('emails', 'email')
                ]:
                    if id_key in record and record[id_key]:
                        identifiers[id_type].add(record[id_key])
                
                # Use profile record as primary if available
                if record.get('dataset') == 'profiles' and primary_profile is None:
                    primary_profile = record
            
            # Calculate cluster confidence
            if len(cluster) > 1:
                subgraph = self.entity_graph.subgraph(cluster)
                if subgraph.number_of_edges() > 0:
                    cluster_confidence = np.mean([data['weight'] for _, _, data in subgraph.edges(data=True)])
            
            resolved_entity = ResolvedEntity(
                unified_id=unified_id,
                entity_ids=entity_ids,
                names=names,
                identifiers=identifiers,
                confidence=cluster_confidence,
                primary_profile=primary_profile or {}
            )
            
            resolved_entities[unified_id] = resolved_entity
        
        return resolved_entities
    
    def get_entity_by_identifier(self, identifier: str, identifier_type: str = None) -> Optional[ResolvedEntity]:
        """Find a resolved entity by any of its identifiers"""
        for entity in self.resolved_entities.values():
            # Check entity IDs
            if identifier in entity.entity_ids:
                return entity
            
            # Check specific identifier types
            if identifier_type and identifier_type in entity.identifiers:
                if identifier in entity.identifiers[identifier_type]:
                    return entity
            
            # Check all identifier types if no specific type given
            if not identifier_type:
                for id_set in entity.identifiers.values():
                    if identifier in id_set:
                        return entity
        
        return None
    
    def get_resolution_statistics(self) -> Dict[str, any]:
        """Get statistics about the entity resolution process"""
        if not self.resolved_entities:
            return {}
        
        total_entities = len(self.resolved_entities)
        merged_entities = sum(1 for entity in self.resolved_entities.values() if len(entity.entity_ids) > 1)
        avg_confidence = np.mean([entity.confidence for entity in self.resolved_entities.values()])
        
        return {
            'total_resolved_entities': total_entities,
            'merged_entities': merged_entities,
            'merge_rate': merged_entities / total_entities if total_entities > 0 else 0,
            'average_confidence': avg_confidence,
            'graph_nodes': self.entity_graph.number_of_nodes(),
            'graph_edges': self.entity_graph.number_of_edges()
        }
