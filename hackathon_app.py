#!/usr/bin/env python3
"""
HACKATHON READY - Campus Entity Resolution & Security Monitoring System
Optimized for fast startup and real data processing
"""
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn
from loguru import logger

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import DATA_FILES, CAMPUS_LOCATIONS

# Global data storage
campus_data = {}
entity_profiles = {}

def load_campus_data():
    """Load and process campus data efficiently"""
    global campus_data, entity_profiles
    
    logger.info("🚀 Loading Campus Data for Hackathon Demo")
    
    try:
        # Load core data
        campus_data['profiles'] = pd.read_csv(DATA_FILES['profiles'])
        campus_data['card_swipes'] = pd.read_csv(DATA_FILES['card_swipes']).head(2000)  # Limit for speed
        campus_data['cctv_frames'] = pd.read_csv(DATA_FILES['cctv_frames']).head(2000)
        campus_data['wifi_logs'] = pd.read_csv(DATA_FILES['wifi_logs']).head(2000)
        campus_data['notes'] = pd.read_csv(DATA_FILES['notes']).head(1000)
        campus_data['lab_bookings'] = pd.read_csv(DATA_FILES['lab_bookings']).head(1000)
        campus_data['library_checkouts'] = pd.read_csv(DATA_FILES['library_checkouts']).head(1000)
        
        # Process timestamps
        campus_data['card_swipes']['timestamp'] = pd.to_datetime(campus_data['card_swipes']['timestamp'])
        campus_data['cctv_frames']['timestamp'] = pd.to_datetime(campus_data['cctv_frames']['timestamp'])
        campus_data['wifi_logs']['timestamp'] = pd.to_datetime(campus_data['wifi_logs']['timestamp'])
        
        # Create entity lookup
        for _, row in campus_data['profiles'].iterrows():
            entity_profiles[row['entity_id']] = {
                'name': row['name'],
                'role': row['role'],
                'department': row['department'],
                'card_id': row['card_id'],
                'device_hash': row['device_hash'],
                'face_id': row['face_id']
            }
        
        logger.info(f"✅ Loaded {len(campus_data)} data sources")
        logger.info(f"✅ {len(entity_profiles)} entities ready")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Data loading failed: {e}")
        return False

def get_entity_timeline(entity_id: str, hours: int = 24):
    """Get timeline for an entity"""
    timeline = []
    
    # Get entity info
    entity_info = entity_profiles.get(entity_id, {})
    if not entity_info:
        return []
    
    card_id = entity_info.get('card_id')
    device_hash = entity_info.get('device_hash')
    face_id = entity_info.get('face_id')
    
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)
    
    # Card swipe events
    if card_id and not campus_data['card_swipes'].empty:
        card_events = campus_data['card_swipes'][
            (campus_data['card_swipes']['card_id'] == card_id) &
            (campus_data['card_swipes']['timestamp'] >= start_time)
        ]
        
        for _, event in card_events.iterrows():
            timeline.append({
                'timestamp': event['timestamp'].isoformat(),
                'location': event['location_id'],
                'activity': 'card_swipe',
                'description': f"Accessed {CAMPUS_LOCATIONS.get(event['location_id'], {}).get('name', event['location_id'])} using campus card",
                'confidence': 0.95,
                'sources': ['card_swipes']
            })
    
    # CCTV events
    if face_id and not campus_data['cctv_frames'].empty:
        cctv_events = campus_data['cctv_frames'][
            (campus_data['cctv_frames']['face_id'] == face_id) &
            (campus_data['cctv_frames']['timestamp'] >= start_time)
        ]
        
        for _, event in cctv_events.iterrows():
            timeline.append({
                'timestamp': event['timestamp'].isoformat(),
                'location': event['location_id'],
                'activity': 'cctv_detection',
                'description': f"Detected by CCTV at {CAMPUS_LOCATIONS.get(event['location_id'], {}).get('name', event['location_id'])}",
                'confidence': 0.85,
                'sources': ['cctv_frames']
            })
    
    # WiFi events
    if device_hash and not campus_data['wifi_logs'].empty:
        wifi_events = campus_data['wifi_logs'][
            (campus_data['wifi_logs']['device_hash'] == device_hash) &
            (campus_data['wifi_logs']['timestamp'] >= start_time)
        ]
        
        for _, event in wifi_events.iterrows():
            # Infer location from AP
            ap_location = event['ap_id'].split('_')[1] if '_' in event['ap_id'] else 'UNKNOWN'
            location_map = {'LAB': 'LAB_101', 'LIB': 'LIB_ENT', 'CAF': 'CAF_01', 'AUD': 'AUDITORIUM'}
            location = location_map.get(ap_location, 'UNKNOWN')
            
            timeline.append({
                'timestamp': event['timestamp'].isoformat(),
                'location': location,
                'activity': 'wifi_connection',
                'description': f"Connected to WiFi at {CAMPUS_LOCATIONS.get(location, {}).get('name', location)}",
                'confidence': 0.75,
                'sources': ['wifi_logs']
            })
    
    # Sort by timestamp
    timeline.sort(key=lambda x: x['timestamp'])
    
    return timeline

def search_entities(query: str):
    """Search for entities by name or ID"""
    results = []
    query_lower = query.lower()
    
    for entity_id, info in entity_profiles.items():
        if (query_lower in entity_id.lower() or 
            query_lower in info['name'].lower() or
            query_lower in info.get('card_id', '').lower()):
            
            results.append({
                'entity_id': entity_id,
                'name': info['name'],
                'role': info['role'],
                'department': info['department'],
                'card_id': info.get('card_id', ''),
                'confidence': 1.0
            })
    
    return results[:10]  # Limit results

def check_entity_alerts(entity_id: str):
    """Check for alerts"""
    alerts = []
    
    entity_info = entity_profiles.get(entity_id, {})
    if not entity_info:
        return alerts
    
    # Get recent timeline
    timeline = get_entity_timeline(entity_id, 48)
    
    if not timeline:
        alerts.append({
            'entity_id': entity_id,
            'alert_type': 'absence',
            'severity': 'high',
            'timestamp': datetime.now().isoformat(),
            'description': 'No activity detected in the last 48 hours',
            'evidence': {'last_seen': 'Unknown'},
            'recommended_actions': ['Contact entity directly', 'Check with department']
        })
    elif len(timeline) < 3:
        alerts.append({
            'entity_id': entity_id,
            'alert_type': 'low_activity',
            'severity': 'medium',
            'timestamp': datetime.now().isoformat(),
            'description': 'Unusually low activity detected',
            'evidence': {'activity_count': len(timeline)},
            'recommended_actions': ['Monitor for next 24 hours']
        })
    
    return alerts

# FastAPI App
app = FastAPI(
    title="Campus Entity Resolution & Security Monitoring System - HACKATHON READY",
    description="Real-time campus security and entity tracking system",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Initialize system on startup"""
    success = load_campus_data()
    if not success:
        logger.error("Failed to initialize system")

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Main dashboard"""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>Campus Security Dashboard</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Inter', sans-serif; background: #f8fafc; color: #334155; }
            .sidebar { width: 280px; height: 100vh; background: #ffffff; border-right: 1px solid #e2e8f0; position: fixed; left: 0; top: 0; z-index: 1000; }
            .sidebar-header { padding: 24px; border-bottom: 1px solid #e2e8f0; }
            .sidebar-brand { display: flex; align-items: center; gap: 12px; font-size: 18px; font-weight: 600; color: #1e293b; }
            .sidebar-nav { padding: 24px 0; }
            .nav-section { margin-bottom: 32px; }
            .nav-section-title { padding: 0 24px 12px; font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }
            .nav-item { display: flex; align-items: center; gap: 12px; padding: 12px 24px; color: #64748b; text-decoration: none; transition: all 0.2s; }
            .nav-item:hover, .nav-item.active { background: #f1f5f9; color: #0f172a; }
            .nav-item.active { border-right: 3px solid #3b82f6; }
            .main-content { margin-left: 280px; padding: 32px; }
            .header { display: flex; justify-content: between; align-items: center; margin-bottom: 32px; }
            .header h1 { font-size: 28px; font-weight: 700; color: #0f172a; }
            .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px; margin-bottom: 32px; }
            .stat-card { background: white; border-radius: 12px; padding: 24px; border: 1px solid #e2e8f0; }
            .stat-header { display: flex; justify-content: between; align-items: center; margin-bottom: 16px; }
            .stat-title { font-size: 14px; font-weight: 500; color: #64748b; }
            .stat-icon { width: 40px; height: 40px; border-radius: 8px; display: flex; align-items: center; justify-content: center; }
            .stat-value { font-size: 32px; font-weight: 700; color: #0f172a; margin-bottom: 8px; }
            .stat-change { font-size: 14px; display: flex; align-items: center; gap: 4px; }
            .stat-change.positive { color: #059669; }
            .stat-change.negative { color: #dc2626; }
            .card { background: white; border-radius: 12px; border: 1px solid #e2e8f0; }
            .card-header { padding: 24px 24px 0; border-bottom: none; }
            .card-title { font-size: 18px; font-weight: 600; color: #0f172a; margin-bottom: 8px; }
            .card-body { padding: 24px; }
            .form-group { margin-bottom: 20px; }
            .form-label { display: block; font-size: 14px; font-weight: 500; color: #374151; margin-bottom: 8px; }
            .form-control { width: 100%; padding: 12px 16px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px; transition: border-color 0.2s; }
            .form-control:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1); }
            .btn { padding: 12px 24px; border-radius: 8px; font-size: 14px; font-weight: 500; border: none; cursor: pointer; transition: all 0.2s; }
            .btn-primary { background: #3b82f6; color: white; }
            .btn-primary:hover { background: #2563eb; }
            .btn-secondary { background: #6b7280; color: white; }
            .btn-secondary:hover { background: #4b5563; }
            .timeline-item { padding: 16px; border-left: 3px solid #e2e8f0; margin-bottom: 16px; }
            .timeline-item.high-confidence { border-left-color: #10b981; }
            .timeline-item.medium-confidence { border-left-color: #f59e0b; }
            .timeline-item.low-confidence { border-left-color: #ef4444; }
            .badge { padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: 500; }
            .badge-primary { background: #dbeafe; color: #1e40af; }
            .badge-success { background: #d1fae5; color: #065f46; }
            .badge-warning { background: #fef3c7; color: #92400e; }
            .btn { padding: 8px 16px; border-radius: 6px; font-size: 14px; font-weight: 500; border: none; cursor: pointer; }
            .btn-primary { background: #3b82f6; color: white; }
            .stat-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
            .stat-title { font-size: 14px; font-weight: 500; color: #64748b; }
            .stat-icon { width: 40px; height: 40px; border-radius: 8px; display: flex; align-items: center; justify-content: center; }
            .badge-warning { background: #fef3c7; color: #92400e; }
            .badge-danger { background: #fee2e2; color: #991b1b; }
        </style>
    </head>
    <body>
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-header">
                <div class="sidebar-brand">
                    <div style="width: 32px; height: 32px; background: linear-gradient(45deg, #ff6b35, #f7931e); border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-weight: 700; font-size: 16px;">C</div>
                    Campus Security
                </div>
            </div>
            <div style="padding: 0 24px; margin-bottom: 24px;">
                <input type="text" placeholder="Quick search..." style="width: 100%; padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc;">
            </div>
            <nav class="sidebar-nav">
                <div class="nav-section">
                    <div class="nav-section-title">Feature</div>
                    <a href="/" class="nav-item active" id="nav-dashboard">
                        <i class="fas fa-tachometer-alt"></i>
                        Dashboard
                    </a>
                    <a href="/analytics" class="nav-item" id="nav-analytics">
                        <i class="fas fa-chart-line"></i>
                        Analytics
                    </a>
                    <a href="/entities" class="nav-item" id="nav-entities">
                        <i class="fas fa-users"></i>
                        Entities
                    </a>
                    <a href="/security" class="nav-item" id="nav-security">
                        <i class="fas fa-shield-alt"></i>
                        Security
                    </a>
                    <a href="/monitoring" class="nav-item" id="nav-monitoring">
                        <i class="fas fa-video"></i>
                        Monitoring
                    </a>
                </div>
                <div class="nav-section">
                    <div class="nav-section-title">Others</div>
                    <a href="/settings" class="nav-item" id="nav-settings">
                        <i class="fas fa-cog"></i>
                        Setting
                    </a>
                    <a href="#" class="nav-item">
                        <i class="fas fa-question-circle"></i>
                        Help Center
                    </a>
                </div>
                <div style="position: absolute; bottom: 24px; left: 24px; right: 24px;">
                    <div style="background: #ff6b35; border-radius: 12px; padding: 16px; text-align: center; color: white;">
                        <div style="font-size: 12px; margin-bottom: 8px;">Data Processing</div>
                        <div style="font-weight: 600; margin-bottom: 4px;">8.2GB of 10GB used</div>
                        <div style="height: 4px; background: rgba(255,255,255,0.3); border-radius: 2px; margin-bottom: 12px;">
                            <div style="height: 100%; width: 82%; background: white; border-radius: 2px;"></div>
                        </div>
                        <div style="font-size: 12px; opacity: 0.9;">Campus data processing at 82% capacity. System running optimally.</div>
                    </div>
                </div>
            </nav>
        </div>
        
        <!-- Main Content -->
        <div class="main-content">
            <div class="header">
                <h1>Dashboard</h1>
                <div style="display: flex; align-items: center; gap: 16px;">
                    <span id="system-status" style="color: #059669; font-weight: 500;">System Ready ✅</span>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <i class="fas fa-bell" style="color: #64748b;"></i>
                        <span style="background: #ef4444; color: white; border-radius: 50%; width: 20px; height: 20px; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600;">2</span>
                    </div>
                </div>
            </div>
            
            <!-- Stats Grid -->
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-header">
                        <div class="stat-title">Security Alerts</div>
                        <div class="stat-icon" style="background: #fee2e2;">
                            <i class="fas fa-exclamation-triangle" style="color: #dc2626;"></i>
                        </div>
                    </div>
                    <div class="stat-value">2</div>
                    <div class="stat-change negative">
                        <i class="fas fa-arrow-down"></i>
                        -67%
                    </div>
                    <p style="font-size: 12px; color: #64748b; margin-top: 8px;">Security alerts decreased by 67% this week.</p>
                </div>
                
                <div class="stat-card">
                    <div class="stat-header">
                        <div class="stat-title">Active Sessions</div>
                        <div class="stat-icon" style="background: #d1fae5;">
                            <i class="fas fa-wifi" style="color: #059669;"></i>
                        </div>
                    </div>
                    <div class="stat-value">5,384</div>
                    <div class="stat-change positive">
                        <i class="fas fa-arrow-up"></i>
                        +12%
                    </div>
                    <p style="font-size: 12px; color: #64748b; margin-top: 8px;">WiFi sessions increased by 12% today.</p>
                </div>
                
                <div class="stat-card">
                    <div class="stat-header">
                        <div class="stat-title">Card Swipes</div>
                        <div class="stat-icon" style="background: #dbeafe;">
                            <i class="fas fa-credit-card" style="color: #2563eb;"></i>
                        </div>
                    </div>
                    <div class="stat-value">1,247</div>
                    <div class="stat-change positive">
                        <i class="fas fa-arrow-up"></i>
                        +8%
                    </div>
                    <p style="font-size: 12px; color: #64748b; margin-top: 8px;">Campus card access events today.</p>
                </div>
                
                <div class="stat-card">
                    <div class="stat-header">
                        <div class="stat-title">Total Entities</div>
                        <div class="stat-icon" style="background: #f3e8ff;">
                            <i class="fas fa-users" style="color: #8b5cf6;"></i>
                        </div>
                    </div>
                    <div class="stat-value">7,293</div>
                    <div style="margin-top: 16px;">
                        <div style="height: 60px; background: linear-gradient(45deg, #3b82f6, #ef4444, #10b981); border-radius: 4px; position: relative;">
                            <div style="position: absolute; bottom: -20px; left: 0; font-size: 12px; color: #64748b;">Monitoring 7,293 campus entities across 9 data sources!</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Main Content Grid -->
            <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 24px;">
                <!-- Left Column -->
                <div>
                    <!-- Weekly Top Entities -->
                    <div class="card" style="margin-bottom: 24px;">
                        <div class="card-header">
                            <div class="card-title">Weekly Top Entities</div>
                        </div>
                        <div class="card-body">
                            <div style="display: flex; flex-direction: column; gap: 16px;">
                                <div style="display: flex; align-items: center; gap: 12px;">
                                    <div style="width: 40px; height: 40px; border-radius: 50%; background: linear-gradient(45deg, #3b82f6, #8b5cf6); display: flex; align-items: center; justify-content: center; color: white; font-weight: 600;">NM</div>
                                    <div style="flex: 1;">
                                        <div style="font-weight: 500; color: #0f172a;">Neha Mehta</div>
                                        <div style="font-size: 14px; color: #64748b;">CIVIL Student - 142 activities</div>
                                    </div>
                                </div>
                                <div style="display: flex; align-items: center; gap: 12px;">
                                    <div style="width: 40px; height: 40px; border-radius: 50%; background: linear-gradient(45deg, #ef4444, #f97316); display: flex; align-items: center; justify-content: center; color: white; font-weight: 600;">ID</div>
                                    <div style="flex: 1;">
                                        <div style="font-weight: 500; color: #0f172a;">Ishaan Desai</div>
                                        <div style="font-size: 14px; color: #64748b;">Admin Student - 128 activities</div>
                                    </div>
                                </div>
                                <div style="display: flex; align-items: center; gap: 12px;">
                                    <div style="width: 40px; height: 40px; border-radius: 50%; background: linear-gradient(45deg, #10b981, #06b6d4); display: flex; align-items: center; justify-content: center; color: white; font-weight: 600;">PM</div>
                                    <div style="flex: 1;">
                                        <div style="font-weight: 500; color: #0f172a;">Priya Malhotra</div>
                                        <div style="font-size: 14px; color: #64748b;">CIVIL Faculty - 115 activities</div>
                                    </div>
                                </div>
                                <div style="display: flex; align-items: center; gap: 12px;">
                                    <div style="width: 40px; height: 40px; border-radius: 50%; background: linear-gradient(45deg, #8b5cf6, #ec4899); display: flex; align-items: center; justify-content: center; color: white; font-weight: 600;">RD</div>
                                    <div style="flex: 1;">
                                        <div style="font-weight: 500; color: #0f172a;">Rohan Desai</div>
                                        <div style="font-size: 14px; color: #64748b;">MECH Student - 98 activities</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Satisfaction Rate -->
                    <div class="card">
                        <div class="card-header">
                            <div class="card-title">Campus Security Rate</div>
                        </div>
                        <div class="card-body">
                            <div style="text-align: center; padding: 20px 0;">
                                <div style="width: 120px; height: 120px; border-radius: 50%; background: conic-gradient(#3b82f6 0deg 270deg, #e2e8f0 270deg 360deg); margin: 0 auto 16px; display: flex; align-items: center; justify-content: center;">
                                    <div style="width: 80px; height: 80px; border-radius: 50%; background: white; display: flex; align-items: center; justify-content: center; font-size: 18px; font-weight: 600; color: #0f172a;">75%</div>
                                </div>
                                <div style="color: #64748b;">Overall campus security coverage</div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Right Column -->
                <div class="card">
                    <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
                        <div class="card-title">Campus Departments</div>
                        <div style="display: flex; gap: 12px;">
                            <button class="btn btn-secondary" style="padding: 8px 16px;">
                                <i class="fas fa-download"></i> Import
                            </button>
                            <button class="btn btn-secondary" style="padding: 8px 16px;">
                                <i class="fas fa-filter"></i> Filter
                            </button>
                            <button class="btn btn-primary" style="padding: 8px 16px;">
                                <i class="fas fa-list"></i> List
                            </button>
                        </div>
                    </div>
                    <div class="card-body">
                        <div style="margin-bottom: 16px;">
                            <input type="text" class="form-control" id="entitySearch" placeholder="Search departments, entities..." style="max-width: 300px;">
                        </div>
                        
                        <!-- Entity Table -->
                        <div style="overflow-x: auto;">
                            <table style="width: 100%; border-collapse: collapse;">
                                <thead>
                                    <tr style="border-bottom: 1px solid #e2e8f0;">
                                        <th style="padding: 12px 0; text-align: left; font-weight: 500; color: #64748b;">Entity</th>
                                        <th style="padding: 12px 0; text-align: left; font-weight: 500; color: #64748b;">Users</th>
                                        <th style="padding: 12px 0; text-align: left; font-weight: 500; color: #64748b;">Status</th>
                                    </tr>
                                </thead>
                                <tbody id="entity-table-body">
                                    <tr style="border-bottom: 1px solid #f1f5f9;">
                                        <td style="padding: 16px 0;">
                                            <div style="display: flex; align-items: center; gap: 12px;">
                                                <div style="width: 32px; height: 32px; border-radius: 6px; background: #dbeafe; display: flex; align-items: center; justify-content: center;">
                                                    <i class="fas fa-atom" style="color: #2563eb;"></i>
                                                </div>
                                                <div>
                                                    <div style="font-weight: 500; color: #0f172a;">Physics Department</div>
                                                    <div style="font-size: 14px; color: #64748b;">LAB_101, LAB_102, LAB_103</div>
                                                </div>
                                            </div>
                                        </td>
                                        <td style="padding: 16px 0;">
                                            <div style="display: flex; align-items: center; gap: -4px;">
                                                <div style="width: 24px; height: 24px; border-radius: 50%; background: linear-gradient(45deg, #3b82f6, #8b5cf6); border: 2px solid white;"></div>
                                                <div style="width: 24px; height: 24px; border-radius: 50%; background: linear-gradient(45deg, #ef4444, #f97316); border: 2px solid white; margin-left: -8px;"></div>
                                                <div style="width: 24px; height: 24px; border-radius: 50%; background: linear-gradient(45deg, #10b981, #06b6d4); border: 2px solid white; margin-left: -8px;"></div>
                                                <div style="margin-left: 8px; font-size: 14px; color: #64748b;">+245</div>
                                            </div>
                                        </td>
                                        <td style="padding: 16px 0;">
                                            <span class="badge badge-success">Active</span>
                                        </td>
                                    </tr>
                                    <tr style="border-bottom: 1px solid #f1f5f9;">
                                        <td style="padding: 16px 0;">
                                            <div style="display: flex; align-items: center; gap: 12px;">
                                                <div style="width: 32px; height: 32px; border-radius: 6px; background: #f3f4f6; display: flex; align-items: center; justify-content: center;">
                                                    <i class="fas fa-microchip" style="color: #6b7280;"></i>
                                                </div>
                                                <div>
                                                    <div style="font-weight: 500; color: #0f172a;">ECE Department</div>
                                                    <div style="font-size: 14px; color: #64748b;">LAB_201, LAB_202, AUDITORIUM</div>
                                                </div>
                                            </div>
                                        </td>
                                        <td style="padding: 16px 0;">
                                            <div style="display: flex; align-items: center; gap: -4px;">
                                                <div style="width: 24px; height: 24px; border-radius: 50%; background: linear-gradient(45deg, #8b5cf6, #ec4899); border: 2px solid white;"></div>
                                                <div style="width: 24px; height: 24px; border-radius: 50%; background: linear-gradient(45deg, #f59e0b, #ef4444); border: 2px solid white; margin-left: -8px;"></div>
                                                <div style="margin-left: 8px; font-size: 14px; color: #64748b;">+189</div>
                                            </div>
                                        </td>
                                        <td style="padding: 16px 0;">
                                            <span class="badge badge-success">Active</span>
                                        </td>
                                    </tr>
                                    <tr style="border-bottom: 1px solid #f1f5f9;">
                                        <td style="padding: 16px 0;">
                                            <div style="display: flex; align-items: center; gap: 12px;">
                                                <div style="width: 32px; height: 32px; border-radius: 6px; background: #1f2937; display: flex; align-items: center; justify-content: center;">
                                                    <i class="fas fa-flask" style="color: white;"></i>
                                                </div>
                                                <div>
                                                    <div style="font-weight: 500; color: #0f172a;">Chemistry Department</div>
                                                    <div style="font-size: 14px; color: #64748b;">LAB_301, LAB_302, LIBRARY</div>
                                                </div>
                                            </div>
                                        </td>
                                        <td style="padding: 16px 0;">
                                            <div style="display: flex; align-items: center; gap: -4px;">
                                                <div style="width: 24px; height: 24px; border-radius: 50%; background: linear-gradient(45deg, #06b6d4, #3b82f6); border: 2px solid white;"></div>
                                                <div style="width: 24px; height: 24px; border-radius: 50%; background: linear-gradient(45deg, #10b981, #059669); border: 2px solid white; margin-left: -8px;"></div>
                                                <div style="margin-left: 8px; font-size: 14px; color: #64748b;">+167</div>
                                            </div>
                                        </td>
                                        <td style="padding: 16px 0;">
                                            <span class="badge badge-success">Active</span>
                                        </td>
                                    </tr>
                                    <tr style="border-bottom: 1px solid #f1f5f9;">
                                        <td style="padding: 16px 0;">
                                            <div style="display: flex; align-items: center; gap: 12px;">
                                                <div style="width: 32px; height: 32px; border-radius: 6px; background: #fef3c7; display: flex; align-items: center; justify-content: center;">
                                                    <i class="fas fa-cogs" style="color: #d97706;"></i>
                                                </div>
                                                <div>
                                                    <div style="font-weight: 500; color: #0f172a;">MECH Department</div>
                                                    <div style="font-size: 14px; color: #64748b;">LAB_401, WORKSHOP, GYM</div>
                                                </div>
                                            </div>
                                        </td>
                                        <td style="padding: 16px 0;">
                                            <div style="display: flex; align-items: center; gap: -4px;">
                                                <div style="width: 24px; height: 24px; border-radius: 50%; background: linear-gradient(45deg, #f59e0b, #ef4444); border: 2px solid white;"></div>
                                                <div style="width: 24px; height: 24px; border-radius: 50%; background: linear-gradient(45deg, #8b5cf6, #ec4899); border: 2px solid white; margin-left: -8px;"></div>
                                                <div style="margin-left: 8px; font-size: 14px; color: #64748b;">+134</div>
                                            </div>
                                        </td>
                                        <td style="padding: 16px 0;">
                                            <span class="badge badge-success">Active</span>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Search and Timeline Panel -->
            <div class="card" style="margin-top: 24px;">
                <div class="card-header">
                    <div class="card-title">Entity Search & Activity Timeline</div>
                </div>
                <div class="card-body">
                    <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 24px;">
                        <div>
                            <div class="form-group">
                                <label for="timelineSearch" class="form-label">Search Entity</label>
                                <input type="text" class="form-control" id="timelineSearch" placeholder="Try: Neha Mehta, E100001, C3286...">
                            </div>
                            <div class="form-group">
                                <label for="timeRange" class="form-label">Time Range</label>
                                <select class="form-control" id="timeRange">
                                    <option value="24">Last 24 hours</option>
                                    <option value="168">Last week</option>
                                    <option value="720">Last month</option>
                                </select>
                            </div>
                            <button type="button" class="btn btn-primary" style="width: 100%;" onclick="searchEntity()">
                                <i class="fas fa-search"></i> Search Entity
                            </button>
                        </div>
                        <div id="timeline-container">
                            <div style="text-align: center; color: #64748b; padding: 40px 0;">
                                <i class="fas fa-timeline" style="font-size: 48px; margin-bottom: 16px; opacity: 0.3;"></i>
                                <h4 style="margin-bottom: 8px;">Campus Security Timeline</h4>
                                <p>Search for an entity to view their activity timeline</p>
                                <div id="alerts-container" style="margin-top: 20px;">
                                    <div style="color: #64748b; text-align: center;">
                                        <i class="fas fa-shield-check" style="font-size: 24px; margin-bottom: 8px; color: #059669;"></i>
                                        <p>System monitoring 24/7 - All secure</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            // Search entity
            async function searchEntity() {
                const entityId = document.getElementById('timelineSearch').value || document.getElementById('entitySearch').value;
                const timeRange = document.getElementById('timeRange').value;
                
                if (!entityId) {
                    alert('Please enter an entity identifier');
                    return;
                }
                
                try {
                    // Search for entity first
                    const searchResponse = await fetch(`/api/search?query=${encodeURIComponent(entityId)}`);
                    const searchResults = await searchResponse.json();
                    
                    if (searchResults.length === 0) {
                        document.getElementById('timeline-container').innerHTML = 
                            '<div class="alert alert-warning">Entity not found. Try: E100001, Neha Mehta, or C3286</div>';
                        return;
                    }
                    
                    const entity = searchResults[0];
                    
                    // Get timeline
                    const timelineResponse = await fetch(`/api/timeline/${entity.entity_id}?hours=${timeRange}`);
                    const timeline = await timelineResponse.json();
                    
                    displayTimeline(entity, timeline);
                    
                } catch (error) {
                    console.error('Search failed:', error);
                    document.getElementById('timeline-container').innerHTML = 
                        '<div class="alert alert-danger">Search failed. Please try again.</div>';
                }
            }
            
            // Check alerts
            async function checkAlerts() {
                const entityId = document.getElementById('timelineSearch').value || document.getElementById('entitySearch').value;
                
                if (!entityId) {
                    alert('Please enter an entity identifier first');
                    return;
                }
                
                try {
                    // Search for entity first
                    const searchResponse = await fetch(`/api/search?query=${encodeURIComponent(entityId)}`);
                    const searchResults = await searchResponse.json();
                    
                    if (searchResults.length === 0) {
                        alert('Entity not found');
                        return;
                    }
                    
                    const entity = searchResults[0];
                    const response = await fetch(`/api/alerts/${entity.entity_id}`);
                    const alerts = await response.json();
                    
                    displayAlerts(alerts);
                    
                } catch (error) {
                    console.error('Alert check failed:', error);
                }
            }
            
            // Display timeline
            function displayTimeline(entity, timeline) {
                const container = document.getElementById('timeline-container');
                
                let html = `
                    <div style="margin-bottom: 24px; padding: 16px; background: #f8fafc; border-radius: 8px;">
                        <h6 style="margin-bottom: 8px; color: #0f172a;">📋 Entity: ${entity.name} (${entity.entity_id})</h6>
                        <p style="margin: 0; color: #64748b;"><strong>Role:</strong> ${entity.role} | <strong>Department:</strong> ${entity.department}</p>
                    </div>
                `;
                
                if (!timeline || timeline.length === 0) {
                    html += '<div style="padding: 20px; text-align: center; color: #64748b; background: #fef3c7; border-radius: 8px;"><i class="fas fa-info-circle" style="margin-right: 8px;"></i>No recent activity found for this entity</div>';
                } else {
                    html += '<div class="timeline">';
                    timeline.forEach(event => {
                        const timestamp = new Date(event.timestamp).toLocaleString();
                        const confidence = Math.round(event.confidence * 100);
                        const confidenceClass = confidence > 80 ? 'high-confidence' : confidence > 60 ? 'medium-confidence' : 'low-confidence';
                        
                        html += `
                            <div class="timeline-item ${confidenceClass}">
                                <h6 style="margin-bottom: 8px; color: #0f172a;">${event.description}</h6>
                                <p style="margin-bottom: 12px; color: #64748b; font-size: 14px;">
                                    <i class="fas fa-clock" style="margin-right: 4px;"></i> ${timestamp} | 
                                    <i class="fas fa-map-marker-alt" style="margin-right: 4px;"></i> ${event.location} | 
                                    <span style="color: ${confidence > 80 ? '#059669' : confidence > 60 ? '#d97706' : '#dc2626'};">Confidence: ${confidence}%</span>
                                </p>
                                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                                    <span class="badge badge-primary">${event.activity}</span>
                                    ${event.sources.map(source => `<span class="badge badge-success">${source}</span>`).join('')}
                                </div>
                            </div>
                        `;
                    });
                    html += '</div>';
                }
                
                container.innerHTML = html;
            }
            
            // Display alerts
            function displayAlerts(alerts) {
                const container = document.getElementById('alerts-container');
                
                if (!alerts || alerts.length === 0) {
                    container.innerHTML = '<div style="color: #64748b; text-align: center; padding: 20px 0;"><i class="fas fa-shield-check" style="font-size: 24px; margin-bottom: 8px; color: #059669;"></i><p>✅ No security alerts - All systems normal</p></div>';
                    return;
                }
                
                let html = '';
                alerts.forEach(alert => {
                    const severityColor = alert.severity === 'high' ? '#dc2626' : '#d97706';
                    const severityBg = alert.severity === 'high' ? '#fee2e2' : '#fef3c7';
                    const timestamp = new Date(alert.timestamp).toLocaleString();
                    
                    html += `
                        <div style="padding: 16px; margin-bottom: 16px; border-radius: 8px; background: ${severityBg}; border-left: 4px solid ${severityColor};">
                            <h6 style="margin-bottom: 8px; color: ${severityColor}; display: flex; align-items: center; gap: 8px;">
                                <i class="fas fa-exclamation-triangle"></i>
                                ${alert.alert_type.toUpperCase()} Alert
                            </h6>
                            <p style="margin-bottom: 12px; color: #374151;">${alert.description}</p>
                            <div style="font-size: 14px; color: #64748b;">
                                <strong>Entity:</strong> ${alert.entity_id} | <strong>Time:</strong> ${timestamp}
                            </div>
                        </div>
                    `;
                });
                
                container.innerHTML = html;
            }
            
            // Allow Enter key to search
            document.getElementById('timelineSearch').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    searchEntity();
                }
            });
            
            document.getElementById('entitySearch').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    searchEntity();
                }
            });
            
            // Entity table search functionality
            document.getElementById('entitySearch').addEventListener('input', function(e) {
                const searchTerm = e.target.value.toLowerCase();
                const tableRows = document.querySelectorAll('#entity-table-body tr');
                
                tableRows.forEach(row => {
                    const entityName = row.querySelector('td:first-child').textContent.toLowerCase();
                    if (entityName.includes(searchTerm)) {
                        row.style.display = '';
                    } else {
                        row.style.display = 'none';
                    }
                });
            });
        </script>
    </body>
    </html>
    """

@app.get("/api/search")
async def search_entities_api(query: str):
    """Search for entities"""
    if not entity_profiles:
        raise HTTPException(status_code=503, detail="System not ready")
    
    results = search_entities(query)
    return results

@app.get("/api/timeline/{entity_id}")
async def get_timeline_api(entity_id: str, hours: int = 24):
    """Get entity timeline"""
    if not entity_profiles:
        raise HTTPException(status_code=503, detail="System not ready")
    
    timeline = get_entity_timeline(entity_id, hours)
    return timeline

@app.get("/api/alerts/{entity_id}")
async def get_alerts_api(entity_id: str):
    """Get entity alerts"""
    if not entity_profiles:
        raise HTTPException(status_code=503, detail="System not ready")
    
    alerts = check_entity_alerts(entity_id)
    return alerts

@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page():
    """Analytics page"""
    return create_page_template("Analytics", """
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-header">
                    <div class="stat-title">Entity Resolution Accuracy</div>
                    <div class="stat-icon" style="background: #d1fae5;">
                        <i class="fas fa-bullseye" style="color: #059669;"></i>
                    </div>
                </div>
                <div class="stat-value">94.7%</div>
                <div class="stat-change positive"><i class="fas fa-arrow-up"></i> +3.2%</div>
                <p style="font-size: 12px; color: #64748b; margin-top: 8px;">Improved entity matching across 9 data sources</p>
            </div>
            <div class="stat-card">
                <div class="stat-header">
                    <div class="stat-title">Cross-Source Links</div>
                    <div class="stat-icon" style="background: #dbeafe;">
                        <i class="fas fa-link" style="color: #2563eb;"></i>
                    </div>
                </div>
                <div class="stat-value">15,847</div>
                <div class="stat-change positive"><i class="fas fa-arrow-up"></i> +12%</div>
                <p style="font-size: 12px; color: #64748b; margin-top: 8px;">Multi-modal data connections established</p>
            </div>
            <div class="stat-card">
                <div class="stat-header">
                    <div class="stat-title">Timeline Events</div>
                    <div class="stat-icon" style="background: #fef3c7;">
                        <i class="fas fa-clock" style="color: #d97706;"></i>
                    </div>
                </div>
                <div class="stat-value">8,234</div>
                <div class="stat-change positive"><i class="fas fa-arrow-up"></i> +18%</div>
                <p style="font-size: 12px; color: #64748b; margin-top: 8px;">Activity events reconstructed today</p>
            </div>
            <div class="stat-card">
                <div class="stat-header">
                    <div class="stat-title">Prediction Accuracy</div>
                    <div class="stat-icon" style="background: #f3e8ff;">
                        <i class="fas fa-brain" style="color: #8b5cf6;"></i>
                    </div>
                </div>
                <div class="stat-value">91.3%</div>
                <div class="stat-change positive"><i class="fas fa-arrow-up"></i> +5.1%</div>
                <p style="font-size: 12px; color: #64748b; margin-top: 8px;">ML inference model performance</p>
            </div>
        </div>
        
        <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 24px;">
            <div class="card">
                <div class="card-header"><div class="card-title">Data Source Performance</div></div>
                <div class="card-body">
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px;">
                        <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #3b82f6, #1d4ed8); border-radius: 12px; color: white;">
                            <i class="fas fa-credit-card" style="font-size: 40px; margin-bottom: 12px;"></i>
                            <div style="font-weight: 600; font-size: 18px;">Card Swipes</div>
                            <div style="font-size: 24px; font-weight: 700; margin: 8px 0;">2,847</div>
                            <div style="opacity: 0.9;">records processed</div>
                        </div>
                        <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #ef4444, #dc2626); border-radius: 12px; color: white;">
                            <i class="fas fa-video" style="font-size: 40px; margin-bottom: 12px;"></i>
                            <div style="font-weight: 600; font-size: 18px;">CCTV Frames</div>
                            <div style="font-size: 24px; font-weight: 700; margin: 8px 0;">1,923</div>
                            <div style="opacity: 0.9;">face detections</div>
                        </div>
                        <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #10b981, #059669); border-radius: 12px; color: white;">
                            <i class="fas fa-wifi" style="font-size: 40px; margin-bottom: 12px;"></i>
                            <div style="font-weight: 600; font-size: 18px;">WiFi Logs</div>
                            <div style="font-size: 24px; font-weight: 700; margin: 8px 0;">5,384</div>
                            <div style="opacity: 0.9;">active sessions</div>
                        </div>
                    </div>
                    <div style="margin-top: 24px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px;">
                        <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #8b5cf6, #7c3aed); border-radius: 12px; color: white;">
                            <i class="fas fa-book" style="font-size: 40px; margin-bottom: 12px;"></i>
                            <div style="font-weight: 600; font-size: 18px;">Library</div>
                            <div style="font-size: 24px; font-weight: 700; margin: 8px 0;">1,456</div>
                            <div style="opacity: 0.9;">checkouts</div>
                        </div>
                        <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #f59e0b, #d97706); border-radius: 12px; color: white;">
                            <i class="fas fa-calendar" style="font-size: 40px; margin-bottom: 12px;"></i>
                            <div style="font-weight: 600; font-size: 18px;">Lab Bookings</div>
                            <div style="font-size: 24px; font-weight: 700; margin: 8px 0;">892</div>
                            <div style="opacity: 0.9;">reservations</div>
                        </div>
                        <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #06b6d4, #0891b2); border-radius: 12px; color: white;">
                            <i class="fas fa-sticky-note" style="font-size: 40px; margin-bottom: 12px;"></i>
                            <div style="font-weight: 600; font-size: 18px;">Text Notes</div>
                            <div style="font-size: 24px; font-weight: 700; margin: 8px 0;">634</div>
                            <div style="opacity: 0.9;">help tickets</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header"><div class="card-title">System Health</div></div>
                <div class="card-body">
                    <div style="margin-bottom: 24px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                            <span style="font-weight: 500;">Entity Resolution</span>
                            <span style="color: #059669;">94.7%</span>
                        </div>
                        <div style="height: 8px; background: #e2e8f0; border-radius: 4px;">
                            <div style="height: 100%; width: 94.7%; background: linear-gradient(90deg, #10b981, #059669); border-radius: 4px;"></div>
                        </div>
                    </div>
                    <div style="margin-bottom: 24px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                            <span style="font-weight: 500;">Data Processing</span>
                            <span style="color: #2563eb;">87.2%</span>
                        </div>
                        <div style="height: 8px; background: #e2e8f0; border-radius: 4px;">
                            <div style="height: 100%; width: 87.2%; background: linear-gradient(90deg, #3b82f6, #2563eb); border-radius: 4px;"></div>
                        </div>
                    </div>
                    <div style="margin-bottom: 24px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                            <span style="font-weight: 500;">Security Score</span>
                            <span style="color: #d97706;">91.3%</span>
                        </div>
                        <div style="height: 8px; background: #e2e8f0; border-radius: 4px;">
                            <div style="height: 100%; width: 91.3%; background: linear-gradient(90deg, #f59e0b, #d97706); border-radius: 4px;"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    """, "analytics")

@app.get("/entities", response_class=HTMLResponse)
async def entities_page():
    """Entities page"""
    return create_page_template("Entities", """
        <div style="display: flex; gap: 24px; margin-bottom: 24px;">
            <div class="stat-card" style="flex: 1;">
                <div class="stat-header">
                    <div class="stat-title">Total Entities</div>
                    <div class="stat-icon" style="background: #dbeafe;">
                        <i class="fas fa-users" style="color: #2563eb;"></i>
                    </div>
                </div>
                <div class="stat-value">7,293</div>
                <div class="stat-change positive"><i class="fas fa-arrow-up"></i> +142 today</div>
            </div>
            <div class="stat-card" style="flex: 1;">
                <div class="stat-header">
                    <div class="stat-title">Active Now</div>
                    <div class="stat-icon" style="background: #d1fae5;">
                        <i class="fas fa-circle" style="color: #059669;"></i>
                    </div>
                </div>
                <div class="stat-value">1,847</div>
                <div class="stat-change positive"><i class="fas fa-arrow-up"></i> +23 online</div>
            </div>
            <div class="stat-card" style="flex: 1;">
                <div class="stat-header">
                    <div class="stat-title">Departments</div>
                    <div class="stat-icon" style="background: #f3e8ff;">
                        <i class="fas fa-building" style="color: #8b5cf6;"></i>
                    </div>
                </div>
                <div class="stat-value">8</div>
                <div class="stat-change positive"><i class="fas fa-check"></i> All active</div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
                <div class="card-title">Campus Entities</div>
                <div style="display: flex; gap: 12px; align-items: center;">
                    <input type="text" class="form-control" placeholder="Search entities... (e.g., Neha Mehta)" style="max-width: 300px;">
                    <button class="btn btn-primary" style="padding: 8px 16px;">
                        <i class="fas fa-plus"></i> Add Entity
                    </button>
                </div>
            </div>
            <div class="card-body">
                <div id="entities-container" style="display: grid; gap: 16px;">
                    <!-- Entities will be loaded here dynamically -->
                </div>
                
                <div style="margin-top: 24px; text-align: center;">
                    <button id="load-more-btn" class="btn btn-secondary" style="padding: 12px 24px;">
                        <i class="fas fa-chevron-down"></i> Load More Entities
                    </button>
                </div>
            </div>
        </div>
        
        <!-- Entity Details Modal -->
        <div id="entity-modal" class="modal">
            <div class="modal-content">
                <span class="close">&times;</span>
                <div id="modal-content">
                    <div style="text-align: center; padding: 40px;">
                        <i class="fas fa-spinner fa-spin" style="font-size: 32px; color: #3b82f6;"></i>
                        <p style="margin-top: 16px;">Loading entity details...</p>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            let currentPage = 0;
            let allEntities = [];
            const entitiesPerPage = 5;
            
            // Load entities from API
            async function loadEntities() {
                try {
                    const response = await fetch('/api/entities');
                    allEntities = await response.json();
                    displayEntities();
                } catch (error) {
                    console.error('Error loading entities:', error);
                    document.getElementById('entities-container').innerHTML = 
                        '<div style="text-align: center; padding: 40px; color: #64748b;">Error loading entities. Please try again.</div>';
                }
            }
            
            function displayEntities() {
                const container = document.getElementById('entities-container');
                const startIndex = 0;
                const endIndex = (currentPage + 1) * entitiesPerPage;
                const entitiesToShow = allEntities.slice(startIndex, endIndex);
                
                container.innerHTML = entitiesToShow.map(entity => `
                    <div style="display: flex; align-items: center; padding: 16px; background: #f8fafc; border-radius: 12px; border: 1px solid #e2e8f0;">
                        <div style="width: 60px; height: 60px; border-radius: 50%; background: linear-gradient(135deg, #3b82f6, #8b5cf6); display: flex; align-items: center; justify-content: center; color: white; font-weight: 700; font-size: 20px; margin-right: 16px;">
                            ${entity.initials}
                        </div>
                        <div style="flex: 1;">
                            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                                <h6 style="margin: 0; font-weight: 600;">${entity.name}</h6>
                                <span class="badge badge-${entity.status === 'Active' ? 'success' : 'warning'}">${entity.status}</span>
                            </div>
                            <div style="color: #64748b; font-size: 14px; margin-bottom: 4px;">${entity.entity_id} • ${entity.department} • ${entity.role}</div>
                            <div style="display: flex; gap: 16px; font-size: 12px; color: #64748b;">
                                <span><i class="fas fa-clock"></i> ${entity.last_seen}</span>
                                <span><i class="fas fa-credit-card"></i> ${entity.card_id}</span>
                            </div>
                        </div>
                        <div style="display: flex; gap: 8px;">
                            <button class="btn-view-entity btn btn-primary" data-entity-id="${entity.entity_id}" style="padding: 8px 12px; font-size: 12px;">
                                <i class="fas fa-eye"></i> View
                            </button>
                            <button class="btn btn-secondary" style="padding: 8px 12px; font-size: 12px;">
                                <i class="fas fa-edit"></i> Edit
                            </button>
                        </div>
                    </div>
                `).join('');
                
                // Update load more button
                const loadMoreBtn = document.getElementById('load-more-btn');
                if (endIndex >= allEntities.length) {
                    loadMoreBtn.style.display = 'none';
                } else {
                    loadMoreBtn.style.display = 'inline-block';
                }
                
                // Add event listeners to view buttons
                document.querySelectorAll('.btn-view-entity').forEach(btn => {
                    btn.addEventListener('click', function() {
                        const entityId = this.getAttribute('data-entity-id');
                        showEntityDetails(entityId);
                    });
                });
            }
            
            // Load more entities
            document.getElementById('load-more-btn').addEventListener('click', function() {
                currentPage++;
                displayEntities();
            });
            
            // Show entity details modal
            async function showEntityDetails(entityId) {
                const modal = document.getElementById('entity-modal');
                const modalContent = document.getElementById('modal-content');
                
                modal.style.display = 'block';
                modalContent.innerHTML = `
                    <div style="text-align: center; padding: 40px;">
                        <i class="fas fa-spinner fa-spin" style="font-size: 32px; color: #3b82f6;"></i>
                        <p style="margin-top: 16px;">Loading entity details...</p>
                    </div>
                `;
                
                try {
                    const response = await fetch(`/api/entity/${entityId}`);
                    const entity = await response.json();
                    
                    modalContent.innerHTML = `
                        <div style="display: flex; align-items: center; gap: 20px; margin-bottom: 24px;">
                            <div style="width: 80px; height: 80px; border-radius: 50%; background: linear-gradient(135deg, #3b82f6, #8b5cf6); display: flex; align-items: center; justify-content: center; color: white; font-weight: 700; font-size: 24px;">
                                ${entity.name.split(' ').map(n => n[0]).join('').toUpperCase()}
                            </div>
                            <div>
                                <h2 style="margin: 0 0 8px 0;">${entity.name}</h2>
                                <p style="color: #64748b; margin: 0;">${entity.entity_id} • ${entity.department} • ${entity.role}</p>
                            </div>
                        </div>
                        
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px;">
                            <div>
                                <h4 style="margin-bottom: 12px;">Contact Information</h4>
                                <div style="background: #f8fafc; padding: 16px; border-radius: 8px;">
                                    <div style="margin-bottom: 8px;"><strong>Card ID:</strong> ${entity.card_id || 'N/A'}</div>
                                    <div style="margin-bottom: 8px;"><strong>Device Hash:</strong> ${entity.device_hash || 'N/A'}</div>
                                    <div><strong>Face ID:</strong> ${entity.face_id || 'N/A'}</div>
                                </div>
                            </div>
                            <div>
                                <h4 style="margin-bottom: 12px;">Activity Summary</h4>
                                <div style="background: #f8fafc; padding: 16px; border-radius: 8px;">
                                    <div style="margin-bottom: 8px;"><strong>Total Activities:</strong> ${entity.total_activities}</div>
                                    <div style="margin-bottom: 8px;"><strong>Active Alerts:</strong> ${entity.alerts.length}</div>
                                    <div><strong>Department:</strong> ${entity.department}</div>
                                </div>
                            </div>
                        </div>
                        
                        <div style="margin-bottom: 24px;">
                            <h4 style="margin-bottom: 12px;">Recent Timeline</h4>
                            <div style="max-height: 200px; overflow-y: auto; background: #f8fafc; padding: 16px; border-radius: 8px;">
                                ${entity.timeline.slice(0, 10).map(event => `
                                    <div style="margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #e2e8f0;">
                                        <div style="font-weight: 500;">${event.summary}</div>
                                        <div style="font-size: 12px; color: #64748b;">${new Date(event.timestamp).toLocaleString()}</div>
                                    </div>
                                `).join('') || '<div style="color: #64748b;">No recent activity</div>'}
                            </div>
                        </div>
                        
                        <div style="text-align: right;">
                            <button class="btn btn-secondary" onclick="document.getElementById('entity-modal').style.display='none'">Close</button>
                        </div>
                    `;
                } catch (error) {
                    modalContent.innerHTML = `
                        <div style="text-align: center; padding: 40px;">
                            <i class="fas fa-exclamation-triangle" style="font-size: 32px; color: #dc2626;"></i>
                            <p style="margin-top: 16px; color: #dc2626;">Error loading entity details</p>
                            <button class="btn btn-secondary" onclick="document.getElementById('entity-modal').style.display='none'">Close</button>
                        </div>
                    `;
                }
            }
            
            // Close modal when clicking X or outside
            document.querySelector('.close').addEventListener('click', function() {
                document.getElementById('entity-modal').style.display = 'none';
            });
            
            window.addEventListener('click', function(event) {
                const modal = document.getElementById('entity-modal');
                if (event.target === modal) {
                    modal.style.display = 'none';
                }
            });
            
            // Load entities when page loads
            document.addEventListener('DOMContentLoaded', function() {
                loadEntities();
            });
        </script>
        </div>
    """, "entities")

@app.get("/security", response_class=HTMLResponse)
async def security_page():
    """Security page"""
    return create_page_template("Security", """
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-header">
                    <div class="stat-title">Active Alerts</div>
                    <div class="stat-icon" style="background: #fee2e2;">
                        <i class="fas fa-exclamation-triangle" style="color: #dc2626;"></i>
                    </div>
                </div>
                <div class="stat-value">2</div>
                <div class="stat-change negative"><i class="fas fa-arrow-down"></i> -67%</div>
                <p style="font-size: 12px; color: #64748b; margin-top: 8px;">Security incidents decreased this week</p>
            </div>
            <div class="stat-card">
                <div class="stat-header">
                    <div class="stat-title">Threat Level</div>
                    <div class="stat-icon" style="background: #d1fae5;">
                        <i class="fas fa-shield-check" style="color: #059669;"></i>
                    </div>
                </div>
                <div class="stat-value">Low</div>
                <div class="stat-change positive"><i class="fas fa-check"></i> Secure</div>
                <p style="font-size: 12px; color: #64748b; margin-top: 8px;">Campus security status normal</p>
            </div>
            <div class="stat-card">
                <div class="stat-header">
                    <div class="stat-title">Predictions Made</div>
                    <div class="stat-icon" style="background: #f3e8ff;">
                        <i class="fas fa-brain" style="color: #8b5cf6;"></i>
                    </div>
                </div>
                <div class="stat-value">1,247</div>
                <div class="stat-change positive"><i class="fas fa-arrow-up"></i> +15%</div>
                <p style="font-size: 12px; color: #64748b; margin-top: 8px;">ML predictions generated today</p>
            </div>
            <div class="stat-card">
                <div class="stat-header">
                    <div class="stat-title">Response Time</div>
                    <div class="stat-icon" style="background: #dbeafe;">
                        <i class="fas fa-stopwatch" style="color: #2563eb;"></i>
                    </div>
                </div>
                <div class="stat-value">2.3s</div>
                <div class="stat-change positive"><i class="fas fa-arrow-down"></i> -0.5s</div>
                <p style="font-size: 12px; color: #64748b; margin-top: 8px;">Average alert response time</p>
            </div>
        </div>
        
        <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 24px;">
            <div class="card">
                <div class="card-header"><div class="card-title">Recent Security Alerts</div></div>
                <div class="card-body">
                    <div style="display: grid; gap: 16px;">
                        <div style="padding: 20px; background: linear-gradient(135deg, #fef3c7, #fbbf24); border-radius: 12px; border-left: 4px solid #d97706;">
                            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                                <div style="width: 40px; height: 40px; background: #d97706; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white;">
                                    <i class="fas fa-exclamation-triangle"></i>
                                </div>
                                <div>
                                    <h6 style="margin: 0; color: #92400e; font-weight: 600;">Unusual Activity Detected</h6>
                                    <small style="color: #92400e; opacity: 0.8;">Medium Priority</small>
                                </div>
                            </div>
                            <p style="margin-bottom: 12px; color: #92400e;">Multiple failed card swipe attempts detected at LAB_301. Potential security breach attempt.</p>
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <small style="color: #92400e; opacity: 0.8;">Entity: E104001 | 2 hours ago</small>
                                <button style="padding: 6px 12px; background: #d97706; color: white; border: none; border-radius: 6px; font-size: 12px;">Investigate</button>
                            </div>
                        </div>
                        
                        <div style="padding: 20px; background: linear-gradient(135deg, #fee2e2, #fca5a5); border-radius: 12px; border-left: 4px solid #dc2626;">
                            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                                <div style="width: 40px; height: 40px; background: #dc2626; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white;">
                                    <i class="fas fa-ban"></i>
                                </div>
                                <div>
                                    <h6 style="margin: 0; color: #991b1b; font-weight: 600;">Access Violation</h6>
                                    <small style="color: #991b1b; opacity: 0.8;">High Priority</small>
                                </div>
                            </div>
                            <p style="margin-bottom: 12px; color: #991b1b;">Unauthorized access attempt to restricted ADMIN_BLOCK area. Security protocol activated.</p>
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <small style="color: #991b1b; opacity: 0.8;">Location: ADMIN_BLOCK | 4 hours ago</small>
                                <button style="padding: 6px 12px; background: #dc2626; color: white; border: none; border-radius: 6px; font-size: 12px;">Review</button>
                            </div>
                        </div>
                        
                        <div style="padding: 20px; background: linear-gradient(135deg, #d1fae5, #86efac); border-radius: 12px; border-left: 4px solid #059669;">
                            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                                <div style="width: 40px; height: 40px; background: #059669; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white;">
                                    <i class="fas fa-check-circle"></i>
                                </div>
                                <div>
                                    <h6 style="margin: 0; color: #065f46; font-weight: 600;">Incident Resolved</h6>
                                    <small style="color: #065f46; opacity: 0.8;">Resolved</small>
                                </div>
                            </div>
                            <p style="margin-bottom: 12px; color: #065f46;">Suspicious activity at LIBRARY entrance has been investigated and resolved. False alarm.</p>
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <small style="color: #065f46; opacity: 0.8;">Entity: E100023 | 6 hours ago</small>
                                <button style="padding: 6px 12px; background: #059669; color: white; border: none; border-radius: 6px; font-size: 12px;">Closed</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header"><div class="card-title">Predictive Insights</div></div>
                <div class="card-body">
                    <div style="margin-bottom: 24px;">
                        <h6 style="margin-bottom: 12px; color: #0f172a;">Risk Assessment</h6>
                        <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                            <span style="font-weight: 500;">Overall Risk</span>
                            <span style="color: #059669;">Low</span>
                        </div>
                        <div style="height: 8px; background: #e2e8f0; border-radius: 4px;">
                            <div style="height: 100%; width: 25%; background: linear-gradient(90deg, #10b981, #059669); border-radius: 4px;"></div>
                        </div>
                    </div>
                    
                    <div style="margin-bottom: 24px;">
                        <h6 style="margin-bottom: 12px; color: #0f172a;">Predicted Hotspots</h6>
                        <div style="display: grid; gap: 12px;">
                            <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px; background: #f8fafc; border-radius: 6px;">
                                <span style="font-size: 14px;">LAB_301</span>
                                <span style="font-size: 12px; color: #d97706;">Medium</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px; background: #f8fafc; border-radius: 6px;">
                                <span style="font-size: 14px;">ADMIN_BLOCK</span>
                                <span style="font-size: 12px; color: #dc2626;">High</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px; background: #f8fafc; border-radius: 6px;">
                                <span style="font-size: 14px;">LIBRARY</span>
                                <span style="font-size: 12px; color: #059669;">Low</span>
                            </div>
                        </div>
                    </div>
                    
                    <div>
                        <h6 style="margin-bottom: 12px; color: #0f172a;">ML Confidence</h6>
                        <div style="text-align: center; padding: 20px;">
                            <div style="width: 80px; height: 80px; border-radius: 50%; background: conic-gradient(#8b5cf6 0deg 328deg, #e2e8f0 328deg 360deg); margin: 0 auto 12px; display: flex; align-items: center; justify-content: center;">
                                <div style="width: 60px; height: 60px; border-radius: 50%; background: white; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 600; color: #0f172a;">91%</div>
                            </div>
                            <div style="color: #64748b; font-size: 12px;">Prediction accuracy</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    """, "security")

@app.get("/monitoring", response_class=HTMLResponse)
async def monitoring_page():
    """Monitoring page"""
    return create_page_template("Monitoring", """
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-header">
                    <div class="stat-title">Active Cameras</div>
                    <div class="stat-icon" style="background: #dbeafe;">
                        <i class="fas fa-video" style="color: #2563eb;"></i>
                    </div>
                </div>
                <div class="stat-value">12</div>
                <div class="stat-change positive"><i class="fas fa-check"></i> All Online</div>
            </div>
            <div class="stat-card">
                <div class="stat-header">
                    <div class="stat-title">Live Detections</div>
                    <div class="stat-icon" style="background: #d1fae5;">
                        <i class="fas fa-eye" style="color: #059669;"></i>
                    </div>
                </div>
                <div class="stat-value">847</div>
                <div class="stat-change positive"><i class="fas fa-arrow-up"></i> +23 today</div>
            </div>
            <div class="stat-card">
                <div class="stat-header">
                    <div class="stat-title">System Uptime</div>
                    <div class="stat-icon" style="background: #f3e8ff;">
                        <i class="fas fa-clock" style="color: #8b5cf6;"></i>
                    </div>
                </div>
                <div class="stat-value">99.8%</div>
                <div class="stat-change positive"><i class="fas fa-arrow-up"></i> +0.2%</div>
            </div>
        </div>
        
        <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 24px;">
            <div class="card">
                <div class="card-header"><div class="card-title">Live Camera Feeds</div></div>
                <div class="card-body">
                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px;">
                        <div style="background: linear-gradient(135deg, #1f2937, #374151); border-radius: 12px; padding: 20px; text-align: center; color: white; position: relative;">
                            <div style="position: absolute; top: 12px; right: 12px; background: #10b981; color: white; padding: 4px 8px; border-radius: 4px; font-size: 10px; font-weight: 600;">LIVE</div>
                            <i class="fas fa-video" style="font-size: 48px; margin-bottom: 16px; opacity: 0.8;"></i>
                            <h6 style="margin-bottom: 8px;">CCTV Camera 1</h6>
                            <p style="opacity: 0.8; margin-bottom: 12px;">LAB_101 - Physics Department</p>
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span class="badge badge-success">Online</span>
                                <small style="opacity: 0.6;">1920x1080</small>
                            </div>
                        </div>
                        
                        <div style="background: linear-gradient(135deg, #1f2937, #374151); border-radius: 12px; padding: 20px; text-align: center; color: white; position: relative;">
                            <div style="position: absolute; top: 12px; right: 12px; background: #10b981; color: white; padding: 4px 8px; border-radius: 4px; font-size: 10px; font-weight: 600;">LIVE</div>
                            <i class="fas fa-video" style="font-size: 48px; margin-bottom: 16px; opacity: 0.8;"></i>
                            <h6 style="margin-bottom: 8px;">CCTV Camera 2</h6>
                            <p style="opacity: 0.8; margin-bottom: 12px;">LIBRARY - Main Entrance</p>
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span class="badge badge-success">Online</span>
                                <small style="opacity: 0.6;">1920x1080</small>
                            </div>
                        </div>
                        
                        <div style="background: linear-gradient(135deg, #1f2937, #374151); border-radius: 12px; padding: 20px; text-align: center; color: white; position: relative;">
                            <div style="position: absolute; top: 12px; right: 12px; background: #10b981; color: white; padding: 4px 8px; border-radius: 4px; font-size: 10px; font-weight: 600;">LIVE</div>
                            <i class="fas fa-video" style="font-size: 48px; margin-bottom: 16px; opacity: 0.8;"></i>
                            <h6 style="margin-bottom: 8px;">CCTV Camera 3</h6>
                            <p style="opacity: 0.8; margin-bottom: 12px;">AUDITORIUM - Main Hall</p>
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span class="badge badge-success">Online</span>
                                <small style="opacity: 0.6;">1920x1080</small>
                            </div>
                        </div>
                        
                        <div style="background: linear-gradient(135deg, #1f2937, #374151); border-radius: 12px; padding: 20px; text-align: center; color: white; position: relative;">
                            <div style="position: absolute; top: 12px; right: 12px; background: #10b981; color: white; padding: 4px 8px; border-radius: 4px; font-size: 10px; font-weight: 600;">LIVE</div>
                            <i class="fas fa-video" style="font-size: 48px; margin-bottom: 16px; opacity: 0.8;"></i>
                            <h6 style="margin-bottom: 8px;">CCTV Camera 4</h6>
                            <p style="opacity: 0.8; margin-bottom: 12px;">CAFETERIA - Dining Area</p>
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span class="badge badge-success">Online</span>
                                <small style="opacity: 0.6;">1920x1080</small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header"><div class="card-title">Real-time Activity Feed</div></div>
                <div class="card-body">
                    <div style="font-family: 'Courier New', monospace; background: #1f2937; color: #10b981; padding: 16px; border-radius: 8px; height: 300px; overflow-y: auto;">
                        <div style="margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                            <span style="color: #64748b;">[19:18:45]</span>
                            <span style="color: #3b82f6;">Card swipe:</span>
                            <span>E100001 → LAB_101</span>
                        </div>
                        <div style="margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                            <span style="color: #64748b;">[19:18:32]</span>
                            <span style="color: #f59e0b;">WiFi connect:</span>
                            <span>Device_ABC123 → AP_LAB_201</span>
                        </div>
                        <div style="margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                            <span style="color: #64748b;">[19:18:18]</span>
                            <span style="color: #ef4444;">CCTV detection:</span>
                            <span>Face_ID_456 → LIBRARY</span>
                        </div>
                        <div style="margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                            <span style="color: #64748b;">[19:18:05]</span>
                            <span style="color: #3b82f6;">Card swipe:</span>
                            <span>E100002 → AUDITORIUM</span>
                        </div>
                        <div style="margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                            <span style="color: #64748b;">[19:17:52]</span>
                            <span style="color: #8b5cf6;">Lab booking:</span>
                            <span>E100003 → LAB_301</span>
                        </div>
                        <div style="margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                            <span style="color: #64748b;">[19:17:38]</span>
                            <span style="color: #10b981;">Library checkout:</span>
                            <span>E100004 → LIBRARY</span>
                        </div>
                        <div style="margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                            <span style="color: #64748b;">[19:17:25]</span>
                            <span style="color: #f59e0b;">WiFi disconnect:</span>
                            <span>Device_XYZ789 → AP_CAFETERIA</span>
                        </div>
                        <div style="margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                            <span style="color: #64748b;">[19:17:12]</span>
                            <span style="color: #ef4444;">CCTV detection:</span>
                            <span>Face_ID_789 → ADMIN_BLOCK</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="card" style="margin-top: 24px;">
            <div class="card-header"><div class="card-title">Location Heatmap</div></div>
            <div class="card-body">
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;">
                    <div style="text-align: center; padding: 16px; background: linear-gradient(135deg, #ef4444, #dc2626); border-radius: 8px; color: white;">
                        <i class="fas fa-fire" style="font-size: 24px; margin-bottom: 8px;"></i>
                        <div style="font-weight: 600;">LAB_301</div>
                        <div style="font-size: 12px; opacity: 0.9;">High Activity</div>
                    </div>
                    <div style="text-align: center; padding: 16px; background: linear-gradient(135deg, #f59e0b, #d97706); border-radius: 8px; color: white;">
                        <i class="fas fa-thermometer-half" style="font-size: 24px; margin-bottom: 8px;"></i>
                        <div style="font-weight: 600;">LIBRARY</div>
                        <div style="font-size: 12px; opacity: 0.9;">Medium Activity</div>
                    </div>
                    <div style="text-align: center; padding: 16px; background: linear-gradient(135deg, #10b981, #059669); border-radius: 8px; color: white;">
                        <i class="fas fa-snowflake" style="font-size: 24px; margin-bottom: 8px;"></i>
                        <div style="font-weight: 600;">AUDITORIUM</div>
                        <div style="font-size: 12px; opacity: 0.9;">Low Activity</div>
                    </div>
                    <div style="text-align: center; padding: 16px; background: linear-gradient(135deg, #3b82f6, #2563eb); border-radius: 8px; color: white;">
                        <i class="fas fa-chart-bar" style="font-size: 24px; margin-bottom: 8px;"></i>
                        <div style="font-weight: 600;">CAFETERIA</div>
                        <div style="font-size: 12px; opacity: 0.9;">Normal Activity</div>
                    </div>
                </div>
            </div>
        </div>
    """, "monitoring")

@app.get("/settings", response_class=HTMLResponse)
async def settings_page():
    """Settings page"""
    return create_page_template("Settings", """
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;">
            <div class="card">
                <div class="card-header">
                    <div class="card-title">System Configuration</div>
                    <p style="color: #64748b; font-size: 14px; margin: 0;">Configure system-wide settings and preferences</p>
                </div>
                <div class="card-body">
                    <div class="form-group">
                        <label class="form-label">Data Refresh Interval</label>
                        <select class="form-control" style="background: white;">
                            <option>Every 5 minutes</option>
                            <option selected>Every 10 minutes</option>
                            <option>Every 30 minutes</option>
                            <option>Every 1 hour</option>
                        </select>
                        <small style="color: #64748b;">How often to refresh campus data from sources</small>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">Alert Threshold Level</label>
                        <div style="display: flex; align-items: center; gap: 16px;">
                            <input type="range" style="flex: 1;" min="1" max="10" value="7" id="alertRange">
                            <span style="background: #3b82f6; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 600;" id="alertValue">7</span>
                        </div>
                        <small style="color: #64748b;">Security alert sensitivity (1=Low, 10=High)</small>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">Entity Resolution Settings</label>
                        <div style="display: flex; align-items: center; gap: 16px; margin-bottom: 12px;">
                            <input type="checkbox" checked id="autoResolve">
                            <label for="autoResolve" style="margin: 0;">Enable automatic entity resolution</label>
                        </div>
                        <div style="display: flex; align-items: center; gap: 16px;">
                            <input type="checkbox" checked id="crossSource">
                            <label for="crossSource" style="margin: 0;">Cross-source data linking</label>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">Confidence Threshold</label>
                        <div style="display: flex; align-items: center; gap: 16px;">
                            <input type="range" style="flex: 1;" min="50" max="100" value="85" id="confidenceRange">
                            <span style="background: #10b981; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 600;" id="confidenceValue">85%</span>
                        </div>
                        <small style="color: #64748b;">Minimum confidence for entity matching</small>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <div class="card-title">Notification Settings</div>
                    <p style="color: #64748b; font-size: 14px; margin: 0;">Configure alerts and notification preferences</p>
                </div>
                <div class="card-body">
                    <div class="form-group">
                        <label class="form-label">Email Notifications</label>
                        <div style="display: grid; gap: 12px;">
                            <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: #f8fafc; border-radius: 8px;">
                                <input type="checkbox" checked id="securityAlerts">
                                <div style="flex: 1;">
                                    <label for="securityAlerts" style="margin: 0; font-weight: 500;">Security Alerts</label>
                                    <div style="font-size: 12px; color: #64748b;">High-priority security incidents</div>
                                </div>
                            </div>
                            <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: #f8fafc; border-radius: 8px;">
                                <input type="checkbox" checked id="systemHealth">
                                <div style="flex: 1;">
                                    <label for="systemHealth" style="margin: 0; font-weight: 500;">System Health</label>
                                    <div style="font-size: 12px; color: #64748b;">System performance and uptime alerts</div>
                                </div>
                            </div>
                            <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: #f8fafc; border-radius: 8px;">
                                <input type="checkbox" id="dailyReports">
                                <div style="flex: 1;">
                                    <label for="dailyReports" style="margin: 0; font-weight: 500;">Daily Reports</label>
                                    <div style="font-size: 12px; color: #64748b;">Daily activity summaries</div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">Email Address</label>
                        <input type="email" class="form-control" value="admin@campus-security.edu" placeholder="Enter email address">
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">Notification Frequency</label>
                        <select class="form-control" style="background: white;">
                            <option selected>Immediate</option>
                            <option>Every 15 minutes</option>
                            <option>Every hour</option>
                            <option>Daily digest</option>
                        </select>
                    </div>
                </div>
            </div>
        </div>
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-top: 24px;">
            <div class="card">
                <div class="card-header">
                    <div class="card-title">Data Sources</div>
                    <p style="color: #64748b; font-size: 14px; margin: 0;">Manage campus data source connections</p>
                </div>
                <div class="card-body">
                    <div style="display: grid; gap: 12px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #f8fafc; border-radius: 8px;">
                            <div style="display: flex; align-items: center; gap: 12px;">
                                <div style="width: 32px; height: 32px; background: #3b82f6; border-radius: 6px; display: flex; align-items: center; justify-content: center;">
                                    <i class="fas fa-credit-card" style="color: white; font-size: 14px;"></i>
                                </div>
                                <div>
                                    <div style="font-weight: 500;">Card Swipes</div>
                                    <div style="font-size: 12px; color: #64748b;">2,847 records</div>
                                </div>
                            </div>
                            <span class="badge badge-success">Connected</span>
                        </div>
                        
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #f8fafc; border-radius: 8px;">
                            <div style="display: flex; align-items: center; gap: 12px;">
                                <div style="width: 32px; height: 32px; background: #ef4444; border-radius: 6px; display: flex; align-items: center; justify-content: center;">
                                    <i class="fas fa-video" style="color: white; font-size: 14px;"></i>
                                </div>
                                <div>
                                    <div style="font-weight: 500;">CCTV Frames</div>
                                    <div style="font-size: 12px; color: #64748b;">1,923 detections</div>
                                </div>
                            </div>
                            <span class="badge badge-success">Connected</span>
                        </div>
                        
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #f8fafc; border-radius: 8px;">
                            <div style="display: flex; align-items: center; gap: 12px;">
                                <div style="width: 32px; height: 32px; background: #10b981; border-radius: 6px; display: flex; align-items: center; justify-content: center;">
                                    <i class="fas fa-wifi" style="color: white; font-size: 14px;"></i>
                                </div>
                                <div>
                                    <div style="font-weight: 500;">WiFi Logs</div>
                                    <div style="font-size: 12px; color: #64748b;">5,384 sessions</div>
                                </div>
                            </div>
                            <span class="badge badge-success">Connected</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <div class="card-title">Security & Privacy</div>
                    <p style="color: #64748b; font-size: 14px; margin: 0;">Configure security and privacy settings</p>
                </div>
                <div class="card-body">
                    <div class="form-group">
                        <label class="form-label">Data Retention Period</label>
                        <select class="form-control" style="background: white;">
                            <option>30 days</option>
                            <option>90 days</option>
                            <option selected>180 days</option>
                            <option>1 year</option>
                        </select>
                        <small style="color: #64748b;">How long to keep historical data</small>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">Privacy Settings</label>
                        <div style="display: grid; gap: 12px;">
                            <div style="display: flex; align-items: center; gap: 12px;">
                                <input type="checkbox" checked id="anonymizeData">
                                <label for="anonymizeData" style="margin: 0;">Anonymize personal data in reports</label>
                            </div>
                            <div style="display: flex; align-items: center; gap: 12px;">
                                <input type="checkbox" checked id="encryptStorage">
                                <label for="encryptStorage" style="margin: 0;">Encrypt data at rest</label>
                            </div>
                            <div style="display: flex; align-items: center; gap: 12px;">
                                <input type="checkbox" id="auditLog">
                                <label for="auditLog" style="margin: 0;">Enable detailed audit logging</label>
                            </div>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">Access Control</label>
                        <div style="display: flex; gap: 12px;">
                            <button class="btn btn-primary" style="flex: 1;">Manage Users</button>
                            <button class="btn btn-secondary" style="flex: 1;">View Audit Log</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div style="margin-top: 24px; text-align: center;">
            <button class="btn btn-primary" style="padding: 12px 32px; margin-right: 12px;">Save Settings</button>
            <button class="btn btn-secondary" style="padding: 12px 32px;">Reset to Defaults</button>
        </div>
        
        <script>
            // Update range slider values
            document.getElementById('alertRange').addEventListener('input', function(e) {
                document.getElementById('alertValue').textContent = e.target.value;
            });
            
            document.getElementById('confidenceRange').addEventListener('input', function(e) {
                document.getElementById('confidenceValue').textContent = e.target.value + '%';
            });
        </script>
    """, "settings")

def create_page_template(page_title, content, active_page="dashboard"):
    """Create page template with sidebar"""
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>{page_title} - Campus Security</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: 'Inter', sans-serif; background: #f8fafc; color: #334155; }}
            .sidebar {{ width: 280px; height: 100vh; background: #ffffff; border-right: 1px solid #e2e8f0; position: fixed; left: 0; top: 0; z-index: 1000; }}
            .sidebar-header {{ padding: 24px; border-bottom: 1px solid #e2e8f0; }}
            .sidebar-brand {{ display: flex; align-items: center; gap: 12px; font-size: 18px; font-weight: 600; color: #1e293b; }}
            .sidebar-nav {{ padding: 24px 0; }}
            .nav-section {{ margin-bottom: 32px; }}
            .nav-section-title {{ padding: 0 24px 12px; font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }}
            .nav-item {{ display: flex; align-items: center; gap: 12px; padding: 12px 24px; color: #64748b; text-decoration: none; transition: all 0.2s; }}
            .nav-item:hover, .nav-item.active {{ background: #f1f5f9; color: #0f172a; }}
            .nav-item.active {{ border-right: 3px solid #3b82f6; }}
            .main-content {{ margin-left: 280px; padding: 32px; }}
            .header {{ display: flex; justify-content: between; align-items: center; margin-bottom: 32px; }}
            .header h1 {{ font-size: 28px; font-weight: 700; color: #0f172a; }}
            .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px; margin-bottom: 32px; }}
            .stat-card {{ background: white; border-radius: 12px; padding: 24px; border: 1px solid #e2e8f0; }}
            .stat-value {{ font-size: 32px; font-weight: 700; color: #0f172a; margin-bottom: 8px; }}
            .stat-change {{ font-size: 14px; display: flex; align-items: center; gap: 4px; }}
            .stat-change.positive {{ color: #059669; }}
            .stat-change.negative {{ color: #dc2626; }}
            .card {{ background: white; border-radius: 12px; border: 1px solid #e2e8f0; }}
            .card-header {{ padding: 24px 24px 0; border-bottom: none; }}
            .card-title {{ font-size: 18px; font-weight: 600; color: #0f172a; margin-bottom: 8px; }}
            .card-body {{ padding: 24px; }}
            .form-group {{ margin-bottom: 20px; }}
            .form-label {{ display: block; font-size: 14px; font-weight: 500; color: #374151; margin-bottom: 8px; }}
            .form-control {{ width: 100%; padding: 12px 16px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px; transition: border-color 0.2s; }}
            .form-control:focus {{ outline: none; border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1); }}
            .badge {{ padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: 500; }}
            .badge-success {{ background: #d1fae5; color: #065f46; }}
            .badge-warning {{ background: #fef3c7; color: #92400e; }}
            .badge-danger {{ background: #fee2e2; color: #991b1b; }}
            .btn {{ padding: 8px 16px; border-radius: 6px; font-size: 14px; font-weight: 500; border: none; cursor: pointer; transition: all 0.2s; }}
            .btn-primary {{ background: #3b82f6; color: white; }}
            .btn-primary:hover {{ background: #2563eb; }}
            .btn-secondary {{ background: #6b7280; color: white; }}
            .btn-secondary:hover {{ background: #4b5563; }}
            .btn-danger {{ background: #dc2626; color: white; }}
            .btn-danger:hover {{ background: #b91c1c; }}
            .stat-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }}
            .stat-title {{ font-size: 14px; font-weight: 500; color: #64748b; }}
            .stat-icon {{ width: 40px; height: 40px; border-radius: 8px; display: flex; align-items: center; justify-content: center; }}
            .modal {{ display: none; position: fixed; z-index: 2000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.5); }}
            .modal-content {{ background-color: white; margin: 5% auto; padding: 20px; border-radius: 12px; width: 80%; max-width: 600px; }}
            .close {{ color: #aaa; float: right; font-size: 28px; font-weight: bold; cursor: pointer; }}
            .close:hover {{ color: black; }}
        </style>
    </head>
    <body>
        <div class="sidebar">
            <div class="sidebar-header">
                <div class="sidebar-brand">
                    <div style="width: 32px; height: 32px; background: linear-gradient(45deg, #ff6b35, #f7931e); border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-weight: 700; font-size: 16px;">C</div>
                    Campus Security
                </div>
            </div>
            <nav class="sidebar-nav">
                <div class="nav-section">
                    <div class="nav-section-title">Feature</div>
                    <a href="/" class="nav-item {'active' if active_page == 'dashboard' else ''}"><i class="fas fa-tachometer-alt"></i> Dashboard</a>
                    <a href="/analytics" class="nav-item {'active' if active_page == 'analytics' else ''}"><i class="fas fa-chart-line"></i> Analytics</a>
                    <a href="/entities" class="nav-item {'active' if active_page == 'entities' else ''}"><i class="fas fa-users"></i> Entities</a>
                    <a href="/security" class="nav-item {'active' if active_page == 'security' else ''}"><i class="fas fa-shield-alt"></i> Security</a>
                    <a href="/monitoring" class="nav-item {'active' if active_page == 'monitoring' else ''}"><i class="fas fa-video"></i> Monitoring</a>
                </div>
                <div class="nav-section">
                    <div class="nav-section-title">Others</div>
                    <a href="/settings" class="nav-item {'active' if active_page == 'settings' else ''}"><i class="fas fa-cog"></i> Setting</a>
                </div>
            </nav>
        </div>
        <div class="main-content">
            <div class="header">
                <h1>{page_title}</h1>
            </div>
            {content}
        </div>
    </body>
    </html>
    """

@app.get("/api/entities")
async def get_entities_api():
    """Get all entities with details"""
    if not entity_profiles:
        raise HTTPException(status_code=503, detail="System not ready")
    
    entities = []
    for entity_id, info in list(entity_profiles.items())[:20]:  # Limit to 20 for demo
        # Get recent timeline to determine last seen
        timeline = get_entity_timeline(entity_id, 24)
        last_seen = "Unknown"
        status = "Away"
        
        if timeline:
            last_event = timeline[0]
            last_seen_time = datetime.fromisoformat(last_event['timestamp'].replace('Z', '+00:00'))
            hours_ago = (datetime.now() - last_seen_time.replace(tzinfo=None)).total_seconds() / 3600
            
            if hours_ago < 2:
                last_seen = f"{int(hours_ago)} hour{'s' if hours_ago != 1 else ''} ago"
                status = "Active"
            elif hours_ago < 24:
                last_seen = f"{int(hours_ago)} hours ago"
                status = "Away"
            else:
                last_seen = f"{int(hours_ago/24)} days ago"
                status = "Away"
        
        entities.append({
            'entity_id': entity_id,
            'name': info['name'],
            'role': info['role'],
            'department': info['department'],
            'card_id': info.get('card_id', ''),
            'last_seen': last_seen,
            'status': status,
            'initials': ''.join([n[0] for n in info['name'].split()[:2]]).upper()
        })
    
    return entities

@app.get("/api/entity/{entity_id}")
async def get_entity_details(entity_id: str):
    """Get detailed entity information"""
    if not entity_profiles:
        raise HTTPException(status_code=503, detail="System not ready")
    
    if entity_id not in entity_profiles:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    info = entity_profiles[entity_id]
    timeline = get_entity_timeline(entity_id, 168)  # Last week
    alerts = check_entity_alerts(entity_id)
    
    return {
        'entity_id': entity_id,
        'name': info['name'],
        'role': info['role'],
        'department': info['department'],
        'card_id': info.get('card_id', ''),
        'device_hash': info.get('device_hash', ''),
        'face_id': info.get('face_id', ''),
        'timeline': timeline,
        'alerts': alerts,
        'total_activities': len(timeline)
    }

@app.get("/api/security/alerts")
async def get_all_alerts():
    """Get all security alerts"""
    if not entity_profiles:
        raise HTTPException(status_code=503, detail="System not ready")
    
    all_alerts = []
    # Check alerts for top entities
    for entity_id in list(entity_profiles.keys())[:10]:
        alerts = check_entity_alerts(entity_id)
        all_alerts.extend(alerts)
    
    # Add some mock alerts for demo
    mock_alerts = [
        {
            'alert_id': 'ALT001',
            'entity_id': 'E104001',
            'alert_type': 'unusual_activity',
            'severity': 'medium',
            'timestamp': datetime.now().isoformat(),
            'description': 'Multiple failed card swipe attempts detected at LAB_301',
            'location': 'LAB_301',
            'status': 'active'
        },
        {
            'alert_id': 'ALT002',
            'entity_id': 'UNKNOWN',
            'alert_type': 'access_violation',
            'severity': 'high',
            'timestamp': (datetime.now() - timedelta(hours=4)).isoformat(),
            'description': 'Unauthorized access attempt to restricted ADMIN_BLOCK area',
            'location': 'ADMIN_BLOCK',
            'status': 'active'
        }
    ]
    
    all_alerts.extend(mock_alerts)
    return sorted(all_alerts, key=lambda x: x['timestamp'], reverse=True)

@app.post("/api/security/alert/{alert_id}/resolve")
async def resolve_alert(alert_id: str):
    """Resolve a security alert"""
    return {
        'alert_id': alert_id,
        'status': 'resolved',
        'resolved_at': datetime.now().isoformat(),
        'message': f'Alert {alert_id} has been resolved'
    }

@app.get("/api/debug/entities")
async def debug_entities():
    """Debug endpoint to see actual entities in dataset"""
    if not entity_profiles:
        return {"error": "System not ready"}
    
    # Return first 10 entities for debugging
    sample_entities = {}
    for i, (entity_id, info) in enumerate(list(entity_profiles.items())[:10]):
        sample_entities[entity_id] = info
    
    return {
        "total_entities": len(entity_profiles),
        "sample_entities": sample_entities
    }

@app.get("/api/status")
async def get_status():
    """Get system status"""
    return {
        'system_ready': len(entity_profiles) > 0,
        'total_entities': len(entity_profiles),
        'data_sources': len(campus_data),
        'last_update': datetime.now().isoformat()
    }

if __name__ == "__main__":
    logger.info("🚀 Starting HACKATHON READY Campus Security System")
    logger.info("🎯 Optimized for fast startup and real data processing")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )
