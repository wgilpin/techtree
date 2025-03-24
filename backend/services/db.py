import os
import uuid
from datetime import datetime
from pathlib import Path

from backend.services.sqlite_db import SQLiteDatabaseService

"""
Module providing database services for the TechTree application.
"""

class DatabaseService(SQLiteDatabaseService):
    """
    Service class for interacting with the SQLite database.
    """
    def __init__(self, db_path="techtree.db"):
        """
        Initializes the DatabaseService, connecting to the SQLite database.
        """
        super().__init__(db_path)

    # User methods
    def create_user(self, email, password_hash, name=None):
        """
        Creates a new user in the database.

        Args:
            email (str): The user's email address.
            password_hash (str): The hashed password.
            name (str, optional): The user's name. Defaults to the email prefix if not provided.

        Returns:
            str: The newly created user's ID.

        Raises:
            Exception: If there is an error creating the user.
        """
        return super().create_user(email, password_hash, name)


    def get_user_by_email(self, email):
        """
        Retrieves a user from the database by their email address.

        Args:
            email (str): The email address of the user to retrieve.

        Returns:
            dict: The user data if found, otherwise None.

        Raises:
            Exception: If there is an error retrieving the user.
        """
        return super().get_user_by_email(email)


    def get_user_by_id(self, user_id):
        """
        Retrieves a user from the database by their user ID.

        Args:
            user_id (str): The ID of the user to retrieve.

        Returns:
            dict: The user data if found, otherwise None.

        Raises:
            Exception: If there is an error retrieving the user.
        """
        return super().get_user_by_id(user_id)

    # Assessment methods
    def save_assessment(self, user_id, topic, knowledge_level, score, questions, responses):
        """
        Saves a user's assessment data to the database.

        Args:
            user_id (str): The ID of the user taking the assessment.
            topic (str): The topic of the assessment.
            knowledge_level (str): The user's self-assessed knowledge level.
            score (float): The user's score on the assessment.
            questions (list): The list of questions asked.
            responses (list): The user's responses to the questions.

        Returns:
            str: The newly created assessment's ID.
        """
        return super().save_assessment(user_id, topic, knowledge_level, score, questions, responses)


    def get_user_assessments(self, user_id):
        """
        Retrieves all assessments for a given user.

        Args:
            user_id (str): The ID of the user.

        Returns:
            list: A list of assessment data.
        """
        return super().get_user_assessments(user_id)


    def get_assessment(self, assessment_id):
        """
        Retrieves a specific assessment by its ID.

        Args:
            assessment_id (str): The ID of the assessment.

        Returns:
            dict: The assessment data if found, otherwise None.
        """
        return super().get_assessment(assessment_id)

    # Syllabus methods
    def save_syllabus(self, topic, level, content, user_id=None):
        """
        Saves a syllabus to the database.

        Args:
            topic (str): The topic of the syllabus.
            level (str): The level of the syllabus.
            content (dict): The content of the syllabus.
            user_id (str, optional): The ID of the user creating the syllabus, if applicable.

        Returns:
            str: The newly created syllabus's ID.
        """
        return super().save_syllabus(topic, level, content, user_id)


    def get_syllabus(self, topic, level, user_id=None):
        """
        Retrieves a syllabus based on topic, level, and optionally user ID.

        Args:
            topic (str): The topic of the syllabus.
            level (str): The level of the syllabus.
            user_id (str, optional): The ID of the user, if retrieving a user-specific syllabus.

        Returns:
            dict: The syllabus data if found, otherwise None.
        """
        return super().get_syllabus(topic, level, user_id)


    def get_syllabus_by_id(self, syllabus_id):
        """
        Retrieves a syllabus by its ID.

        Args:
            syllabus_id (str): The ID of the syllabus.

        Returns:
            dict: The syllabus data if found, otherwise None.
        """
        return super().get_syllabus_by_id(syllabus_id)


    # Lesson content methods
    def save_lesson_content(self, syllabus_id, module_index, lesson_index, content):
        """
        Saves lesson content to the database.

        Args:
            syllabus_id (str): The ID of the syllabus the lesson belongs to.
            module_index (int): The index of the module within the syllabus.
            lesson_index (int): The index of the lesson within the module.
            content (dict): The content of the lesson.

        Returns:
            str: The newly created lesson's ID.
        """
        return super().save_lesson_content(syllabus_id, module_index, lesson_index, content)


    def get_lesson_content(self, syllabus_id, module_index, lesson_index):
        """
        Retrieves lesson content based on syllabus ID, module index, and lesson index.

        Args:
            syllabus_id (str): The ID of the syllabus.
            module_index (int): The index of the module.
            lesson_index (int): The index of the lesson.

        Returns:
            dict: The lesson content if found, otherwise None.
        """
        return super().get_lesson_content(syllabus_id, module_index, lesson_index)


    def get_lesson_by_id(self, lesson_id):
        """
        Retrieves a lesson by its ID.

        Args:
            lesson_id (str): The ID of the lesson.

        Returns:
            dict: The lesson data if found, otherwise None.
        """
        return super().get_lesson_by_id(lesson_id)

    # User progress methods
    def save_user_progress(self, user_id, syllabus_id, module_index, lesson_index, status, score=None):
        """
        Saves or updates user progress for a specific lesson.

        Args:
            user_id (str): The ID of the user.
            syllabus_id (str): The ID of the syllabus.
            module_index (int): The index of the module.
            lesson_index (int): The index of the lesson.
            status (str): The status of the lesson ("not_started", "in_progress", "completed").
            score (float, optional): The user's score for the lesson, if applicable.

        Returns:
            str: The ID of the progress entry.
        """
        return super().save_user_progress(user_id, syllabus_id, module_index, lesson_index, status, score)


    def get_user_syllabus_progress(self, user_id, syllabus_id):
        """
        Retrieves all progress entries for a user within a specific syllabus.

        Args:
            user_id (str): The ID of the user.
            syllabus_id (str): The ID of the syllabus.

        Returns:
            list: A list of progress entries.
        """
        return super().get_user_syllabus_progress(user_id, syllabus_id)


    def get_user_in_progress_courses(self, user_id):
        """
        Retrieves a list of courses the user is currently in progress on, along with progress details.

        Args:
            user_id (str): The ID of the user.

        Returns:
            list: A list of dictionaries, each containing syllabus details and progress information.
        """
        return super().get_user_in_progress_courses(user_id)