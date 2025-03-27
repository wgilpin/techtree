#!/usr/bin/env python3
"""
Update the database schema to include user progress tracking
"""

from tinydb import TinyDB

# Initialize the database
db = TinyDB("syllabus_db.json")

# Check if user_progress table exists
if "user_progress" not in db.tables():
    print("Creating user_progress table...")
    user_progress_table = db.table("user_progress")
    user_progress_table.insert({"_schema_version": "1.0"})
    print("user_progress table created.")
else:
    print("user_progress table already exists.")

# Check if lesson_content table exists
if "lesson_content" not in db.tables():
    print("Creating lesson_content table...")
    lesson_content_table = db.table("lesson_content")
    lesson_content_table.insert({"_schema_version": "1.0"})
    print("lesson_content table created.")
else:
    print("lesson_content table already exists.")

# Print the current database schema
print("\nCurrent database schema:")
for table_name in db.tables():
    table = db.table(table_name)
    print(f"- {table_name}: {len(table)} records")

print("\nDatabase schema update complete.")