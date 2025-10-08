"""
Configuration settings for Campus Entity Resolution System
"""
import os
from pathlib import Path
from typing import Dict, List

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "Product_Dataset" / "Test_Dataset"
OUTPUT_DIR = PROJECT_ROOT / "output"
LOGS_DIR = PROJECT_ROOT / "logs"

# Create directories if they don't exist
OUTPUT_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Data file paths
DATA_FILES = {
    "profiles": DATA_DIR / "student or staff profiles.csv",
    "card_swipes": DATA_DIR / "campus card_swipes.csv",
    "cctv_frames": DATA_DIR / "cctv_frames.csv",
    "face_embeddings": DATA_DIR / "face_embeddings.csv",
    "face_images": DATA_DIR / "face_images.zip",
    "notes": DATA_DIR / "free_text_notes (helpdesk or RSVPs).csv",
    "lab_bookings": DATA_DIR / "lab_bookings.csv",
    "library_checkouts": DATA_DIR / "library_checkouts.csv",
    "wifi_logs": DATA_DIR / "wifi_associations_logs.csv"
}

# Entity Resolution Configuration
ENTITY_RESOLUTION_CONFIG = {
    "name_similarity_threshold": 0.85,
    "fuzzy_match_threshold": 0.80,
    "time_window_minutes": 10,
    "location_match_weight": 0.3,
    "temporal_match_weight": 0.4,
    "identifier_match_weight": 0.3
}

# Multi-Modal Fusion Configuration
FUSION_CONFIG = {
    "confidence_threshold": 0.7,
    "max_time_gap_minutes": 15,
    "face_similarity_threshold": 0.85,
    "location_proximity_meters": 50
}

# Timeline Configuration
TIMELINE_CONFIG = {
    "max_gap_hours": 2,
    "summary_window_hours": 24,
    "activity_categories": [
        "access_control", "wifi_connection", "library_activity", 
        "lab_booking", "cctv_detection", "helpdesk_interaction"
    ]
}

# Predictive Monitoring Configuration
PREDICTION_CONFIG = {
    "missing_data_threshold_hours": 1,
    "prediction_confidence_threshold": 0.6,
    "anomaly_detection_threshold": 0.8,
    "alert_absence_hours": 12
}

# Security Dashboard Configuration
DASHBOARD_CONFIG = {
    "refresh_interval_seconds": 30,
    "max_timeline_days": 7,
    "alert_retention_days": 30,
    "query_timeout_seconds": 10
}

# Privacy & Security Configuration
PRIVACY_CONFIG = {
    "anonymize_names": False,  # Set to True for production
    "log_retention_days": 90,
    "audit_trail_enabled": True,
    "data_encryption_enabled": False  # Set to True for production
}

# Logging Configuration
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
    "rotation": "1 day",
    "retention": "1 week"
}

# API Configuration
API_CONFIG = {
    "host": "0.0.0.0",
    "port": 8000,
    "debug": True,
    "cors_origins": ["*"],
    "api_prefix": "/api/v1"
}

# Campus Locations
CAMPUS_LOCATIONS = {
    "LAB_101": {"name": "Computer Lab 101", "building": "Engineering", "floor": 1},
    "LAB_102": {"name": "Computer Lab 102", "building": "Engineering", "floor": 1},
    "LAB_305": {"name": "Research Lab 305", "building": "Engineering", "floor": 3},
    "LIB_ENT": {"name": "Library Entrance", "building": "Library", "floor": 0},
    "GYM": {"name": "Gymnasium", "building": "Sports Complex", "floor": 0},
    "AUDITORIUM": {"name": "Main Auditorium", "building": "Academic Block", "floor": 0},
    "CAF_01": {"name": "Cafeteria", "building": "Student Center", "floor": 0},
    "HOSTEL_GATE": {"name": "Hostel Gate", "building": "Residential", "floor": 0},
    "ADMIN_LOBBY": {"name": "Administration Lobby", "building": "Admin Block", "floor": 0},
    "SEM_01": {"name": "Seminar Room 1", "building": "Academic Block", "floor": 1},
    "ROOM_A2": {"name": "Classroom A2", "building": "Academic Block", "floor": 2}
}

# Entity Types
ENTITY_TYPES = {
    "student": {"priority": 1, "default_access_hours": (6, 22)},
    "staff": {"priority": 2, "default_access_hours": (8, 18)},
    "faculty": {"priority": 2, "default_access_hours": (8, 20)},
    "visitor": {"priority": 3, "default_access_hours": (9, 17)}
}

# Departments
DEPARTMENTS = [
    "Physics", "MECH", "ECE", "CIVIL", "BIO", "Chemistry", 
    "Admin", "Maths", "Computer Science", "Electrical"
]
