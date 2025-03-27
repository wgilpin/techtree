# Database Schema (Mermaid Diagram)

```mermaid
erDiagram
    USERS ||--o{ USER_ASSESSMENTS : takes
    USERS ||--o{ USER_PROGRESS : has
    USERS ||--o{ SYLLABI : "creates (optional)"
    SYLLABI ||--|{ MODULES : contains
    SYLLABI ||--o{ USER_PROGRESS : "tracks progress for"
    MODULES ||--|{ LESSONS : contains
    LESSONS ||--|| LESSON_CONTENT : has

    USERS {
        string user_id PK
        string email
        string name
        string password_hash
        string created_at
        string updated_at
    }

    SYLLABI {
        string syllabus_id PK
        string user_id FK
        string topic
        string level
        string created_at
        string updated_at
    }

    MODULES {
        string module_id PK
        string syllabus_id FK
        int module_index
        string title
        string summary
        string created_at
        string updated_at
    }

    LESSONS {
        string lesson_id PK
        string module_id FK
        int lesson_index
        string title
        string summary
        string duration
        string created_at
        string updated_at
    }

    LESSON_CONTENT {
        string content_id PK
        string lesson_id FK
        string content
        string created_at
        string updated_at
    }

    USER_ASSESSMENTS {
        string assessment_id PK
        string user_id FK
        string topic
        string knowledge_level
        float score
        string question_history
        string response_history
        string created_at
    }

    USER_PROGRESS {
        string progress_id PK
        string user_id FK
        string syllabus_id FK
        int module_index
        int lesson_index
        string status
        float score
        string lesson_state_json
        string created_at
        string updated_at
    }
```

**Explanation of Relationships:**

*   `users` to `user_assessments`: One user can take zero or more assessments.
*   `users` to `user_progress`: One user can have zero or more progress entries.
*   `users` to `syllabi`: One user can optionally create zero or more syllabi (some syllabi might be general, not user-specific).
*   `syllabi` to `modules`: One syllabus contains one or more modules.
*   `syllabi` to `user_progress`: One syllabus can have zero or more progress entries associated with it (across different users).
*   `modules` to `lessons`: One module contains one or more lessons.
*   `lessons` to `lesson_content`: One lesson has exactly one content entry (based on the current upsert logic in `save_lesson_content`).

**Notes:**

*   Data types like `TEXT`, `INTEGER`, `REAL` are inferred based on common SQLite usage and the Python code. `TEXT` is often used for UUIDs and timestamps (ISO format).
*   `FK` denotes a Foreign Key relationship.
*   `PK` denotes a Primary Key.
*   The `lesson_content` to `lessons` relationship is marked as `||--||` (one-to-one) because the current code updates existing content rather than creating multiple versions per lesson.
*   The `user_progress` table uses `syllabus_id`, `module_index`, and `lesson_index` to identify the specific lesson for progress tracking, rather than a direct `lesson_id` foreign key. This might be a design choice to simplify progress lookup based on the syllabus structure known by the application layer.