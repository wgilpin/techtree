# Lesson Service Refactoring Plan

**Objective:** Refactor the monolithic `backend/services/lesson_service.py` to improve maintainability by separating concerns. Specifically, split the generation of static lesson exposition from the handling of interactive elements (chat, exercises, assessments).

**Proposed New Services:**

1.  **`LessonExpositionService`**: Handles the creation and retrieval of the static lesson exposition content.
2.  **`LessonInteractionService`**: Manages the user's interactive session with a lesson, including chat, state management, and the generation/handling of adaptive exercises and assessments.

**Proposed Structure Diagram:**

```mermaid
graph TD
    subgraph Routers/API Layer
        A[API Endpoint (e.g., /lesson/{id})]
    end

    subgraph Dependency Injection
        DI(Dependency Injector)
    end

    subgraph Services
        subgraph New Services
            LES[LessonExpositionService]
            LIS[LessonInteractionService]
        end
        subgraph Supporting Services
            DB[SQLiteDatabaseService]
            SS[SyllabusService]
            LAI[LessonAI]
        end
    end

    A --> DI
    DI --> LIS
    DI --> LES

    LIS --> LES(Get Exposition)
    LIS --> DB(Save/Load State, Exercises, Questions)
    LIS --> SS(Get Syllabus Details)
    LIS --> LAI(Process Chat)
    LIS --> LLM_Interaction(Generate Exercise/Assessment) %% Called by LAI?

    LES --> DB(Save/Load Exposition)
    LES --> SS(Get Syllabus Details)
    LES --> LLM_Exposition(Generate Exposition)

    %% Dashed lines for LLM calls
    LLM_Exposition -- LLM Call --> LES
    LLM_Interaction -- LLM Call --> LIS %% Or directly from LAI?

    style LLM_Exposition fill:#f9f,stroke:#333,stroke-width:2px
    style LLM_Interaction fill:#f9f,stroke:#333,stroke-width:2px
```

**Refactoring Steps:**

1.  **Create `backend/services/lesson_exposition_service.py`:**
    *   Class `LessonExpositionService`.
    *   Dependencies: `db_service: SQLiteDatabaseService`, `syllabus_service: SyllabusService`.
    *   Methods:
        *   `_generate_and_save_exposition` (from `_generate_and_save_lesson_content`).
        *   `get_or_generate_exposition` (logic from `get_or_generate_lesson` focused on fetching/generating static content and `lesson_db_id`).
        *   `get_exposition_by_id` (adapted from `get_lesson_by_id`).

2.  **Create `backend/services/lesson_interaction_service.py`:**
    *   Class `LessonInteractionService`.
    *   Dependencies: `db_service: SQLiteDatabaseService`, `syllabus_service: SyllabusService`, `exposition_service: LessonExpositionService`, `lesson_ai: LessonAI`.
    *   Methods:
        *   `_initialize_lesson_state` (from `LessonService`).
        *   `get_or_create_lesson_state` (new method orchestrating `exposition_service.get_or_generate_exposition`, loading state via `db_service.get_lesson_progress`, and calling `_initialize_lesson_state` if needed).
        *   `handle_chat_turn` (from `LessonService`, calls `lesson_ai.process_chat_turn`).
        *   `generate_exercise` (from `generate_exercise_for_lesson`, likely called *by* `LessonAI`).
        *   `generate_assessment_question` (from `generate_assessment_question_for_lesson`, likely called *by* `LessonAI`).
        *   `update_lesson_progress` (from `LessonService`).

3.  **Update Dependency Injection (`backend/dependencies.py`):**
    *   Instantiate `LessonExpositionService`.
    *   Instantiate `LessonInteractionService`, injecting its dependencies (including the `LessonExpositionService` instance and `LessonAI`). Ensure `LessonAI` receives the `LessonInteractionService` instance if it needs to call back for generation/saving.
    *   Remove `LessonService` instantiation.

4.  **Update API Routers (`backend/routers/`):**
    *   Change route dependencies from `LessonService` to `LessonInteractionService`.
    *   Update calls (e.g., use `interaction_service.get_or_create_lesson_state`).

5.  **Remove `backend/services/lesson_service.py`**.

6.  **Update and Run Tests (`backend/tests/`)**: Ensure all tests pass after refactoring.