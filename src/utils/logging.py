"""
Logging Configuration

Sets up centralized logging for the RKLLM server.

Log Format:
    YYYY-MM-DD HH:MM:SS - module_name - LEVEL - message

Log Levels:
    - DEBUG: Detailed diagnostic information
    - INFO: General operational messages
    - WARNING: Warning messages
    - ERROR: Error conditions
    - CRITICAL: Critical conditions

Usage:
    from src.utils.logging import setup_logging
    logger = setup_logging("info")
    logger.info("Server started")
"""

import logging

def setup_logging(level: str = "info"):
    """Configure logging for the server"""
    log_level = logging.DEBUG if level.lower() == "debug" else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger("rkllm-server")
