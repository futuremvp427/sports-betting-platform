"""Centralized logging configuration."""
import logging
import os
import sys
from datetime import datetime


def setup_logging(level: str = "INFO", log_dir: str = None) -> logging.Logger:
    """Configure and return the root logger for the platform."""
    if log_dir is None:
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f"platform_{datetime.now().strftime('%Y%m%d')}.log")

    formatter = logging.Formatter(
        "%(asctime)s | %(name)-25s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger("betting_platform")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger for a specific module."""
    return logging.getLogger(f"betting_platform.{name}")
