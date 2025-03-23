from tinydb import TinyDB, Query
import uuid
from datetime import datetime
import os
from pathlib import Path

class DatabaseService:
    def __init__(self, db_path="techtree_db.json"):
        try:
            print(f"Initializing DatabaseService with db_path: {db_path}")

            # Always use the root directory techtree_db.json
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            abs_path = os.path.join(root_dir, "techtree_db.json")
            print(f"Using database at root directory: {abs_path}")

            # Ensure the directory exists
            db_dir = os.path.dirname(abs_path)
            print(f"Database directory: {db_dir}")
            Path(db_dir).mkdir(parents=True, exist_ok=True)
            print(f"Directory created/verified")

            # Check if file exists
            if os.path.exists(abs_path):
                print(f"Database file exists at: {abs_path}")
            else:
                print(f"Database file does not exist, will be created at: {abs_path}")

            self.db = TinyDB(abs_path)
            print(f"TinyDB initialized")

            self.users = self.db.table("users")
            self.assessments = self.db.table("user_assessments")
            self.syllabi = self.db.table("syllabi")
            self.lesson_content = self.db.table("lesson_content")
            self.user_progress = self.db.table("user_progress")
            self.User = Query()

            print(f"All tables initialized")
        except Exception as e:
            print(f"Error initializing database: {str(e)}")
            raise

    # User methods
    def create_user(self, email, password_hash, name=None):
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
        try:
            print(f"Looking up user by email: {email}")
            user = self.users.get(self.User.email == email)
            print(f"User lookup result: {user}")
            return user
        except Exception as e:
            print(f"Error looking up user by email: {str(e)}")
            raise

    def get_user_by_id(self, user_id):
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
        return self.assessments.search(self.User.user_id == user_id)

    def get_assessment(self, assessment_id):
        Assessment = Query()
        return self.assessments.get(Assessment.assessment_id == assessment_id)

    # Syllabus methods
    def save_syllabus(self, topic, level, content, user_id=None):
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
        Syllabus = Query()
        query = (Syllabus.topic == topic) & (Syllabus.level == level)

        if user_id:
            query = query & ((Syllabus.user_id == user_id) | (Syllabus.user_id == None))

        return self.syllabi.get(query)

    def get_syllabus_by_id(self, syllabus_id):
        Syllabus = Query()
        return self.syllabi.get(Syllabus.syllabus_id == syllabus_id)

    # Lesson content methods
    def save_lesson_content(self, syllabus_id, module_index, lesson_index, content):
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
        Lesson = Query()
        return self.lesson_content.get(
            (Lesson.syllabus_id == syllabus_id) &
            (Lesson.module_index == module_index) &
            (Lesson.lesson_index == lesson_index)
        )

    def get_lesson_by_id(self, lesson_id):
        Lesson = Query()
        return self.lesson_content.get(Lesson.lesson_id == lesson_id)

    # User progress methods
    def save_user_progress(self, user_id, syllabus_id, module_index, lesson_index, status, score=None):
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
        Progress = Query()
        return self.user_progress.search(
            (Progress.user_id == user_id) &
            (Progress.syllabus_id == syllabus_id)
        )

    def get_user_in_progress_courses(self, user_id):
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