import sqlite3
import os

db_path = "techtree.db"
syllabus_id_to_find = "30643741-275d-4a09-a3a0-707588680816"
module_index_to_find = 1
lesson_index_to_find = 1

conn = None
try:
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
    else:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row # Ensure we can access columns by name
        cursor = conn.cursor()
        print(f"Finding module_id for syllabus {syllabus_id_to_find}, module index {module_index_to_find}")
        cursor.execute(
            "SELECT module_id FROM modules WHERE syllabus_id = ? AND module_index = ?",
            (syllabus_id_to_find, module_index_to_find)
        )
        module_row = cursor.fetchone()
        if not module_row:
            print("Error: Module not found.")
        else:
            module_id = module_row["module_id"]
            print(f"Found module_id: {module_id}")
            print(f"Finding lesson_id for module {module_id}, lesson index {lesson_index_to_find}")
            cursor.execute(
                "SELECT lesson_id FROM lessons WHERE module_id = ? AND lesson_index = ?",
                (module_id, lesson_index_to_find)
            )
            lesson_row = cursor.fetchone()
            if not lesson_row:
                print("Error: Lesson not found.")
            else:
                lesson_id_pk = lesson_row["lesson_id"]
                print(f"*** Found lesson_id Primary Key: {lesson_id_pk} ***")

except sqlite3.Error as e:
    print(f"Database error: {e}")
except Exception as e:
    print(f"An error occurred: {e}")
finally:
    if conn:
        conn.close()
        print("Database connection closed.")