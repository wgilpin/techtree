"""
Migration script to add the lesson_id column and index to the user_progress table
and backfill existing rows.
"""
import sqlite3
from pathlib import Path

DB_NAME = "techtree.db"

def migrate():
    """Applies the database migration."""
    conn = None # Initialize conn outside try block
    try:
        # Construct path relative to the script's directory's parent (project root)
        script_dir = Path(__file__).parent
        db_path = script_dir / DB_NAME
        print(f"Attempting to connect to database at: {db_path}")

        if not db_path.exists():
            print(f"Error: Database file not found at {db_path}. Cannot migrate.")
            return

        conn = sqlite3.connect(str(db_path))
        # Use Row factory for easier access
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        print("Database connection successful.")

        # --- 1. Add column if it doesn't exist ---
        cursor.execute("PRAGMA table_info(user_progress)")
        columns = [column['name'] for column in cursor.fetchall()]

        if "lesson_id" not in columns:
            print("Adding 'lesson_id' column to 'user_progress' table...")
            # Add with NULL allowed initially for backfilling
            cursor.execute("ALTER TABLE user_progress ADD COLUMN lesson_id INTEGER NULL")
            conn.commit() # Commit after altering table
            print("'lesson_id' column added.")
        else:
            print("'lesson_id' column already exists in 'user_progress'.")

        # --- 2. Backfill lesson_id for existing rows ---
        print("Checking for existing user_progress rows with NULL lesson_id...")
        cursor.execute("""
            SELECT progress_id, syllabus_id, module_index, lesson_index
            FROM user_progress
            WHERE lesson_id IS NULL
        """)
        rows_to_update = cursor.fetchall()

        if not rows_to_update:
            print("No rows found needing lesson_id backfill.")
        else:
            print(f"Found {len(rows_to_update)} rows to backfill lesson_id...")
            updated_count = 0
            not_found_count = 0
            for row in rows_to_update:
                progress_id = row['progress_id']
                syllabus_id = row['syllabus_id']
                module_index = row['module_index']
                lesson_index = row['lesson_index']

                # Query to find the corresponding lesson_id
                lookup_query = """
                    SELECT l.lesson_id
                    FROM lessons l
                    JOIN modules m ON l.module_id = m.module_id
                    WHERE m.syllabus_id = ? AND m.module_index = ? AND l.lesson_index = ?
                """
                cursor.execute(lookup_query, (syllabus_id, module_index, lesson_index))
                lesson_result = cursor.fetchone()

                if lesson_result and lesson_result['lesson_id'] is not None:
                    found_lesson_id = lesson_result['lesson_id']
                    print(f"  Updating progress_id {progress_id} with lesson_id {found_lesson_id}...")
                    update_query = "UPDATE user_progress SET lesson_id = ? WHERE progress_id = ?"
                    cursor.execute(update_query, (found_lesson_id, progress_id))
                    updated_count += 1
                else:
                    print(f"  WARNING: Could not find matching lesson_id for progress_id {progress_id} "
                          f"(syllabus={syllabus_id}, mod={module_index}, lesson={lesson_index}). Skipping.")
                    not_found_count += 1

            conn.commit() # Commit after updating rows
            print(f"Backfill complete. Updated: {updated_count}, Not Found/Skipped: {not_found_count}")

        # --- 3. Add index for the column ---
        print("Creating index 'idx_progress_lesson_id' on 'user_progress(lesson_id)' if not exists...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_progress_lesson_id ON user_progress(lesson_id)")
        print("Index check/creation complete.")

        # Note: Adding FOREIGN KEY constraint retroactively is complex in SQLite.
        # The primary benefit comes from having the correct ID populated for application logic.

        print("Migration finished successfully.")

    except sqlite3.Error as e:
        print(f"Database error during migration: {e}")
        if conn:
            conn.rollback() # Rollback changes on error
            print("Rolled back database changes.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        if conn:
            conn.rollback()
            print("Rolled back database changes.")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    migrate()