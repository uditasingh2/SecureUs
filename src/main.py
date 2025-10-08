"""
Main Application - Campus Entity Resolution & Security Monitoring System
Integrates all components and provides API endpoints
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn
from loguru import logger
import asyncio
from pathlib import Path

from .config import API_CONFIG, DATA_FILES, OUTPUT_DIR
from .data_loader import CampusDataLoader
from .entity_resolver import EntityResolver, ResolvedEntity
from .multimodal_fusion import MultiModalFusion, FusionRecord
from .timeline_generator import TimelineGenerator, TimelineEvent, TimelineSummary
from .predictive_monitor import PredictiveMonitor, Prediction, AnomalyAlert


# Pydantic models for API
class EntityQuery(BaseModel):
    entity_identifier: str
    identifier_type: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class TimelineRequest(BaseModel):
    entity_id: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    include_predictions: bool = False


class PredictionRequest(BaseModel):
    entity_id: str
    timestamp: datetime
    context_hours: int = 24


class SecurityAlert(BaseModel):
    alert_id: str
    entity_id: str
    alert_type: str
    severity: str
    timestamp: datetime
    description: str
    status: str = "active"


class CampusEntityResolutionSystem:
    """
    Main system class that orchestrates all components
    """
    
    def __init__(self):
        self.data_loader = CampusDataLoader()
        self.entity_resolver = EntityResolver()
        self.fusion_engine = MultiModalFusion()
        self.timeline_generator = TimelineGenerator()
        self.predictive_monitor = PredictiveMonitor()
        
        self.data = {}
        self.resolved_entities = {}
        self.entity_timelines = {}
        self.active_alerts = {}
        self.system_ready = False
        
        logger.info("Campus Entity Resolution System initialized")
    
    async def initialize_system(self):
        """Initialize the system by loading data and training models"""
        try:
            logger.info("Starting system initialization...")
            
            # Load all data
            self.data = self.data_loader.load_all_data()
            logger.info("Data loading completed")
            
            # Resolve entities with limited dataset for performance
            # Use only profiles + first 1000 records from other sources for demo
            limited_data = {
                'profiles': self.data['profiles'],
                'card_swipes': self.data['card_swipes'].head(1000),
                'cctv_frames': self.data['cctv_frames'].head(1000),
                'wifi_logs': self.data['wifi_logs'].head(1000),
                'notes': self.data['notes'].head(1000)
            }
            
            self.resolved_entities = self.entity_resolver.resolve_entities(limited_data)
            logger.info(f"Entity resolution completed: {len(self.resolved_entities)} entities")
            
            # Prepare training data for predictive models
            training_records = []
            for entity_id, entity in list(self.resolved_entities.items())[:100]:  # Use first 100 for training
                entity_data = self.data_loader.get_entity_data(list(entity.entity_ids)[0] if entity.entity_ids else entity_id)
                fused_records = self.fusion_engine.fuse_entity_data(entity, entity_data, self.data.get('face_embeddings'))
                training_records.extend(fused_records)
            
            # Train predictive models
            if training_records:
                performance = self.predictive_monitor.train_predictive_models(
                    training_records, self.data['profiles']
                )
                logger.info(f"Predictive models trained: {performance}")
            
            self.system_ready = True
            logger.info("System initialization completed successfully")
            
        except Exception as e:
            logger.error(f"System initialization failed: {e}")
            raise
    
    def get_entity_by_identifier(self, identifier: str, identifier_type: Optional[str] = None) -> Optional[ResolvedEntity]:
        """Find entity by any identifier"""
        return self.entity_resolver.get_entity_by_identifier(identifier, identifier_type)
    
    def get_entity_timeline(self, entity_id: str, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> List[TimelineEvent]:
        """Get timeline for an entity"""
        if not self.system_ready:
            raise HTTPException(status_code=503, detail="System not ready")
        
        # Get entity
        entity = self.resolved_entities.get(entity_id)
        if not entity:
            # Try to find by identifier
            entity = self.get_entity_by_identifier(entity_id)
            if not entity:
                raise HTTPException(status_code=404, detail="Entity not found")
        
        # Get entity data
        primary_entity_id = list(entity.entity_ids)[0] if entity.entity_ids else entity_id
        entity_data = self.data_loader.get_entity_data(primary_entity_id)
        
        # Fuse data
        fused_records = self.fusion_engine.fuse_entity_data(entity, entity_data, self.data.get('face_embeddings'))
        
        # Generate timeline
        timeline = self.timeline_generator.generate_timeline(entity.unified_id, fused_records, start_time, end_time)
        
        return timeline
    
    def get_entity_summary(self, entity_id: str) -> TimelineSummary:
        """Get summary for an entity"""
        timeline = self.get_entity_timeline(entity_id)
        return self.timeline_generator.generate_summary(entity_id, timeline)
    
    def predict_entity_state(self, entity_id: str, timestamp: datetime, context_hours: int = 24) -> Optional[Prediction]:
        """Predict entity state at given timestamp"""
        if not self.system_ready:
            raise HTTPException(status_code=503, detail="System not ready")
        
        # Get entity
        entity = self.resolved_entities.get(entity_id)
        if not entity:
            entity = self.get_entity_by_identifier(entity_id)
            if not entity:
                raise HTTPException(status_code=404, detail="Entity not found")
        
        # Get context records
        context_start = timestamp - timedelta(hours=context_hours)
        timeline = self.get_entity_timeline(entity.unified_id, context_start, timestamp)
        
        # Convert timeline to fusion records (simplified)
        context_records = []
        for event in timeline:
            if event.activity != 'gap':
                context_record = FusionRecord(
                    unified_entity_id=entity.unified_id,
                    timestamp=event.timestamp,
                    location=event.location,
                    activity_type=event.activity,
                    confidence=event.confidence,
                    source_records=[{'dataset': source} for source in event.sources],
                    provenance={},
                    evidence={}
                )
                context_records.append(context_record)
        
        # Get entity profile
        primary_entity_id = list(entity.entity_ids)[0] if entity.entity_ids else entity_id
        entity_profile = self.data['profiles'][self.data['profiles']['entity_id'] == primary_entity_id].iloc[0].to_dict() if not self.data['profiles'].empty else {}
        
        # Make prediction
        return self.predictive_monitor.predict_missing_data(entity.unified_id, timestamp, context_records, entity_profile)
    
    def check_entity_alerts(self, entity_id: str) -> List[AnomalyAlert]:
        """Check for alerts related to an entity"""
        if not self.system_ready:
            return []
        
        # Get entity
        entity = self.resolved_entities.get(entity_id)
        if not entity:
            entity = self.get_entity_by_identifier(entity_id)
            if not entity:
                return []
        
        # Get recent timeline
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=48)  # Last 48 hours
        timeline = self.get_entity_timeline(entity.unified_id, start_time, end_time)
        
        # Convert to fusion records
        recent_records = []
        for event in timeline:
            if event.activity != 'gap':
                record = FusionRecord(
                    unified_entity_id=entity.unified_id,
                    timestamp=event.timestamp,
                    location=event.location,
                    activity_type=event.activity,
                    confidence=event.confidence,
                    source_records=[{'dataset': source} for source in event.sources],
                    provenance={},
                    evidence={}
                )
                recent_records.append(record)
        
        # Get entity profile
        primary_entity_id = list(entity.entity_ids)[0] if entity.entity_ids else entity_id
        entity_profile = self.data['profiles'][self.data['profiles']['entity_id'] == primary_entity_id].iloc[0].to_dict() if not self.data['profiles'].empty else {}
        
        # Detect anomalies
        return self.predictive_monitor.detect_anomalies(recent_records, entity_profile)
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status"""
        return {
            'system_ready': self.system_ready,
            'total_entities': len(self.resolved_entities),
            'data_sources': len(self.data),
            'active_alerts': len(self.active_alerts),
            'last_update': datetime.now().isoformat()
        }


# Initialize system
system = CampusEntityResolutionSystem()

# Create FastAPI app
app = FastAPI(
    title="Campus Entity Resolution & Security Monitoring System",
    description="Advanced system for campus security and entity tracking",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=API_CONFIG['cors_origins'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.on_event("startup")
async def startup_event():
    """Initialize system on startup"""
    await system.initialize_system()


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the main dashboard"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Campus Security Dashboard</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    </head>
    <body>
        <nav class="navbar navbar-dark bg-dark">
            <div class="container-fluid">
                <span class="navbar-brand mb-0 h1">Campus Security Dashboard</span>
                <span class="navbar-text" id="system-status">System Loading...</span>
            </div>
        </nav>
        
        <div class="container-fluid mt-4">
            <div class="row">
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-header">
                            <h5>Entity Search</h5>
                        </div>
                        <div class="card-body">
                            <div class="mb-3">
                                <label for="entitySearch" class="form-label">Entity ID/Name</label>
                                <input type="text" class="form-control" id="entitySearch" placeholder="Enter entity identifier">
                            </div>
                            <div class="mb-3">
                                <label for="timeRange" class="form-label">Time Range</label>
                                <select class="form-select" id="timeRange">
                                    <option value="24">Last 24 hours</option>
                                    <option value="168">Last week</option>
                                    <option value="720">Last month</option>
                                </select>
                            </div>
                            <button type="button" class="btn btn-primary" onclick="searchEntity()">Search</button>
                            <button type="button" class="btn btn-warning ms-2" onclick="checkAlerts()">Check Alerts</button>
                        </div>
                    </div>
                    
                    <div class="card mt-3">
                        <div class="card-header">
                            <h5>System Statistics</h5>
                        </div>
                        <div class="card-body" id="system-stats">
                            Loading...
                        </div>
                    </div>
                </div>
                
                <div class="col-md-8">
                    <div class="card">
                        <div class="card-header">
                            <h5>Entity Timeline</h5>
                        </div>
                        <div class="card-body">
                            <div id="timeline-container">
                                <p class="text-muted">Search for an entity to view timeline</p>
                            </div>
                        </div>
                    </div>
                    
                    <div class="card mt-3">
                        <div class="card-header">
                            <h5>Alerts & Predictions</h5>
                        </div>
                        <div class="card-body">
                            <div id="alerts-container">
                                <p class="text-muted">No active alerts</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            // Load system status
            async function loadSystemStatus() {
                try {
                    const response = await fetch('/api/v1/system/status');
                    const status = await response.json();
                    
                    document.getElementById('system-status').textContent = 
                        status.system_ready ? 'System Ready' : 'System Loading...';
                    
                    document.getElementById('system-stats').innerHTML = `
                        <p><strong>Total Entities:</strong> ${status.total_entities}</p>
                        <p><strong>Data Sources:</strong> ${status.data_sources}</p>
                        <p><strong>Active Alerts:</strong> ${status.active_alerts}</p>
                        <p><strong>Last Update:</strong> ${new Date(status.last_update).toLocaleString()}</p>
                    `;
                } catch (error) {
                    console.error('Failed to load system status:', error);
                }
            }
            
            // Search entity
            async function searchEntity() {
                const entityId = document.getElementById('entitySearch').value;
                const timeRange = document.getElementById('timeRange').value;
                
                if (!entityId) {
                    alert('Please enter an entity identifier');
                    return;
                }
                
                try {
                    // Get entity timeline
                    const timelineResponse = await fetch(`/api/v1/entity/${entityId}/timeline?hours=${timeRange}`);
                    const timeline = await timelineResponse.json();
                    
                    displayTimeline(timeline);
                    
                    // Get entity summary
                    const summaryResponse = await fetch(`/api/v1/entity/${entityId}/summary`);
                    const summary = await summaryResponse.json();
                    
                    displaySummary(summary);
                    
                } catch (error) {
                    console.error('Search failed:', error);
                    alert('Entity not found or search failed');
                }
            }
            
            // Check alerts
            async function checkAlerts() {
                const entityId = document.getElementById('entitySearch').value;
                
                if (!entityId) {
                    alert('Please enter an entity identifier');
                    return;
                }
                
                try {
                    const response = await fetch(`/api/v1/entity/${entityId}/alerts`);
                    const alerts = await response.json();
                    
                    displayAlerts(alerts);
                    
                } catch (error) {
                    console.error('Alert check failed:', error);
                }
            }
            
            // Display timeline
            function displayTimeline(timeline) {
                const container = document.getElementById('timeline-container');
                
                if (!timeline || timeline.length === 0) {
                    container.innerHTML = '<p class="text-muted">No timeline data available</p>';
                    return;
                }
                
                let html = '<div class="timeline">';
                timeline.forEach(event => {
                    const timestamp = new Date(event.timestamp).toLocaleString();
                    const confidence = Math.round(event.confidence * 100);
                    
                    html += `
                        <div class="card mb-2">
                            <div class="card-body">
                                <h6 class="card-title">${event.description}</h6>
                                <p class="card-text">
                                    <small class="text-muted">
                                        ${timestamp} | ${event.location} | Confidence: ${confidence}%
                                    </small>
                                </p>
                                <span class="badge bg-secondary">${event.activity}</span>
                                ${event.sources.map(source => `<span class="badge bg-info ms-1">${source}</span>`).join('')}
                            </div>
                        </div>
                    `;
                });
                html += '</div>';
                
                container.innerHTML = html;
            }
            
            // Display summary
            function displaySummary(summary) {
                // Add summary display logic here
                console.log('Summary:', summary);
            }
            
            // Display alerts
            function displayAlerts(alerts) {
                const container = document.getElementById('alerts-container');
                
                if (!alerts || alerts.length === 0) {
                    container.innerHTML = '<p class="text-muted">No active alerts</p>';
                    return;
                }
                
                let html = '';
                alerts.forEach(alert => {
                    const severityClass = alert.severity === 'high' ? 'danger' : 'warning';
                    const timestamp = new Date(alert.timestamp).toLocaleString();
                    
                    html += `
                        <div class="alert alert-${severityClass}" role="alert">
                            <h6 class="alert-heading">${alert.alert_type.toUpperCase()} Alert</h6>
                            <p>${alert.description}</p>
                            <hr>
                            <p class="mb-0">
                                <small>Entity: ${alert.entity_id} | ${timestamp}</small>
                            </p>
                        </div>
                    `;
                });
                
                container.innerHTML = html;
            }
            
            // Initialize dashboard
            document.addEventListener('DOMContentLoaded', function() {
                loadSystemStatus();
                setInterval(loadSystemStatus, 30000); // Refresh every 30 seconds
            });
        </script>
    </body>
    </html>
    """


# API Routes
@app.get("/api/v1/system/status")
async def get_system_status():
    """Get system status"""
    return system.get_system_status()


@app.get("/api/v1/entity/{entity_id}/timeline")
async def get_entity_timeline(
    entity_id: str,
    hours: int = Query(24, description="Hours to look back"),
    include_predictions: bool = Query(False, description="Include predictions for gaps")
):
    """Get entity timeline"""
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)
    
    timeline = system.get_entity_timeline(entity_id, start_time, end_time)
    
    # Convert to serializable format
    timeline_data = []
    for event in timeline:
        timeline_data.append({
            'timestamp': event.timestamp.isoformat(),
            'location': event.location,
            'activity': event.activity,
            'description': event.description,
            'confidence': event.confidence,
            'sources': event.sources,
            'duration_minutes': event.duration.total_seconds() / 60 if event.duration else None
        })
    
    return timeline_data


@app.get("/api/v1/entity/{entity_id}/summary")
async def get_entity_summary(entity_id: str):
    """Get entity summary"""
    summary = system.get_entity_summary(entity_id)
    
    return {
        'entity_id': summary.entity_id,
        'start_time': summary.start_time.isoformat(),
        'end_time': summary.end_time.isoformat(),
        'total_events': summary.total_events,
        'locations_visited': summary.locations_visited,
        'primary_activities': summary.primary_activities,
        'summary_text': summary.summary_text,
        'confidence_score': summary.confidence_score,
        'gaps': [(gap[0].isoformat(), gap[1].isoformat()) for gap in summary.gaps]
    }


@app.get("/api/v1/entity/{entity_id}/alerts")
async def get_entity_alerts(entity_id: str):
    """Get alerts for entity"""
    alerts = system.check_entity_alerts(entity_id)
    
    alert_data = []
    for alert in alerts:
        alert_data.append({
            'entity_id': alert.entity_id,
            'alert_type': alert.alert_type,
            'severity': alert.severity,
            'timestamp': alert.timestamp.isoformat(),
            'description': alert.description,
            'evidence': alert.evidence,
            'recommended_actions': alert.recommended_actions
        })
    
    return alert_data


@app.post("/api/v1/entity/{entity_id}/predict")
async def predict_entity_state(entity_id: str, request: PredictionRequest):
    """Predict entity state"""
    prediction = system.predict_entity_state(entity_id, request.timestamp, request.context_hours)
    
    if not prediction:
        raise HTTPException(status_code=404, detail="Unable to make prediction")
    
    return {
        'entity_id': prediction.entity_id,
        'timestamp': prediction.timestamp.isoformat(),
        'predicted_location': prediction.predicted_location,
        'predicted_activity': prediction.predicted_activity,
        'confidence': prediction.confidence,
        'explanation': prediction.explanation,
        'evidence': prediction.evidence,
        'alternative_predictions': prediction.alternative_predictions
    }


@app.get("/api/v1/entities/search")
async def search_entities(
    query: str = Query(..., description="Search query"),
    limit: int = Query(10, description="Maximum results")
):
    """Search for entities"""
    results = []
    
    for entity_id, entity in list(system.resolved_entities.items())[:limit]:
        # Simple search in names and IDs
        search_text = f"{' '.join(entity.names)} {' '.join(entity.entity_ids)}".lower()
        if query.lower() in search_text:
            results.append({
                'unified_id': entity.unified_id,
                'names': list(entity.names),
                'entity_ids': list(entity.entity_ids),
                'confidence': entity.confidence,
                'primary_profile': entity.primary_profile
            })
    
    return results


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=API_CONFIG['host'],
        port=API_CONFIG['port'],
        reload=API_CONFIG['debug']
    )
