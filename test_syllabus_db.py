"""
Test script to verify the syllabus database functionality.
This script tests:
1. Creating and saving a syllabus
2. Retrieving an existing syllabus with the same topic and level
3. Verifying that a syllabus with the same topic but different level is not found
4. Verifying that retrieving the same syllabus again loads it from the database, not recreates it

Uses mocking to avoid actual LLM and search API calls.
"""

import sys
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.append(".")

from syllabus.ai.langgraph_app import SyllabusAI, call_with_retry

# Mock data for tests
MOCK_SYLLABUS = {
    "topic": "Python Programming",
    "level": "Beginner",
    "duration": "4 weeks",
    "learning_objectives": [
        "Understand basic Python syntax",
        "Learn about variables, data types, and control structures",
        "Create simple Python programs",
    ],
    "modules": [
        {
            "week": 1,
            "title": "Introduction to Python",
            "lessons": [
                {"title": "Setting up Python environment"},
                {"title": "Basic syntax and data types"},
            ],
        },
        {
            "week": 2,
            "title": "Control Structures",
            "lessons": [
                {"title": "Conditional statements"},
                {"title": "Loops and iterations"},
            ],
        },
    ],
}

MOCK_ADVANCED_SYLLABUS = {
    "topic": "Python Programming",
    "level": "Advanced",
    "duration": "6 weeks",
    "learning_objectives": [
        "Master advanced Python concepts",
        "Understand concurrency and parallelism",
        "Implement design patterns in Python",
    ],
    "modules": [
        {
            "week": 1,
            "title": "Advanced Python Concepts",
            "lessons": [
                {"title": "Decorators and metaclasses"},
                {"title": "Context managers"},
            ],
        },
        {
            "week": 2,
            "title": "Concurrency",
            "lessons": [
                {"title": "Threading and multiprocessing"},
                {"title": "Asyncio"},
            ],
        },
    ],
}


# Mock response for Gemini API
class MockGeminiResponse:
    def __init__(self, text):
        self.text = text


# Mock response for Tavily API
MOCK_SEARCH_RESULTS = {
    "results": [
        {"content": "Python is a high-level programming language."},
        {"content": "Python is widely used in data science and web development."},
    ]
}


class TestSyllabusDB(unittest.TestCase):
    """Test case for syllabus database functionality."""

    @patch("syllabus.ai.langgraph_app.tavily.search")
    @patch("syllabus.ai.langgraph_app.call_with_retry")
    def test_syllabus_db(self, mock_call_with_retry, mock_tavily_search):
        """Test the syllabus database functionality with mocks."""
        print("Starting syllabus database test...")

        # Configure mocks
        mock_tavily_search.return_value = MOCK_SEARCH_RESULTS

        # Mock the Gemini API response
        mock_call_with_retry.return_value = MockGeminiResponse(
            text=f"```json\n{json.dumps(MOCK_SYLLABUS)}\n```"
        )

        # Test data
        test_topic = "Python Programming"
        test_level_1 = "beginner"
        test_level_2 = "advanced"

        # Create first syllabus (beginner level)
        print(f"\nCreating syllabus for {test_topic} at {test_level_1} level...")
        syllabus_ai_1 = SyllabusAI()
        syllabus_ai_1.initialize(test_topic, test_level_1)

        # Generate and save the syllabus
        syllabus_1 = syllabus_ai_1.get_or_create_syllabus()
        print(f"Generated syllabus: {syllabus_1['topic']} - {syllabus_1['level']}")
        syllabus_ai_1.save_syllabus()
        print("Syllabus saved to database.")

        # Create a new instance and try to retrieve the same syllabus
        print(
            f"\nTrying to retrieve syllabus for {test_topic} at {test_level_1} level..."
        )
        syllabus_ai_2 = SyllabusAI()
        syllabus_ai_2.initialize(test_topic, test_level_1)
        syllabus_2 = syllabus_ai_2.get_or_create_syllabus()

        # Check if the retrieved syllabus is the same as the one we created
        is_existing = syllabus_ai_2.state["existing_syllabus"] is not None
        self.assertTrue(is_existing, "Should retrieve existing syllabus from database")
        if is_existing:
            print("SUCCESS: Retrieved existing syllabus from database.")
            print(f"Retrieved syllabus: {syllabus_2['topic']} - {syllabus_2['level']}")

        # Test retrieving the syllabus again to ensure it's loaded from the database
        print(
            f"\nTrying to retrieve syllabus again for {test_topic} at {test_level_1} level..."
        )
        syllabus_ai_4 = SyllabusAI()
        syllabus_ai_4.initialize(test_topic, test_level_1)
        syllabus_4 = syllabus_ai_4.get_or_create_syllabus()

        # Check if the syllabus was loaded from the database
        is_existing = syllabus_ai_4.state["existing_syllabus"] is not None
        self.assertTrue(is_existing, "Should retrieve existing syllabus from database")
        mock_call_with_retry.assert_not_called()
        if is_existing:
            print("SUCCESS: Retrieved existing syllabus from database (again).")
            print(f"Retrieved syllabus: {syllabus_4['topic']} - {syllabus_4['level']}")

        # Update mock for advanced syllabus
        mock_call_with_retry.return_value = MockGeminiResponse(
            text=f"```json\n{json.dumps(MOCK_ADVANCED_SYLLABUS)}\n```"
        )

        # Try to retrieve a syllabus with the same topic but different level
        print(
            f"\nTrying to retrieve syllabus for {test_topic} at {test_level_2} level..."
        )
        syllabus_ai_3 = SyllabusAI()
        syllabus_ai_3.initialize(test_topic, test_level_2)
        syllabus_3 = syllabus_ai_3.get_or_create_syllabus()

        # Check if a new syllabus was created (should not find existing one)
        is_existing = syllabus_ai_3.state["existing_syllabus"] is not None
        self.assertFalse(
            is_existing, "Should not find existing syllabus for different level"
        )
        if not is_existing:
            print(
                "SUCCESS: No existing syllabus found for different level, new one created."
            )
            print(f"New syllabus: {syllabus_3['topic']} - {syllabus_3['level']}")

        print("\nTest completed.")

    def tearDown(self):
        """Clean up the database after each test."""
        print("\nCleaning up database...")
        # Delete the created syllabus entries
        syllabus_ai_1 = SyllabusAI()
        syllabus_ai_1.initialize("Python Programming", "beginner")
        syllabus_ai_1.delete_syllabus()
        syllabus_ai_2 = SyllabusAI()
        syllabus_ai_2.initialize("Python Programming", "advanced")
        syllabus_ai_2.delete_syllabus()
        print("Database cleaned up.")


if __name__ == "__main__":
    unittest.main()
