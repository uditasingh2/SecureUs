"""
Data loading and preprocessing module for Campus Entity Resolution System
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from loguru import logger
import ast
import zipfile
from PIL import Image
import io

from .config import DATA_FILES, CAMPUS_LOCATIONS, ENTITY_TYPES


class CampusDataLoader:
    """Handles loading and preprocessing of all campus data sources"""
    
    def __init__(self):
        self.data = {}
        self.processed_data = {}
        
    def load_all_data(self) -> Dict[str, pd.DataFrame]:
        """Load all data sources into memory"""
        logger.info("Loading all campus data sources...")
        
        # Load structured data
        self.data['profiles'] = self._load_profiles()
        self.data['card_swipes'] = self._load_card_swipes()
        self.data['cctv_frames'] = self._load_cctv_frames()
        self.data['face_embeddings'] = self._load_face_embeddings()
        self.data['notes'] = self._load_notes()
        self.data['lab_bookings'] = self._load_lab_bookings()
        self.data['library_checkouts'] = self._load_library_checkouts()
        self.data['wifi_logs'] = self._load_wifi_logs()
        
        logger.info(f"Loaded {len(self.data)} data sources successfully")
        return self.data
    
    def _load_profiles(self) -> pd.DataFrame:
        """Load student and staff profiles"""
        df = pd.read_csv(DATA_FILES['profiles'])
        
        # Clean and standardize data
        df['name'] = df['name'].str.strip()
        df['email'] = df['email'].str.lower().str.strip()
        df['role'] = df['role'].str.lower().str.strip()
        df['department'] = df['department'].fillna('Unknown')
        
        # Create unified entity mapping
        df['entity_type'] = df['role'].map(lambda x: x if x in ENTITY_TYPES else 'student')
        
        logger.info(f"Loaded {len(df)} profiles")
        return df
    
    def _load_card_swipes(self) -> pd.DataFrame:
        """Load campus card swipe data"""
        df = pd.read_csv(DATA_FILES['card_swipes'])
        
        # Parse timestamps
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date
        df['hour'] = df['timestamp'].dt.hour
        
        # Add location metadata
        df['location_name'] = df['location_id'].map(
            lambda x: CAMPUS_LOCATIONS.get(x, {}).get('name', x)
        )
        
        logger.info(f"Loaded {len(df)} card swipe records")
        return df
    
    def _load_cctv_frames(self) -> pd.DataFrame:
        """Load CCTV frame data"""
        df = pd.read_csv(DATA_FILES['cctv_frames'])
        
        # Parse timestamps (handle different formats)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date
        df['hour'] = df['timestamp'].dt.hour
        
        # Handle missing face_id
        df['has_face_detection'] = df['face_id'].notna()
        
        logger.info(f"Loaded {len(df)} CCTV frame records")
        return df
    
    def _load_face_embeddings(self) -> pd.DataFrame:
        """Load face embedding vectors"""
        df = pd.read_csv(DATA_FILES['face_embeddings'])
        
        # Parse embedding vectors from string representation
        def parse_embedding(embedding_str):
            try:
                return np.array(ast.literal_eval(embedding_str))
            except:
                return np.zeros(128)  # Default embedding size
        
        df['embedding_vector'] = df['embedding'].apply(parse_embedding)
        df['embedding_dimension'] = df['embedding_vector'].apply(len)
        
        logger.info(f"Loaded {len(df)} face embeddings")
        return df
    
    def _load_notes(self) -> pd.DataFrame:
        """Load free text notes (helpdesk, RSVPs, etc.)"""
        df = pd.read_csv(DATA_FILES['notes'])
        
        # Parse timestamps
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date
        
        # Categorize notes
        df['category'] = df['category'].str.lower().str.strip()
        df['text_length'] = df['text'].str.len()
        
        logger.info(f"Loaded {len(df)} text notes")
        return df
    
    def _load_lab_bookings(self) -> pd.DataFrame:
        """Load lab booking data"""
        df = pd.read_csv(DATA_FILES['lab_bookings'])
        
        # Parse timestamps
        df['start_time'] = pd.to_datetime(df['start_time'])
        df['end_time'] = pd.to_datetime(df['end_time'])
        df['duration_minutes'] = (df['end_time'] - df['start_time']).dt.total_seconds() / 60
        
        # Parse attendance
        df['attended'] = df['attended (YES/NO)'].str.upper() == 'YES'
        
        logger.info(f"Loaded {len(df)} lab booking records")
        return df
    
    def _load_library_checkouts(self) -> pd.DataFrame:
        """Load library checkout data"""
        df = pd.read_csv(DATA_FILES['library_checkouts'])
        
        # Parse timestamps
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date
        df['hour'] = df['timestamp'].dt.hour
        
        logger.info(f"Loaded {len(df)} library checkout records")
        return df
    
    def _load_wifi_logs(self) -> pd.DataFrame:
        """Load WiFi association logs"""
        df = pd.read_csv(DATA_FILES['wifi_logs'])
        
        # Parse timestamps (handle different formats)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date
        df['hour'] = df['timestamp'].dt.hour
        
        # Extract location from AP ID
        df['location_from_ap'] = df['ap_id'].str.extract(r'AP_([A-Z]+)_\d+')[0]
        
        logger.info(f"Loaded {len(df)} WiFi association records")
        return df
    
    def get_entity_data(self, entity_id: str) -> Dict[str, pd.DataFrame]:
        """Get all data related to a specific entity"""
        entity_data = {}
        
        # Profile data
        if 'profiles' in self.data:
            entity_data['profile'] = self.data['profiles'][
                self.data['profiles']['entity_id'] == entity_id
            ]
        
        # Card swipes
        if 'card_swipes' in self.data and 'profiles' in self.data:
            card_id = self.data['profiles'][
                self.data['profiles']['entity_id'] == entity_id
            ]['card_id'].iloc[0] if len(self.data['profiles'][
                self.data['profiles']['entity_id'] == entity_id
            ]) > 0 else None
            
            if card_id:
                entity_data['card_swipes'] = self.data['card_swipes'][
                    self.data['card_swipes']['card_id'] == card_id
                ]
        
        # CCTV frames
        if 'cctv_frames' in self.data and 'profiles' in self.data:
            face_id = self.data['profiles'][
                self.data['profiles']['entity_id'] == entity_id
            ]['face_id'].iloc[0] if len(self.data['profiles'][
                self.data['profiles']['entity_id'] == entity_id
            ]) > 0 else None
            
            if face_id:
                entity_data['cctv_frames'] = self.data['cctv_frames'][
                    self.data['cctv_frames']['face_id'] == face_id
                ]
        
        # WiFi logs
        if 'wifi_logs' in self.data and 'profiles' in self.data:
            device_hash = self.data['profiles'][
                self.data['profiles']['entity_id'] == entity_id
            ]['device_hash'].iloc[0] if len(self.data['profiles'][
                self.data['profiles']['entity_id'] == entity_id
            ]) > 0 else None
            
            if device_hash:
                entity_data['wifi_logs'] = self.data['wifi_logs'][
                    self.data['wifi_logs']['device_hash'] == device_hash
                ]
        
        # Notes
        if 'notes' in self.data:
            entity_data['notes'] = self.data['notes'][
                self.data['notes']['entity_id'] == entity_id
            ]
        
        # Lab bookings
        if 'lab_bookings' in self.data:
            entity_data['lab_bookings'] = self.data['lab_bookings'][
                self.data['lab_bookings']['entity_id'] == entity_id
            ]
        
        # Library checkouts
        if 'library_checkouts' in self.data:
            entity_data['library_checkouts'] = self.data['library_checkouts'][
                self.data['library_checkouts']['entity_id'] == entity_id
            ]
        
        return entity_data
    
    def get_data_summary(self) -> Dict[str, Dict]:
        """Get summary statistics for all loaded data"""
        summary = {}
        
        for source_name, df in self.data.items():
            if isinstance(df, pd.DataFrame):
                summary[source_name] = {
                    'records': len(df),
                    'columns': list(df.columns),
                    'date_range': self._get_date_range(df),
                    'memory_usage_mb': df.memory_usage(deep=True).sum() / 1024 / 1024
                }
        
        return summary
    
    def _get_date_range(self, df: pd.DataFrame) -> Optional[Tuple[str, str]]:
        """Extract date range from dataframe"""
        timestamp_cols = [col for col in df.columns if 'timestamp' in col.lower() or 'time' in col.lower()]
        
        if timestamp_cols:
            col = timestamp_cols[0]
            if df[col].dtype == 'datetime64[ns]':
                min_date = df[col].min().strftime('%Y-%m-%d')
                max_date = df[col].max().strftime('%Y-%m-%d')
                return (min_date, max_date)
        
        return None
    
    def validate_data_integrity(self) -> Dict[str, List[str]]:
        """Validate data integrity and return issues"""
        issues = {}
        
        # Check for missing files
        missing_files = []
        for name, path in DATA_FILES.items():
            if not path.exists():
                missing_files.append(f"{name}: {path}")
        
        if missing_files:
            issues['missing_files'] = missing_files
        
        # Check for data consistency
        if 'profiles' in self.data and 'card_swipes' in self.data:
            profile_cards = set(self.data['profiles']['card_id'].dropna())
            swipe_cards = set(self.data['card_swipes']['card_id'])
            orphaned_swipes = swipe_cards - profile_cards
            
            if orphaned_swipes:
                issues['orphaned_card_swipes'] = list(orphaned_swipes)
        
        return issues
