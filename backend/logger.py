import logging
import sys

# Configure more verbose logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            "../techtree.log", mode="a", encoding="utf-8"
        )  # Log to root dir, append mode, USE UTF-8
    ],
)

logger = logging.getLogger(__name__)
logger.debug(f"sys.prefix: {sys.prefix}")
logger.debug(f"sys.real_prefix: {getattr(sys, 'real_prefix', 'Not present')}")
