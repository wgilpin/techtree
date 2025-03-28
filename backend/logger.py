import logging
import sys
import os

# Define log file path relative to this file's directory
log_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Project root
log_file_path = os.path.join(log_dir, "techtree.log")

# Get the root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG) # Set the desired level on the root logger

# Create formatter
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Check if handlers are already configured to avoid duplicates
if not any(isinstance(h, logging.FileHandler) and h.baseFilename == log_file_path for h in root_logger.handlers):
    # Create file handler
    file_handler = logging.FileHandler(log_file_path, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG) # Set level on the handler
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

# Optional: Add a StreamHandler to see logs in console as well (useful for debugging startup)
# if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
#     stream_handler = logging.StreamHandler(sys.stdout)
#     stream_handler.setLevel(logging.INFO) # Or DEBUG
#     stream_handler.setFormatter(formatter)
#     root_logger.addHandler(stream_handler)

# Get logger for the current module
logger = logging.getLogger(__name__)
logger.info(f"Logging configured. Log file: {log_file_path}") # Use info level for confirmation
logger.debug(f"sys.prefix: {sys.prefix}")
logger.debug(f"sys.real_prefix: {getattr(sys, 'real_prefix', 'Not present')}")
