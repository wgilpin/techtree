# backend/services/sqlite_db.py
"""Sqlite database service"""
# pylint: disable=broad-exception-caught

import os
import uuid
import json
import sqlite3
from datetime import datetime, timezone # Added timezone
from pathlib import Path
from typing import (
    Optional,
    List,
    Dict,
    Any,
    Callable,
    Tuple,
    Union,
)

# Import logger
from backend.logger import logger


class SQLiteDatabaseService:
    """
    Service class for interacting with the SQLite database.
    """

    def __init__(self, db_path: str = "techtree.db") -> None:
        """
        Initializes SQLiteDatabaseService, connecting to the SQLite database and creating tables.
        """
        self.conn: sqlite3.Connection
        try:
            # Always use the root directory for the database
            root_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            abs_path = os.path.join(root_dir, db_path)
            logger.info(f"Using database at root directory: {abs_path}")

            # Ensure the directory exists
            db_dir = os.path.dirname(abs_path)
            Path(db_dir).mkdir(parents=True, exist_ok=True)

            # Check if file exists
            db_exists = os.path.exists(abs_path)
            if not db_exists:
                logger.warning(
                    f"Database file does not exist, will be created at: {abs_path}"
                )

            # Connect to the database with proper settings for concurrent access
            self.conn = sqlite3.connect(
                abs_path,
                check_same_thread=False,
                timeout=30.0,
            )

            # Enable foreign keys
            self.conn.execute("PRAGMA foreign_keys = ON")

            # Enable WAL mode for better concurrency
            self.conn.execute("PRAGMA journal_mode = WAL")

            # Use Row factory for dict-like access to rows
            self.conn.row_factory = sqlite3.Row

            logger.info(f"SQLite database initialized at: {abs_path}")

            # Create tables if they don't exist
            if not db_exists:
                self._create_tables()
                logger.info("Database tables created")

        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}", exc_info=True)
            raise

    def _create_tables(self) -> None:
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

    def close(self) -> None:
        """
        Closes the database connection.
        """
        if hasattr(self, "conn") and self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    # Type hint for params and return value
    def execute_query(
        self,
        query: str,
        params: Optional[Union[Tuple[Any, ...], Dict[str, Any]]] = None,
        fetch_one: bool = False,
        commit: bool = False,
    ) -> Any:
        """
        Executes a SQL query with error handling and optional commit.

        Args:
            query (str): The SQL query to execute
            params (tuple or dict, optional): Parameters for the query
            fetch_one (bool): Whether to fetch one result or all results
            commit (bool): Whether to commit the transaction

        Returns:
            The query results (single row, list of rows, or None).
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
                return cursor.fetchone()  # Returns a Row or None
            else:
                return cursor.fetchall()  # Returns a list of Rows

        except sqlite3.Error as e:
            logger.error(f"Database error: {str(e)}", exc_info=True)
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            raise

    # Type hint for params and return value
    def execute_read_query(
        self,
        query: str,
        params: Optional[Union[Tuple[Any, ...], Dict[str, Any]]] = None,
    ) -> List[sqlite3.Row]:
        """
        Executes a read-only SQL query.

        Args:
            query (str): The SQL query to execute.
            params (tuple or dict, optional): Parameters for the query.

        Returns:
            list: The query results as a list of Row objects.
        """
        # execute_query returns List[Row] when fetch_one=False
        result = self.execute_query(query, params, fetch_one=False)
        return result if isinstance(result, list) else []

    # Type hint for func and return value
    def _transaction(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """
        Executes a function within a transaction.

        Args:
            func: The function to execute
            *args, **kwargs: Arguments to pass to the function

        Returns:
            The result of the function
        """
        try:
            with self.conn:
                return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Transaction error: {str(e)}", exc_info=True)
            raise

    # Type hint for return value
    def get_all_table_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieves all data from all tables in the database.

        Returns:
            dict: A dictionary containing all table data.
        """
        # Add type hint for data
        data: Dict[str, List[Dict[str, Any]]] = {}

        # Get list of tables
        tables_query = """SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'"""
        tables = self.execute_read_query(tables_query)  # Use typed read query

        for table_row in tables:
            table_name = table_row[0]
            data[table_name] = []

            # Get all rows from the table
            rows = self.execute_read_query(
                f"SELECT * FROM {table_name}"
            )  # Use typed read query

            for row in rows:
                data[table_name].append(dict(row))

        return data

    # User methods
    # Type hints for args and return
    def create_user(
        self, email: str, password_hash: str, name: Optional[str] = None
    ) -> str:
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
            logger.info(f"Creating user with email: {email}, name: {name}")
            user_id = str(uuid.uuid4())
            now = datetime.now().isoformat()

            effective_name = name or email.split("@")[0]

            query = """
                INSERT INTO users (user_id, email, name, password_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            params = (user_id, email, effective_name, password_hash, now, now)

            self.execute_query(query, params, commit=True)
            logger.info(f"User inserted into database with ID: {user_id}")
            return user_id

        except Exception as e:
            logger.error(f"Error creating user: {str(e)}", exc_info=True)
            raise

    # Type hints for args and return
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a user from the database by their email address.

        Args:
            email (str): The email address of the user to retrieve

        Returns:
            dict: The user data if found, otherwise None
        """
        try:
            query = "SELECT * FROM users WHERE email = ?"
            user_row = self.execute_query(
                query, (email,), fetch_one=True
            )  # Returns Row or None

            if user_row:
                user_dict = dict(user_row)
                return user_dict

            logger.warning(f"User not found: {email}")
            return None

        except Exception as e:
            logger.error(f"Error looking up user by email: {str(e)}", exc_info=True)
            raise

    # Type hints for args and return
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a user from the database by their user ID.

        Args:
            user_id (str): The ID of the user to retrieve

        Returns:
            dict: The user data if found, otherwise None
        """
        try:
            query = "SELECT * FROM users WHERE user_id = ?"
            user_row = self.execute_query(
                query, (user_id,), fetch_one=True
            )  # Returns Row or None

            if user_row:
                user_dict = dict(user_row)
                return user_dict

            logger.warning(f"User not found: {user_id}")
            return None

        except Exception as e:
            logger.error(f"Error looking up user by ID: {str(e)}", exc_info=True)
            raise

    # Assessment methods
    # Type hints for args and return
    def save_assessment(
        self,
        user_id: str,
        topic: str,
        knowledge_level: str,
        score: float,
        questions: List[Any],  # Use List[Any] for JSON-serializable list
        responses: List[Any],  # Use List[Any] for JSON-serializable list
    ) -> str:
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
            (assessment_id, user_id, topic, knowledge_level, score, question_history,
                response_history, created_at)
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

    # Type hints for args and return
    def get_user_assessments(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all assessments for a given user.

        Args:
            user_id (str): The ID of the user

        Returns:
            list: A list of assessment data dictionaries.
        """
        query = "SELECT * FROM user_assessments WHERE user_id = ?"
        assessments = self.execute_read_query(query, (user_id,))  # Use typed read query

        result: List[Dict[str, Any]] = []
        for assessment_row in assessments:
            assessment_dict = dict(assessment_row)

            # Parse JSON strings back to lists
            q_history = assessment_dict.get("question_history")
            if isinstance(q_history, str):
                try:
                    assessment_dict["question_history"] = json.loads(q_history)
                except json.JSONDecodeError:
                    logger.warning(
                        "Failed to parse question_history for assessment "
                        f"{assessment_dict.get('assessment_id')}"
                    )
                    assessment_dict["question_history"] = []
            else:
                assessment_dict["question_history"] = []

            r_history = assessment_dict.get("response_history")
            if isinstance(r_history, str):
                try:
                    assessment_dict["response_history"] = json.loads(r_history)
                except json.JSONDecodeError:
                    logger.warning(
                        "Failed to parse response_history for assessment "
                        f"{assessment_dict.get('assessment_id')}"
                    )
                    assessment_dict["response_history"] = []
            else:
                assessment_dict["response_history"] = []

            result.append(assessment_dict)

        return result

    # Type hints for args and return
    def get_assessment(self, assessment_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a specific assessment by its ID.

        Args:
            assessment_id (str): The ID of the assessment

        Returns:
            dict: The assessment data if found, otherwise None
        """
        query = "SELECT * FROM user_assessments WHERE assessment_id = ?"
        assessment_row = self.execute_query(
            query, (assessment_id,), fetch_one=True
        )  # Returns Row or None

        if assessment_row:
            assessment_dict = dict(assessment_row)

            # Parse JSON strings back to lists
            q_history = assessment_dict.get("question_history")
            if isinstance(q_history, str):
                try:
                    assessment_dict["question_history"] = json.loads(q_history)
                except json.JSONDecodeError:
                    logger.warning(
                        "Failed to parse question_history for assessment "
                        f"{assessment_dict.get('assessment_id')}"
                    )
                    assessment_dict["question_history"] = []
            else:
                assessment_dict["question_history"] = []

            r_history = assessment_dict.get("response_history")
            if isinstance(r_history, str):
                try:
                    assessment_dict["response_history"] = json.loads(r_history)
                except json.JSONDecodeError:
                    logger.warning(
                        "Failed to parse response_history for assessment "
                        f"{assessment_dict.get('assessment_id')}"
                    )
                    assessment_dict["response_history"] = []
            else:
                assessment_dict["response_history"] = []

            return assessment_dict

        return None

    # Syllabus methods
    # Type hints for args and return
    def save_syllabus(
        self,
        topic: str,
        level: str,
        content: Dict[str, Any],
        user_id: Optional[str] = None,
        user_entered_topic: Optional[str] = None,
    ) -> str:
        """
        Saves a syllabus to the database. Assumes 'content' contains 'modules',
        and each module dictionary contains 'title', 'summary', and 'lessons'.

        Args:
            topic (str): The topic of the syllabus (potentially AI-refined)
            level (str): The level of the syllabus
            content (dict): The content of the syllabus generated by AI/service.
                            Expected structure:
                                {"modules": [{"title": ..., "summary": ..., "lessons": [...]}]}
            user_id (str, optional): The ID of the user creating the syllabus
            user_entered_topic (str, optional): The original topic entered by the user.

        Returns:
            str: The newly created syllabus's ID
        """

        def _save_syllabus_transaction() -> str:  # Added return type hint
            syllabus_id = str(uuid.uuid4())
            now = datetime.now().isoformat()

            # Insert syllabus record
            syllabus_query = """
                INSERT INTO syllabi (syllabus_id, user_id, topic, level, user_entered_topic,
                    created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            effective_user_entered_topic = (
                user_entered_topic if user_entered_topic is not None else topic
            )
            syllabus_params = (
                syllabus_id,
                user_id,
                topic,
                level,
                effective_user_entered_topic,
                now,
                now,
            )
            cursor = self.conn.cursor()
            cursor.execute(syllabus_query, syllabus_params)

            # Insert modules and lessons
            modules_list = content.get("modules", [])
            for module_index, module_data in enumerate(modules_list):
                module_title = module_data.get("title", f"Module {module_index + 1}")
                module_summary = module_data.get("summary", "")

                module_query = """
                    INSERT INTO modules (syllabus_id, module_index, title, summary, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                module_params = (syllabus_id, module_index, module_title, module_summary, now, now)
                cursor.execute(module_query, module_params)
                module_id_result = cursor.execute(
                    "SELECT last_insert_rowid()"
                ).fetchone()
                if not module_id_result:
                    logger.error(
                        f"Failed to retrieve last insert rowid for module {module_index}"
                    )
                    raise RuntimeError("Failed to get module ID after insert.")
                module_id = module_id_result[0]

                lessons_list = module_data.get("lessons", [])
                for lesson_index, lesson_data in enumerate(lessons_list):
                    lesson_title = lesson_data.get("title", f"Lesson {lesson_index + 1}")
                    lesson_summary = lesson_data.get("summary", "")

                    lesson_query = """
                        INSERT INTO lessons (module_id, lesson_index, title, summary, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """
                    lesson_params = (
                        module_id,
                        lesson_index,
                        lesson_title,
                        lesson_summary,
                        now,
                        now,
                    )
                    cursor.execute(lesson_query, lesson_params)

            return syllabus_id

        try:
            # Execute the entire save operation within a transaction
            return self._transaction(_save_syllabus_transaction)
        except Exception as e:
            logger.error(f"Error saving syllabus transaction: {e}", exc_info=True)
            raise  # Re-raise the exception after logging

    # Type hints for args and return
    def get_syllabus(
        self, topic: str, level: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves a syllabus by topic and level, prioritizing user-specific syllabi.

        Args:
            topic (str): The topic of the syllabus
            level (str): The level of the syllabus
            user_id (str, optional): The ID of the user

        Returns:
            dict: The syllabus data if found, otherwise None
        """
        # Normalize topic and level for case-insensitive comparison
        norm_topic = topic.lower()
        norm_level = level.lower()

        syllabus_row: Optional[sqlite3.Row] = None

        if user_id:
            # Prioritize user-specific syllabus
            query_user = """
                SELECT * FROM syllabi
                WHERE user_id = ? AND lower(topic) = ? AND lower(level) = ?
                ORDER BY created_at DESC LIMIT 1
            """
            syllabus_row = self.execute_query(
                query_user, (user_id, norm_topic, norm_level), fetch_one=True
            )
            if syllabus_row is None:
                query_general = """
                    SELECT * FROM syllabi
                    WHERE user_id IS NULL AND lower(topic) = ? AND lower(level) = ?
                    ORDER BY created_at DESC LIMIT 1
                """
                syllabus_row = self.execute_query(
                    query_general, (norm_topic, norm_level), fetch_one=True
                )

        else:
            query_general = """
                SELECT * FROM syllabi
                WHERE user_id IS NULL AND lower(topic) = ? AND lower(level) = ?
                ORDER BY created_at DESC LIMIT 1
            """
            syllabus_row = self.execute_query(
                query_general, (norm_topic, norm_level), fetch_one=True
            )

        if syllabus_row:
            syllabus_dict = dict(syllabus_row)
            return self._build_syllabus_dict(syllabus_dict)
        else:
            return None

    # Type hints for args and return
    def get_syllabus_by_id(self, syllabus_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a syllabus by its unique ID.

        Args:
            syllabus_id (str): The unique ID of the syllabus

        Returns:
            dict: The syllabus data if found, otherwise None
        """
        query = "SELECT * FROM syllabi WHERE syllabus_id = ?"
        syllabus_row = self.execute_query(
            query, (syllabus_id,), fetch_one=True
        )  # Returns Row or None

        if syllabus_row:
            syllabus_dict = dict(syllabus_row)
            return self._build_syllabus_dict(syllabus_dict)

        return None

    # Type hints for args and return
    def _build_syllabus_dict(self, syllabus_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Helper function to build the full syllabus dictionary including modules and lessons.

        Args:
            syllabus_dict (dict): The base syllabus dictionary from the 'syllabi' table.

        Returns:
            dict: The fully constructed syllabus dictionary.
        """
        syllabus_id = syllabus_dict["syllabus_id"]

        # Fetch modules
        modules_query = """
            SELECT * FROM modules WHERE syllabus_id = ? ORDER BY module_index ASC
        """
        modules_result = self.execute_read_query(
            modules_query, (syllabus_id,)
        )  # Use typed read query

        top_level_content: Dict[str, Any] = {"modules": []}
        for module_data in modules_result:
            module_pk = module_data["module_id"]
            module_dict = dict(module_data)

            # Fetch lessons for the module
            lessons_query = """
                SELECT * FROM lessons WHERE module_id = ? ORDER BY lesson_index ASC
            """
            lessons_result = self.execute_read_query(
                lessons_query, (module_pk,)
            )  # Use typed read query

            module_dict["lessons"] = [dict(lesson) for lesson in lessons_result]
            top_level_content["modules"].append(module_dict)

        # Add the fetched content under the 'content' key
        syllabus_dict["content"] = top_level_content

        return syllabus_dict

    # Lesson methods
    # Type hints for args and return
    def save_lesson_content(
        self,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
        content: Dict[str, Any],
    ) -> int:
        """
        Saves the generated content for a specific lesson.

        Args:
            syllabus_id (str): The ID of the syllabus.
            module_index (int): The index of the module.
            lesson_index (int): The index of the lesson.
            content (dict): The generated lesson content (e.g., exposition).

        Returns:
            int: The primary key (lesson_id) of the lesson this content is associated with.

        Raises:
            ValueError: If the corresponding lesson cannot be found in the database.
            RuntimeError: If saving fails unexpectedly.
        """

        def _save_lesson_content_transaction() -> int:  # Added return type hint
            # 1. Find the lesson's primary key (lesson_id)
            lesson_pk_query = """
                SELECT l.lesson_id FROM lessons l
                JOIN modules m ON l.module_id = m.module_id
                WHERE m.syllabus_id = ? AND m.module_index = ? AND l.lesson_index = ?
            """
            lesson_pk_result = self.execute_query(
                lesson_pk_query,
                (syllabus_id, module_index, lesson_index),
                fetch_one=True,
            )

            if not lesson_pk_result:
                raise ValueError(
                    f"Lesson not found for syllabus {syllabus_id}, "
                    f"module {module_index}, lesson {lesson_index}"
                )
            lesson_pk = lesson_pk_result[0]

            # 2. Check if content already exists for this lesson_id
            existing_content_query = """
                SELECT content_id FROM lesson_content WHERE lesson_id = ?
            """
            existing_content_row = self.execute_query(
                existing_content_query, (lesson_pk,), fetch_one=True
            )

            content_json = json.dumps(content)
            now = datetime.now().isoformat()

            if existing_content_row:
                # Update existing content
                content_id = existing_content_row["content_id"]
                update_query = """
                    UPDATE lesson_content SET content = ?, updated_at = ?
                    WHERE content_id = ?
                """
                self.execute_query(update_query, (content_json, now, content_id))
            else:
                # Insert new content
                insert_query = """
                    INSERT INTO lesson_content (lesson_id, content, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                """
                self.execute_query(insert_query, (lesson_pk, content_json, now, now))
                content_id_result = self.execute_query("SELECT last_insert_rowid()", fetch_one=True)
                if not content_id_result:
                    raise RuntimeError("Failed to get content_id after insert.")
                content_id = content_id_result[0]

            return lesson_pk  # Return the lesson's primary key

        try:
            return self._transaction(_save_lesson_content_transaction)
        except Exception as e:
            logger.error(f"Error saving lesson content transaction: {e}", exc_info=True)
            raise

    # Type hints for args and return
    def get_lesson_content(
        self, syllabus_id: str, module_index: int, lesson_index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves the saved content for a specific lesson using syllabus/module/lesson indices.

        Args:
            syllabus_id (str): The ID of the syllabus.
            module_index (int): The index of the module.
            lesson_index (int): The index of the lesson.

        Returns:
            dict: The lesson content dictionary, or None if not found or error occurs.
        """
        # Query to get content using joins
        query = """
            SELECT lc.content
            FROM lesson_content lc
            JOIN lessons l ON lc.lesson_id = l.lesson_id
            JOIN modules m ON l.module_id = m.module_id
            WHERE m.syllabus_id = ? AND m.module_index = ? AND l.lesson_index = ?
        """
        params = (syllabus_id, module_index, lesson_index)
        content_row = self.execute_query(query, params, fetch_one=True)

        if content_row:
            content_str = content_row["content"]
            if isinstance(content_str, str):
                try:
                    parsed_content = json.loads(content_str)
                    return parsed_content if isinstance(parsed_content, dict) else None
                except json.JSONDecodeError:
                    logger.error(
                        f"Failed to parse lesson content JSON for {syllabus_id}/"
                        f"{module_index}/{lesson_index}",
                        exc_info=True,
                    )
                    return None
            else:
                logger.error(
                    f"Content fetched for {syllabus_id}/{module_index}/{lesson_index} "
                    "is not a string."
                )
                return None

        return None

    # Type hints for args and return
    def get_lesson_content_by_lesson_pk(
        self, lesson_pk: int
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves the saved content for a specific lesson using its primary key.

        Args:
            lesson_pk (int): The primary key (lesson_id) of the lesson.

        Returns:
            dict: The lesson content dictionary, or None if not found or error occurs.
        """
        content_query = "SELECT content FROM lesson_content WHERE lesson_id = ?"
        content_row = self.execute_query(content_query, (lesson_pk,), fetch_one=True)

        if content_row:
            content_str = content_row["content"]
            if isinstance(content_str, str):
                try:
                    parsed_content = json.loads(content_str)
                    # Ensure return is Dict or None
                    return parsed_content if isinstance(parsed_content, dict) else None
                except json.JSONDecodeError:
                    logger.error(
                        f"Failed to parse lesson content JSON for lesson_pk {lesson_pk}",
                        exc_info=True,
                    )
                    return None
            else:
                logger.error(
                    f"Content fetched for lesson_pk {lesson_pk} is not a string."
                )
                return None

        return None

    # Type hints for args and return
    def get_lesson_id(
        self, syllabus_id: str, module_index: int, lesson_index: int
    ) -> Optional[int]:
        """
        Retrieves the primary key (lesson_id) of a lesson using its indices.

        Args:
            syllabus_id (str): The ID of the syllabus.
            module_index (int): The index of the module.
            lesson_index (int): The index of the lesson.

        Returns:
            int: The lesson's primary key (lesson_id), or None if not found.
        """
        query = """
            SELECT l.lesson_id FROM lessons l
            JOIN modules m ON l.module_id = m.module_id
            WHERE m.syllabus_id = ? AND m.module_index = ? AND l.lesson_index = ?
        """
        params = (syllabus_id, module_index, lesson_index)
        try:
            result_row = self.execute_query(query, params, fetch_one=True)
            if result_row:
                lesson_pk = result_row["lesson_id"]
                if isinstance(lesson_pk, int):
                    return lesson_pk
                else:
                    logger.error(f"Retrieved non-integer lesson_pk: {lesson_pk}")
                    return None
            return None
        except Exception as e:
            logger.error(f"Error retrieving lesson ID (PK): {str(e)}", exc_info=True)
            raise

    # Type hints for args and return
    def get_lesson_by_id(self, lesson_content_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves lesson details (title, summary, indices) using the lesson_content_id.

        Args:
            lesson_content_id (str): The ID from the lesson_content table.

        Returns:
            dict: Lesson details including title, summary, module_index, lesson_index,
                  or None if not found.
        """
        # Query joining lesson_content, lessons, and modules tables
        query = """
            SELECT l.title, l.summary, l.lesson_index, m.module_index, m.syllabus_id
            FROM lesson_content lc
            JOIN lessons l ON lc.lesson_id = l.lesson_id
            JOIN modules m ON l.module_id = m.module_id
            WHERE lc.content_id = ?
        """
        params = (lesson_content_id,)
        result_row = self.execute_query(query, params, fetch_one=True)

        if result_row:
            lesson_details = {
                "title": result_row["title"],
                "summary": result_row["summary"],
                "lesson_index": result_row["lesson_index"],
                "module_index": result_row["module_index"],
                "syllabus_id": result_row["syllabus_id"],
            }
            return lesson_details

        return None

    # Progress methods
    # Type hints for args and return
    def save_user_progress(
        self,
        user_id: str,
        syllabus_id: str,
        module_index: int,
        lesson_index: int,
        status: str,
        lesson_id: Optional[int] = None,  # Allow passing lesson_id PK directly
        lesson_state_json: Optional[str] = None,
    ) -> str:
        """
        Saves or updates the progress for a specific lesson for a user.

        Args:
            user_id (str): The ID of the user.
            syllabus_id (str): The ID of the syllabus.
            module_index (int): The index of the module.
            lesson_index (int): The index of the lesson.
            status (str): The progress status (e.g., 'not_started', 'in_progress', 'completed').
            lesson_id (int, optional): The primary key of the lesson. If None, it will be looked up.
            lesson_state_json (str, optional): JSON string representing the conversational state.

        Returns:
            str: The ID of the progress entry (UUID)
        """
        now = datetime.now().isoformat()

        # Ensure we have the lesson_id PK if not provided
        if lesson_id is None:
            retrieved_lesson_id = self.get_lesson_id(
                syllabus_id, module_index, lesson_index
            )
            if retrieved_lesson_id is None:
                raise ValueError(
                    f"Could not find lesson_id PK for syllabus {syllabus_id}, "
                    f"mod {module_index}, lesson {lesson_index} to save progress."
                )
            lesson_id = retrieved_lesson_id

        # Check if progress entry already exists for this user and lesson
        check_query = "SELECT progress_id FROM user_progress WHERE user_id = ? AND lesson_id = ?"
        existing_progress = self.execute_query(
            check_query, (user_id, lesson_id), fetch_one=True
        )

        if existing_progress:
            progress_id = existing_progress["progress_id"]
            update_query = """
                UPDATE user_progress
                SET status = ?, updated_at = ?, lesson_state_json = ?
                WHERE progress_id = ?
            """
            update_params = (status, now, lesson_state_json, progress_id)
            self.execute_query(update_query, update_params, commit=True)
        else:
            progress_id = str(uuid.uuid4())
            insert_query = """
                INSERT INTO user_progress
                (progress_id, user_id, syllabus_id, module_index, lesson_index, lesson_id, status, created_at, updated_at, lesson_state_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            insert_params = (
                progress_id,
                user_id,
                syllabus_id,  # Added
                module_index, # Added
                lesson_index, # Added
                lesson_id,
                status,
                now,
                now,
                lesson_state_json,
            )
            self.execute_query(insert_query, insert_params, commit=True)

        return progress_id

    # Type hints for args and return
    def get_lesson_progress(
        self, user_id: str, syllabus_id: str, module_index: int, lesson_index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves the progress entry for a specific lesson for a user, including parsed state.

        Args:
            user_id (str): The ID of the user.
            syllabus_id (str): The ID of the syllabus.
            module_index (int): The index of the module.
            lesson_index (int): The index of the lesson.

        Returns:
            dict: Progress entry inc. parsed 'lesson_state' and 'lesson_id', or None if not found.
        """
        lesson_id_pk = self.get_lesson_id(syllabus_id, module_index, lesson_index)

        if lesson_id_pk is None:
            logger.warning("Could not find lesson_id PK to retrieve progress.")
            return None

        query = "SELECT * FROM user_progress WHERE user_id = ? AND lesson_id = ?"
        params = (user_id, lesson_id_pk)
        entry_row = self.execute_query(
            query, params, fetch_one=True
        )  # Returns Row or None

        if entry_row:
            entry_dict = dict(entry_row)

            # Parse lesson_state_json if it exists
            state_json = entry_dict.get("lesson_state_json")
            parsed_state: Optional[Dict[str, Any]] = None
            if isinstance(state_json, str):
                try:
                    parsed_state = json.loads(state_json)
                    if not isinstance(parsed_state, dict):
                        logger.warning("Parsed lesson_state_json is not a dictionary.")
                        parsed_state = None  # Treat non-dict JSON as invalid state
                except json.JSONDecodeError as json_err:
                    logger.error(
                        "Failed to parse lesson_state_json for progress_id "
                        f"{entry_dict.get('progress_id')}: {json_err}",
                        exc_info=True,
                    )
                    parsed_state = None
            else:
                parsed_state = None

            entry_dict["lesson_state"] = parsed_state  # Add parsed state to dict
            return entry_dict

        return None

    # Type hints for args and return
    def get_user_syllabus_progress(
        self, user_id: str, syllabus_id: str
    ) -> List[Dict[str, Any]]:
        """
        Retrieves all progress entries for a specific syllabus for a user.

        Args:
            user_id (str): The ID of the user.
            syllabus_id (str): The ID of the syllabus.

        Returns:
            list: A list of progress entry dictionaries.
        """
        query = """
            SELECT up.*, l.lesson_index, m.module_index
            FROM user_progress up
            JOIN lessons l ON up.lesson_id = l.lesson_id
            JOIN modules m ON l.module_id = m.module_id
            WHERE up.user_id = ? AND m.syllabus_id = ?
            ORDER BY m.module_index, l.lesson_index
        """
        params = (user_id, syllabus_id)
        result_rows = self.execute_read_query(query, params)

        result = [dict(row) for row in result_rows]
        return result

    # Type hints for args and return
    def _calculate_total_lessons(self, syllabus: Dict[str, Any] | None, syllabus_id: str) -> int:
        """Helper to calculate total lessons, preferring passed syllabus dict."""
        if syllabus and "content" in syllabus and "modules" in syllabus["content"]:
            return sum(
                len(module.get("lessons", []))
                for module in syllabus["content"]["modules"]
            )
        else:
            # Fallback to DB query if syllabus dict is incomplete/missing
            query = """
                SELECT COUNT(l.lesson_id)
                FROM lessons l
                JOIN modules m ON l.module_id = m.module_id
                WHERE m.syllabus_id = ?
            """
            result = self.execute_query(query, (syllabus_id,), fetch_one=True)
            total_lessons = result[0] if result else 0
            return total_lessons

    # Type hints for args and return
    def get_user_in_progress_courses(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves a summary of syllabi the user has made progress on.

        Returns:
            list: A list of dictionaries, each containing syllabus details and progress summary.
        """
        # Get unique syllabus_ids & the latest updated_at for each syllabus the user has progress on
        syllabi_query = """
            SELECT m.syllabus_id, MAX(up.updated_at) as last_accessed
            FROM user_progress up
            JOIN lessons l ON up.lesson_id = l.lesson_id
            JOIN modules m ON l.module_id = m.module_id
            WHERE up.user_id = ?
            GROUP BY m.syllabus_id
            ORDER BY last_accessed DESC
        """
        syllabi_progress = self.execute_read_query(
            syllabi_query, (user_id,)
        )  # Use typed read query

        in_progress_courses: List[Dict[str, Any]] = []
        for syllabus_row in syllabi_progress:
            syllabus_id = syllabus_row["syllabus_id"]
            last_accessed = syllabus_row["last_accessed"]

            # Get syllabus details (topic, level)
            syllabus_details = self.get_syllabus_by_id(syllabus_id)
            if not syllabus_details:
                logger.warning(f"Could not retrieve details for syllabus {syllabus_id}")
                continue

            # Calculate progress percentage
            completed_lessons_query = """
                SELECT COUNT(up.progress_id)
                FROM user_progress up
                JOIN lessons l ON up.lesson_id = l.lesson_id
                JOIN modules m ON l.module_id = m.module_id
                WHERE up.user_id = ? AND m.syllabus_id = ? AND up.status = 'completed'
            """
            completed_result = self.execute_query(
                completed_lessons_query, (user_id, syllabus_id), fetch_one=True
            )
            completed_lessons = completed_result[0] if completed_result else 0

            total_lessons = self._calculate_total_lessons(syllabus_details, syllabus_id)
            progress_percentage = (
                (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0
            )

            course_summary = {
                "syllabus_id": syllabus_id,
                "topic": syllabus_details.get("topic", "Unknown Topic"),
                "level": syllabus_details.get("level", "Unknown Level"),
                "progress_percentage": round(progress_percentage),
                "last_accessed": last_accessed,
                "total_lessons": total_lessons,
                "completed_lessons": completed_lessons,
            }
            in_progress_courses.append(course_summary)

        return in_progress_courses

    # Conversation History methods
    # Type hints for args
    def save_conversation_message(
        self,
        progress_id: str,
        role: str,
        message_type: str,
        content: str,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Saves a single message from a conversation turn to the history.

        Args:
            progress_id (str): The ID of the user progress entry this message belongs to.
            role (str): 'user' or 'assistant'.
            message_type (str): The type of message (e.g., 'CHAT_USER', 'EXERCISE_PROMPT').
            content (str): The text content of the message.
            timestamp (datetime, optional): When the message occurred. Defaults to now.
            metadata (dict, optional): Additional structured data related to the message.
        """
        message_id = str(uuid.uuid4())
        ts = timestamp or datetime.now(timezone.utc)
        ts_iso = ts.isoformat()
        metadata_json = json.dumps(metadata) if metadata else None

        query = """
            INSERT INTO conversation_history
            (message_id, progress_id, role, message_type, content, timestamp, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (message_id, progress_id, role, message_type, content, ts_iso, metadata_json)

        try:
            self.execute_query(query, params, commit=True)
        except Exception as e:
            logger.error(
                f"Error saving conversation message for progress {progress_id}: {e}",
                exc_info=True,
            )
            # Decide if we should raise here or just log

    # Type hints for args and return
    def get_conversation_history(self, progress_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves the conversation history for a specific user progress entry,
        ordered by timestamp.

        Args:
            progress_id (str): The ID of the user progress entry.

        Returns:
            list: A list of message dictionaries, ordered chronologically.
                  Returns an empty list if no history is found or on error.
        """
        query = """
            SELECT * FROM conversation_history
            WHERE progress_id = ?
            ORDER BY timestamp ASC
        """
        params = (progress_id,)
        history: List[Dict[str, Any]] = []

        try:
            message_rows = self.execute_read_query(query, params)
            for row in message_rows:
                message_dict = dict(row)
                # Deserialize metadata if present
                metadata_json = message_dict.get("metadata")
                if isinstance(metadata_json, str):
                    try:
                        message_dict["metadata"] = json.loads(metadata_json)
                    except json.JSONDecodeError:
                        logger.warning(
                            "Failed to parse metadata JSON for message "
                            f"{message_dict.get('message_id')}"
                        )
                        message_dict["metadata"] = (
                            None  # Or keep as string? Set to None for consistency.
                        )
                else:
                    message_dict["metadata"] = None  # Ensure it's None if not a string

                history.append(message_dict)

            return history
        except Exception as e:
            logger.error(
                f"Error retrieving conversation history for progress {progress_id}: {e}",
                exc_info=True,
            )
            return []  # Return empty list on error
