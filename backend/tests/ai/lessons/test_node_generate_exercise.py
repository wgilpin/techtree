# backend/tests/ai/lessons/test_node_generate_exercise.py
"""Tests for backend/ai/lessons/nodes.py generate_new_exercise node"""
# pylint: disable=protected-access, unused-argument, invalid-name

from unittest.mock import MagicMock, patch
from typing import Optional, List, Dict, Any, cast # Added imports



# Import the node functions directly
from backend.ai.lessons import nodes
from backend.models import (
    Exercise,
    GeneratedLessonContent,
    LessonState,
)
from backend.ai.prompt_formatting import LATEX_FORMATTING_INSTRUCTIONS



class TestGenerateExerciseNode:
    """Tests for the generate_new_exercise node action."""

    # Basic state setup helper (copied and adapted)
    def _get_base_state(
        self,
        history: Optional[List[Dict[str, str]]] = None, # Use List[Dict[str, str]]
        existing_exercise_ids: Optional[List[str]] = None # Use List[str]
    ) -> LessonState:
        """Creates a base LessonState dictionary for testing exercise generation."""
        current_history = list(history) if history is not None else []

        # Ensure all keys from LessonState are present
        state: LessonState = {
            "topic": "Generation",
            "knowledge_level": "intermediate",
            "syllabus": None,
            "lesson_title": "Gen Ex Lesson",
            "module_title": "Module Gen",
            "generated_content": GeneratedLessonContent(
                exposition_content="Lesson content here."
            ),
            "user_responses": [],
            "user_performance": {},
            "user_id": "gen_ex_user",
            "lesson_uid": "gen_ex_lesson_uid",
            "created_at": "sometime",
            "updated_at": "sometime",
            "history_context": current_history, # Use history_context
            "current_interaction_mode": "chatting", # Assume user just requested
            "current_exercise_index": None,
            "current_quiz_question_index": None,
            "generated_exercises": [], # Will be populated by tests if needed
            "generated_assessment_questions": [],
            "generated_exercise_ids":
                existing_exercise_ids if existing_exercise_ids is not None else [],
            "generated_assessment_question_ids": [],
            "error_message": None,
            "active_exercise": None,
            "active_assessment": None,
            "potential_answer": None,
            "lesson_db_id": None,
        }
        return state

    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch("backend.ai.lessons.nodes.call_llm_with_json_parsing")
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_generate_new_exercise_success(
        self, mock_call_llm: MagicMock, mock_load_prompt: MagicMock
    ) -> None: # Added return type hint
        """Test successful generation of a new exercise."""
        mock_load_prompt.return_value = "mocked_gen_ex_prompt"
        mock_new_exercise = Exercise(
            id="ex_new_1",
            type="short_answer",
            instructions="New exercise?",
            correct_answer="Yes",
        )
        mock_call_llm.return_value = mock_new_exercise

        initial_history = [{"role": "assistant", "content": "What next?"}]
        state = self._get_base_state(history=initial_history)

        # Cast state before calling node
        # Node now returns state, exercise object, and assistant message dict
        updated_state, generated_exercise, assistant_message = nodes.generate_new_exercise(
            cast(Dict[str, Any], state)
        )

        mock_load_prompt.assert_called_once_with(
            "generate_exercises",
            topic="Generation",
            lesson_title="Gen Ex Lesson",
            user_level="intermediate",
            exposition_summary="Lesson content here.",
            syllabus_context="Module: Module Gen, Lesson: Gen Ex Lesson",
            existing_exercise_descriptions_json="[]",
            latex_formatting_instructions=LATEX_FORMATTING_INSTRUCTIONS,
        )
        mock_call_llm.assert_called_once_with(
            "mocked_gen_ex_prompt", validation_model=Exercise, max_retries=2
        )

        assert generated_exercise == mock_new_exercise
        assert updated_state["active_exercise"] == mock_new_exercise
        assert updated_state["generated_exercise_ids"] == ["ex_new_1"]
        assert updated_state["current_interaction_mode"] == "awaiting_answer"

        # Check the returned assistant message
        assert assistant_message is not None
        assert assistant_message["role"] == "assistant"
        assert "Okay, I've generated a new" in assistant_message["content"]
        assert "short answer exercise" in assistant_message["content"]

    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch(
        "backend.ai.lessons.nodes.call_llm_with_json_parsing", return_value=None
    )
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_generate_new_exercise_llm_failure(
        self, mock_call_llm: MagicMock, mock_load_prompt: MagicMock
    ) -> None: # Added return type hint
        """Test failure during LLM call for exercise generation."""
        mock_load_prompt.return_value = "mocked_gen_ex_prompt"
        initial_history = [{"role": "assistant", "content": "What next?"}]
        state = self._get_base_state(history=initial_history)

        # Cast state before calling node
        updated_state, generated_exercise, assistant_message = nodes.generate_new_exercise(
            cast(Dict[str, Any], state)
        )

        mock_call_llm.assert_called_once()
        assert generated_exercise is None
        assert updated_state["active_exercise"] is None
        assert updated_state["generated_exercise_ids"] == []
        assert updated_state["current_interaction_mode"] == "chatting"
        assert updated_state["error_message"] == "Exercise generation failed."

        # Check the returned assistant message
        assert assistant_message is not None
        assert assistant_message["role"] == "assistant"
        assert "Sorry, I wasn't able to generate an exercise" in assistant_message["content"]

    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch("backend.ai.lessons.nodes.call_llm_with_json_parsing")
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_generate_new_exercise_duplicate_id(
        self, mock_call_llm: MagicMock, mock_load_prompt: MagicMock
    ) -> None: # Added return type hint
        """Test discarding exercise if LLM returns a duplicate ID."""
        mock_load_prompt.return_value = "mocked_gen_ex_prompt"
        mock_duplicate_exercise = Exercise(
            id="ex_existing",
            type="short_answer",
            instructions="Duplicate?",
            correct_answer="No",
        )
        mock_call_llm.return_value = mock_duplicate_exercise

        initial_history = [{"role": "assistant", "content": "What next?"}]
        state = self._get_base_state(
            history=initial_history,
            existing_exercise_ids=["ex_existing"] # Pre-populate with the ID
        )

        # Cast state before calling node
        updated_state, generated_exercise, assistant_message = nodes.generate_new_exercise(
            cast(Dict[str, Any], state)
        )

        mock_call_llm.assert_called_once()
        assert generated_exercise is None
        assert updated_state["active_exercise"] is None
        assert updated_state["generated_exercise_ids"] == ["ex_existing"] # Should not change
        assert updated_state["current_interaction_mode"] == "chatting"
        assert updated_state["error_message"] == "Duplicate exercise ID generated."

        # Check the returned assistant message
        assert assistant_message is not None
        assert assistant_message["role"] == "assistant"
        assert "Sorry, I couldn't come up with a new exercise" in assistant_message["content"]

    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_generate_new_exercise_missing_content(self) -> None: # Added return type hint
        """Test exercise generation fails if exposition content is missing."""
        state = self._get_base_state()
        state["generated_content"] = None # Remove content

        # Cast state before calling node
        updated_state, generated_exercise, assistant_message = nodes.generate_new_exercise(
            cast(Dict[str, Any], state)
        )

        assert generated_exercise is None
        assert updated_state["error_message"] is not None
        assert "lesson content is missing" in updated_state["error_message"]

        # Check the returned assistant message
        assert assistant_message is not None
        assert assistant_message["role"] == "assistant"
        assert "lesson content is missing" in assistant_message["content"]

        # State should have error message added, but otherwise be the same
        expected_state = cast(Dict[str, Any], state)
        # Copy error message for comparison
        expected_state["error_message"] = updated_state["error_message"]
        assert updated_state == expected_state
