#!/usr/bin/env python3
"""
Syllabus Demo for TechTree
"""

import os
import sys
from dotenv import load_dotenv

# Add the current directory to the path so we can import the syllabus package
sys.path.append(".")

# Load environment variables
load_dotenv()

# Import the syllabus packages
from syllabus.streamlit_app.app import run_app

if __name__ == "__main__":
    run_app()