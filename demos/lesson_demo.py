#!/usr/bin/env python3
"""
Lesson Demo for TechTree
"""

import sys
from dotenv import load_dotenv

# Add the current directory to the path so we can import the lessons package
sys.path.append(".")

# Load environment variables
load_dotenv()

# Import the lessons packages
from lessons.streamlit_app.app import run_app

if __name__ == "__main__":
    run_app()