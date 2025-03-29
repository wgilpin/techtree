# backend/services/sqlite_db.py
""" Sqlite database service """
import os
import uuid
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any # Added List, Dict, Any
# Import logger
from backend.logger import logger


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
            logger.info(f"Using database at root directory: {abs_path}") # Use logger

            # Ensure the directory exists
            db_dir = os.path.dirname(abs_path)
            Path(db_dir).mkdir(parents=True, exist_ok=True)

            # Check if file exists
            db_exists = os.path.exists(abs_path)
            if not db_exists:
                logger.warning(f"Database file does not exist, will be created at: {abs_path}") # Use logger

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

            logger.info(f"SQLite database initialized at: {abs_path}") # Use logger

            # Create tables if they don't exist
            if not db_exists:
                self._create_tables()
                logger.info("Database tables created") # Use logger

        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}", exc_info=True) # Use logger
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
            logger.info("Database connection closed") # Use logger

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
            logger.error(f"Database error: {str(e)}", exc_info=True) # Use logger
            logger.error(f"Query: {query}") # Use logger
            logger.error(f"Params: {params}") # Use logger
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
            logger.error(f"Transaction error: {str(e)}", exc_info=True) # Use logger
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
            logger.info(f"Creating user with email: {email}, name: {name}") # Use logger
            user_id = str(uuid.uuid4())
            now = datetime.now().isoformat()

            name = name or email.split("@")[0]

            query = """
                INSERT INTO users (user_id, email, name, password_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            params = (user_id, email, name, password_hash, now, now)

            self.execute_query(query, params, commit=True)
            logger.info(f"User inserted into database with ID: {user_id}") # Use logger
            return user_id

        except Exception as e:
            logger.error(f"Error creating user: {str(e)}", exc_info=True) # Use logger
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

            logger.warning(f"User not found: {email}") # Use logger
            return None

        except Exception as e:
            logger.error(f"Error looking up user by email: {str(e)}", exc_info=True) # Use logger
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

            logger.warning(f"User not found: {user_id}") # Use logger
            return None

        except Exception as e:
            logger.error(f"Error looking up user by ID: {str(e)}", exc_info=True) # Use logger
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
                try:
                    assessment_dict["question_history"] = json.loads(
                        assessment_dict["question_history"]
                    )
                except json.JSONDecodeError:
                     logger.warning(f"Failed to parse question_history for assessment {assessment_dict.get('assessment_id')}")
                     assessment_dict["question_history"] = [] # Default to empty list

            if assessment_dict["response_history"]:
                try:
                    assessment_dict["response_history"] = json.loads(
                        assessment_dict["response_history"]
                    )
                except json.JSONDecodeError:
                     logger.warning(f"Failed to parse response_history for assessment {assessment_dict.get('assessment_id')}")
                     assessment_dict["response_history"] = [] # Default to empty list


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
                 try:
                    assessment_dict["question_history"] = json.loads(
                        assessment_dict["question_history"]
                    )
                 except json.JSONDecodeError:
                     logger.warning(f"Failed to parse question_history for assessment {assessment_dict.get('assessment_id')}")
                     assessment_dict["question_history"] = []

            if assessment_dict["response_history"]:
                 try:
                    assessment_dict["response_history"] = json.loads(
                        assessment_dict["response_history"]
                    )
                 except json.JSONDecodeError:
                     logger.warning(f"Failed to parse response_history for assessment {assessment_dict.get('assessment_id')}")
                     assessment_dict["response_history"] = []

            return assessment_dict

        return None

    # Syllabus methods
    def save_syllabus(self, topic, level, content, user_id=None, user_entered_topic=None):
        """
        Saves a syllabus to the database. Assumes 'content' contains 'modules',
        and each module contains 'title', 'content' (with 'summary', 'lessons').

        Args:
            topic (str): The topic of the syllabus (potentially AI-refined)
            level (str): The level of the syllabus
            content (dict): The content of the syllabus generated by AI/service.
            user_id (str, optional): The ID of the user creating the syllabus
            user_entered_topic (str, optional): The original topic entered by the user.

        Returns:
            str: The newly created syllabus's ID
        """

        def _save_syllabus_transaction():
            syllabus_id = str(uuid.uuid4())
            now = datetime.now().isoformat()

            # Insert syllabus record
            syllabus_query = """
                INSERT INTO syllabi (syllabus_id, user_id, topic, level, user_entered_topic, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            effective_user_entered_topic = user_entered_topic if user_entered_topic is not None else topic
            syllabus_params = (syllabus_id, user_id, topic, level, effective_user_entered_topic, now, now)
            self.execute_query(syllabus_query, syllabus_params)
            logger.debug(f"Inserted syllabus record with ID: {syllabus_id}")

            # Insert modules and lessons from the provided content structure
            if "modules" in content and isinstance(content["modules"], list):
                for module_index, module_data in enumerate(content["modules"]):
                    # Ensure module_data has the expected keys from the Pydantic model
                    module_title = module_data.get("title", f"Module {module_index + 1}")
                    module_content = module_data.get("content", {}) # Get the nested content dict
                    module_summary = module_content.get("summary", "") # Summary is inside content

                    # Insert module record
                    module_query = """
                        INSERT INTO modules
                        (syllabus_id, module_index, title, summary, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """
                    module_params = (
                        syllabus_id,
                        module_index,
                        module_title,
                        module_summary,
                        now,
                        now,
                    )
                    self.execute_query(module_query, module_params)
                    logger.debug(f"Inserted module index {module_index} for syllabus {syllabus_id}")

                    # Get the auto-generated module_id (PK)
                    module_id_query = "SELECT last_insert_rowid()"
                    module_id_result = self.execute_query(module_id_query, fetch_one=True)
                    module_id = module_id_result[0] # last_insert_rowid returns a tuple
                    logger.debug(f"Retrieved module_id: {module_id}")


                    # Insert lessons (lessons are inside the module's content dict)
                    if "lessons" in module_content and isinstance(module_content["lessons"], list):
                        for lesson_index, lesson_data in enumerate(module_content["lessons"]):
                            lesson_title = lesson_data.get("title", f"Lesson {lesson_index + 1}")
                            lesson_summary = lesson_data.get("summary", "")
                            lesson_duration = lesson_data.get("duration", "")

                            # Insert lesson record
                            lesson_query = """
                                INSERT INTO lessons
                                (module_id, lesson_index, title, summary, duration, created_at, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """
                            lesson_params = (
                                module_id,
                                lesson_index,
                                lesson_title,
                                lesson_summary,
                                lesson_duration,
                                now,
                                now,
                            )
                            self.execute_query(lesson_query, lesson_params)
                        logger.debug(f"Inserted {len(module_content['lessons'])} lessons for module {module_id}")
                    else:
                         logger.warning(f"No 'lessons' list found in content for module index {module_index}")

            else:
                 logger.warning("No 'modules' list found in content for saving syllabus.")


            return syllabus_id

        # Execute the save operation within a transaction
        try:
            return self._transaction(_save_syllabus_transaction)
        except Exception as e:
            logger.error(f"Error saving syllabus transaction: {e}", exc_info=True)
            raise # Re-raise the exception after logging


    def get_syllabus(self, topic, level, user_id=None):
        """
        Retrieves a syllabus based on topic, level, and optionally user ID.
        Performs case-insensitive and whitespace-trimmed matching for topic and level.

        Args:
            topic (str): The topic of the syllabus
            level (str): The level of the syllabus
            user_id (str, optional): The ID of the user

        Returns:
            dict: The syllabus data structured by _build_syllabus_dict if found, otherwise None
        """
        # Normalize input parameters
        norm_topic = topic.lower().strip()
        norm_level = level.lower().strip()
        syllabus_row = None # Initialize syllabus_row to None

        logger.debug(f"Attempting to get syllabus: topic='{norm_topic}', level='{norm_level}', user_id='{user_id}'")

        if user_id:
            # Try to find a user-specific syllabus first (case-insensitive, trimmed)
            query_user = """
                SELECT * FROM syllabi
                WHERE LOWER(TRIM(topic)) = ? AND LOWER(TRIM(level)) = ? AND user_id = ?
            """
            syllabus_row = self.execute_query(
                query_user, (norm_topic, norm_level, user_id), fetch_one=True
            )
            if syllabus_row:
                 logger.debug("Found user-specific syllabus.")
            else:
                 logger.debug("User-specific syllabus not found, checking for general.")
                 # If not found, try to find a general syllabus (case-insensitive, trimmed)
                 query_general = """
                     SELECT * FROM syllabi
                     WHERE LOWER(TRIM(topic)) = ? AND LOWER(TRIM(level)) = ? AND user_id IS NULL
                 """
                 syllabus_row = self.execute_query(query_general, (norm_topic, norm_level), fetch_one=True)
                 if syllabus_row:
                      logger.debug("Found general syllabus.")

        else:
            # Look for a general syllabus (case-insensitive, trimmed)
            logger.debug("No user_id provided, checking for general syllabus.")
            query_general = """
                SELECT * FROM syllabi
                WHERE LOWER(TRIM(topic)) = ? AND LOWER(TRIM(level)) = ? AND user_id IS NULL
            """
            syllabus_row = self.execute_query(query_general, (norm_topic, norm_level), fetch_one=True)
            if syllabus_row:
                 logger.debug("Found general syllabus.")

        if syllabus_row:
            # Use _build_syllabus_dict to construct the full nested structure
            return self._build_syllabus_dict(dict(syllabus_row))
        else:
            logger.debug("Syllabus not found.")
            return None

    def get_syllabus_by_id(self, syllabus_id):
        """
        Retrieves a syllabus by its ID.

        Args:
            syllabus_id (str): The ID of the syllabus

        Returns:
            dict: The syllabus data structured by _build_syllabus_dict if found, otherwise None
        """
        logger.debug(f"Getting syllabus by ID: {syllabus_id}")
        query = "SELECT * FROM syllabi WHERE syllabus_id = ?"
        syllabus_row = self.execute_query(query, (syllabus_id,), fetch_one=True)

        if syllabus_row:
            # Use _build_syllabus_dict to construct the full nested structure
            return self._build_syllabus_dict(dict(syllabus_row))
        else:
            logger.warning(f"Syllabus not found for ID: {syllabus_id}")
            return None

    def _build_syllabus_dict(self, syllabus_dict):
        """
        Builds a complete syllabus dictionary including modules and lessons,
        structured to match the Pydantic models used in the service layer.

        Args:
            syllabus_dict (dict): The basic syllabus data from the 'syllabi' table.

        Returns:
            dict: The complete syllabus data with nested modules and lessons.
                  The structure returned here is intended for internal use within
                  the service layer, which will then adapt it for the API response model.
        """
        syllabus_id = syllabus_dict["syllabus_id"]
        logger.debug(f"Building syllabus dict for syllabus_id: {syllabus_id}")

        # Get modules associated with this syllabus
        modules_query = """
            SELECT * FROM modules
            WHERE syllabus_id = ?
            ORDER BY module_index
        """
        modules_result = self.execute_query(modules_query, (syllabus_id,))
        logger.debug(f"Found {len(modules_result)} modules for syllabus {syllabus_id}")

        modules_list_for_content = []
        for module_row in modules_result:
            module_data = dict(module_row)
            # module_id here is the PK from the modules table (likely integer)
            module_pk = module_data["module_id"]
            logger.debug(f"Processing module PK: {module_pk}, index: {module_data['module_index']}")

            # Get lessons associated with this module
            lessons_query = """
                SELECT * FROM lessons
                WHERE module_id = ?
                ORDER BY lesson_index
            """
            lessons_result = self.execute_query(lessons_query, (module_pk,))
            logger.debug(f"Found {len(lessons_result)} lessons for module PK {module_pk}")

            lessons_list_for_module_content = []
            for lesson_row in lessons_result:
                lesson_data = dict(lesson_row)
                # Structure for lesson content (can be expanded later if needed)
                lessons_list_for_module_content.append(
                    {
                        "title": lesson_data["title"],
                        "summary": lesson_data["summary"],
                        "duration": lesson_data["duration"],
                        # Add lesson_id if needed by consumers of this structure
                        # "lesson_id": lesson_data["lesson_id"],
                    }
                )

            # Structure for the module's 'content' field (matching Module Pydantic model's content field)
            module_content_dict = {
                 "summary": module_data["summary"],
                 "lessons": lessons_list_for_module_content,
                 # Add other relevant module details here if needed by the Module.content model
            }

            # Structure for the module itself, matching the Module Pydantic model
            # Use syllabus_id + module_index as a stable identifier if module_pk isn't suitable
            # For now, let's assume module_pk (the primary key) is the intended module_id
            # Ensure it's a string as required by the Pydantic model
            module_id_str = f"mod_{module_pk}" # Example: Create a string ID

            modules_list_for_content.append(
                {
                    "module_id": module_id_str, # Use the generated string ID
                    "title": module_data["title"],
                    "content": module_content_dict, # Nest details under 'content'
                }
            )

        # Build the top-level 'content' dictionary (as previously structured)
        # This structure is primarily for internal representation or if needed elsewhere.
        # The service layer will extract 'modules' from this for the final response.
        top_level_content = {
            "topic": syllabus_dict['topic'],
            "level": syllabus_dict['level'],
            "title": f"{syllabus_dict['topic']} - {syllabus_dict['level']}",
            "description": f"Syllabus for {syllabus_dict['topic']} at {syllabus_dict['level']} level",
            "duration": "4 weeks",  # Example default
            "learning_objectives": [ # Example defaults
                f"Understand the core concepts of {syllabus_dict['topic']}",
                f"Apply {syllabus_dict['topic']} knowledge",
            ],
            "modules": modules_list_for_content, # Use the correctly structured modules list
        }

        # Add the constructed 'content' dict back to the main syllabus dict
        syllabus_dict["content"] = top_level_content
        logger.debug(f"Finished building syllabus dict for syllabus_id: {syllabus_id}")

        # Return the full syllabus dictionary including the nested content
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
            # Get the module_id (PK)
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

            module_pk = module["module_id"]

            # Get the lesson_id (PK)
            lesson_query = """
                SELECT lesson_id FROM lessons
                WHERE module_id = ? AND lesson_index = ?
            """
            lesson = self.execute_query(
                lesson_query, (module_pk, lesson_index), fetch_one=True
            )

            if not lesson:
                raise ValueError(
                    f"Lesson not found for module PK {module_pk}, index {lesson_index}"
                )

            lesson_pk = lesson["lesson_id"]

            # Check if content already exists for this lesson_pk
            content_query = "SELECT content_id FROM lesson_content WHERE lesson_id = ?"
            existing_content = self.execute_query(
                content_query, (lesson_pk,), fetch_one=True
            )

            content_id = str(uuid.uuid4()) # Generate potential new content_id
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
                    update_query, (content_json, now, lesson_pk), commit=True
                )
                content_id = existing_content["content_id"] # Use existing content_id
                logger.debug(f"Updated lesson content for lesson_pk {lesson_pk}")
            else:
                # Insert new content
                insert_query = """
                    INSERT INTO lesson_content
                    (content_id, lesson_id, content, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """
                self.execute_query(
                    insert_query,
                    (content_id, lesson_pk, content_json, now, now),
                    commit=True,
                )
                logger.debug(f"Inserted new lesson content for lesson_pk {lesson_pk} with content_id {content_id}")

            # Return the lesson_pk (ID from lessons table), not content_id
            return lesson_pk

        # Execute the transaction and return its result (the lesson_pk)
        try:
            lesson_pk = self._transaction(_save_lesson_content_transaction)
            return lesson_pk
        except Exception as e:
             logger.error(f"Error saving lesson content transaction: {e}", exc_info=True)
             raise


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
        # Get the module_id (PK)
        module_query = """
            SELECT module_id FROM modules
            WHERE syllabus_id = ? AND module_index = ?
        """
        module = self.execute_query(
            module_query, (syllabus_id, module_index), fetch_one=True
        )

        if not module:
            logger.warning(f"Module not found for syllabus {syllabus_id}, index {module_index}")
            return None

        module_pk = module["module_id"]

        # Get the lesson_id (PK)
        lesson_query = """
            SELECT lesson_id FROM lessons
            WHERE module_id = ? AND lesson_index = ?
        """
        lesson = self.execute_query(
            lesson_query, (module_pk, lesson_index), fetch_one=True
        )

        if not lesson:
            logger.warning(f"Lesson not found for module PK {module_pk}, index {lesson_index}")
            return None

        lesson_pk = lesson["lesson_id"]

        # Get the content using lesson_pk
        content_query = "SELECT content FROM lesson_content WHERE lesson_id = ?"
        content_row = self.execute_query(content_query, (lesson_pk,), fetch_one=True)

        if content_row:
            try:
                # Directly return the parsed JSON content from the 'content' column
                return json.loads(content_row["content"])
            except json.JSONDecodeError:
                logger.error(f"Failed to parse lesson content JSON for lesson_pk {lesson_pk}", exc_info=True)
                return None # Return None if JSON is invalid
        else:
             logger.warning(f"Lesson content not found for lesson_pk {lesson_pk}")
             return None


    def get_lesson_id(self, syllabus_id: str, module_index: int, lesson_index: int) -> Optional[int]:
        """
        Retrieves the primary key (lesson_id) of a lesson based on its indices.

        Args:
            syllabus_id (str): The ID of the syllabus.
            module_index (int): The index of the module within the syllabus.
            lesson_index (int): The index of the lesson within the module.

        Returns:
            Optional[int]: The lesson_id (PK from lessons table) if found, otherwise None.
        """
        try:
            # Get the module_id (PK)
            module_query = """
                SELECT module_id FROM modules
                WHERE syllabus_id = ? AND module_index = ?
            """
            module_result = self.execute_query(
                module_query, (syllabus_id, module_index), fetch_one=True
            )

            if not module_result:
                logger.warning(
                    f"Module not found for syllabus {syllabus_id}, index {module_index}"
                )
                return None

            module_pk = module_result["module_id"]

            # Get the lesson_id (PK)
            lesson_query = """
                SELECT lesson_id FROM lessons
                WHERE module_id = ? AND lesson_index = ?
            """
            lesson_result = self.execute_query(
                lesson_query, (module_pk, lesson_index), fetch_one=True
            )

            if not lesson_result:
                logger.warning(
                    f"Lesson not found for module PK {module_pk}, index {lesson_index}"
                )
                return None

            lesson_pk = lesson_result["lesson_id"]
            # lesson_id from the table is likely an integer PK
            return int(lesson_pk) if lesson_pk is not None else None

        except Exception as e:
            logger.error(f"Error retrieving lesson ID (PK): {str(e)}", exc_info=True)
            raise

    def get_lesson_by_id(self, lesson_content_id: str):
        """
        Retrieves lesson details (including content) using the lesson_content_id.

        Args:
            lesson_content_id (str): The UUID from the lesson_content table.

        Returns:
            dict: A dictionary containing syllabus_id, module_index, lesson_index,
                  and parsed content if found, otherwise None.
        """
        logger.debug(f"Getting lesson by content_id: {lesson_content_id}")
        # Query joining lesson_content, lessons, and modules tables
        query = """
            SELECT
                lc.content,
                l.lesson_index,
                m.module_index,
                m.syllabus_id
            FROM lesson_content lc
            JOIN lessons l ON lc.lesson_id = l.lesson_id
            JOIN modules m ON l.module_id = m.module_id
            WHERE lc.content_id = ?
        """
        result = self.execute_query(query, (lesson_content_id,), fetch_one=True)

        if result:
            try:
                parsed_content = json.loads(result["content"])
            except json.JSONDecodeError:
                logger.error(f"Failed to parse lesson content JSON for content_id {lesson_content_id}", exc_info=True)
                parsed_content = None # Handle invalid JSON

            lesson_details = {
                "lesson_id": lesson_content_id, # Return the ID that was queried
                "syllabus_id": result["syllabus_id"],
                "module_index": result["module_index"],
                "lesson_index": result["lesson_index"],
                "content": parsed_content,
            }
            logger.debug(f"Found lesson details: {lesson_details}")
            return lesson_details
        else:
            logger.warning(f"Lesson not found for content_id: {lesson_content_id}")
            return None


    # User progress methods
    def save_user_progress(
        self,
        user_id,
        syllabus_id,
        module_index,
        lesson_index,
        status,
        lesson_id: Optional[int] = None, # lesson_id is the PK from lessons table
        score: Optional[float] = None,
        lesson_state_json: Optional[str] = None,
    ):
        """
        Saves or updates user progress for a specific lesson, including conversational state.

        Args:
            user_id (str): The ID of the user
            syllabus_id (str): The ID of the syllabus
            module_index (int): The index of the module
            lesson_index (int): The index of the lesson
            status (str): The status of the lesson ("not_started", "in_progress", "completed")
            lesson_id (int, optional): The actual primary key of the lesson from the lessons table.
            score (float, optional): The user's score for the lesson
            lesson_state_json (str, optional): JSON string representing the conversational state.

        Returns:
            str: The ID of the progress entry (UUID)
        """
        now = datetime.now().isoformat()
        logger.debug(f"Saving progress for user {user_id}, syllabus {syllabus_id}, mod {module_index}, lesson {lesson_index}, lesson_id PK {lesson_id}, status {status}")


        # Ensure we have the lesson_id PK if not provided
        if lesson_id is None:
             retrieved_lesson_id = self.get_lesson_id(syllabus_id, module_index, lesson_index)
             if retrieved_lesson_id is None:
                  logger.error(f"Could not find lesson_id PK for syllabus {syllabus_id}, mod {module_index}, lesson {lesson_index} to save progress.")
                  # Decide how to handle: raise error, return None, or save without lesson_id?
                  # For now, let's raise an error as progress is tied to a specific lesson instance.
                  raise ValueError("Cannot save progress: Lesson primary key not found.")
             lesson_id = retrieved_lesson_id # Use the retrieved PK
             logger.debug(f"Retrieved lesson_id PK: {lesson_id}")


        # Check if progress entry already exists using user_id and lesson_id PK
        query = """
            SELECT progress_id FROM user_progress
            WHERE user_id = ? AND lesson_id = ?
        """
        # WHERE user_id = ? AND syllabus_id = ? AND module_index = ? AND lesson_index = ?
        # Using lesson_id PK is more robust if syllabus structure changes
        params = (user_id, lesson_id)
        existing = self.execute_query(query, params, fetch_one=True)

        if existing:
            # Update existing entry
            progress_id = existing["progress_id"]
            logger.debug(f"Updating existing progress entry: {progress_id}")
            update_query = """
                UPDATE user_progress
                SET status = ?, score = ?, lesson_state_json = ?, updated_at = ?,
                    syllabus_id = ?, module_index = ?, lesson_index = ?
                WHERE progress_id = ?
            """
            # Update indices as well, in case they somehow changed (though unlikely with lesson_id lookup)
            update_params = (status, score, lesson_state_json, now, syllabus_id, module_index, lesson_index, progress_id)
            self.execute_query(update_query, update_params, commit=True)
            return progress_id
        else:
            # Create new entry
            progress_id = str(uuid.uuid4())
            logger.debug(f"Creating new progress entry: {progress_id}")
            insert_query = """
                INSERT INTO user_progress
                (progress_id, user_id, syllabus_id, module_index, lesson_index, lesson_id, status, score, lesson_state_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            insert_params = (
                progress_id,
                user_id,
                syllabus_id,
                module_index,
                lesson_index,
                lesson_id, # Use the lesson PK
                status,
                score,
                lesson_state_json,
                now,
                now,
            )
            self.execute_query(insert_query, insert_params, commit=True)
            return progress_id

    def get_lesson_progress(self, user_id, syllabus_id, module_index, lesson_index):
        """
        Retrieves a specific progress entry for a user and lesson, including parsed state.
        Uses indices to find the lesson_id PK first.

        Args:
            user_id (str): The ID of the user.
            syllabus_id (str): The ID of the syllabus.
            module_index (int): The index of the module.
            lesson_index (int): The index of the lesson.

        Returns:
            dict: The progress entry including parsed 'lesson_state' and 'lesson_id', or None if not found.
        """
        logger.debug(f"Getting lesson progress for user {user_id}, syllabus {syllabus_id}, mod {module_index}, lesson {lesson_index}")
        # First, find the lesson_id PK using the indices
        lesson_id_pk = self.get_lesson_id(syllabus_id, module_index, lesson_index)

        if lesson_id_pk is None:
             logger.warning("Could not find lesson_id PK to retrieve progress.")
             return None

        # Now query progress using the lesson_id PK
        query = """
            SELECT * FROM user_progress
            WHERE user_id = ? AND lesson_id = ?
        """
        params = (user_id, lesson_id_pk)
        logger.debug(f"Executing get_lesson_progress query with params: {params}")
        entry = self.execute_query(query, params, fetch_one=True)
        logger.debug(f"Raw entry fetched from DB: {entry}")

        if entry:
            entry_dict = dict(entry)
            logger.debug(f"Converted entry_dict: {entry_dict}")

            # Parse lesson_state_json if it exists
            raw_json_string = entry_dict.get('lesson_state_json')
            if raw_json_string:
                log_json_str = (raw_json_string[:200] + '...') if len(raw_json_string) > 200 else raw_json_string
                logger.debug(f"Attempting to parse lesson_state_json: {log_json_str}")
                try:
                    entry_dict['lesson_state'] = json.loads(raw_json_string)
                    logger.debug("Successfully parsed lesson_state_json.")
                except json.JSONDecodeError as json_err:
                    logger.error(f"Failed to parse lesson_state_json for progress_id {entry_dict.get('progress_id')}: {json_err}", exc_info=True)
                    entry_dict['lesson_state'] = None
            else:
                 logger.debug("lesson_state_json is null or empty.")
                 entry_dict['lesson_state'] = None

            logger.debug(f"Returning entry_dict from get_lesson_progress: {entry_dict}")
            return entry_dict

        logger.debug("No progress entry found, returning None.")
        return None

    def get_user_syllabus_progress(self, user_id, syllabus_id):
        """
        Retrieves all progress entries for a user within a specific syllabus.

        Args:
            user_id (str): The ID of the user
            syllabus_id (str): The ID of the syllabus

        Returns:
            list: A list of progress entries, each including parsed 'lesson_state'.
        """
        logger.debug(f"Getting all progress for user {user_id}, syllabus {syllabus_id}")
        query = """
            SELECT * FROM user_progress
            WHERE user_id = ? AND syllabus_id = ?
        """
        progress_entries = self.execute_query(query, (user_id, syllabus_id))

        result = []
        for entry_row in progress_entries:
            entry_dict = dict(entry_row)
            # Parse lesson_state_json if it exists
            raw_json_string = entry_dict.get('lesson_state_json')
            if raw_json_string:
                try:
                    entry_dict['lesson_state'] = json.loads(raw_json_string)
                except json.JSONDecodeError as json_err:
                    logger.warning(f"Failed to parse lesson_state_json for progress_id {entry_dict.get('progress_id')}: {json_err}")
                    entry_dict['lesson_state'] = None
            else:
                 entry_dict['lesson_state'] = None
            result.append(entry_dict)

        logger.debug(f"Found {len(result)} progress entries.")
        return result

    def get_user_in_progress_courses(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves courses the user has progress entries for, along with progress details.
        Includes the last accessed timestamp for each course.

        Args:
            user_id (str): The ID of the user

        Returns:
            list: A list of dicts, each containing syllabus details and progress information.
        """
        logger.debug(f"Getting in-progress courses for user: {user_id}")
        # Get unique syllabus_ids and the latest updated_at for each syllabus the user has progress on
        progress_query = """
            SELECT syllabus_id, MAX(updated_at) as last_accessed
            FROM user_progress
            WHERE user_id = ?
            GROUP BY syllabus_id
            ORDER BY last_accessed DESC -- Optional: Order by most recently accessed
        """
        syllabi_progress = self.execute_query(progress_query, (user_id,))
        logger.debug(f"Found {len(syllabi_progress)} syllabi with progress for user {user_id}")

        in_progress_courses = []

        for syllabus_row in syllabi_progress:
            syllabus_id = syllabus_row["syllabus_id"]
            last_accessed = syllabus_row["last_accessed"]
            logger.debug(f"Processing syllabus {syllabus_id}, last accessed {last_accessed}")

            # Get syllabus details using the method that returns the nested structure
            syllabus = self.get_syllabus_by_id(syllabus_id) # Returns dict with nested 'content'

            if syllabus:
                # Calculate total lessons from the syllabus structure
                total_lessons = 0
                try:
                    # Access modules correctly within the nested structure
                    modules_in_content = syllabus.get("content", {}).get("modules", [])
                    if isinstance(modules_in_content, list):
                        for module in modules_in_content:
                            # Access lessons within the module's content field
                            lessons_in_module = module.get("content", {}).get("lessons", [])
                            if isinstance(lessons_in_module, list):
                                total_lessons += len(lessons_in_module)
                    logger.debug(f"Calculated total lessons for syllabus {syllabus_id}: {total_lessons}")
                except Exception as e:
                    logger.error(f"Error calculating total lessons for syllabus {syllabus_id}: {e}", exc_info=True)
                    # Decide how to handle - skip course, set total_lessons to 0 or -1?
                    continue # Skip this course if structure is invalid

                # Get completed lessons count from progress table
                progress_entries = self.get_user_syllabus_progress(user_id, syllabus_id)
                completed_lessons = sum(
                    1 for entry in progress_entries if entry["status"] == "completed"
                )
                logger.debug(f"Found {completed_lessons} completed lessons for syllabus {syllabus_id}")


                progress_percentage = (
                    round((completed_lessons / total_lessons * 100))
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
                        "last_accessed": last_accessed,
                    }
                )
            else:
                 logger.warning(f"Syllabus details not found for syllabus_id {syllabus_id} listed in progress.")


        logger.debug(f"Returning {len(in_progress_courses)} in-progress courses.")
        return in_progress_courses
