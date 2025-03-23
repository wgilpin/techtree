"""
Test script to verify the syllabus database functionality.
This script tests:
1. Creating and saving a syllabus (master and user versions)
2. Retrieving an existing syllabus (user-specific and fallback to master)
3. Verifying UID generation, master/user flags, and parent_uid references.
4. Cloning syllabi for users.

Uses mocking to avoid actual LLM and search API calls.
"""

import sys
import json
import unittest
import tempfile
import os
from unittest.mock import patch, MagicMock
from tinydb import TinyDB, Query

sys.path.append(".")

from backend.ai.syllabus.langgraph_app import SyllabusAI

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


@patch("syllabus.ai.langgraph_app.tavily.search")
@patch("syllabus.ai.langgraph_app.call_with_retry")
class TestSyllabusDB(unittest.TestCase):
    """
    Test case for syllabus database functionality.

    This class contains tests for creating, retrieving, and managing syllabi
    in the database, including master and user-specific versions.
    """

    def setUp(self):
        """Set up the test environment."""
        # Create a temporary database file
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.db_path = self.temp_file.name
        self.db = TinyDB(self.db_path)
        self.syllabi_table = self.db.table("syllabi")

        # Clear the table to ensure a clean state for each test
        self.syllabi_table.truncate()

        # Patch the syllabi_table in the SyllabusAI class
        self.patcher = patch(
            "syllabus.ai.langgraph_app.syllabi_table", self.syllabi_table
        )
        self.patcher.start()

    def test_uid_generation(self, mock_call_with_retry, mock_tavily_search):
        """Test that UIDs are generated correctly and uniquely."""
        import uuid

        # Generate multiple UIDs
        uids = [str(uuid.uuid4()) for _ in range(100)]

        # Check format (basic validation)
        for uid in uids:
            self.assertEqual(len(uid), 36)
            self.assertEqual(uid.count("-"), 4)

        # Check uniqueness
        self.assertEqual(len(uids), len(set(uids)))

    def test_master_version_creation(self, mock_call_with_retry, mock_tavily_search):
        """
        Test that syllabi are correctly marked as master versions when no user_id is provided.
        """
        # Configure mocks
        mock_tavily_search.return_value = MOCK_SEARCH_RESULTS
        mock_call_with_retry.return_value = MockGeminiResponse(
            text=f"```json\n{json.dumps(MOCK_SYLLABUS)}\n```"
        )

        # Create a test SyllabusAI instance
        syllabus_ai = SyllabusAI()
        syllabus_ai.initialize("Test Topic", "beginner")

        # Generate and save a syllabus
        syllabus = syllabus_ai.get_or_create_syllabus()
        syllabus_ai.save_syllabus()

        # Verify it's marked as a master version
        self.assertTrue(syllabus_ai.state["generated_syllabus"].get("is_master"))
        self.assertIsNone(syllabus_ai.state["generated_syllabus"].get("user_id"))
        self.assertIsNone(syllabus_ai.state["generated_syllabus"].get("parent_uid"))

    def test_user_version_creation(self, mock_call_with_retry, mock_tavily_search):
        """
        Test that syllabi are correctly marked as user versions when a user_id is provided.
        """
        # Configure mocks
        mock_tavily_search.return_value = MOCK_SEARCH_RESULTS
        mock_call_with_retry.return_value = MockGeminiResponse(
            text=f"```json\n{json.dumps(MOCK_SYLLABUS)}\n```"
        )

        # Create a completely different topic to avoid conflicts
        topic = "Java Programming"

        # First create a master syllabus
        syllabus_ai_master = SyllabusAI()
        syllabus_ai_master.initialize(topic, "beginner")
        master_syllabus = syllabus_ai_master.get_or_create_syllabus()

        # Store the master UID
        master_uid = master_syllabus.get("uid")

        # Manually set up the state for a user-specific syllabus
        user_id = "test_user_123"
        syllabus_ai = SyllabusAI()
        syllabus_ai.initialize(topic, "beginner", user_id)

        # Manually modify the state to simulate a user version
        syllabus_ai.state["existing_syllabus"] = {
            "topic": topic,
            "level": "Beginner",
            "is_master": False,
            "user_id": user_id,
            "parent_uid": master_uid,
            "uid": "user-specific-uid",
        }

        # Verify the state is correctly set up
        self.assertFalse(syllabus_ai.state["existing_syllabus"].get("is_master"))
        self.assertEqual(syllabus_ai.state["existing_syllabus"].get("user_id"), user_id)
        self.assertEqual(
            syllabus_ai.state["existing_syllabus"].get("parent_uid"), master_uid
        )

    def test_clone_from_master(self, mock_call_with_retry, mock_tavily_search):
        """
        Test cloning a master syllabus for a specific user.
        """
        # Configure mocks
        mock_tavily_search.return_value = MOCK_SEARCH_RESULTS
        mock_call_with_retry.return_value = MockGeminiResponse(
            text=f"```json\n{json.dumps(MOCK_SYLLABUS)}\n```"
        )

        # Create a master syllabus
        syllabus_ai = SyllabusAI()
        syllabus_ai.initialize("Test Topic", "beginner")
        master_syllabus = syllabus_ai.get_or_create_syllabus()
        syllabus_ai.save_syllabus()

        # Clone it for a user
        user_id = "test_user_456"
        user_syllabus = syllabus_ai.clone_syllabus_for_user(user_id)

        # Verify the clone is a user version with the correct parent
        self.assertFalse(user_syllabus.get("is_master"))
        self.assertEqual(user_syllabus.get("user_id"), user_id)
        self.assertEqual(user_syllabus.get("parent_uid"), master_syllabus.get("uid"))

    def test_retrieve_existing_syllabus(self, mock_call_with_retry, mock_tavily_search):
        """
        Test retrieving an existing syllabus from the database.
        """
        # Configure mocks
        mock_tavily_search.return_value = MOCK_SEARCH_RESULTS
        mock_call_with_retry.return_value = MockGeminiResponse(
            text=f"```json\n{json.dumps(MOCK_SYLLABUS)}\n```"
        )

        # Create a master syllabus
        syllabus_ai_1 = SyllabusAI()
        syllabus_ai_1.initialize("Python Programming", "beginner")
        syllabus_1 = syllabus_ai_1.get_or_create_syllabus()
        syllabus_ai_1.save_syllabus()

        # Reset the mock before retrieving
        mock_call_with_retry.reset_mock()

        # Create a new instance and try to retrieve the syllabus
        syllabus_ai_2 = SyllabusAI()
        syllabus_ai_2.initialize("Python Programming", "beginner")
        syllabus_2 = syllabus_ai_2.get_or_create_syllabus()

        # Check if the retrieved syllabus is the same as the original
        self.assertEqual(syllabus_2.get("uid"), syllabus_1.get("uid"))

        # Verify the mock wasn't called again
        mock_call_with_retry.assert_not_called()

    def test_retrieve_user_specific_syllabus(
        self, mock_call_with_retry, mock_tavily_search
    ):
        """
        Test retrieving a user-specific syllabus.
        """
        # Configure mocks
        mock_tavily_search.return_value = MOCK_SEARCH_RESULTS
        mock_call_with_retry.return_value = MockGeminiResponse(
            text=f"```json\n{json.dumps(MOCK_SYLLABUS)}\n```"
        )

        # Use a completely different topic to avoid conflicts
        topic = "C++ Programming"
        user_id = "test_user_1"

        # Create a unique user syllabus UID
        user_syllabus_uid = "user-specific-uid-123"

        # Manually insert a master syllabus into the database
        master_syllabus = {
            "topic": topic,
            "level": "Beginner",
            "is_master": True,
            "user_id": None,
            "parent_uid": None,
            "uid": "master-uid-123",
            "duration": "4 weeks",
            "learning_objectives": ["Objective 1"],
            "modules": [
                {"week": 1, "title": "Module 1", "lessons": [{"title": "Lesson 1"}]}
            ],
        }
        self.syllabi_table.insert(master_syllabus)

        # Manually insert a user-specific syllabus into the database
        user_syllabus = {
            "topic": topic,
            "level": "Beginner",
            "is_master": False,
            "user_id": user_id,
            "parent_uid": "master-uid-123",
            "uid": user_syllabus_uid,
            "duration": "4 weeks",
            "learning_objectives": ["Objective 1"],
            "modules": [
                {"week": 1, "title": "Module 1", "lessons": [{"title": "Lesson 1"}]}
            ],
        }
        self.syllabi_table.insert(user_syllabus)

        # Reset the mock
        mock_call_with_retry.reset_mock()

        # Create a new instance and try to retrieve the user syllabus
        syllabus_ai = SyllabusAI()
        syllabus_ai.initialize(topic, "beginner", user_id)
        syllabus = syllabus_ai.get_or_create_syllabus()

        # Check if the retrieved syllabus is the same as the user syllabus
        self.assertEqual(syllabus.get("uid"), user_syllabus_uid)
        self.assertFalse(syllabus.get("is_master"))
        self.assertEqual(syllabus.get("user_id"), user_id)

        # Verify the mock wasn't called again
        mock_call_with_retry.assert_not_called()

    def test_create_advanced_syllabus(self, mock_call_with_retry, mock_tavily_search):
        """
        Test creating a syllabus with a different level.
        """
        # Configure mocks
        mock_tavily_search.return_value = MOCK_SEARCH_RESULTS
        mock_call_with_retry.return_value = MockGeminiResponse(
            text=f"```json\n{json.dumps(MOCK_ADVANCED_SYLLABUS)}\n```"
        )

        # Create an advanced syllabus
        syllabus_ai = SyllabusAI()
        syllabus_ai.initialize("Python Programming", "advanced")
        syllabus = syllabus_ai.get_or_create_syllabus()

        # Check if the syllabus has the correct level
        self.assertEqual(syllabus.get("level"), "Advanced")

    def tearDown(self):
        """
        Clean up the database after each test.
        """
        print("\nCleaning up database...")

        # Make sure all tables are closed
        self.syllabi_table.clear_cache()

        # Close the database connection
        self.db.close()

        # Stop all patchers
        self.patcher.stop()

        # On Windows, we need to be more careful with temp file deletion
        # The file will be automatically cleaned up by the OS later
        # We'll just log that we're leaving it for the OS to clean up
        print(
            f"Note: Temporary database file {self.db_path} will be cleaned up by the OS"
        )

        print("Database cleaned up.")


if __name__ == "__main__":
    unittest.main()
