# pylint: skip-file
# type: ignore

# migrate_conversation_history.py
import sqlite3
import json
import uuid
import os
from datetime import datetime
import logging
from typing import List, Dict, Any, Optional

# --- Configuration ---
# Assume DB is in the same root directory as this script
DB_FILENAME = "techtree_db.sqlite"
DB_PATH = os.path.abspath(DB_FILENAME)

# Setup basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- Helper Functions ---


def infer_message_type(role: str, content: str) -> str:
    """
    Attempts to infer the message type based on role and content keywords.
    This is a best-effort approach for historical data.
    """
    content_lower = content.lower() if isinstance(content, str) else ""

    if role == "user":
        return "CHAT_USER"
    elif role == "assistant":
        if "exercise" in content_lower and (
            "generated" in content_lower or "here's" in content_lower
        ):
            return "EXERCISE_PROMPT"
        if "assessment question" in content_lower and (
            "generated" in content_lower or "here's" in content_lower
        ):
            return "ASSESSMENT_PROMPT"
        # Basic check for feedback - might need refinement
        if (
            "correct" in content_lower
            or "incorrect" in content_lower
            or "feedback" in content_lower
            or "evaluation" in content_lower
        ):
            # Could be exercise or assessment feedback - default to generic?
            # Or try to guess based on previous message? Too complex for migration.
            # Let's default to CHAT_ASSISTANT for ambiguous feedback for now.
            # A more robust check might look at the previous message type if available.
            return "CHAT_ASSISTANT"  # Defaulting ambiguous feedback
        if "sorry" in content_lower and (
            "generate" in content_lower
            or "error" in content_lower
            or "issue" in content_lower
        ):
            return "ERROR"  # Treat generation failures as errors
        return "CHAT_ASSISTANT"  # Default assistant message
    elif role == "system":
        if "error" in content_lower:
            return "ERROR"
        return "SYSTEM_INFO"  # Default system message
    else:
        return "UNKNOWN"


# --- Main Migration Logic ---


def migrate_history() -> None:  # Added return type hint
    """Performs the conversation history migration."""
    logger.info(f"Starting conversation history migration for database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        logger.error(f"Database file not found at {DB_PATH}. Aborting migration.")
        return

    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # Access columns by name
        cursor = conn.cursor()

        # 1. Check if the new table exists (basic check)
        try:
            cursor.execute("SELECT 1 FROM conversation_history LIMIT 1")
            logger.info("'conversation_history' table already exists.")
        except sqlite3.OperationalError:
            logger.error(
                "'conversation_history' table not found. Ensure schema changes were applied first."
            )
            return

        # 2. Fetch all relevant user progress records
        cursor.execute(
            "SELECT progress_id, lesson_state_json FROM user_progress WHERE lesson_state_json IS NOT NULL"
        )
        progress_records = cursor.fetchall()
        logger.info(
            f"Found {len(progress_records)} user_progress records with lesson state."
        )

        migrated_message_count = 0
        updated_progress_count = 0

        # 3. Iterate and migrate each record
        for record in progress_records:
            progress_id = record["progress_id"]
            lesson_state_json = record["lesson_state_json"]
            needs_update = False

            try:
                lesson_state: Dict[str, Any] = json.loads(lesson_state_json)
                old_history: Optional[List[Dict[str, Any]]] = lesson_state.get(
                    "conversation_history"
                )

                if isinstance(old_history, list) and old_history:
                    logger.info(
                        f"Migrating {len(old_history)} messages for progress_id: {progress_id}"
                    )
                    needs_update = (
                        True  # Mark for update only if history exists and is processed
                    )

                    for message in old_history:
                        if not isinstance(message, dict):
                            logger.warning(
                                f"Skipping invalid message format in progress_id {progress_id}: {message}"
                            )
                            continue

                        role = message.get("role")
                        content = message.get("content")

                        if not role or not content:
                            logger.warning(
                                f"Skipping message with missing role/content in progress_id {progress_id}: {message}"
                            )
                            continue

                        message_type = infer_message_type(role, content)
                        message_id = str(uuid.uuid4())
                        timestamp = (
                            datetime.now().isoformat()
                        )  # Use current time for migration timestamp

                        # Insert into new table
                        cursor.execute(
                            """
                            INSERT INTO conversation_history
                            (message_id, progress_id, timestamp, role, message_type, content, metadata)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                message_id,
                                progress_id,
                                timestamp,
                                role,
                                message_type,
                                content,
                                None,
                            ),
                        )  # No metadata in old format
                        migrated_message_count += 1

                    # Remove old history from the state dict
                    lesson_state.pop("conversation_history", None)

                # Update the user_progress record if history was processed
                if needs_update:
                    updated_state_json = json.dumps(lesson_state)
                    cursor.execute(
                        """
                        UPDATE user_progress
                        SET lesson_state_json = ?
                        WHERE progress_id = ?
                    """,
                        (updated_state_json, progress_id),
                    )
                    updated_progress_count += 1

            except json.JSONDecodeError:
                logger.error(
                    f"Failed to parse lesson_state_json for progress_id: {progress_id}. Skipping."
                )
            except Exception as e:
                logger.error(
                    f"Error processing progress_id {progress_id}: {e}", exc_info=True
                )

        # 4. Commit changes
        conn.commit()
        logger.info(f"Migration complete. Migrated {migrated_message_count} messages.")
        logger.info(f"Updated {updated_progress_count} user_progress records.")

    except sqlite3.Error as e:
        logger.error(f"Database error during migration: {e}", exc_info=True)
        if conn:
            conn.rollback()  # Rollback on error
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed.")


# --- Execution ---
if __name__ == "__main__":
    migrate_history()
