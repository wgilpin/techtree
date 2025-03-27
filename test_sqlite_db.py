import os
import sys
import unittest
from backend.services.sqlite_db import SQLiteDatabaseService

class TestSQLiteDatabaseService(unittest.TestCase):
    """
    Test cases for the SQLiteDatabaseService class.
    """

    def setUp(self):
        """
        Set up the test environment.
        """
        # Use a test database file
        self.db_service = SQLiteDatabaseService("test_techtree.db")

    def tearDown(self):
        """
        Clean up after the tests.
        """
        self.db_service.close()

        # Remove the test database file
        if os.path.exists("test_techtree.db"):
            os.remove("test_techtree.db")

    def test_create_and_get_user(self):
        """
        Test creating a user and retrieving it by email.
        """
        # Create a test user
        email = "test@example.com"
        password_hash = "hashed_password"
        name = "Test User"

        user_id = self.db_service.create_user(email, password_hash, name)

        # Retrieve the user by email
        user = self.db_service.get_user_by_email(email)

        # Verify the user was created correctly
        self.assertIsNotNone(user)
        self.assertEqual(user["user_id"], user_id)
        self.assertEqual(user["email"], email)
        self.assertEqual(user["name"], name)
        self.assertEqual(user["password_hash"], password_hash)

    def test_create_and_get_syllabus(self):
        """
        Test creating a syllabus and retrieving it.
        """
        # Create a test syllabus
        topic = "Python Programming"
        level = "Beginner"
        content = {
            "title": "Python for Beginners",
            "description": "Learn Python programming from scratch",
            "modules": [
                {
                    "title": "Introduction to Python",
                    "summary": "Basic Python concepts",
                    "lessons": [
                        {
                            "title": "Getting Started",
                            "summary": "Setting up Python environment",
                            "duration": "30 minutes"
                        }
                    ]
                }
            ]
        }

        syllabus_id = self.db_service.save_syllabus(topic, level, content)

        # Retrieve the syllabus
        syllabus = self.db_service.get_syllabus_by_id(syllabus_id)

        # Verify the syllabus was created correctly
        self.assertIsNotNone(syllabus)
        self.assertEqual(syllabus["syllabus_id"], syllabus_id)
        self.assertEqual(syllabus["topic"], topic)
        self.assertEqual(syllabus["level"], level)
        self.assertIn("content", syllabus)
        self.assertIn("modules", syllabus["content"])
        self.assertEqual(len(syllabus["content"]["modules"]), 1)

    def test_save_and_get_lesson_content(self):
        """
        Test saving lesson content and retrieving it.
        """
        # Create a test syllabus
        topic = "Python Programming"
        level = "Beginner"
        content = {
            "title": "Python for Beginners",
            "description": "Learn Python programming from scratch",
            "modules": [
                {
                    "title": "Introduction to Python",
                    "summary": "Basic Python concepts",
                    "lessons": [
                        {
                            "title": "Getting Started",
                            "summary": "Setting up Python environment",
                            "duration": "30 minutes"
                        }
                    ]
                }
            ]
        }

        syllabus_id = self.db_service.save_syllabus(topic, level, content)

        # Create lesson content
        lesson_content = {
            "title": "Getting Started with Python",
            "content": "Python is a versatile programming language...",
            "exercises": [
                {
                    "question": "What is Python?",
                    "answer": "Python is a programming language"
                }
            ]
        }

        content_id = self.db_service.save_lesson_content(syllabus_id, 0, 0, lesson_content)

        # Retrieve the lesson content
        lesson = self.db_service.get_lesson_content(syllabus_id, 0, 0)

        # Verify the lesson content was retrieved correctly
        self.assertIsNotNone(lesson)
        # Assuming get_lesson_content returns the content dict directly
        self.assertEqual(lesson, lesson_content)

    def test_save_and_get_user_progress(self):
        """
        Test saving user progress and retrieving it.
        """
        # Create a test user
        email = "test@example.com"
        password_hash = "hashed_password"
        name = "Test User"
        user_id = self.db_service.create_user(email, password_hash, name)

        # Create a test syllabus
        topic = "Python Programming"
        level = "Beginner"
        content = {
            "title": "Python for Beginners",
            "description": "Learn Python programming from scratch",
            "modules": [
                {
                    "title": "Introduction to Python",
                    "summary": "Basic Python concepts",
                    "lessons": [
                        {
                            "title": "Getting Started",
                            "summary": "Setting up Python environment",
                            "duration": "30 minutes"
                        }
                    ]
                }
            ]
        }
        syllabus_id = self.db_service.save_syllabus(topic, level, content)

        # Save user progress
        progress_id = self.db_service.save_user_progress(
            user_id=user_id,
            syllabus_id=syllabus_id,
            module_index=0,
            lesson_index=0,
            status="in_progress"
        )

        # Retrieve user progress
        progress = self.db_service.get_user_syllabus_progress(user_id, syllabus_id)

        # Verify the progress was created correctly
        self.assertIsNotNone(progress)
        self.assertEqual(len(progress), 1)
        self.assertEqual(progress[0]["progress_id"], progress_id)
        self.assertEqual(progress[0]["user_id"], user_id)
        self.assertEqual(progress[0]["syllabus_id"], syllabus_id)
        self.assertEqual(progress[0]["module_index"], 0)
        self.assertEqual(progress[0]["lesson_index"], 0)
        self.assertEqual(progress[0]["status"], "in_progress")

if __name__ == "__main__":
    unittest.main()