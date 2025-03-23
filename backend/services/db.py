import os
import uuid
from datetime import datetime
from pathlib import Path

from tinydb import Query, TinyDB

"""
Module providing database services for the TechTree application.
"""

class DatabaseService:
    """
    Service class for interacting with the TinyDB database.
    """
    def __init__(self, db_path="techtree_db.json"):
        """
        Initializes the DatabaseService, connecting to the TinyDB database and creating tables.
        """
        try:
            # Always use the root directory techtree_db.json
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            abs_path = os.path.join(root_dir, "techtree_db.json")
            print(f"Using database at root directory: {abs_path}")

            # Ensure the directory exists
            db_dir = os.path.dirname(abs_path)
            Path(db_dir).mkdir(parents=True, exist_ok=True)

            # Check if file exists
            if not os.path.exists(abs_path):
                print(f"Database file does not exist, will be created at: {abs_path}")

            self.db = TinyDB(abs_path)
            print(f"TinyDB initialized at: {abs_path}")

            self.users = self.db.table("users")
            print("Created users table")
            self.assessments = self.db.table("user_assessments")
            print("Created assessments table")
            self.syllabi = self.db.table("syllabi")
            print("Created syllabi table")
            self.lesson_content = self.db.table("lesson_content")
            print("Created lesson_content table")
            self.user_progress = self.db.table("user_progress")
            print("Created user_progress table")
            self.User = Query()
            print("Created User query")

        except Exception as e:
            print(f"Error initializing database: {str(e)}")
            raise

    def get_all_table_data(self):
        """
        Retrieves all data from all tables in the database.

        Returns:
            dict: A dictionary containing all table data.
        """
        data = {}
        for table_name in self.db.tables():
            table = self.db.table(table_name)
            data[table_name] = table.all()
        return data

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
        try:
            print(f"Creating user with email: {email}, name: {name}")
            user_id = str(uuid.uuid4())
            now = datetime.now().isoformat()

            user = {
                "user_id": user_id,
                "email": email,
                "name": name or email.split("@")[0],
                "password_hash": password_hash,
                "created_at": now,
                "updated_at": now
            }

            print(f"User object created: {user}")
            self.users.insert(user)
            print(f"User inserted into database with ID: {user_id}")
            return user_id
        except Exception as e:
            print(f"Error creating user: {str(e)}")
            raise

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
        try:
            print(f"Looking up user by email: {email}")
            user = self.users.get(self.User.email == email)
            print(f"User lookup result: {user}")
            return user
        except Exception as e:
            print(f"Error looking up user by email: {str(e)}")
            raise

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
        try:
            print(f"Looking up user by ID: {user_id}")
            user = self.users.get(self.User.user_id == user_id)
            print(f"User lookup result: {user}")
            return user
        except Exception as e:
            print(f"Error looking up user by ID: {str(e)}")
            raise

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
        assessment_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        assessment = {
            "assessment_id": assessment_id,
            "user_id": user_id,
            "topic": topic,
            "knowledge_level": knowledge_level,
            "score": score,
            "question_history": questions,
            "response_history": responses,
            "created_at": now
        }

        self.assessments.insert(assessment)
        return assessment_id

    def get_user_assessments(self, user_id):
        """
        Retrieves all assessments for a given user.

        Args:
            user_id (str): The ID of the user.

        Returns:
            list: A list of assessment data.
        """
        return self.assessments.search(self.User.user_id == user_id)

    def get_assessment(self, assessment_id):
        """
        Retrieves a specific assessment by its ID.

        Args:
            assessment_id (str): The ID of the assessment.

        Returns:
            dict: The assessment data if found, otherwise None.
        """
        Assessment = Query()
        return self.assessments.get(Assessment.assessment_id == assessment_id)

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
        syllabus_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        syllabus = {
            "syllabus_id": syllabus_id,
            "user_id": user_id,
            "topic": topic,
            "level": level,
            "content": content,
            "created_at": now,
            "updated_at": now
        }

        self.syllabi.insert(syllabus)
        return syllabus_id

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
        Syllabus = Query()
        query = (Syllabus.topic == topic) & (Syllabus.level == level)

        if user_id:
            query = query & ((Syllabus.user_id == user_id) | (Syllabus.user_id == None))

        return self.syllabi.get(query)

    def get_syllabus_by_id(self, syllabus_id):
        """
        Retrieves a syllabus by its ID.

        Args:
            syllabus_id (str): The ID of the syllabus.

        Returns:
            dict: The syllabus data if found, otherwise None.
        """
        Syllabus = Query()
        return self.syllabi.get(Syllabus.syllabus_id == syllabus_id)

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
        lesson_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        lesson = {
            "lesson_id": lesson_id,
            "syllabus_id": syllabus_id,
            "module_index": module_index,
            "lesson_index": lesson_index,
            "content": content,
            "created_at": now,
            "updated_at": now
        }

        self.lesson_content.insert(lesson)
        return lesson_id

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
        Lesson = Query()
        return self.lesson_content.get(
            (Lesson.syllabus_id == syllabus_id) &
            (Lesson.module_index == module_index) &
            (Lesson.lesson_index == lesson_index)
        )

    def get_lesson_by_id(self, lesson_id):
        """
        Retrieves a lesson by its ID.

        Args:
            lesson_id (str): The ID of the lesson.

        Returns:
            dict: The lesson data if found, otherwise None.
        """
        Lesson = Query()
        return self.lesson_content.get(Lesson.lesson_id == lesson_id)

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
        progress_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        Progress = Query()
        existing = self.user_progress.get(
            (Progress.user_id == user_id) &
            (Progress.syllabus_id == syllabus_id) &
            (Progress.module_index == module_index) &
            (Progress.lesson_index == lesson_index)
        )

        if existing:
            self.user_progress.update({
                "status": status,
                "score": score,
                "updated_at": now
            },
            (Progress.user_id == user_id) &
            (Progress.syllabus_id == syllabus_id) &
            (Progress.module_index == module_index) &
            (Progress.lesson_index == lesson_index))

            return existing["progress_id"]

        progress = {
            "progress_id": progress_id,
            "user_id": user_id,
            "syllabus_id": syllabus_id,
            "module_index": module_index,
            "lesson_index": lesson_index,
            "status": status,  # "not_started", "in_progress", "completed"
            "score": score,
            "created_at": now,
            "updated_at": now
        }

        self.user_progress.insert(progress)
        return progress_id

    def get_user_syllabus_progress(self, user_id, syllabus_id):
        """
        Retrieves all progress entries for a user within a specific syllabus.

        Args:
            user_id (str): The ID of the user.
            syllabus_id (str): The ID of the syllabus.

        Returns:
            list: A list of progress entries.
        """
        Progress = Query()
        return self.user_progress.search(
            (Progress.user_id == user_id) &
            (Progress.syllabus_id == syllabus_id)
        )

    def get_user_in_progress_courses(self, user_id):
        """
        Retrieves a list of courses the user is currently in progress on, along with progress details.

        Args:
            user_id (str): The ID of the user.

        Returns:
            list: A list of dictionaries, each containing syllabus details and progress information.
        """
        Progress = Query()
        # Get unique syllabus_ids where the user has progress
        progress_entries = self.user_progress.search(Progress.user_id == user_id)

        # Extract unique syllabus_ids
        syllabus_ids = set(entry["syllabus_id"] for entry in progress_entries)

        # Get syllabus details for each syllabus_id
        in_progress_courses = []

        for syllabus_id in syllabus_ids:
            syllabus = self.get_syllabus_by_id(syllabus_id)
            if syllabus:
                # Calculate progress
                total_lessons = 0
                completed_lessons = 0

                for entry in progress_entries:
                    if entry["syllabus_id"] == syllabus_id:
                        total_lessons += 1
                        if entry["status"] == "completed":
                            completed_lessons += 1

                progress_percentage = (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0

                in_progress_courses.append({
                    "syllabus_id": syllabus_id,
                    "topic": syllabus["topic"],
                    "level": syllabus["level"],
                    "progress_percentage": progress_percentage,
                    "completed_lessons": completed_lessons,
                    "total_lessons": total_lessons
                })

        return in_progress_courses