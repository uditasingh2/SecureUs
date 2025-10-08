#!/usr/bin/env python3
"""
System Test - Verify the system works with real data
"""
import sys
from pathlib import Path
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import DATA_FILES
from loguru import logger


def test_data_files():
    """Test if all data files exist and are readable"""
    logger.info("🔍 Testing data file accessibility...")
    
    missing_files = []
    readable_files = []
    
    for name, path in DATA_FILES.items():
        if path.exists():
            try:
                if name == 'face_images':
                    # Just check if zip file exists
                    readable_files.append(f"{name}: {path.stat().st_size / 1024 / 1024:.1f} MB")
                else:
                    df = pd.read_csv(path)
                    readable_files.append(f"{name}: {len(df)} records")
            except Exception as e:
                missing_files.append(f"{name}: Error reading - {e}")
        else:
            missing_files.append(f"{name}: File not found at {path}")
    
    logger.info("✅ Readable files:")
    for file_info in readable_files:
        logger.info(f"   - {file_info}")
    
    if missing_files:
        logger.error("❌ Missing/unreadable files:")
        for file_info in missing_files:
            logger.error(f"   - {file_info}")
        return False
    
    return True


def test_basic_functionality():
    """Test basic system functionality"""
    logger.info("🧪 Testing basic system functionality...")
    
    try:
        from src.data_loader import CampusDataLoader
        from src.entity_resolver import EntityResolver
        
        # Test data loading
        data_loader = CampusDataLoader()
        data = data_loader.load_all_data()
        
        logger.info(f"✅ Data loading successful: {len(data)} sources loaded")
        
        # Test entity resolution with small subset
        entity_resolver = EntityResolver()
        
        # Use only profiles for quick test
        test_data = {'profiles': data['profiles'].head(10)}  # First 10 records
        resolved_entities = entity_resolver.resolve_entities(test_data)
        
        logger.info(f"✅ Entity resolution successful: {len(resolved_entities)} entities resolved")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Basic functionality test failed: {e}")
        return False


def main():
    """Run system tests"""
    logger.info("🚀 Starting System Tests")
    
    # Test 1: Data files
    if not test_data_files():
        logger.error("❌ Data file test failed - check your dataset location")
        return
    
    # Test 2: Basic functionality
    if not test_basic_functionality():
        logger.error("❌ Basic functionality test failed")
        return
    
    logger.info("🎉 All tests passed!")
    logger.info("✅ System is ready to run")
    logger.info("\n💡 Next steps:")
    logger.info("   1. Run 'python demo.py' for full demonstration")
    logger.info("   2. Run 'python run.py' to start the web interface")


if __name__ == "__main__":
    main()
