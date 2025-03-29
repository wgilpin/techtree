"""Configures logging for the TechTree application.

Sets up a timed rotating file handler to manage log file size and retention.
Logs are written to 'techtree.log' in the project root directory.
"""

import logging
import logging.handlers # Import handlers module
import sys
import os

# Define log file path relative to this file's directory
# Assumes logger.py is in backend/, so two levels up gets the project root
log_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
log_file_path = os.path.join(log_dir, "techtree.log")

# Get the root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG) # Set the desired level on the root logger

# Create formatter
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Check if the specific TimedRotatingFileHandler is already configured
handler_exists = any(
    isinstance(h, logging.handlers.TimedRotatingFileHandler) and h.baseFilename == log_file_path
    for h in root_logger.handlers
)

if not handler_exists:
    # Create TimedRotatingFileHandler for daily rotation, keeping 7 backups
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file_path,
        when="D",        # Rotate interval: 'D' for daily
        interval=1,      # Interval multiplier: 1 day
        backupCount=7,   # Number of backup files to keep (7 days)
        encoding="utf-8",
        delay=True       # Defer file opening until first log message
    )
    file_handler.setLevel(logging.DEBUG) # Set level on the handler
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

# Optional: Add a StreamHandler to see logs in console as well (useful for debugging startup)
# stream_handler_exists = any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers)
# if not stream_handler_exists:
#     stream_handler = logging.StreamHandler(sys.stdout)
#     stream_handler.setLevel(logging.INFO) # Or DEBUG
#     stream_handler.setFormatter(formatter)
#     root_logger.addHandler(stream_handler)

# Get logger for the current module
logger = logging.getLogger(__name__)

# Log configuration confirmation only if the handler was newly added
if not handler_exists:
    logger.info(f"Logging configured with TimedRotatingFileHandler. Log file: {log_file_path}")
else:
    logger.debug("Logging handlers already configured.") # Use debug if already set up

logger.debug(f"sys.prefix: {sys.prefix}")
logger.debug(f"sys.real_prefix: {getattr(sys, 'real_prefix', 'Not present')}")
