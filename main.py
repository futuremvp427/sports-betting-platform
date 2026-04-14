#!/usr/bin/env python3
"""
Sports Betting Intelligence Platform - Main Entry Point
Starts the FastAPI server with all endpoints.
"""
import os
import sys
import uvicorn

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings
from config.logging_config import setup_logging, get_logger
from storage.database import get_db

def main():
    """Initialize database and start the API server."""
    setup_logging()
    logger = get_logger("main")

    logger.info("=" * 60)
    logger.info("Sports Betting Intelligence Platform")
    logger.info("=" * 60)

    # Initialize database
    db = get_db()
    logger.info("Database initialized")

    # Start server
    host = settings.api.host
    port = settings.api.port
    logger.info(f"Starting API server on {host}:{port}")
    logger.info(f"API docs: http://{host}:{port}/docs")

    uvicorn.run(
        "api.app:app",
        host=host,
        port=port,
        reload=settings.api.debug,
        log_level="info",
    )


if __name__ == "__main__":
    main()
