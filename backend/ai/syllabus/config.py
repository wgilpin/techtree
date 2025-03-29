"""Configuration for syllabus generation external APIs."""
#pylint: disable=broad-exception-caught

import os
import google.generativeai as genai
from dotenv import load_dotenv
from tavily import TavilyClient # type: ignore
from typing import Optional # Import Optional
from backend.logger import logger # Import logger

# Load environment variables
load_dotenv()

# Define type hints before assignment
MODEL: Optional[genai.GenerativeModel] = None
TAVILY: Optional[TavilyClient] = None

# Configure Gemini API
try:
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    gemini_model_name = os.environ.get("GEMINI_MODEL")
    if not gemini_api_key:
        logger.error("Missing environment variable: GEMINI_API_KEY")
        raise KeyError("GEMINI_API_KEY")
    if not gemini_model_name:
        logger.error("Missing environment variable: GEMINI_MODEL")
        raise KeyError("GEMINI_MODEL")

    genai.configure(api_key=gemini_api_key)
    MODEL = genai.GenerativeModel(gemini_model_name)
    logger.info(f"Syllabus Config: Gemini model '{gemini_model_name}' configured.")
except KeyError as e:
    logger.error(f"Syllabus Config: Gemini configuration failed due to missing env var: {e}")
    MODEL = None
except Exception as e:
    logger.error(f"Syllabus Config: Error configuring Gemini: {e}", exc_info=True)
    MODEL = None

# Configure Tavily API
try:
    tavily_api_key = os.environ.get("TAVILY_API_KEY")
    if not tavily_api_key:
         logger.warning("Missing environment variable TAVILY_API_KEY. Tavily search disabled.")
    else:
        TAVILY = TavilyClient(api_key=tavily_api_key)
        logger.info("Syllabus Config: Tavily client configured.")
except Exception as e:
    logger.error(f"Syllabus Config: Error configuring Tavily: {e}", exc_info=True)
    TAVILY = None
