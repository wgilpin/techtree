# Plan to Update docs/PRD.md

This document outlines the plan to update `docs/PRD.md` to reflect the current state of the Tech Tree application, based on analysis of planning documents and source code. The goal is to create an accurate description of the existing system, which can inform future development, including potential rebuilds in other languages.

## Key Findings from Analysis:

*   **Frontend:** Implemented using Flask (Python) serving HTML, not React/React Native.
*   **Backend:** Uses FastAPI (Python) and heavily relies on LangGraph for AI orchestration (Onboarding, Syllabus generation, Lesson interactions).
*   **Database:** Uses SQLite, not PostgreSQL/MongoDB. Includes tables for users, assessments, syllabi (modules, lessons), lesson content, user progress (with `lesson_state_json`), and conversation history.
*   **Architecture:** Client-server model: Flask Frontend -> FastAPI Backend -> LangGraph Services -> SQLite DB.

## Revised Update Plan for `docs/PRD.md`:

1.  **Section 1.3 Path to Production:**
    *   Describe the current implementation using LangGraph for AI orchestration.
    *   Add a note highlighting LangGraph's Python/TS specificity and the need for alternatives if rebuilding in Go/Elixir.

2.  **Section 4. User Stories / Use Cases:**
    *   Align Syllabus, Lessons, Adaptive Difficulty, and New Topic definitions with the current LangGraph/SQLite implementation (mentioning state and history storage).

3.  **Section 5. Key Features & Functionality:**
    *   Rephrase features to reflect the current LangGraph-driven implementation and stateful interactions/history.

4.  **Section 6. Non-Functional Requirements:**
    *   Re-evaluate Scalability based on SQLite (mentioning WAL mode) and potential bottlenecks.

5.  **Section 7. Technical Approach & Architecture:**
    *   **Major Overhaul:** Detail the *current* stack: Flask frontend, FastAPI backend, LangGraph for AI logic, SQLite database.
    *   **Add Portability Note:** Explicitly mention under the Backend/AI section that LangGraph is Python-specific and alternatives would be needed for a Go/Elixir rebuild.
    *   **Include Diagrams:** Add/reference diagrams showing the current Flask -> FastAPI -> LangGraph -> SQLite flow.

6.  **Section 7. Release Plan & Milestones:** (Optional)
    *   Review alignment with the current tech stack.

7.  **Section 8. Risks & Mitigations:**
    *   Add Risk: "Technology Lock-in (LangGraph)" hindering portability. Mitigation: "Identify/develop alternative graph libraries for target languages during rebuild planning."
    *   Keep risk related to SQLite scalability.

## Conceptual Flow Diagram (Current Architecture):

```mermaid
graph LR
    A[User (Browser)] -- HTTP --> B(Flask Frontend);
    B -- API Calls --> C(FastAPI Backend);
    C -- Uses --> D(SQLite DB Service);
    C -- Uses --> E(LangGraph Services);
    E -- Orchestrates --> F(Onboarding Graph);
    E -- Orchestrates --> G(Syllabus Graph);
    E -- Orchestrates --> H(Lesson Graph);
    F -- Calls --> I{LLM API};
    G -- Calls --> I;
    H -- Calls --> I;
    D -- Reads/Writes --> J[(SQLite DB)];