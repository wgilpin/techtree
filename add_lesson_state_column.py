import sqlite3
import os

def add_lesson_state_column():
    """
    Adds the 'lesson_state_json' column to the 'user_progress' table
    in the SQLite database if it doesn't already exist.
    """
    db_path = "techtree.db"
    root_dir = os.path.dirname(os.path.abspath(__file__))
    abs_path = os.path.join(root_dir, db_path)

    print(f"Attempting to update schema for database: {abs_path}")

    if not os.path.exists(abs_path):
        print(f"Error: Database file not found at {abs_path}")
        print("Please ensure the database exists before running this script.")
        return

    conn = None
    try:
        conn = sqlite3.connect(abs_path)
        cursor = conn.cursor()

        # Check if the column already exists
        cursor.execute("PRAGMA table_info(user_progress)")
        columns = [column[1] for column in cursor.fetchall()]

        if "lesson_state_json" in columns:
            print("'lesson_state_json' column already exists in 'user_progress' table.")
        else:
            print("Adding 'lesson_state_json' column to 'user_progress' table...")
            # Add the column
            cursor.execute("ALTER TABLE user_progress ADD COLUMN lesson_state_json TEXT")
            conn.commit()
            print("'lesson_state_json' column added successfully.")

    except sqlite3.Error as e:
        print(f"SQLite error occurred: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    add_lesson_state_column()