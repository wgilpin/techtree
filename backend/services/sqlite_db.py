""" Sqlite database service """
import os
import uuid
import json
import sqlite3
from datetime import datetime
from pathlib import Path


class SQLiteDatabaseService:
    """
    Service class for interacting with the SQLite database.
    """

    def __init__(self, db_path="techtree.db"):
        """
        Initializes SQLiteDatabaseService, connecting to the SQLite database and creating tables.
        """
        try:
            # Always use the root directory for the database
            root_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            abs_path = os.path.join(root_dir, db_path)
            print(f"Using database at root directory: {abs_path}")

            # Ensure the directory exists
            db_dir = os.path.dirname(abs_path)
            Path(db_dir).mkdir(parents=True, exist_ok=True)

            # Check if file exists
            db_exists = os.path.exists(abs_path)
            if not db_exists:
                print(f"Database file does not exist, will be created at: {abs_path}")

            # Connect to the database with proper settings for concurrent access
            self.conn = sqlite3.connect(
                abs_path,
                check_same_thread=False,  # Allow access from multiple threads
                timeout=30.0,  # Set timeout for busy waiting
            )

            # Enable foreign keys
            self.conn.execute("PRAGMA foreign_keys = ON")

            # Enable WAL mode for better concurrency
            self.conn.execute("PRAGMA journal_mode = WAL")

            # Use Row factory for dict-like access to rows
            self.conn.row_factory = sqlite3.Row

            print(f"SQLite database initialized at: {abs_path}")

            # Create tables if they don't exist
            if not db_exists:
                self._create_tables()
                print("Database tables created")

        except Exception as e:
            print(f"Error initializing database: {str(e)}")
            raise

    def _create_tables(self):
        """
        Creates the database tables if they don't exist.
        """
        # Read the schema creation script
        schema_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "schema.sql"
        )

        with open(schema_path, "r", encoding="utf-8") as f:
            schema_script = f.read()

        # Execute the schema script
        self.conn.executescript(schema_script)
        self.conn.commit()

    def close(self):
        """
        Closes the database connection.
        """
        if self.conn:
            self.conn.close()
            print("Database connection closed")

    def execute_query(self, query, params=None, fetch_one=False, commit=False):
        """
        Executes a SQL query with error handling and optional commit.

        Args:
            query (str): The SQL query to execute
            params (tuple, optional): Parameters for the query
            fetch_one (bool): Whether to fetch one result or all results
            commit (bool): Whether to commit the transaction

        Returns:
            The query results, if any
        """
        try:
            cursor = self.conn.cursor()

            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            if commit:
                self.conn.commit()

            if fetch_one:
                return cursor.fetchone()
            else:
                return cursor.fetchall()

        except sqlite3.Error as e:
            print(f"Database error: {str(e)}")
            print(f"Query: {query}")
            print(f"Params: {params}")
            raise

    def execute_read_query(self, query, params=None):
        """
        Executes a read-only SQL query.

        Args:
            query (str): The SQL query to execute.
            params (tuple, optional): Parameters for the query.

        Returns:
            list: The query results.
        """
        return self.execute_query(query, params, fetch_one=False)

    def _transaction(self, func, *args, **kwargs):
        """
        Executes a function within a transaction.

        Args:
            func: The function to execute
            *args, **kwargs: Arguments to pass to the function

        Returns:
            The result of the function
        """
        try:
            with self.conn:  # This automatically handles BEGIN/COMMIT/ROLLBACK
                return func(*args, **kwargs)
        except Exception as e:
            print(f"Transaction error: {str(e)}")
            raise

    def get_all_table_data(self):
        """
        Retrieves all data from all tables in the database.

        Returns:
            dict: A dictionary containing all table data.
        """
        data = {}

        # Get list of tables
        tables_query = """SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'"""
        tables = self.execute_query(tables_query)

        for table in tables:
            table_name = table[0]
            data[table_name] = []

            # Get all rows from the table
            rows = self.execute_query(f"SELECT * FROM {table_name}")

            for row in rows:
                data[table_name].append(dict(row))

        return data

    # User methods
    def create_user(self, email, password_hash, name=None):
        """
        Creates a new user in the database.

        Args:
            email (str): The user's email address
            password_hash (str): The hashed password
            name (str, optional): The user's name

        Returns:
            str: The newly created user's ID
        """
        try:
            print(f"Creating user with email: {email}, name: {name}")
            user_id = str(uuid.uuid4())
            now = datetime.now().isoformat()

            name = name or email.split("@")[0]

            query = """
                INSERT INTO users (user_id, email, name, password_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            params = (user_id, email, name, password_hash, now, now)

            self.execute_query(query, params, commit=True)
            print(f"User inserted into database with ID: {user_id}")
            return user_id

        except Exception as e:
            print(f"Error creating user: {str(e)}")
            raise

    def get_user_by_email(self, email):
        """
        Retrieves a user from the database by their email address.

        Args:
            email (str): The email address of the user to retrieve

        Returns:
            dict: The user data if found, otherwise None
        """
        try:
            query = "SELECT * FROM users WHERE email = ?"
            user = self.execute_query(query, (email,), fetch_one=True)

            if user:
                user_dict = dict(user)
                return user_dict

            print(f"User not found: {email}")
            return None

        except Exception as e:
            print(f"Error looking up user by email: {str(e)}")
            raise

    def get_user_by_id(self, user_id):
        """
        Retrieves a user from the database by their user ID.

        Args:
            user_id (str): The ID of the user to retrieve

        Returns:
            dict: The user data if found, otherwise None
        """
        try:
            query = "SELECT * FROM users WHERE user_id = ?"
            user = self.execute_query(query, (user_id,), fetch_one=True)

            if user:
                user_dict = dict(user)
                return user_dict

            print("User not found: {user_id}")
            return None

        except Exception as e:
            print(f"Error looking up user by ID: {str(e)}")
            raise

    # Assessment methods
    def save_assessment(
        self, user_id, topic, knowledge_level, score, questions, responses
    ):
        """
        Saves a user's assessment data to the database.

        Args:
            user_id (str): The ID of the user taking the assessment
            topic (str): The topic of the assessment
            knowledge_level (str): The user's self-assessed knowledge level
            score (float): The user's score on the assessment
            questions (list): The list of questions asked
            responses (list): The user's responses to the questions

        Returns:
            str: The newly created assessment's ID
        """
        assessment_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        # Convert lists to JSON strings
        question_history = json.dumps(questions)
        response_history = json.dumps(responses)

        query = """
            INSERT INTO user_assessments
            (assessment_id, user_id, topic, knowledge_level, score, question_history, response_history, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            assessment_id,
            user_id,
            topic,
            knowledge_level,
            score,
            question_history,
            response_history,
            now,
        )

        self.execute_query(query, params, commit=True)
        return assessment_id

    def get_user_assessments(self, user_id):
        """
        Retrieves all assessments for a given user.

        Args:
            user_id (str): The ID of the user

        Returns:
            list: A list of assessment data
        """
        query = "SELECT * FROM user_assessments WHERE user_id = ?"
        assessments = self.execute_query(query, (user_id,))

        result = []
        for assessment in assessments:
            assessment_dict = dict(assessment)

            # Parse JSON strings back to lists
            if assessment_dict["question_history"]:
                assessment_dict["question_history"] = json.loads(
                    assessment_dict["question_history"]
                )

            if assessment_dict["response_history"]:
                assessment_dict["response_history"] = json.loads(
                    assessment_dict["response_history"]
                )

            result.append(assessment_dict)

        return result

    def get_assessment(self, assessment_id):
        """
        Retrieves a specific assessment by its ID.

        Args:
            assessment_id (str): The ID of the assessment

        Returns:
            dict: The assessment data if found, otherwise None
        """
        query = "SELECT * FROM user_assessments WHERE assessment_id = ?"
        assessment = self.execute_query(query, (assessment_id,), fetch_one=True)

        if assessment:
            assessment_dict = dict(assessment)

            # Parse JSON strings back to lists
            if assessment_dict["question_history"]:
                assessment_dict["question_history"] = json.loads(
                    assessment_dict["question_history"]
                )

            if assessment_dict["response_history"]:
                assessment_dict["response_history"] = json.loads(
                    assessment_dict["response_history"]
                )

            return assessment_dict

        return None

    # Syllabus methods
    def save_syllabus(self, topic, level, content, user_id=None):
        """
        Saves a syllabus to the database.

        Args:
            topic (str): The topic of the syllabus
            level (str): The level of the syllabus
            content (dict): The content of the syllabus
            user_id (str, optional): The ID of the user creating the syllabus

        Returns:
            str: The newly created syllabus's ID
        """

        def _save_syllabus_transaction():
            syllabus_id = str(uuid.uuid4())
            now = datetime.now().isoformat()

            # Insert syllabus
            syllabus_query = """
                INSERT INTO syllabi (syllabus_id, user_id, topic, level, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            syllabus_params = (syllabus_id, user_id, topic, level, now, now)
            self.execute_query(syllabus_query, syllabus_params)

            # Insert modules and lessons
            if "modules" in content:
                for module_index, module in enumerate(content["modules"]):
                    # Insert module
                    module_query = """
                        INSERT INTO modules
                        (syllabus_id, module_index, title, summary, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """
                    module_params = (
                        syllabus_id,
                        module_index,
                        module["title"],
                        module.get("summary", ""),
                        now,
                        now,
                    )
                    self.execute_query(module_query, module_params)

                    # Get the module_id
                    module_id_query = """
                        SELECT module_id FROM modules
                        WHERE syllabus_id = ? AND module_index = ?
                    """
                    module_id_result = self.execute_query(
                        module_id_query, (syllabus_id, module_index), fetch_one=True
                    )
                    module_id = module_id_result["module_id"]

                    # Insert lessons
                    if "lessons" in module:
                        for lesson_index, lesson in enumerate(module["lessons"]):
                            # Insert lesson
                            lesson_query = """
                                INSERT INTO lessons
                                (module_id, lesson_index, title, summary, duration, created_at, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """
                            lesson_params = (
                                module_id,
                                lesson_index,
                                lesson["title"],
                                lesson.get("summary", ""),
                                lesson.get("duration", ""),
                                now,
                                now,
                            )
                            self.execute_query(lesson_query, lesson_params)

            return syllabus_id

        return self._transaction(_save_syllabus_transaction)

    def get_syllabus(self, topic, level, user_id=None):
        """
        Retrieves a syllabus based on topic, level, and optionally user ID.

        Args:
            topic (str): The topic of the syllabus
            level (str): The level of the syllabus
            user_id (str, optional): The ID of the user

        Returns:
            dict: The syllabus data if found, otherwise None
        """
        if user_id:
            # Try to find a user-specific syllabus first
            query = """
                SELECT * FROM syllabi
                WHERE topic = ? AND level = ? AND user_id = ?
            """
            syllabus = self.execute_query(
                query, (topic, level, user_id), fetch_one=True
            )

            if not syllabus:
                # If not found, try to find a general syllabus
                query = """
                    SELECT * FROM syllabi
                    WHERE topic = ? AND level = ? AND user_id IS NULL
                """
                syllabus = self.execute_query(query, (topic, level), fetch_one=True)
        else:
            # Look for a general syllabus
            query = """
                SELECT * FROM syllabi
                WHERE topic = ? AND level = ? AND user_id IS NULL
            """
            syllabus = self.execute_query(query, (topic, level), fetch_one=True)

        if syllabus:
            return self._build_syllabus_dict(dict(syllabus))

        return None

    def get_syllabus_by_id(self, syllabus_id):
        """
        Retrieves a syllabus by its ID.

        Args:
            syllabus_id (str): The ID of the syllabus

        Returns:
            dict: The syllabus data if found, otherwise None
        """
        query = "SELECT * FROM syllabi WHERE syllabus_id = ?"
        syllabus = self.execute_query(query, (syllabus_id,), fetch_one=True)

        if syllabus:
            return self._build_syllabus_dict(dict(syllabus))

        return None

    def _build_syllabus_dict(self, syllabus_dict):
        """
        Builds a complete syllabus dictionary with modules and lessons.

        Args:
            syllabus_dict (dict): The basic syllabus data

        Returns:
            dict: The complete syllabus data with modules and lessons
        """
        syllabus_id = syllabus_dict["syllabus_id"]

        # Get modules
        modules_query = """
            SELECT * FROM modules
            WHERE syllabus_id = ?
            ORDER BY module_index
        """
        modules = self.execute_query(modules_query, (syllabus_id,))

        modules_list = []
        for module in modules:
            module_dict = dict(module)
            module_id = module_dict["module_id"]

            # Get lessons
            lessons_query = """
                SELECT * FROM lessons
                WHERE module_id = ?
                ORDER BY lesson_index
            """
            lessons = self.execute_query(lessons_query, (module_id,))

            lessons_list = []
            for lesson in lessons:
                lesson_dict = dict(lesson)
                lessons_list.append(
                    {
                        "title": lesson_dict["title"],
                        "summary": lesson_dict["summary"],
                        "duration": lesson_dict["duration"],
                    }
                )

            modules_list.append(
                {
                    "title": module_dict["title"],
                    "summary": module_dict["summary"],
                    "lessons": lessons_list,
                }
            )

        # Build the content structure
        content = {
            "topic": syllabus_dict['topic'],
            "level": syllabus_dict['level'],
            "title": f"{syllabus_dict['topic']} - {syllabus_dict['level']}",
            "description": f"Syllabus for {syllabus_dict['topic']}"
                           f" at {syllabus_dict['level']} level",
            "duration": "4 weeks",  # Default duration
            "learning_objectives": [
                f"Understand the core concepts of {syllabus_dict['topic']}",
                f"Apply {syllabus_dict['topic']} knowledge to solve real-world problems",
                f"Develop critical thinking skills related to {syllabus_dict['topic']}",
                f"Build practical experience with {syllabus_dict['topic']} tools and techniques",
                f"Evaluate and analyze {syllabus_dict['topic']} applications in various contexts"
            ],
            "modules": modules_list,
        }

        # Add content to the syllabus dictionary
        syllabus_dict["content"] = content

        return syllabus_dict

    # Lesson content methods
    def save_lesson_content(self, syllabus_id, module_index, lesson_index, content):
        """
        Saves lesson content to the database.

        Args:
            syllabus_id (str): The ID of the syllabus the lesson belongs to
            module_index (int): The index of the module within the syllabus
            lesson_index (int): The index of the lesson within the module
            content (dict): The content of the lesson

        Returns:
            str: The newly created lesson's ID
        """

        def _save_lesson_content_transaction():
            # Get the module_id
            module_query = """
                SELECT module_id FROM modules
                WHERE syllabus_id = ? AND module_index = ?
            """
            module = self.execute_query(
                module_query, (syllabus_id, module_index), fetch_one=True
            )

            if not module:
                raise ValueError(
                    f"Module not found for syllabus {syllabus_id}, index {module_index}"
                )

            module_id = module["module_id"]

            # Get the lesson_id
            lesson_query = """
                SELECT lesson_id FROM lessons
                WHERE module_id = ? AND lesson_index = ?
            """
            lesson = self.execute_query(
                lesson_query, (module_id, lesson_index), fetch_one=True
            )

            if not lesson:
                raise ValueError(
                    f"Lesson not found for module {module_id}, index {lesson_index}"
                )

            lesson_id = lesson["lesson_id"]

            # Check if content already exists
            content_query = "SELECT content_id FROM lesson_content WHERE lesson_id = ?"
            existing_content = self.execute_query(
                content_query, (lesson_id,), fetch_one=True
            )

            content_id = str(uuid.uuid4())
            now = datetime.now().isoformat()
            content_json = json.dumps(content)

            if existing_content:
                # Update existing content
                update_query = """
                    UPDATE lesson_content
                    SET content = ?, updated_at = ?
                    WHERE lesson_id = ?
                """
                self.execute_query(
                    update_query, (content_json, now, lesson_id), commit=True
                )
                content_id = existing_content["content_id"]
            else:
                # Insert new content
                insert_query = """
                    INSERT INTO lesson_content
                    (content_id, lesson_id, content, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """
                self.execute_query(
                    insert_query,
                    (content_id, lesson_id, content_json, now, now),
                    commit=True,
                )

            return content_id

        return self._transaction(_save_lesson_content_transaction)

    def get_lesson_content(self, syllabus_id, module_index, lesson_index):
        """
        Retrieves lesson content based on syllabus ID, module index, and lesson index.

        Args:
            syllabus_id (str): The ID of the syllabus
            module_index (int): The index of the module
            lesson_index (int): The index of the lesson

        Returns:
            dict: The lesson content if found, otherwise None
        """
        # Get the module_id
        module_query = """
            SELECT module_id FROM modules
            WHERE syllabus_id = ? AND module_index = ?
        """
        module = self.execute_query(
            module_query, (syllabus_id, module_index), fetch_one=True
        )

        if not module:
            return None

        module_id = module["module_id"]

        # Get the lesson_id and basic lesson info
        lesson_query = """
            SELECT * FROM lessons
            WHERE module_id = ? AND lesson_index = ?
        """
        lesson = self.execute_query(
            lesson_query, (module_id, lesson_index), fetch_one=True
        )

        if not lesson:
            return None

        lesson_id = lesson["lesson_id"]

        # Get the content
        content_query = "SELECT * FROM lesson_content WHERE lesson_id = ?"
        content = self.execute_query(content_query, (lesson_id,), fetch_one=True)

        if content:
            content_dict = dict(content)
            content_json = json.loads(content_dict["content"])

            result = {
                "lesson_id": content_dict["content_id"],
                "syllabus_id": syllabus_id,
                "module_index": module_index,
                "lesson_index": lesson_index,
                "content": content_json,
            }

            return result

        return None

    def get_lesson_by_id(self, lesson_id):
        """
        Retrieves a lesson by its ID.

        Args:
            lesson_id (str): The ID of the lesson

        Returns:
            dict: The lesson data if found, otherwise None
        """
        # First, check if this is a content_id
        content_query = "SELECT * FROM lesson_content WHERE content_id = ?"
        content = self.execute_query(content_query, (lesson_id,), fetch_one=True)

        if content:
            content_dict = dict(content)
            lesson_id = content_dict["lesson_id"]

            # Get the lesson
            lesson_query = "SELECT * FROM lessons WHERE lesson_id = ?"
            lesson = self.execute_query(lesson_query, (lesson_id,), fetch_one=True)

            if lesson:
                lesson_dict = dict(lesson)
                module_id = lesson_dict["module_id"]

                # Get the module
                module_query = "SELECT * FROM modules WHERE module_id = ?"
                module = self.execute_query(module_query, (module_id,), fetch_one=True)

                if module:
                    module_dict = dict(module)
                    syllabus_id = module_dict["syllabus_id"]

                    result = {
                        "lesson_id": content_dict["content_id"],
                        "syllabus_id": syllabus_id,
                        "module_index": module_dict["module_index"],
                        "lesson_index": lesson_dict["lesson_index"],
                        "content": json.loads(content_dict["content"]),
                    }

                    return result

        return None

    # User progress methods
    def save_user_progress(
        self, user_id, syllabus_id, module_index, lesson_index, status, score=None
    ):
        """
        Saves or updates user progress for a specific lesson.

        Args:
            user_id (str): The ID of the user
            syllabus_id (str): The ID of the syllabus
            module_index (int): The index of the module
            lesson_index (int): The index of the lesson
            status (str): The status of the lesson ("not_started", "in_progress", "completed")
            score (float, optional): The user's score for the lesson

        Returns:
            str: The ID of the progress entry
        """
        now = datetime.now().isoformat()

        # Check if progress entry already exists
        query = """
            SELECT progress_id FROM user_progress
            WHERE user_id = ? AND syllabus_id = ? AND module_index = ? AND lesson_index = ?
        """
        params = (user_id, syllabus_id, module_index, lesson_index)
        existing = self.execute_query(query, params, fetch_one=True)

        if existing:
            # Update existing entry
            progress_id = existing["progress_id"]
            update_query = """
                UPDATE user_progress
                SET status = ?, score = ?, updated_at = ?
                WHERE progress_id = ?
            """
            update_params = (status, score, now, progress_id)
            self.execute_query(update_query, update_params, commit=True)
            return progress_id
        else:
            # Create new entry
            progress_id = str(uuid.uuid4())
            insert_query = """
                INSERT INTO user_progress
                (progress_id, user_id, syllabus_id, module_index, lesson_index, status, score, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            insert_params = (
                progress_id,
                user_id,
                syllabus_id,
                module_index,
                lesson_index,
                status,
                score,
                now,
                now,
            )
            self.execute_query(insert_query, insert_params, commit=True)
            return progress_id

    def get_user_syllabus_progress(self, user_id, syllabus_id):
        """
        Retrieves all progress entries for a user within a specific syllabus.

        Args:
            user_id (str): The ID of the user
            syllabus_id (str): The ID of the syllabus

        Returns:
            list: A list of progress entries
        """
        query = """
            SELECT * FROM user_progress
            WHERE user_id = ? AND syllabus_id = ?
        """
        progress_entries = self.execute_query(query, (user_id, syllabus_id))

        result = []
        for entry in progress_entries:
            result.append(dict(entry))

        return result

    def get_user_in_progress_courses(self, user_id):
        """
        Retrieves courses the user is currently in progress on, along with progress details.

        Args:
            user_id (str): The ID of the user

        Returns:
            list: A list of dicts, of syllabus details and progress information
        """
        # Get unique syllabus_ids where the user has progress
        progress_query = """
            SELECT DISTINCT syllabus_id
            FROM user_progress
            WHERE user_id = ?
        """
        syllabi = self.execute_query(progress_query, (user_id,))

        in_progress_courses = []

        for syllabus_row in syllabi:
            syllabus_id = syllabus_row[0]

            # Get syllabus details
            syllabus = self.get_syllabus_by_id(syllabus_id)

            if syllabus:
                # Get progress for this syllabus
                progress_entries = self.get_user_syllabus_progress(user_id, syllabus_id)

                # Calculate progress
                total_lessons = len(progress_entries)
                completed_lessons = sum(
                    1 for entry in progress_entries if entry["status"] == "completed"
                )

                progress_percentage = (
                    (completed_lessons / total_lessons * 100)
                    if total_lessons > 0
                    else 0
                )

                in_progress_courses.append(
                    {
                        "syllabus_id": syllabus_id,
                        "topic": syllabus["topic"],
                        "level": syllabus["level"],
                        "progress_percentage": progress_percentage,
                        "completed_lessons": completed_lessons,
                        "total_lessons": total_lessons,
                    }
                )

        return in_progress_courses
