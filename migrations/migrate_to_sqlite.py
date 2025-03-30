import sys
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