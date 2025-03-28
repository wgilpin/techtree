# Plan: On-Demand Exercise & Assessment Generation

**Goal:** Modify the system to generate lesson content (exposition) first, and then generate exercises and knowledge assessment questions only when requested by the user, ensuring no repetition.

**Phase 1: Backend Modifications**

1.  **Update Generation Prompts:**
    *   **Modify `backend/system_prompt.txt`:** Remove the sections defining "Active Learning Exercises" and "Knowledge Assessment" from the output requirements and format. Ensure the output only includes `exposition_content`, `thought_questions`, and `metadata`.
    *   **Create `backend/ai/lessons/prompts/generate_exercises.prompt`:** This new prompt will take lesson context (topic, exposition, syllabus context) and a list of *already generated* exercise descriptions/hashes as input. Its goal is to generate a specified number (e.g., 1-3) of *new* exercises, formatted similarly to the original `system_prompt.txt` definition, ensuring they are distinct from the provided list.
    *   **Create `backend/ai/lessons/prompts/generate_assessment.prompt`:** Similar to the exercises prompt, this will take lesson context and a list of *already generated* assessment question descriptions/hashes. It will generate a specified number of *new* assessment questions.

2.  **Update Data Models (`backend/models.py`):**
    *   Examine the current `Lesson` model (or equivalent Pydantic/SQLAlchemy model).
    *   Modify it to store exercises and assessment questions separately from the main content. Suggestion: Add fields like `generated_exercises: List[dict] = []` and `generated_assessment_questions: List[dict] = []`.
    *   Consider adding a mechanism to uniquely identify generated questions/exercises (e.g., hashing the question text) to facilitate the "no repetition" requirement when calling the new generation prompts.

3.  **Update AI Logic (`backend/ai/lessons/lessons_graph.py` or relevant module):**
    *   Modify the existing function responsible for generating the initial lesson content. It should now use the updated `system_prompt.txt` and expect the reduced JSON output.
    *   Implement new functions (e.g., `generate_new_exercises`, `generate_new_assessment_questions`) that:
        *   Accept lesson ID/context and the list of already generated items for that lesson.
        *   Load and format the new prompts (`generate_exercises.prompt`, `generate_assessment.prompt`).
        *   Call the LLM via `backend/ai/llm_utils.py`.
        *   Parse the LLM response containing the new items.
        *   Return the newly generated items.

4.  **Update Database/Storage Logic (`backend/services/` or data access layer):**
    *   Modify functions that save/update lesson data to handle the separate storage of exercises and assessment questions according to the updated models.
    *   Ensure retrieval functions can fetch the core content and the lists of generated items separately or together as needed.

5.  **Update API Endpoints (`backend/routers/lesson_router.py`):**
    *   Modify the endpoint that returns lesson details (e.g., `GET /lessons/{lesson_id}`) to initially return only the core content (`exposition_content`, `thought_questions`, `metadata`).
    *   Add a new endpoint: `POST /lessons/{lesson_id}/exercises`:
        *   Retrieves the lesson context and already generated exercises from the database.
        *   Calls the `generate_new_exercises` AI function.
        *   Appends the newly generated exercises to the lesson's `generated_exercises` list in the database.
        *   Returns the *newly* generated exercises.
    *   Add a new endpoint: `POST /lessons/{lesson_id}/assessment`:
        *   Functions similarly to the exercises endpoint but for assessment questions.
        *   Calls `generate_new_assessment_questions`.
        *   Updates and saves `generated_assessment_questions`.
        *   Returns the *newly* generated assessment questions.

**Phase 2: Frontend Modifications**

1.  **Update Lesson Template (`frontend/templates/lesson.html`):**
    *   Adjust the template to initially render only the `exposition_content` and `thought_questions`.
    *   Add buttons or UI elements like "Show me an exercise" and "Test my knowledge".

2.  **Update Frontend Logic (`frontend/lessons/lessons.py` and associated JS):**
    *   Modify the initial lesson loading logic to fetch and display only the core content.
    *   Implement event handlers for the new buttons.
    *   When a button is clicked:
        *   Make an asynchronous request (e.g., using `fetch` API in JS or `requests` in Flask view) to the corresponding new backend endpoint (`POST /lessons/{lesson_id}/exercises` or `POST /lessons/{lesson_id}/assessment`).
        *   Receive the newly generated item(s).
        *   Dynamically append the received exercise/question to the appropriate section on the page.
        *   Potentially disable the button temporarily or update its text (e.g., "Show another exercise").

**Phase 3: Testing (`backend/tests/`)**

1.  **Update Unit Tests:** Modify existing tests for lesson generation to assert that exercises/assessments are *not* present in the initial output.
2.  **Add New Unit Tests:** Create tests for the new AI functions (`generate_new_exercises`, `generate_new_assessment_questions`), potentially mocking the LLM call but verifying prompt formatting and response parsing. Test the "no repetition" logic by providing sample "already generated" lists.
3.  **Add New Integration Tests:** Test the new API endpoints (`POST /lessons/{lesson_id}/exercises`, `POST /lessons/{lesson_id}/assessment`). Verify that they trigger generation, update the database correctly, and return the new items.
4.  **Frontend Testing (Manual/Automated):** Verify the UI changes, button functionality, asynchronous calls, and dynamic display of generated items.

**`.clinerules` Considerations:**

*   **Functional Programming:** Python code implementation (in `code` mode) will adhere to functional principles (pure functions, immutability where practical, side-effect isolation) as specified.
*   **Testing:** Phase 3 explicitly includes testing, and `pytest` will be run after changes during implementation as required.

**Diagram:**

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend API
    participant AI Service
    participant Database

    User->>Frontend: Request Lesson Page
    Frontend->>Backend API: GET /lessons/{id}
    Backend API->>Database: Fetch Lesson Core Content (Exposition, Metadata)
    Database-->>Backend API: Lesson Core Content
    Backend API-->>Frontend: Lesson Core Content
    Frontend->>User: Display Lesson Exposition

    User->>Frontend: Click "Generate Exercise"
    Frontend->>Backend API: POST /lessons/{id}/exercises
    Backend API->>Database: Fetch Lesson Context & Existing Exercises
    Database-->>Backend API: Context, Existing Exercises List
    Backend API->>AI Service: generate_new_exercises(context, existing_list)
    AI Service-->>Backend API: New Exercise(s)
    Backend API->>Database: Append New Exercise(s) to Lesson
    Database-->>Backend API: Success
    Backend API-->>Frontend: New Exercise(s)
    Frontend->>User: Display New Exercise(s)

    Note over User, Database: Similar flow for Assessment Questions