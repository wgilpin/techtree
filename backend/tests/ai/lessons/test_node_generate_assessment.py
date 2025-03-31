# backend/tests/ai/lessons/test_node_generate_assessment.py
"""Tests for backend/ai/lessons/nodes.py generate_new_assessment node"""
# pylint: disable=protected-access, unused-argument, invalid-name

from unittest.mock import MagicMock, patch
from typing import Optional, List, Dict, Any, cast  # Added imports


# Import the node functions directly
from backend.ai.lessons import nodes
from backend.models import (
    AssessmentQuestion,
    GeneratedLessonContent,
    LessonState,
)


class TestGenerateAssessmentNode:
    """Tests for the generate_new_assessment node action."""

    # Basic state setup helper (copied and adapted)
    def _get_base_state(
        self,
        history: Optional[List[Dict[str, str]]] = None,  # Use List[Dict[str, str]]
        existing_assessment_ids: Optional[List[str]] = None,  # Use List[str]
    ) -> LessonState:
        """Creates a base LessonState dictionary for testing assessment generation."""
        current_history = list(history) if history is not None else []

        # Ensure all keys from LessonState are present
        state: LessonState = {
            "topic": "Generation",
            "knowledge_level": "intermediate",
            "syllabus": None,
            "lesson_title": "Gen Assess Lesson",
            "module_title": "Module Gen",
            "generated_content": GeneratedLessonContent(
                exposition_content="Lesson content here."
            ),
            "user_responses": [],
            "user_performance": {},
            "user_id": "gen_assess_user",
            "lesson_uid": "gen_assess_lesson_uid",
            "created_at": "sometime",
            "updated_at": "sometime",
            "history_context": current_history,  # Use history_context
            "current_interaction_mode": "chatting",  # Assume user just requested
            "current_exercise_index": None,
            "current_quiz_question_index": None,
            "generated_exercises": [],
            "generated_assessment_questions": [],
            "generated_exercise_ids": [],
            "generated_assessment_question_ids": (
                existing_assessment_ids if existing_assessment_ids is not None else []
            ),
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
    def test_generate_new_assessment_success(
        self, mock_call_llm: MagicMock, mock_load_prompt: MagicMock
    ) -> None:  # Added return type hint
        """Test successful generation of a new assessment question."""
        mock_load_prompt.return_value = "mocked_gen_q_prompt"
        mock_new_question = AssessmentQuestion(
            id="q_new_1",
            type="true_false",
            question_text="Is this new?",
            correct_answer_id="True",
        )
        mock_call_llm.return_value = mock_new_question

        initial_history = [{"role": "assistant", "content": "What next?"}]
        state = self._get_base_state(history=initial_history)

        # Cast state before calling node
        # Node now returns state, question object, and assistant message dict
        updated_state, generated_question, assistant_message = (
            nodes.generate_new_assessment(cast(Dict[str, Any], state))
        )

        mock_load_prompt.assert_called_once_with(
            "generate_assessment",
            topic="Generation",
            lesson_title="Gen Assess Lesson",
            user_level="intermediate",
            exposition_summary="Lesson content here.",
            existing_question_descriptions_json="[]",
        )
        mock_call_llm.assert_called_once_with(
            "mocked_gen_q_prompt", validation_model=AssessmentQuestion, max_retries=2
        )

        assert generated_question == mock_new_question
        assert updated_state["active_assessment"] == mock_new_question
        assert updated_state["generated_assessment_question_ids"] == ["q_new_1"]
        assert updated_state["current_interaction_mode"] == "awaiting_answer"

        # Check the returned assistant message
        assert assistant_message is not None
        assert assistant_message["role"] == "assistant"
        assert "Okay, here's an assessment question" in assistant_message["content"]
        assert "true false" in assistant_message["content"]

    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch("backend.ai.lessons.nodes.call_llm_with_json_parsing", return_value=None)
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_generate_new_assessment_llm_failure(
        self, mock_call_llm: MagicMock, mock_load_prompt: MagicMock
    ) -> None:  # Added return type hint
        """Test failure during LLM call for assessment generation."""
        mock_load_prompt.return_value = "mocked_gen_q_prompt"
        initial_history = [{"role": "assistant", "content": "What next?"}]
        state = self._get_base_state(history=initial_history)

        # Cast state before calling node
        updated_state, generated_question, assistant_message = (
            nodes.generate_new_assessment(cast(Dict[str, Any], state))
        )

        mock_call_llm.assert_called_once()
        assert generated_question is None
        assert updated_state["active_assessment"] is None
        assert updated_state["generated_assessment_question_ids"] == []
        assert updated_state["current_interaction_mode"] == "chatting"
        assert updated_state["error_message"] == "Assessment generation failed."

        # Check the returned assistant message
        assert assistant_message is not None
        assert assistant_message["role"] == "assistant"
        assert (
            "Sorry, I wasn't able to generate an assessment question"
            in assistant_message["content"]
        )

    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch("backend.ai.lessons.nodes.call_llm_with_json_parsing")
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_generate_new_assessment_duplicate_id(
        self, mock_call_llm: MagicMock, mock_load_prompt: MagicMock
    ) -> None:  # Added return type hint
        """Test discarding assessment question if LLM returns a duplicate ID."""
        mock_load_prompt.return_value = "mocked_gen_q_prompt"
        mock_duplicate_question = AssessmentQuestion(
            id="q_existing",
            type="true_false",
            question_text="Duplicate?",
            correct_answer_id="False",
        )
        mock_call_llm.return_value = mock_duplicate_question

        initial_history = [{"role": "assistant", "content": "What next?"}]
        state = self._get_base_state(
            history=initial_history,
            existing_assessment_ids=["q_existing"],  # Pre-populate with the ID
        )

        # Cast state before calling node
        updated_state, generated_question, assistant_message = (
            nodes.generate_new_assessment(cast(Dict[str, Any], state))
        )

        mock_call_llm.assert_called_once()
        assert generated_question is None
        assert updated_state["active_assessment"] is None
        assert updated_state["generated_assessment_question_ids"] == ["q_existing"]
        assert updated_state["current_interaction_mode"] == "chatting"
        assert updated_state["error_message"] == "Duplicate assessment ID generated."

        # Check the returned assistant message
        assert assistant_message is not None
        assert assistant_message["role"] == "assistant"
        assert (
            "Sorry, I couldn't come up with a new assessment question"
            in assistant_message["content"]
        )

    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_generate_new_assessment_missing_content(
        self,
    ) -> None:  # Added return type hint
        """Test assessment generation fails if exposition content is missing."""
        state = self._get_base_state()
        state["generated_content"] = None  # Remove content

        # Cast state before calling node
        updated_state, generated_question, assistant_message = (
            nodes.generate_new_assessment(cast(Dict[str, Any], state))
        )

        assert generated_question is None
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
