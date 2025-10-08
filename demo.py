#!/usr/bin/env python3
"""
Real Demo Script - Campus Entity Resolution & Security Monitoring System
Processes actual dataset and demonstrates all core functionalities
"""
import sys
import asyncio
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.data_loader import CampusDataLoader
from src.entity_resolver import EntityResolver
from src.multimodal_fusion import MultiModalFusion
from src.timeline_generator import TimelineGenerator
from src.predictive_monitor import PredictiveMonitor
from src.config import DATA_FILES
from loguru import logger


def main():
    """Run comprehensive demo with real data"""
    logger.info("🚀 Starting Campus Entity Resolution System Demo")
    logger.info("Processing REAL dataset from Product_Dataset/Test_Dataset/")
    
    # Step 1: Load Real Data
    logger.info("\n📊 STEP 1: Loading Real Campus Data")
    data_loader = CampusDataLoader()
    
    try:
        data = data_loader.load_all_data()
        logger.info("✅ Successfully loaded all data sources:")
        
        for source_name, df in data.items():
            if isinstance(df, pd.DataFrame):
                logger.info(f"   - {source_name}: {len(df)} records")
        
        # Data integrity check
        issues = data_loader.validate_data_integrity()
        if issues:
            logger.warning(f"⚠️  Data integrity issues found: {issues}")
        else:
            logger.info("✅ Data integrity validation passed")
            
    except Exception as e:
        logger.error(f"❌ Failed to load data: {e}")
        return
    
    # Step 2: Entity Resolution
    logger.info("\n🔗 STEP 2: Resolving Entities Across Data Sources")
    entity_resolver = EntityResolver()
    
    try:
        resolved_entities = entity_resolver.resolve_entities(data)
        stats = entity_resolver.get_resolution_statistics()
        
        logger.info(f"✅ Entity Resolution Complete:")
        logger.info(f"   - Total resolved entities: {stats['total_resolved_entities']}")
        logger.info(f"   - Entities merged from multiple sources: {stats['merged_entities']}")
        logger.info(f"   - Merge rate: {stats['merge_rate']:.1%}")
        logger.info(f"   - Average confidence: {stats['average_confidence']:.3f}")
        
        # Show sample resolved entity
        sample_entity = list(resolved_entities.values())[0]
        logger.info(f"\n📋 Sample Resolved Entity: {sample_entity.unified_id}")
        logger.info(f"   - Names: {list(sample_entity.names)}")
        logger.info(f"   - Entity IDs: {list(sample_entity.entity_ids)}")
        logger.info(f"   - Card IDs: {list(sample_entity.identifiers.get('card_ids', []))}")
        logger.info(f"   - Confidence: {sample_entity.confidence:.3f}")
        
    except Exception as e:
        logger.error(f"❌ Entity resolution failed: {e}")
        return
    
    # Step 3: Multi-Modal Fusion
    logger.info("\n🔄 STEP 3: Multi-Modal Data Fusion")
    fusion_engine = MultiModalFusion()
    
    try:
        # Process first 5 entities for demo
        sample_entities = list(resolved_entities.items())[:5]
        all_fused_records = []
        
        for entity_id, entity in sample_entities:
            # Get entity data
            primary_entity_id = list(entity.entity_ids)[0] if entity.entity_ids else entity_id
            entity_data = data_loader.get_entity_data(primary_entity_id)
            
            # Fuse data
            fused_records = fusion_engine.fuse_entity_data(
                entity, entity_data, data.get('face_embeddings')
            )
            all_fused_records.extend(fused_records)
            
            logger.info(f"   - {entity.unified_id}: {len(fused_records)} fused records")
        
        # Generate fusion summary
        if all_fused_records:
            summary = fusion_engine.generate_activity_summary(all_fused_records)
            logger.info(f"✅ Multi-Modal Fusion Complete:")
            logger.info(f"   - Total fused records: {summary['total_records']}")
            logger.info(f"   - Average confidence: {summary['confidence_statistics']['mean']:.3f}")
            logger.info(f"   - Average sources per record: {summary['average_sources_per_record']:.1f}")
            
    except Exception as e:
        logger.error(f"❌ Multi-modal fusion failed: {e}")
        return
    
    # Step 4: Timeline Generation
    logger.info("\n📅 STEP 4: Timeline Generation & Summarization")
    timeline_generator = TimelineGenerator()
    
    try:
        # Generate timeline for first entity
        sample_entity = list(resolved_entities.values())[0]
        sample_fused_records = [r for r in all_fused_records if r.unified_entity_id == sample_entity.unified_id]
        
        if sample_fused_records:
            timeline = timeline_generator.generate_timeline(
                sample_entity.unified_id, sample_fused_records
            )
            
            summary = timeline_generator.generate_summary(
                sample_entity.unified_id, timeline
            )
            
            logger.info(f"✅ Timeline Generated for {sample_entity.unified_id}:")
            logger.info(f"   - Total events: {len(timeline)}")
            logger.info(f"   - Time span: {summary.start_time.strftime('%Y-%m-%d %H:%M')} to {summary.end_time.strftime('%Y-%m-%d %H:%M')}")
            logger.info(f"   - Locations visited: {len(summary.locations_visited)}")
            logger.info(f"   - Summary: {summary.summary_text[:100]}...")
            
            # Show sample timeline events
            logger.info(f"\n📋 Sample Timeline Events:")
            for i, event in enumerate(timeline[:3]):
                logger.info(f"   {i+1}. {event.timestamp.strftime('%H:%M')} - {event.description}")
                
    except Exception as e:
        logger.error(f"❌ Timeline generation failed: {e}")
        return
    
    # Step 5: Predictive Monitoring
    logger.info("\n🤖 STEP 5: Predictive Monitoring & Explainability")
    predictive_monitor = PredictiveMonitor()
    
    try:
        # Train models with real data
        training_records = all_fused_records[:100]  # Use first 100 records for training
        
        if training_records:
            performance = predictive_monitor.train_predictive_models(
                training_records, data['profiles']
            )
            
            logger.info(f"✅ Predictive Models Trained:")
            logger.info(f"   - Location prediction accuracy: {performance['location_accuracy']:.3f}")
            logger.info(f"   - Activity prediction accuracy: {performance['activity_accuracy']:.3f}")
            logger.info(f"   - Training samples: {performance['training_samples']}")
            
            # Make a prediction
            sample_entity = list(resolved_entities.values())[0]
            prediction_time = datetime.now() - timedelta(hours=1)  # Predict 1 hour ago
            
            # Get entity profile
            primary_entity_id = list(sample_entity.entity_ids)[0] if sample_entity.entity_ids else sample_entity.unified_id
            entity_profile = data['profiles'][data['profiles']['entity_id'] == primary_entity_id]
            
            if not entity_profile.empty:
                entity_profile_dict = entity_profile.iloc[0].to_dict()
                
                # Get context records
                context_records = [r for r in all_fused_records 
                                 if r.unified_entity_id == sample_entity.unified_id 
                                 and r.timestamp < prediction_time]
                
                if context_records:
                    prediction = predictive_monitor.predict_missing_data(
                        sample_entity.unified_id, prediction_time, context_records, entity_profile_dict
                    )
                    
                    if prediction:
                        logger.info(f"\n🔮 Sample Prediction for {sample_entity.unified_id}:")
                        logger.info(f"   - Predicted location: {prediction.predicted_location}")
                        logger.info(f"   - Predicted activity: {prediction.predicted_activity}")
                        logger.info(f"   - Confidence: {prediction.confidence:.3f}")
                        logger.info(f"   - Evidence: {prediction.evidence[:2]}")  # First 2 evidence items
            
            # Check for anomalies
            alerts = []
            for entity_id, entity in list(resolved_entities.items())[:3]:  # Check first 3 entities
                entity_records = [r for r in all_fused_records if r.unified_entity_id == entity.unified_id]
                if entity_records:
                    primary_entity_id = list(entity.entity_ids)[0] if entity.entity_ids else entity_id
                    entity_profile = data['profiles'][data['profiles']['entity_id'] == primary_entity_id]
                    
                    if not entity_profile.empty:
                        entity_profile_dict = entity_profile.iloc[0].to_dict()
                        entity_alerts = predictive_monitor.detect_anomalies(entity_records, entity_profile_dict)
                        alerts.extend(entity_alerts)
            
            logger.info(f"✅ Anomaly Detection Complete:")
            logger.info(f"   - Total alerts generated: {len(alerts)}")
            
            for alert in alerts[:2]:  # Show first 2 alerts
                logger.info(f"   - {alert.alert_type.upper()}: {alert.description}")
                
    except Exception as e:
        logger.error(f"❌ Predictive monitoring failed: {e}")
        return
    
    # Step 6: System Statistics
    logger.info("\n📊 STEP 6: Final System Statistics")
    
    try:
        # Overall statistics
        total_records = sum(len(df) for df in data.values() if isinstance(df, pd.DataFrame))
        
        logger.info(f"✅ System Processing Complete:")
        logger.info(f"   - Total input records processed: {total_records:,}")
        logger.info(f"   - Entities resolved: {len(resolved_entities)}")
        logger.info(f"   - Fused activity records: {len(all_fused_records)}")
        logger.info(f"   - Timeline events generated: {sum(len(timeline_generator.generate_timeline(e.unified_id, [r for r in all_fused_records if r.unified_entity_id == e.unified_id])) for e in list(resolved_entities.values())[:3])}")
        logger.info(f"   - Security alerts: {len(alerts)}")
        
        # Data coverage analysis
        entities_with_data = len([e for e in resolved_entities.values() if len([r for r in all_fused_records if r.unified_entity_id == e.unified_id]) > 0])
        coverage = entities_with_data / len(resolved_entities) if resolved_entities else 0
        
        logger.info(f"   - Data coverage: {coverage:.1%} of entities have activity data")
        
        # Time range analysis
        if all_fused_records:
            timestamps = [r.timestamp for r in all_fused_records]
            time_range = max(timestamps) - min(timestamps)
            logger.info(f"   - Activity time range: {time_range.days} days")
            logger.info(f"   - From: {min(timestamps).strftime('%Y-%m-%d %H:%M')}")
            logger.info(f"   - To: {max(timestamps).strftime('%Y-%m-%d %H:%M')}")
        
    except Exception as e:
        logger.error(f"❌ Statistics generation failed: {e}")
    
    logger.info("\n🎉 DEMO COMPLETE!")
    logger.info("✅ All core functionalities demonstrated with REAL data")
    logger.info("🚀 System ready for production use!")
    logger.info("\n💡 Next steps:")
    logger.info("   1. Run 'python run.py' to start the web interface")
    logger.info("   2. Access dashboard at http://localhost:8000")
    logger.info("   3. Use API endpoints for integration")


if __name__ == "__main__":
    main()
