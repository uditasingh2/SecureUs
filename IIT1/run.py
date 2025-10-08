#!/usr/bin/env python3
"""
Campus Entity Resolution & Security Monitoring System
Main entry point for the application
"""
import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.main import app
import uvicorn
from src.config import API_CONFIG
from loguru import logger


def main():
    """Main entry point"""
    logger.info("Starting Campus Entity Resolution & Security Monitoring System")
    logger.info(f"API will be available at http://{API_CONFIG['host']}:{API_CONFIG['port']}")
    logger.info("Dashboard will be available at http://localhost:8000")
    
    try:
        uvicorn.run(
            "src.main:app",
            host=API_CONFIG['host'],
            port=API_CONFIG['port'],
            reload=API_CONFIG['debug'],
            log_level="info"
        )
    except KeyboardInterrupt:
        logger.info("System shutdown requested")
    except Exception as e:
        logger.error(f"System startup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
