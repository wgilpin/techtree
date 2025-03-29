"""Configuration for syllabus generation external APIs."""
#pylint: disable=broad-exception-caught

import os
import google.generativeai as genai
from dotenv import load_dotenv
from tavily import TavilyClient

# Load environment variables
load_dotenv()

# Configure Gemini API
try:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    MODEL = genai.GenerativeModel(os.environ["GEMINI_MODEL"])
except KeyError as e:
    print(f"Error: Missing environment variable for Gemini configuration: {e}")
    MODEL = None  # Indicate failure
except Exception as e:
    print(f"Error configuring Gemini: {e}")
    MODEL = None

# Configure Tavily API
try:
    TAVILY = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
except KeyError as e:
    print(f"Error: Missing environment variable for Tavily configuration: {e}")
    TAVILY = None  # Indicate failure
except Exception as e:
    print(f"Error configuring Tavily: {e}")
    TAVILY = None
