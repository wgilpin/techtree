# Refactoring Plan for `backend/ai/lessons/lessons_graph.py`

**Goals:**

1.  **Reduce File Length:** Break down `lessons_graph.py` into focused modules.
2.  **Simplify Logic:** Refactor LLM interactions and control flow.
3.  **Externalize Prompts:** Move prompts to separate files.
4.  **Add Type Annotations:** Enhance type safety.
5.  **Use Pydantic:** Leverage Pydantic for data validation.

**Phases:**

1.  **Preparation & Prompt Externalization:**
    *   Create `backend/ai/lessons/prompts/`.
    *   Extract prompts from `lessons_graph.py` methods (`_route_message_logic`, `_generate_chat_response`, `_evaluate_chat_answer`, `_generate_lesson_content`) into files like `intent_classification.prompt`, `chat_response.prompt`, etc., within `prompts/`.
    *   Create `backend/ai/prompt_loader.py` with a utility to load and format prompts.
    *   Update `lessons_graph.py` methods to use the `prompt_loader`.

2.  **Centralize LLM Interaction & Refactor Nodes:**
    *   Create `backend/ai/llm_utils.py`.
    *   Move `call_with_retry` to `llm_utils.py`.
    *   Implement `call_llm_with_json_parsing` in `llm_utils.py` to handle LLM calls, JSON extraction/parsing, optional Pydantic validation, and error handling.
    *   Define Pydantic models (e.g., `IntentClassificationResult`, `EvaluationResult`) in `backend/models.py`.
    *   Refactor LLM-calling methods in `lessons_graph.py` to use `llm_utils.call_llm_with_json_parsing` and the Pydantic models.

3.  **Code Organization & Cleanup:**
    *   Move the `LessonState` TypedDict definition from `lessons_graph.py` to `backend/models.py`.
    *   Remove legacy code: methods from line 906 onwards (`_initialize`, `_retrieve_syllabus`, etc.) and commented-out public methods in `lessons_graph.py`.
    *   Remove the `get_user_progress` method from the `LessonAI` class.
    *   Ensure `_update_progress` node in the graph is a no-op or removed, as progress saving will be handled externally.
    *   Refine `LessonAI` public interface to focus on `__init__`, `start_chat`, and `process_chat_turn`.

4.  **Type Annotations & Final Review:**
    *   Add comprehensive type hints to all modified/new files (`lessons_graph.py`, `llm_utils.py`, `prompt_loader.py`, `models.py`).
    *   Perform a final code review.

**Proposed Structure Diagram:**

```mermaid
graph TD
    subgraph Service_Layer_lesson_service_py
        A[API Request] --> B{Lesson Service};
        B --> C[Load/Create State];
        C --> D(LessonAI Instance);
        D -- start_chat() / process_chat_turn() --> F[lessons_graph.py: LessonAI];
        F -- Uses Nodes --> G[Graph Nodes];
        G -- Uses LLM Util --> H(llm_utils.py);
        H -- Loads Prompts --> I(prompt_loader.py);
        I -- Reads Files --> J[prompts/*.prompt];
        H -- Uses Gemini API --> K[Google Gemini];
        H -- Uses Pydantic --> L(models.py);
        G -- Uses State --> M(LessonState defined in models.py);
        F -- Returns Updated State --> B;
        B --> N[Save State/Progress Externally];
        N --> O[DB Service];
        O --> P[(Database)];
        B --> Q[Return API Response];
    end

    style F fill:#f9f,stroke:#333,stroke-width:2px
    style H fill:#ccf,stroke:#333,stroke-width:2px
    style I fill:#ccf,stroke:#333,stroke-width:2px
    style L fill:#cfc,stroke:#333,stroke-width:2px
    style M fill:#cfc,stroke:#333,stroke-width:2px