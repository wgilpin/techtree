# SQLite Migration Plan: TinyDB to SQLite

## Overview

This document outlines the plan for migrating the TechTree application from TinyDB to SQLite. The migration will improve reliability with concurrent access from multiple servers, provide better data integrity through foreign key constraints, and optimize query performance.

## Table of Contents

1. [Database Schema](#database-schema)
2. [SQLiteDatabaseService Implementation](#sqlitedatabaseservice-implementation)
3. [Migration Strategy](#migration-strategy)
4. [Service Layer Changes](#service-layer-changes)
5. [Testing Approach](#testing-approach)
6. [Deployment Considerations](#deployment-considerations)

## Database Schema

The SQLite database will use the following schema:

```sql
-- Enable foreign key constraints
PRAGMA foreign_keys = ON;

-- Enable Write-Ahead Logging for better concurrency
PRAGMA journal_mode = WAL;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- User assessments table
CREATE TABLE IF NOT EXISTS user_assessments (
    assessment_id TEXT PRIMARY KEY,
    user_id TEXT,
    topic TEXT NOT NULL,
    knowledge_level TEXT NOT NULL,
    score REAL,
    question_history TEXT,  -- JSON text
    response_history TEXT,  -- JSON text
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_assessments_user_id ON user_assessments(user_id);

-- Syllabi table
CREATE TABLE IF NOT EXISTS syllabi (
    syllabus_id TEXT PRIMARY KEY,
    user_id TEXT,
    topic TEXT NOT NULL,
    level TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_syllabi_topic_level ON syllabi(topic, level);
CREATE INDEX IF NOT EXISTS idx_syllabi_user_id ON syllabi(user_id);

-- Modules table
CREATE TABLE IF NOT EXISTS modules (
    module_id INTEGER PRIMARY KEY AUTOINCREMENT,
    syllabus_id TEXT NOT NULL,
    module_index INTEGER NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (syllabus_id) REFERENCES syllabi(syllabus_id) ON DELETE CASCADE,
    UNIQUE(syllabus_id, module_index)
);
CREATE INDEX IF NOT EXISTS idx_modules_syllabus_id ON modules(syllabus_id);

-- Lessons table
CREATE TABLE IF NOT EXISTS lessons (
    lesson_id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id INTEGER NOT NULL,
    lesson_index INTEGER NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    duration TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (module_id) REFERENCES modules(module_id) ON DELETE CASCADE,
    UNIQUE(module_id, lesson_index)
);
CREATE INDEX IF NOT EXISTS idx_lessons_module_id ON lessons(module_id);

-- Lesson content table
CREATE TABLE IF NOT EXISTS lesson_content (
    content_id TEXT PRIMARY KEY,
    lesson_id INTEGER NOT NULL,
    content TEXT NOT NULL,  -- JSON text
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (lesson_id) REFERENCES lessons(lesson_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_lesson_content_lesson_id ON lesson_content(lesson_id);

-- User progress table
CREATE TABLE IF NOT EXISTS user_progress (
    progress_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    syllabus_id TEXT NOT NULL,
    module_index INTEGER NOT NULL,
    lesson_index INTEGER NOT NULL,
    status TEXT NOT NULL,  -- "not_started", "in_progress", "completed"
    score REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (syllabus_id) REFERENCES syllabi(syllabus_id) ON DELETE CASCADE,
    UNIQUE(user_id, syllabus_id, module_index, lesson_index)
);
CREATE INDEX IF NOT EXISTS idx_progress_user_id ON user_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_progress_syllabus_id ON user_progress(syllabus_id);
CREATE INDEX IF NOT EXISTS idx_progress_user_syllabus ON user_progress(user_id, syllabus_id);
```

### Key Design Decisions

1. **Normalized Structure**: The database structure has been normalized to reduce redundancy and improve data integrity. For example, modules and lessons are now separate tables rather than nested JSON objects.

2. **Foreign Key Constraints**: Proper foreign key relationships between tables ensure referential integrity.

3. **Indexes**: Appropriate indexes on frequently queried columns improve performance.

4. **JSON Storage**: For complex nested data that doesn't need to be queried directly (like content), we'll store it as JSON text in the database.

5. **UUID Primary Keys**: UUID-based primary keys are maintained for distributed ID generation without coordination.

## SQLiteDatabaseService Implementation

The `SQLiteDatabaseService` class will replace the current `DatabaseService` class. Here's the implementation plan:

### 1. Create Schema File

Create a file `backend/services/schema.sql` containing the SQL schema defined above.

### 2. Implement SQLiteDatabaseService

Create a new file `backend/services/sqlite_db.py` with the `SQLiteDatabaseService` class:

```python
import os
import uuid
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

class SQLiteDatabaseService:
    """
    Service class for interacting with the SQLite database.
    """
    def __init__(self, db_path="techtree.db"):
        """
        Initializes the SQLiteDatabaseService, connecting to the SQLite database and creating tables.
        """
        try:
            # Always use the root directory for the database
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
                isolation_level=None,     # Enable autocommit mode
                timeout=30.0              # Set timeout for busy waiting
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
            os.path.dirname(os.path.abspath(__file__)),
            "schema.sql"
        )

        with open(schema_path, 'r') as f:
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

    def _execute_query(self, query, params=None, fetch_one=False, commit=False):
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
            self.conn.execute("BEGIN")
            result = func(*args, **kwargs)
            self.conn.execute("COMMIT")
            return result
        except Exception as e:
            self.conn.execute("ROLLBACK")
            print(f"Transaction error: {str(e)}")
            raise
```

### 3. Implement All Database Methods

Implement all the methods from the current `DatabaseService` class in the new `SQLiteDatabaseService` class. The methods should have the same signatures but use SQL queries instead of TinyDB operations.

Key methods to implement:

- User methods: `create_user`, `get_user_by_email`, `get_user_by_id`
- Assessment methods: `save_assessment`, `get_user_assessments`, `get_assessment`
- Syllabus methods: `save_syllabus`, `get_syllabus`, `get_syllabus_by_id`
- Lesson content methods: `save_lesson_content`, `get_lesson_content`, `get_lesson_by_id`
- User progress methods: `save_user_progress`, `get_user_syllabus_progress`, `get_user_in_progress_courses`

## Migration Strategy

### 1. Create Migration Script

Create a migration script `migrate_to_sqlite.py` in the project root:

```python
import os
import json
import sys
from tinydb import TinyDB
from backend.services.db import DatabaseService
from backend.services.sqlite_db import SQLiteDatabaseService

def migrate_data():
    """
    Migrates data from TinyDB to SQLite.
    """
    print("Starting migration from TinyDB to SQLite...")

    # Initialize services
    tinydb_service = DatabaseService()
    sqlite_service = SQLiteDatabaseService()

    try:
        # Get all data from TinyDB
        all_data = tinydb_service.get_all_table_data()

        # Migrate users
        print("\nMigrating users...")
        if "users" in all_data:
            for user in all_data["users"]:
                try:
                    sqlite_service.create_user(
                        email=user["email"],
                        password_hash=user["password_hash"],
                        name=user.get("name", user["email"].split("@")[0])
                    )
                    print(f"  Migrated user: {user['email']}")
                except Exception as e:
                    print(f"  Error migrating user {user.get('email')}: {str(e)}")

        # Migrate syllabi and related data
        print("\nMigrating syllabi...")
        if "syllabi" in all_data:
            for syllabus in all_data["syllabi"]:
                try:
                    # Save syllabus
                    syllabus_id = sqlite_service.save_syllabus(
                        topic=syllabus["topic"],
                        level=syllabus["level"],
                        content=syllabus["content"],
                        user_id=syllabus.get("user_id")
                    )
                    print(f"  Migrated syllabus: {syllabus['topic']} - {syllabus['level']}")
                except Exception as e:
                    print(f"  Error migrating syllabus {syllabus.get('syllabus_id')}: {str(e)}")

        # Migrate lesson content
        print("\nMigrating lesson content...")
        if "lesson_content" in all_data:
            for lesson in all_data["lesson_content"]:
                try:
                    content_id = sqlite_service.save_lesson_content(
                        syllabus_id=lesson["syllabus_id"],
                        module_index=lesson["module_index"],
                        lesson_index=lesson["lesson_index"],
                        content=lesson["content"]
                    )
                    print(f"  Migrated lesson content: {lesson['syllabus_id']}/{lesson['module_index']}/{lesson['lesson_index']}")
                except Exception as e:
                    print(f"  Error migrating lesson content: {str(e)}")

        # Migrate user assessments
        print("\nMigrating user assessments...")
        if "user_assessments" in all_data:
            for assessment in all_data["user_assessments"]:
                try:
                    assessment_id = sqlite_service.save_assessment(
                        user_id=assessment["user_id"],
                        topic=assessment["topic"],
                        knowledge_level=assessment["knowledge_level"],
                        score=assessment["score"],
                        questions=assessment["question_history"],
                        responses=assessment["response_history"]
                    )
                    print(f"  Migrated assessment: {assessment['assessment_id']}")
                except Exception as e:
                    print(f"  Error migrating assessment: {str(e)}")

        # Migrate user progress
        print("\nMigrating user progress...")
        if "user_progress" in all_data:
            for progress in all_data["user_progress"]:
                try:
                    progress_id = sqlite_service.save_user_progress(
                        user_id=progress["user_id"],
                        syllabus_id=progress["syllabus_id"],
                        module_index=progress["module_index"],
                        lesson_index=progress["lesson_index"],
                        status=progress["status"],
                        score=progress.get("score")
                    )
                    print(f"  Migrated progress: {progress['progress_id']}")
                except Exception as e:
                    print(f"  Error migrating progress: {str(e)}")

        print("\nMigration completed successfully!")

    except Exception as e:
        print(f"\nError during migration: {str(e)}")
        return False
    finally:
        # Close connections
        tinydb_service.db.close()
        sqlite_service.close()

    return True

if __name__ == "__main__":
    success = migrate_data()
    sys.exit(0 if success else 1)
```

### 2. Migration Process

1. **Backup**: Create a backup of the current TinyDB database file.
2. **Test Migration**: Run the migration script in a test environment.
3. **Verify Data**: Verify that all data has been correctly migrated.
4. **Switch Services**: Update the application to use the new `SQLiteDatabaseService`.
5. **Production Migration**: Run the migration script in the production environment.

## Service Layer Changes

### 1. Update Database Service Import

Update the import statements in all service files to use the new `SQLiteDatabaseService` instead of `DatabaseService`:

```python
# Before
from backend.services.db import DatabaseService

# After
from backend.services.sqlite_db import SQLiteDatabaseService as DatabaseService
```

### 2. Update Main Application

Update `backend/main.py` to use the new database service:

```python
# Before
from backend.services.db import DatabaseService

# After
from backend.services.sqlite_db import SQLiteDatabaseService as DatabaseService
```

### 3. Update Shutdown Handler

Update the shutdown handler in `backend/main.py`:

```python
@app.on_event("shutdown")
async def shutdown_event():
    """
    Gracefully closes the database connection on application shutdown.
    """
    db_service.close()
    print("Database connection closed.")
```

## Testing Approach

### 1. Unit Tests

Create unit tests for the new `SQLiteDatabaseService` class to ensure all methods work correctly:

```python
import unittest
import os
import tempfile
from backend.services.sqlite_db import SQLiteDatabaseService

class TestSQLiteDatabaseService(unittest.TestCase):
    def setUp(self):
        # Create a temporary database file
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")
        self.db_service = SQLiteDatabaseService(db_path=self.db_path)

    def tearDown(self):
        # Close the database connection and remove the temporary file
        self.db_service.close()
        self.temp_dir.cleanup()

    def test_create_user(self):
        # Test user creation
        user_id = self.db_service.create_user(
            email="test@example.com",
            password_hash="hashed_password",
            name="Test User"
        )

        # Verify user was created
        user = self.db_service.get_user_by_email("test@example.com")
        self.assertIsNotNone(user)
        self.assertEqual(user["user_id"], user_id)
        self.assertEqual(user["name"], "Test User")

    # Add more tests for other methods...
```

### 2. Integration Tests

Create integration tests to verify that the application works correctly with the new database service:

```python
import unittest
from fastapi.testclient import TestClient
from backend.main import app

class TestAPIWithSQLite(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_user_registration(self):
        # Test user registration
        response = self.client.post(
            "/auth/register",
            json={
                "email": "test@example.com",
                "password": "password123",
                "name": "Test User"
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("access_token", data)

    # Add more tests for other endpoints...
```

### 3. Migration Tests

Create tests to verify that the migration script works correctly:

```python
import unittest
import os
import tempfile
import json
from tinydb import TinyDB
from backend.services.sqlite_db import SQLiteDatabaseService
from migrate_to_sqlite import migrate_data

class TestMigration(unittest.TestCase):
    def setUp(self):
        # Create a temporary TinyDB file with test data
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tinydb_path = os.path.join(self.temp_dir.name, "test_tinydb.json")
        self.sqlite_path = os.path.join(self.temp_dir.name, "test_sqlite.db")

        # Create test data in TinyDB
        self.db = TinyDB(self.tinydb_path)
        self.users = self.db.table("users")
        self.users.insert({
            "user_id": "test-user-id",
            "email": "test@example.com",
            "name": "Test User",
            "password_hash": "hashed_password",
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00"
        })

        # Add more test data for other tables...

    def tearDown(self):
        # Close connections and remove temporary files
        self.db.close()
        self.temp_dir.cleanup()

    def test_migration(self):
        # Run migration
        success = migrate_data(
            tinydb_path=self.tinydb_path,
            sqlite_path=self.sqlite_path
        )
        self.assertTrue(success)

        # Verify data was migrated correctly
        sqlite_service = SQLiteDatabaseService(db_path=self.sqlite_path)
        user = sqlite_service.get_user_by_email("test@example.com")
        self.assertIsNotNone(user)
        self.assertEqual(user["name"], "Test User")

        # Verify other data...

        sqlite_service.close()
```

## Deployment Considerations

### 1. Database Backup

Before deploying the new SQLite implementation, create a backup of the current TinyDB database file.

### 2. Deployment Steps

1. **Stop Application**: Stop all running instances of the application.
2. **Backup Data**: Create a backup of the current TinyDB database file.
3. **Deploy New Code**: Deploy the new code with the SQLite implementation.
4. **Run Migration**: Run the migration script to transfer data from TinyDB to SQLite.
5. **Verify Migration**: Verify that all data has been correctly migrated.
6. **Start Application**: Start the application with the new SQLite implementation.
7. **Monitor**: Monitor the application for any issues.

### 3. Rollback Plan

In case of issues with the SQLite implementation, have a rollback plan ready:

1. **Stop Application**: Stop all running instances of the application.
2. **Restore Code**: Restore the previous code with the TinyDB implementation.
3. **Restore Data**: If necessary, restore the TinyDB database file from the backup.
4. **Start Application**: Start the application with the restored TinyDB implementation.

### 4. Concurrent Access Configuration

Configure SQLite for optimal concurrent access:

1. **WAL Mode**: Ensure Write-Ahead Logging (WAL) mode is enabled for better concurrency.
2. **Busy Timeout**: Set an appropriate busy timeout to handle concurrent access.
3. **Connection Pooling**: Consider implementing connection pooling for better performance.

### 5. Monitoring

Monitor the SQLite database for performance and issues:

1. **Database Size**: Monitor the size of the SQLite database file.
2. **Query Performance**: Monitor the performance of database queries.
3. **Locks**: Monitor for lock contention issues.
4. **Errors**: Monitor for database errors.

## Conclusion

This migration plan provides a comprehensive approach to replacing TinyDB with SQLite in the TechTree application. The plan includes a detailed database schema, implementation of the `SQLiteDatabaseService` class, migration strategy, service layer changes, testing approach, and deployment considerations.

By following this plan, the application will benefit from improved reliability with concurrent access, better data integrity through foreign key constraints, and optimized query performance.