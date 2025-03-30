# backend/tests/ai/lessons/test_lessons_graph_routing.py
"""Tests for backend/ai/lessons/nodes.py intent classification logic"""
# pylint: disable=protected-access, unused-argument, invalid-name

from unittest.mock import ANY, MagicMock, patch
from typing import Optional, List, Dict, Any, cast # Added imports

import pytest

from backend.models import (
    IntentClassificationResult,
    LessonState,
    Exercise,
    GeneratedLessonContent, # Added import
)

# Import the nodes module for direct function calls
from backend.ai.lessons import nodes


# Define default history as a constant for clarity and potential reuse
DEFAULT_INITIAL_HISTORY = [{"role": "assistant", "content": "Hello"}]


class TestLessonAIIntentClassification:
    """Tests for the intent classification logic (nodes.classify_intent)."""

    # Basic state setup helper
    def _get_base_state(
        self,
        user_message: Optional[str] = "Test message", # Allow None
        history: Optional[List[Dict[str, str]]] = None # Use List[Dict[str, str]]
    ) -> LessonState:
        """
        Creates a base LessonState dictionary for testing.

        Args:
            user_message: The user message to add to the history. If None, no user message is added.
            history: optional existing conversation history list. If None, a default is used.

        Returns:
            A LessonState dictionary populated with base values and the constructed history.
        """
        current_history = (
            list(history) if history is not None else list(DEFAULT_INITIAL_HISTORY)
        )

        if user_message:
            current_history.append({"role": "user", "content": user_message})

        # Provide a more complete base state matching LessonState TypedDict
        state: LessonState = {
            "topic": "Testing",
            "knowledge_level": "beginner",
            "syllabus": None,
            "lesson_title": "Intent Test",
            "module_title": "Module Test",
            "generated_content": GeneratedLessonContent(
                exposition_content="Some content."
            ),
            "user_responses": [],
            "user_performance": {},
            "user_id": "intent_user",
            "lesson_uid": "intent_test_uid",
            "created_at": "t",
            "updated_at": "t",
            "history_context": current_history, # Use history_context
            "current_interaction_mode": "chatting",
            "current_exercise_index": None,
            "current_quiz_question_index": None,
            "generated_exercises": [],
            "generated_assessment_questions": [],
            "generated_exercise_ids": [],
            "generated_assessment_question_ids": [],
            "error_message": None,
            "active_exercise": None,
            "active_assessment": None,
            "potential_answer": None,
            "lesson_db_id": None,
        }
        return state

    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch(
        "backend.ai.lessons.nodes.call_llm_with_json_parsing"
    )
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    @pytest.mark.parametrize(
        "intent, user_message, expected_mode",
        [
            ("request_exercise", "Give me an exercise", "request_exercise"),
            ("request_assessment", "Quiz me", "request_assessment"),
            ("ask_question", "What is this?", "chatting"),
            ("other_chat", "Okay thanks", "chatting"),
            ("unknown_intent", "Gibberish", "chatting"),
            ("submit_answer", "My answer is 5", "chatting"),
        ],
    )
    def test_classify_intent_no_active_task(
        self,
        mock_call_llm: MagicMock,
        mock_load_prompt: MagicMock,
        intent: str,
        user_message: str,
        expected_mode: str
    ) -> None: # Added return type hint
        """Test intent classification routing when no task is active."""
        mock_load_prompt.return_value = "mocked_intent_prompt"
        mock_call_llm.return_value = IntentClassificationResult(intent=intent)

        state = self._get_base_state(user_message=user_message)

        # Call the classify_intent node function (cast state)
        result_state = nodes.classify_intent(cast(Dict[str, Any], state))

        mock_load_prompt.assert_called_once_with(
            "intent_classification",
            user_input=user_message, # Check prompt key used in node
            history_json=ANY,       # Check prompt key used in node
            topic="Testing",
            lesson_title="Intent Test",
            user_level="beginner",
            exposition_summary="Some content.",
            active_task_context="None",
        )
        mock_call_llm.assert_called_once_with(
            "mocked_intent_prompt",
            validation_model=IntentClassificationResult,
            max_retries=3,
        )
        assert result_state["current_interaction_mode"] == expected_mode
        if expected_mode != "submit_answer":
            assert result_state.get("potential_answer") is None

    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch(
        "backend.ai.lessons.nodes.call_llm_with_json_parsing"
    )
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    @pytest.mark.parametrize(
        "intent, user_message, expected_mode",
        [
            ("submit_answer", "The answer is B", "submit_answer"),
            (
                "request_exercise",
                "Give me another exercise",
                "request_exercise",
            ),
            ("ask_question", "Why is B correct?", "chatting"),
        ],
    )
    def test_classify_intent_with_active_task(
        self,
        mock_call_llm: MagicMock,
        mock_load_prompt: MagicMock,
        intent: str,
        user_message: str,
        expected_mode: str
    ) -> None: # Added return type hint
        """Test intent classification routing when an exercise/assessment is active."""
        mock_load_prompt.return_value = "mocked_intent_prompt"
        mock_call_llm.return_value = IntentClassificationResult(intent=intent)

        active_exercise = Exercise(id="ex1", type="mc", question="Active Q")
        state = self._get_base_state(user_message=user_message)
        state["active_exercise"] = active_exercise

        # Call the classify_intent node function (cast state)
        result_state = nodes.classify_intent(cast(Dict[str, Any], state))

        expected_task_context = (
            f"Active Exercise: {active_exercise.type} - {active_exercise.question}"
        )
        mock_load_prompt.assert_called_once_with(
            "intent_classification",
            user_input=user_message, # Check prompt key used in node
            history_json=ANY,       # Check prompt key used in node
            topic="Testing",
            lesson_title="Intent Test",
            user_level="beginner",
            exposition_summary="Some content.",
            active_task_context=expected_task_context,
        )
        mock_call_llm.assert_called_once_with(
            "mocked_intent_prompt",
            validation_model=IntentClassificationResult,
            max_retries=3,
        )
        assert result_state["current_interaction_mode"] == expected_mode
        if expected_mode == "submit_answer":
            assert result_state.get("potential_answer") == user_message
        else:
            assert result_state.get("potential_answer") is None

    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch(
        "backend.ai.lessons.nodes.call_llm_with_json_parsing",
        return_value=None,
    )
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_classify_intent_llm_failure(
        self, mock_call_llm: MagicMock, mock_load_prompt: MagicMock
    ) -> None: # Added return type hint
        """Test routing default when intent classification LLM call fails."""
        mock_load_prompt.return_value = "mocked_intent_prompt"
        state = self._get_base_state(user_message="Something weird")

        with patch("backend.ai.lessons.nodes.logger.error") as mock_logger_error:
            # Cast state before calling node
            result_state = nodes.classify_intent(cast(Dict[str, Any], state))

            mock_call_llm.assert_called_once()
            assert result_state["current_interaction_mode"] == "chatting"

    @patch("backend.ai.lessons.nodes.load_prompt", side_effect=Exception("LLM Error"))
    @patch(
        "backend.ai.lessons.nodes.call_llm_with_json_parsing"
    )
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_classify_intent_exception(
        self, mock_call_llm: MagicMock, mock_load_prompt_exc: MagicMock
    ) -> None: # Added return type hint
        """Test routing default when an exception occurs during intent classification."""
        state = self._get_base_state(user_message="Something weird")

        with patch("backend.ai.lessons.nodes.logger.error") as mock_logger_error:
            # Cast state before calling node
            result_state = nodes.classify_intent(cast(Dict[str, Any], state))

            mock_load_prompt_exc.assert_called_once()
            mock_call_llm.assert_not_called()
            mock_logger_error.assert_called_once()
            assert result_state["current_interaction_mode"] == "chatting"

    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_classify_intent_no_user_message(self) -> None: # Added return type hint
        """Test classification when the last message isn't from the user."""
        state = self._get_base_state(user_message=None)

        with patch("backend.ai.lessons.nodes.logger.warning") as mock_logger_warning:
            # Cast state before calling node
            result_state = nodes.classify_intent(cast(Dict[str, Any], state))

            mock_logger_warning.assert_called_once()
            assert result_state["current_interaction_mode"] == "chatting"
