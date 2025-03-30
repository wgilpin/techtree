# Conversation History Refactoring Plan

**Date:** 2025-03-30

**Goal:** Refactor the application to store conversation history in a dedicated `conversation_history` table instead of a JSON blob within the `user_progress` table. This improves data structure, queryability, and scalability.

**Current State:**
*   Conversation history is stored as a list of dictionaries within the `lesson_state_json` TEXT column in the `user_progress` table.
*   Persistence is handled via `sqlite3` in `backend/services/sqlite_db.py`.
*   State management (loading/saving) is primarily done in `backend/services/lesson_interaction_service.py`.
*   State structure is defined in `backend/models.py` (`LessonState` TypedDict).

**Proposed Plan:**

1.  **Define Message Types:**
    *   Introduce categories to identify the context of each message. The following types will be used:
        *   `CHAT_USER`: Any message originating from the user.
        *   `CHAT_ASSISTANT`: Regular assistant response generated during general chat.
        *   `EXERCISE_PROMPT`: Assistant message presenting an exercise.
        *   `EXERCISE_FEEDBACK`: Assistant message providing feedback on an exercise attempt.
        *   `ASSESSMENT_PROMPT`: Assistant message presenting an assessment question.
        *   `ASSESSMENT_FEEDBACK`: Assistant message providing feedback on an assessment attempt.
        *   `SYSTEM_INFO`: Automated system messages (e.g., "Generating...").
        *   `ERROR`: Error messages shown to the user.

2.  **Database Schema Changes (`backend/services/schema.sql`):**
    *   Add a new table `conversation_history`:
        ```sql
        -- Conversation History table
        CREATE TABLE IF NOT EXISTS conversation_history (
            message_id TEXT PRIMARY KEY,         -- UUID for the message
            progress_id TEXT NOT NULL,           -- FK to user_progress (progress_id is PK)
            timestamp TEXT NOT NULL,             -- ISO 8601 timestamp
            role TEXT NOT NULL,                  -- 'user', 'assistant', 'system'
            message_type TEXT NOT NULL,          -- e.g., 'CHAT_USER', 'EXERCISE_PROMPT', etc.
            content TEXT NOT NULL,               -- The actual message content
            metadata TEXT,                       -- Optional JSON blob for extra info (e.g., exercise_id)
            FOREIGN KEY (progress_id) REFERENCES user_progress(progress_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_history_progress_id ON conversation_history(progress_id);
        CREATE INDEX IF NOT EXISTS idx_history_timestamp ON conversation_history(timestamp);
        ```

3.  **Database Service (`backend/services/sqlite_db.py`):**
    *   Implement `save_conversation_message(progress_id, role, message_type, content, metadata=None)`: Inserts a new row into `conversation_history`. Generates `message_id` (UUID) and `timestamp` internally.
    *   Implement `get_conversation_history(progress_id)`: Retrieves all messages for a given `progress_id`, ordered by `timestamp`. Returns a list of dictionaries or Row objects.

4.  **State Model (`backend/models.py`):**
    *   Remove the `conversation_history: List[Dict[str, str]]` field from the `LessonState` TypedDict definition.

5.  **Interaction Service (`backend/services/lesson_interaction_service.py`):**
    *   **State Handling:** Modify `serialize_state_data` and `deserialize_state_data` to no longer process the `conversation_history` key within the state dictionary.
    *   **Message Saving:** Update methods that currently modify the state's history list (e.g., `process_chat_turn`, `generate_new_exercise`, `generate_new_assessment`, and potentially logic within called AI nodes if they add messages directly).
        *   Instead of appending to `state['conversation_history']`, determine the correct `role` and `message_type` based on context.
        *   Call `self.db_service.save_conversation_message` with the `progress_id` from the state and the message details.
    *   **Message Retrieval:** Update logic that reads the history (e.g., preparing context for LLM calls in `process_chat_turn`) to call `self.db_service.get_conversation_history(progress_id)` instead of accessing `state['conversation_history']`.

6.  **AI Graph Nodes (`backend/ai/lessons/nodes.py`):**
    *   Review nodes (`chat_with_llm`, `evaluate_answer`, etc.).
    *   If nodes directly read `state["conversation_history"]`, modify them to receive the history list (fetched by the service) as an argument.
    *   If nodes directly append messages to `state["conversation_history"]`, refactor this logic so the message content is returned to the service layer, which will then call `save_conversation_message`.

7.  **Testing:**
    *   Update existing tests in `backend/tests/services/` and `backend/tests/ai/lessons/` that rely on the old `conversation_history` in the state.
    *   Add new tests for `save_conversation_message` and `get_conversation_history` in `sqlite_db.py`.
    *   Add tests to verify the interaction service correctly saves and retrieves history using the new methods.

8.  **Data Migration:**
    *   Create a standalone Python script (`migrate_conversation_history.py`).
    *   This script will:
        *   Connect to the SQLite database.
        *   Iterate through all records in `user_progress`.
        *   For each record:
            *   Parse the `lesson_state_json`.
            *   If `conversation_history` exists and is a list:
                *   Iterate through each message dictionary in the list.
                *   Determine the `role` (should exist).
                *   **Infer** the `message_type`:
                    *   If `role == 'user'`, set `message_type = 'CHAT_USER'`.
                    *   If `role == 'assistant'` or `'system'`: Attempt basic inference based on content keywords (e.g., "exercise", "question", "feedback", "error"). Default to `CHAT_ASSISTANT` or `SYSTEM_INFO` if unsure. This inference will be best-effort for historical data.
                *   Extract `content`.
                *   Call `db_service.save_conversation_message` (or execute direct SQL) to insert into `conversation_history`.
            *   Update the `lesson_state_json` in the `user_progress` record to remove the `conversation_history` key.
            *   Commit changes periodically or at the end.
    *   **Note:** Run this migration script *after* deploying the schema changes but *before* running the updated application code that relies on the new structure.

**Diagram (Simplified Flow):**

```mermaid
graph TD
    A[User Interaction] --> B(API Endpoint);
    B --> C{LessonInteractionService};
    C -- Loads State (minus history) --> D[DB: user_progress];
    C -- Gets History --> E[DB: conversation_history];
    C -- Passes State & History --> F(AI Graph / Nodes);
    F -- Generates Response --> C;
    C -- Saves New Message(s) --> E;
    C -- Saves Updated State (minus history) --> D;
    C --> B;
    B --> A;

    style D fill:#515,stroke:#333,stroke-width:2px;
    style E fill:#115,stroke:#333,stroke-width:2px;