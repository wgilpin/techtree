import os
import sys
import unittest
from backend.services.sqlite_db import SQLiteDatabaseService

class TestSQLiteDatabaseService(unittest.TestCase):
    """
    Test cases for the SQLiteDatabaseService class.
    """

    @classmethod
    def setUpClass(cls):
        """Ensure the test database file does not exist before tests."""
        if os.path.exists("test_techtree.db"):
            os.remove("test_techtree.db")

    def setUp(self):
        """
        Set up the test environment before each test.
        Creates a new DB service instance and ensures tables are created.
        """
        # Use a test database file
        self.db_service = SQLiteDatabaseService("test_techtree.db")
        # Ensure tables are created if the file was just created
        self.db_service._create_tables() # Explicitly create tables

    def tearDown(self):
        """
        Clean up after each test. Closes connection and removes the DB file.
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

        # Save lesson content (this implicitly tests parts of the ID logic)
        self.db_service.save_lesson_content(syllabus_id, 0, 0, lesson_content)

        # Retrieve the lesson content
        retrieved_content = self.db_service.get_lesson_content(syllabus_id, 0, 0)

        # Verify the lesson content was retrieved correctly
        self.assertIsNotNone(retrieved_content)
        self.assertEqual(retrieved_content, lesson_content)

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

        # Get the actual lesson_id after saving the syllabus
        lesson_id = self.db_service.get_lesson_id(syllabus_id, 0, 0)
        self.assertIsNotNone(lesson_id, "Lesson ID should be retrievable after saving syllabus")

        # Save user progress using the retrieved lesson_id
        progress_id = self.db_service.save_user_progress(
            user_id=user_id,
            syllabus_id=syllabus_id,
            module_index=0,
            lesson_index=0,
            status="in_progress",
            lesson_id=lesson_id # Pass the actual lesson_id
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
        self.assertEqual(progress[0]["lesson_id"], lesson_id) # Verify lesson_id was saved

    def test_get_lesson_id(self):
        """
        Test retrieving the lesson ID using syllabus_id, module_index, and lesson_index.
        """
        # 1. Create a syllabus with modules and lessons
        topic = "Advanced SQL"
        level = "Intermediate"
        content = {
            "modules": [
                { # Module 0
                    "title": "Window Functions",
                    "lessons": [
                        {"title": "ROW_NUMBER", "duration": "15m"}, # Lesson 0.0
                        {"title": "RANK/DENSE_RANK", "duration": "20m"} # Lesson 0.1
                    ]
                },
                { # Module 1
                    "title": "Common Table Expressions (CTEs)",
                    "lessons": [
                        {"title": "Basic CTEs", "duration": "25m"} # Lesson 1.0
                    ]
                }
            ]
        }
        syllabus_id = self.db_service.save_syllabus(topic, level, content)
        self.assertIsNotNone(syllabus_id)

        # 2. Test retrieving existing lesson IDs
        lesson_id_0_0 = self.db_service.get_lesson_id(syllabus_id, 0, 0)
        self.assertIsNotNone(lesson_id_0_0)
        self.assertIsInstance(lesson_id_0_0, int)

        lesson_id_0_1 = self.db_service.get_lesson_id(syllabus_id, 0, 1)
        self.assertIsNotNone(lesson_id_0_1)
        self.assertIsInstance(lesson_id_0_1, int)
        self.assertNotEqual(lesson_id_0_0, lesson_id_0_1) # Ensure IDs are unique

        lesson_id_1_0 = self.db_service.get_lesson_id(syllabus_id, 1, 0)
        self.assertIsNotNone(lesson_id_1_0)
        self.assertIsInstance(lesson_id_1_0, int)
        self.assertNotEqual(lesson_id_1_0, lesson_id_0_0)
        self.assertNotEqual(lesson_id_1_0, lesson_id_0_1)

        # 3. Test edge cases
        # Non-existent syllabus ID
        non_existent_syllabus_id = "invalid-syllabus-id"
        self.assertIsNone(self.db_service.get_lesson_id(non_existent_syllabus_id, 0, 0))

        # Non-existent module index
        self.assertIsNone(self.db_service.get_lesson_id(syllabus_id, 99, 0))

        # Non-existent lesson index
        self.assertIsNone(self.db_service.get_lesson_id(syllabus_id, 0, 99))


if __name__ == "__main__":
    # Ensure the script can find the backend package
    # Get the absolute path of the project root directory
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    # Add the project root to the Python path
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    unittest.main()