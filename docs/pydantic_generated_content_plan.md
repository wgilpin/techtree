# Plan: Implement Pydantic for Generated Lesson Content

**Objective:** Improve robustness and maintainability of data handling between the backend and frontend by introducing Pydantic models for the `generated_content` structure.

**Scope:** Focus initially on the `generated_content` data structure.

**Model Location:** `backend/models.py`

---

## Phase 1: Define Pydantic Models

1.  **Create/Update `backend/models.py`:**
    *   Define Pydantic models representing the structure currently found within the `generated_content` dictionary.
    *   Example structure (requires refinement based on actual LLM output variations):
        ```python
        # backend/models.py
        from pydantic import BaseModel, Field
        from typing import List, Dict, Optional, Union, Any

        class Metadata(BaseModel):
            title: Optional[str] = None
            tags: Optional[List[str]] = None
            difficulty: Optional[int] = None
            related_topics: Optional[List[str]] = None
            prerequisites: Optional[List[str]] = None
            # Add any other metadata fields observed

        class ExpositionContentItem(BaseModel):
            # Based on format_exposition_to_markdown logic
            type: str
            text: Optional[str] = None
            level: Optional[int] = None # For headings
            items: Optional[List[str]] = None # For lists
            question: Optional[str] = None # For thought questions

        class ExpositionContent(BaseModel):
             # Assuming it might be a string OR a structured list
             content: Optional[Union[str, List[ExpositionContentItem]]] = None

        class Exercise(BaseModel):
            id: str
            type: str
            question: Optional[str] = None
            instructions: Optional[str] = None # Use alias if needed
            items: Optional[List[str]] = None # For ordering
            options: Optional[Union[Dict[str, str], List[str]]] = None # For MC
            expected_solution: Optional[str] = None
            correct_answer: Optional[str] = None # Use alias if needed
            hints: Optional[List[str]] = None
            explanation: Optional[str] = None
            misconceptions: Optional[Dict[str, str]] = None
            # Add any other exercise fields observed

        class AssessmentQuestion(BaseModel):
            id: str
            type: str
            question: str
            options: Optional[Union[Dict[str, str], List[str]]] = None # For MC/TF
            correct_answer: str
            explanation: Optional[str] = None
            # Add any other assessment fields observed

        # Main model for the generated content
        class GeneratedLessonContent(BaseModel):
            topic: Optional[str] = None # Or retrieve from syllabus context
            level: Optional[str] = None # Or retrieve from syllabus context
            exposition_content: Union[str, ExpositionContent, Dict[str, Any]] # Consider strictness vs flexibility
            # thought_questions: List[str] # Verify if part of exposition
            active_exercises: List[Exercise]
            knowledge_assessment: List[AssessmentQuestion]
            metadata: Metadata
        ```
2.  **Dependency:** Add `pydantic` to `pyproject.toml` (or requirements file) if not already present.

---

## Phase 2: Backend Integration

1.  **Modify `backend/ai/lessons/lessons_graph.py`:**
    *   In `_generate_lesson_content`, after parsing the LLM JSON, validate it against `GeneratedLessonContent` using `GeneratedLessonContent.model_validate(parsed_dict)`.
    *   Handle potential `ValidationError`.
    *   Ensure the function returns/saves the validated Pydantic model object or its dictionary representation (`.model_dump()`).
2.  **Update Backend API Endpoint (e.g., in `backend/routers/lessons.py`):**
    *   Ensure the endpoint returning lesson content uses the `GeneratedLessonContent` model.
    *   Use FastAPI's `response_model` or Flask's `.model_dump_json()` for serialization.

---

## Phase 3: Frontend Integration

1.  **Modify `frontend/lessons/lessons.py`:**
    *   Import models from `backend.models`.
    *   In `_fetch_lesson_data`, parse the received JSON `content` into `GeneratedLessonContent` using `.model_validate()`. Handle `ValidationError`.
    *   In `_process_lesson_content`, update logic to access data via model attributes (e.g., `model.metadata.title`). Pass the `model.exposition_content` object to `format_exposition_to_markdown`.
    *   In `format_exposition_to_markdown`, update logic to handle the `ExpositionContent` model object as input.

---

## Phase 4: Testing

1.  **Unit Tests:** Add/update tests for functions modified in Phase 3 using Pydantic model instances.
2.  **Integration Tests:** Test the backend API endpoint schema and the frontend's fetch/display functionality.

---

## Considerations

*   **Frontend-Backend Coupling:** Acknowledge the tight coupling introduced by `frontend` importing from `backend`.
*   **LLM Output Variability:** Plan for handling `ValidationError` if LLM output deviates from the schema.
*   **Database Storage:** Ensure compatibility between Pydantic models and JSON storage in the database.

---

## Diagram

```mermaid
graph TD
    subgraph Backend
        direction LR
        LLM[LLM Generates JSON String] --> ParseJSON[Parse JSON String to Dict]
        ParseJSON --> ValidatePydantic[Validate Dict vs GeneratedLessonContent Model]
        ValidatePydantic -- Valid --> PydanticObject[GeneratedLessonContent Instance]
        ValidatePydantic -- Invalid --> HandleError[Log Error / Fallback]
        PydanticObject --> StoreDB[(Optional) Store in DB]
        PydanticObject --> BackendAPI[Backend API Endpoint /lessons/.../{content}]
        BackendAPI -- Serialize --> JSONResponse[JSON Payload]
    end

    subgraph Frontend
        direction LR
        JSONResponse --> FetchAPI[Frontend _fetch_lesson_data]
        FetchAPI --> ParsePydantic[Parse JSON to GeneratedLessonContent Model]
        ParsePydantic -- Valid --> PydanticObjectFE[GeneratedLessonContent Instance]
        ParsePydantic -- Invalid --> HandleErrorFE[Flash Error / Fallback]
        PydanticObjectFE --> ProcessContent[_process_lesson_content]
        ProcessContent --> FormatExposition[format_exposition_to_markdown]
        FormatExposition --> MarkdownString[Formatted Markdown]
        MarkdownString --> RenderTemplate[Render lesson.html]
        PydanticObjectFE --> RenderTemplate
    end

    subgraph Shared Definition (in backend/models.py)
      PydanticModels[GeneratedLessonContent, Exercise, etc.]
    end

    ValidatePydantic --> PydanticModels
    ParsePydantic --> PydanticModels

    style PydanticModels fill:#ccf,stroke:#333,stroke-width:2px