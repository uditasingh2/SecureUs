"""
Timeline Generation and Summarization System
Creates chronological activity timelines with human-readable summaries
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import re
from loguru import logger

from .config import TIMELINE_CONFIG, CAMPUS_LOCATIONS
from .multimodal_fusion import FusionRecord


@dataclass
class TimelineEvent:
    """Represents a single event in the timeline"""
    timestamp: datetime
    location: str
    activity: str
    description: str
    confidence: float
    sources: List[str]
    duration: Optional[timedelta] = None
    related_events: List[str] = None


@dataclass
class TimelineSummary:
    """Represents a summarized timeline for a time period"""
    entity_id: str
    start_time: datetime
    end_time: datetime
    total_events: int
    locations_visited: List[str]
    primary_activities: List[str]
    summary_text: str
    confidence_score: float
    gaps: List[Tuple[datetime, datetime]]


class TimelineGenerator:
    """
    Advanced timeline generation system that creates:
    - Chronological activity reconstruction
    - Human-readable summaries
    - Gap detection and analysis
    - Activity pattern recognition
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or TIMELINE_CONFIG
        
    def generate_timeline(self, 
                         entity_id: str, 
                         fused_records: List[FusionRecord],
                         start_time: Optional[datetime] = None,
                         end_time: Optional[datetime] = None) -> List[TimelineEvent]:
        """
        Generate a chronological timeline from fused records
        """
        logger.info(f"Generating timeline for entity {entity_id}")
        
        # Filter records by time range if specified
        filtered_records = self._filter_by_time_range(fused_records, start_time, end_time)
        
        if not filtered_records:
            logger.warning(f"No records found for entity {entity_id} in specified time range")
            return []
        
        # Sort records chronologically
        filtered_records.sort(key=lambda x: x.timestamp)
        
        # Convert fusion records to timeline events
        timeline_events = self._convert_to_timeline_events(filtered_records)
        
        # Merge related events and calculate durations
        merged_events = self._merge_related_events(timeline_events)
        
        # Detect and fill gaps
        gap_filled_events = self._detect_and_analyze_gaps(merged_events)
        
        logger.info(f"Generated timeline with {len(gap_filled_events)} events")
        return gap_filled_events
    
    def _filter_by_time_range(self, 
                             records: List[FusionRecord],
                             start_time: Optional[datetime],
                             end_time: Optional[datetime]) -> List[FusionRecord]:
        """Filter records by time range"""
        if not start_time and not end_time:
            return records
        
        filtered = []
        for record in records:
            if start_time and record.timestamp < start_time:
                continue
            if end_time and record.timestamp > end_time:
                continue
            filtered.append(record)
        
        return filtered
    
    def _convert_to_timeline_events(self, fused_records: List[FusionRecord]) -> List[TimelineEvent]:
        """Convert fusion records to timeline events"""
        timeline_events = []
        
        for record in fused_records:
            # Generate human-readable description
            description = self._generate_event_description(record)
            
            # Extract source datasets
            sources = [sr['dataset'] for sr in record.source_records]
            
            event = TimelineEvent(
                timestamp=record.timestamp,
                location=record.location,
                activity=record.activity_type,
                description=description,
                confidence=record.confidence,
                sources=sources,
                related_events=[]
            )
            
            timeline_events.append(event)
        
        return timeline_events
    
    def _generate_event_description(self, record: FusionRecord) -> str:
        """Generate human-readable description for an event"""
        location_name = CAMPUS_LOCATIONS.get(record.location, {}).get('name', record.location)
        
        # Activity type specific descriptions
        if record.activity_type == 'card_swipe':
            return f"Accessed {location_name} using campus card"
        
        elif record.activity_type == 'cctv_detection':
            return f"Detected by CCTV camera at {location_name}"
        
        elif record.activity_type == 'wifi_connection':
            return f"Connected to WiFi network at {location_name}"
        
        elif record.activity_type == 'lab_booking_start':
            duration = self._extract_booking_duration(record)
            duration_str = f" for {duration}" if duration else ""
            return f"Started lab session at {location_name}{duration_str}"
        
        elif record.activity_type == 'lab_booking_end':
            return f"Ended lab session at {location_name}"
        
        elif record.activity_type == 'library_checkout':
            book_info = self._extract_book_info(record)
            return f"Checked out book at Library{book_info}"
        
        elif record.activity_type.startswith('note_'):
            category = record.activity_type.replace('note_', '')
            return f"Submitted {category} request: {self._extract_note_summary(record)}"
        
        else:
            return f"Activity at {location_name}: {record.activity_type}"
    
    def _extract_booking_duration(self, record: FusionRecord) -> Optional[str]:
        """Extract booking duration from record"""
        for source_record in record.source_records:
            if source_record['dataset'] == 'lab_bookings':
                raw_data = source_record['raw_data']
                if 'duration_minutes' in raw_data:
                    minutes = raw_data['duration_minutes']
                    if minutes < 60:
                        return f"{int(minutes)} minutes"
                    else:
                        hours = int(minutes // 60)
                        remaining_minutes = int(minutes % 60)
                        if remaining_minutes > 0:
                            return f"{hours}h {remaining_minutes}m"
                        else:
                            return f"{hours} hours"
        return None
    
    def _extract_book_info(self, record: FusionRecord) -> str:
        """Extract book information from library checkout"""
        for source_record in record.source_records:
            if source_record['dataset'] == 'library_checkouts':
                raw_data = source_record['raw_data']
                book_id = raw_data.get('book_id', '')
                return f" (Book ID: {book_id})" if book_id else ""
        return ""
    
    def _extract_note_summary(self, record: FusionRecord) -> str:
        """Extract summary from note text"""
        for source_record in record.source_records:
            if source_record['dataset'] == 'notes':
                raw_data = source_record['raw_data']
                text = raw_data.get('text', '')
                # Truncate long text
                return text[:50] + "..." if len(text) > 50 else text
        return "No details available"
    
    def _merge_related_events(self, events: List[TimelineEvent]) -> List[TimelineEvent]:
        """Merge events that are closely related in time and location"""
        if not events:
            return events
        
        merged_events = []
        current_group = [events[0]]
        
        for event in events[1:]:
            last_event = current_group[-1]
            
            # Check if events should be merged
            time_diff = (event.timestamp - last_event.timestamp).total_seconds() / 60
            same_location = event.location == last_event.location
            
            if time_diff <= 5 and same_location:  # 5-minute window for same location
                current_group.append(event)
            else:
                # Process current group
                merged_event = self._create_merged_event(current_group)
                merged_events.append(merged_event)
                current_group = [event]
        
        # Process final group
        if current_group:
            merged_event = self._create_merged_event(current_group)
            merged_events.append(merged_event)
        
        return merged_events
    
    def _create_merged_event(self, event_group: List[TimelineEvent]) -> TimelineEvent:
        """Create a single merged event from a group of related events"""
        if len(event_group) == 1:
            return event_group[0]
        
        # Use earliest timestamp
        timestamp = min(event.timestamp for event in event_group)
        
        # Use most common location
        locations = [event.location for event in event_group]
        location = max(set(locations), key=locations.count)
        
        # Combine activities
        activities = [event.activity for event in event_group]
        unique_activities = list(set(activities))
        primary_activity = max(set(activities), key=activities.count)
        
        # Create combined description
        if len(unique_activities) == 1:
            description = event_group[0].description
        else:
            location_name = CAMPUS_LOCATIONS.get(location, {}).get('name', location)
            description = f"Multiple activities at {location_name}: {', '.join(unique_activities[:3])}"
            if len(unique_activities) > 3:
                description += f" and {len(unique_activities) - 3} more"
        
        # Calculate average confidence
        confidence = np.mean([event.confidence for event in event_group])
        
        # Combine sources
        all_sources = []
        for event in event_group:
            all_sources.extend(event.sources)
        unique_sources = list(set(all_sources))
        
        # Calculate duration if applicable
        duration = None
        if len(event_group) > 1:
            duration = max(event.timestamp for event in event_group) - timestamp
        
        return TimelineEvent(
            timestamp=timestamp,
            location=location,
            activity=primary_activity,
            description=description,
            confidence=confidence,
            sources=unique_sources,
            duration=duration,
            related_events=[f"{event.activity}@{event.timestamp}" for event in event_group[1:]]
        )
    
    def _detect_and_analyze_gaps(self, events: List[TimelineEvent]) -> List[TimelineEvent]:
        """Detect gaps in timeline and add analysis"""
        if len(events) < 2:
            return events
        
        enhanced_events = []
        
        for i, event in enumerate(events):
            enhanced_events.append(event)
            
            # Check for gap to next event
            if i < len(events) - 1:
                next_event = events[i + 1]
                gap_duration = next_event.timestamp - event.timestamp
                
                if gap_duration > timedelta(hours=self.config['max_gap_hours']):
                    # Add gap event
                    gap_event = self._create_gap_event(event, next_event, gap_duration)
                    enhanced_events.append(gap_event)
        
        return enhanced_events
    
    def _create_gap_event(self, 
                         before_event: TimelineEvent, 
                         after_event: TimelineEvent, 
                         gap_duration: timedelta) -> TimelineEvent:
        """Create an event representing a gap in the timeline"""
        gap_start = before_event.timestamp + timedelta(minutes=30)  # Assume activity ended 30 min after last event
        
        hours = int(gap_duration.total_seconds() // 3600)
        minutes = int((gap_duration.total_seconds() % 3600) // 60)
        
        if hours > 0:
            duration_str = f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"
        else:
            duration_str = f"{minutes}m"
        
        description = f"No activity detected for {duration_str}"
        
        return TimelineEvent(
            timestamp=gap_start,
            location="UNKNOWN",
            activity="gap",
            description=description,
            confidence=0.0,
            sources=[],
            duration=gap_duration
        )
    
    def generate_summary(self, 
                        entity_id: str, 
                        timeline_events: List[TimelineEvent],
                        summary_window_hours: Optional[int] = None) -> TimelineSummary:
        """Generate a human-readable summary of the timeline"""
        if not timeline_events:
            return TimelineSummary(
                entity_id=entity_id,
                start_time=datetime.now(),
                end_time=datetime.now(),
                total_events=0,
                locations_visited=[],
                primary_activities=[],
                summary_text="No activity recorded",
                confidence_score=0.0,
                gaps=[]
            )
        
        window_hours = summary_window_hours or self.config['summary_window_hours']
        
        # Filter events within summary window
        end_time = max(event.timestamp for event in timeline_events)
        start_time = end_time - timedelta(hours=window_hours)
        
        recent_events = [event for event in timeline_events 
                        if event.timestamp >= start_time and event.activity != 'gap']
        
        # Extract summary statistics
        locations_visited = list(set(event.location for event in recent_events if event.location != 'UNKNOWN'))
        activities = [event.activity for event in recent_events]
        primary_activities = list(set(activities))
        
        # Calculate confidence score
        if recent_events:
            confidence_score = np.mean([event.confidence for event in recent_events])
        else:
            confidence_score = 0.0
        
        # Identify gaps
        gaps = [(event.timestamp, event.timestamp + event.duration) 
                for event in timeline_events 
                if event.activity == 'gap' and event.duration]
        
        # Generate narrative summary
        summary_text = self._generate_narrative_summary(recent_events, locations_visited, primary_activities)
        
        return TimelineSummary(
            entity_id=entity_id,
            start_time=start_time,
            end_time=end_time,
            total_events=len(recent_events),
            locations_visited=locations_visited,
            primary_activities=primary_activities,
            summary_text=summary_text,
            confidence_score=confidence_score,
            gaps=gaps
        )
    
    def _generate_narrative_summary(self, 
                                  events: List[TimelineEvent], 
                                  locations: List[str], 
                                  activities: List[str]) -> str:
        """Generate a natural language summary"""
        if not events:
            return "No recent activity detected."
        
        # Start with time range
        start_time = min(event.timestamp for event in events)
        end_time = max(event.timestamp for event in events)
        
        summary_parts = []
        
        # Time range
        if start_time.date() == end_time.date():
            time_range = f"on {start_time.strftime('%B %d, %Y')}"
        else:
            time_range = f"from {start_time.strftime('%B %d')} to {end_time.strftime('%B %d, %Y')}"
        
        summary_parts.append(f"Activity summary {time_range}:")
        
        # Location summary
        if locations:
            location_names = [CAMPUS_LOCATIONS.get(loc, {}).get('name', loc) for loc in locations[:3]]
            if len(locations) == 1:
                summary_parts.append(f"Visited {location_names[0]}")
            elif len(locations) <= 3:
                summary_parts.append(f"Visited {', '.join(location_names[:-1])} and {location_names[-1]}")
            else:
                summary_parts.append(f"Visited {', '.join(location_names)} and {len(locations) - 3} other locations")
        
        # Activity summary
        activity_counts = {}
        for activity in activities:
            activity_counts[activity] = activity_counts.get(activity, 0) + 1
        
        top_activities = sorted(activity_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        
        if top_activities:
            activity_descriptions = []
            for activity, count in top_activities:
                if activity == 'card_swipe':
                    activity_descriptions.append(f"{count} access{'es' if count > 1 else ''}")
                elif activity == 'wifi_connection':
                    activity_descriptions.append(f"{count} WiFi connection{'s' if count > 1 else ''}")
                elif activity == 'cctv_detection':
                    activity_descriptions.append(f"{count} CCTV detection{'s' if count > 1 else ''}")
                elif activity.startswith('lab_booking'):
                    activity_descriptions.append(f"{count} lab session{'s' if count > 1 else ''}")
                else:
                    activity_descriptions.append(f"{count} {activity.replace('_', ' ')} event{'s' if count > 1 else ''}")
            
            summary_parts.append(f"Recorded {', '.join(activity_descriptions)}")
        
        # Recent activity
        if events:
            last_event = max(events, key=lambda x: x.timestamp)
            time_since = datetime.now() - last_event.timestamp
            
            if time_since < timedelta(hours=1):
                summary_parts.append(f"Last seen {int(time_since.total_seconds() // 60)} minutes ago at {CAMPUS_LOCATIONS.get(last_event.location, {}).get('name', last_event.location)}")
            elif time_since < timedelta(days=1):
                summary_parts.append(f"Last seen {int(time_since.total_seconds() // 3600)} hours ago at {CAMPUS_LOCATIONS.get(last_event.location, {}).get('name', last_event.location)}")
            else:
                summary_parts.append(f"Last seen on {last_event.timestamp.strftime('%B %d at %I:%M %p')}")
        
        return ". ".join(summary_parts) + "."
    
    def export_timeline(self, timeline_events: List[TimelineEvent]) -> pd.DataFrame:
        """Export timeline to a structured DataFrame"""
        if not timeline_events:
            return pd.DataFrame()
        
        export_data = []
        
        for event in timeline_events:
            row = {
                'timestamp': event.timestamp,
                'location': event.location,
                'location_name': CAMPUS_LOCATIONS.get(event.location, {}).get('name', event.location),
                'activity': event.activity,
                'description': event.description,
                'confidence': event.confidence,
                'sources': ','.join(event.sources),
                'duration_minutes': event.duration.total_seconds() / 60 if event.duration else None,
                'related_events_count': len(event.related_events) if event.related_events else 0
            }
            export_data.append(row)
        
        return pd.DataFrame(export_data)
    
    def get_timeline_statistics(self, timeline_events: List[TimelineEvent]) -> Dict[str, Any]:
        """Get statistical analysis of the timeline"""
        if not timeline_events:
            return {}
        
        # Filter out gap events for statistics
        real_events = [event for event in timeline_events if event.activity != 'gap']
        
        if not real_events:
            return {}
        
        # Time analysis
        timestamps = [event.timestamp for event in real_events]
        time_span = max(timestamps) - min(timestamps)
        
        # Location analysis
        locations = [event.location for event in real_events if event.location != 'UNKNOWN']
        location_counts = pd.Series(locations).value_counts().to_dict() if locations else {}
        
        # Activity analysis
        activities = [event.activity for event in real_events]
        activity_counts = pd.Series(activities).value_counts().to_dict()
        
        # Confidence analysis
        confidences = [event.confidence for event in real_events]
        
        # Source analysis
        all_sources = []
        for event in real_events:
            all_sources.extend(event.sources)
        source_counts = pd.Series(all_sources).value_counts().to_dict() if all_sources else {}
        
        # Gap analysis
        gap_events = [event for event in timeline_events if event.activity == 'gap']
        total_gap_time = sum([event.duration.total_seconds() for event in gap_events if event.duration], 0) / 3600  # hours
        
        return {
            'total_events': len(real_events),
            'time_span_hours': time_span.total_seconds() / 3600,
            'events_per_hour': len(real_events) / (time_span.total_seconds() / 3600) if time_span.total_seconds() > 0 else 0,
            'unique_locations': len(set(locations)),
            'location_distribution': location_counts,
            'activity_distribution': activity_counts,
            'average_confidence': np.mean(confidences) if confidences else 0,
            'confidence_std': np.std(confidences) if confidences else 0,
            'source_distribution': source_counts,
            'total_gaps': len(gap_events),
            'total_gap_hours': total_gap_time,
            'data_coverage': 1 - (total_gap_time / (time_span.total_seconds() / 3600)) if time_span.total_seconds() > 0 else 1
        }
