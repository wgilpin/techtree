import sqlite3
import os

db_path = "techtree.db"
lesson_id_to_delete = "11" # Use the string ID based on previous logs

conn = None
try:
    # Ensure the path is correct relative to the script location if needed
    # For simplicity, assuming script runs from project root where techtree.db is
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
    else:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print(f"Attempting to delete content for lesson_id: {lesson_id_to_delete}")
        cursor.execute("DELETE FROM lesson_content WHERE lesson_id = ?", (lesson_id_to_delete,))
        conn.commit()
        deleted_rows = cursor.rowcount
        if deleted_rows > 0:
            print(f"Successfully deleted {deleted_rows} row(s) for lesson_id {lesson_id_to_delete}.")
        else:
            print(f"No rows found or deleted for lesson_id {lesson_id_to_delete}.")
except sqlite3.Error as e:
    print(f"Database error: {e}")
except Exception as e:
    print(f"An error occurred: {e}")
finally:
    if conn:
        conn.close()
        print("Database connection closed.")