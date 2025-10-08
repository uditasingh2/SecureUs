# Campus Entity Resolution & Security Monitoring System
__version__ = "1.0.0"

# Import main components for easy access
from .data_loader import CampusDataLoader
from .entity_resolver import EntityResolver, ResolvedEntity
from .multimodal_fusion import MultiModalFusion, FusionRecord
from .timeline_generator import TimelineGenerator, TimelineEvent, TimelineSummary
from .predictive_monitor import PredictiveMonitor, Prediction, AnomalyAlert

__all__ = [
    'CampusDataLoader',
    'EntityResolver', 'ResolvedEntity',
    'MultiModalFusion', 'FusionRecord',
    'TimelineGenerator', 'TimelineEvent', 'TimelineSummary',
    'PredictiveMonitor', 'Prediction', 'AnomalyAlert'
]
