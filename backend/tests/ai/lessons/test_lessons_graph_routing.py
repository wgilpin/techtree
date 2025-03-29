# backend/tests/ai/lessons/test_lessons_graph_routing.py
"""Tests for backend/ai/lessons/nodes.py intent classification logic"""
# pylint: disable=protected-access, unused-argument, invalid-name

from unittest.mock import ANY, MagicMock, patch, AsyncMock  # Import AsyncMock

import pytest

from backend.models import (
    IntentClassificationResult,
    LessonState,
    Exercise,
    GeneratedLessonContent,
)

# Import the nodes module for direct function calls
from backend.ai.lessons import nodes


# Define default history as a constant for clarity and potential reuse
DEFAULT_INITIAL_HISTORY = [{"role": "assistant", "content": "Hello"}]


@pytest.mark.asyncio
class TestLessonAIIntentClassification:  # Renamed class
    """Tests for the intent classification logic (nodes.classify_intent)."""

    # Basic state setup helper
    def _get_base_state(
        self, user_message: str = "Test message", history: list | None = None
    ) -> LessonState:
        """
        Creates a base LessonState dictionary for testing.

        Args:
            user_message: The user message to add to the history. If None, no user message is added.
            history: optional existing conversation history list. If None, a default is used.

        Returns:
            A LessonState dictionary populated with base values and the constructed history.
        """
        # Create a copy of the history to avoid mutating the input list.
        # Use the default if history is None.
        # Use list() constructor for clarity in creating a shallow copy.
        current_history = (
            list(history) if history is not None else list(DEFAULT_INITIAL_HISTORY)
        )

        # Append the user message if provided
        if user_message:
            current_history.append({"role": "user", "content": user_message})

        # Provide a more complete base state matching LessonState TypedDict
        return {
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
            "conversation_history": current_history,  # Use the processed history
            "current_interaction_mode": "chatting",  # Initial mode before classification
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
        }

    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch(
        "backend.ai.lessons.nodes.call_llm_with_json_parsing", new_callable=AsyncMock
    )
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    @pytest.mark.parametrize(
        "intent, user_message, expected_mode",
        [
            ("request_exercise", "Give me an exercise", "request_exercise"),
            ("request_assessment", "Quiz me", "request_assessment"),
            ("ask_question", "What is this?", "chatting"),
            ("other_chat", "Okay thanks", "chatting"),
            ("unknown_intent", "Gibberish", "chatting"),  # Test default for unknown
            # Test answer submission without active task -> chatting
            ("submit_answer", "My answer is 5", "chatting"),
        ],
    )
    async def test_classify_intent_no_active_task(
        self, mock_call_llm, mock_load_prompt, intent, user_message, expected_mode
    ):
        """Test intent classification routing when no task is active."""
        mock_load_prompt.return_value = "mocked_intent_prompt"
        mock_call_llm.return_value = IntentClassificationResult(intent=intent)

        state = self._get_base_state(user_message=user_message)

        # Call the classify_intent node function
        result_state = await nodes.classify_intent(state)

        mock_load_prompt.assert_called_once_with(
            "intent_classification",
            user_message=user_message,
            conversation_history=ANY,  # History formatting is complex, check presence
            topic="Testing",
            lesson_title="Intent Test",
            user_level="beginner",
            exposition_summary="Some content.",
            active_task_context="None",  # No active task
        )
        mock_call_llm.assert_called_once_with(
            "mocked_intent_prompt",
            validation_model=IntentClassificationResult,
            max_retries=3,
        )
        # Check the interaction mode set in the returned state
        assert result_state["current_interaction_mode"] == expected_mode
        # Check potential_answer is NOT set when mode isn't submit_answer
        if expected_mode != "submit_answer":
            assert result_state.get("potential_answer") is None

    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch(
        "backend.ai.lessons.nodes.call_llm_with_json_parsing", new_callable=AsyncMock
    )
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    @pytest.mark.parametrize(
        "intent, user_message, expected_mode",
        [
            # If user submits an answer while task is active, mode should be submit_answer
            ("submit_answer", "The answer is B", "submit_answer"),
            # If user asks for exercise while one is active, classify intent as request_exercise
            (
                "request_exercise",
                "Give me another exercise",
                "request_exercise",
            ),  # Corrected expected mode
            # If user asks question while task is active, treat as chat
            ("ask_question", "Why is B correct?", "chatting"),
        ],
    )
    async def test_classify_intent_with_active_task(
        self, mock_call_llm, mock_load_prompt, intent, user_message, expected_mode
    ):
        """Test intent classification routing when an exercise/assessment is active."""
        mock_load_prompt.return_value = "mocked_intent_prompt"
        mock_call_llm.return_value = IntentClassificationResult(intent=intent)

        # Simulate an active exercise
        active_exercise = Exercise(id="ex1", type="mc", question="Active Q")
        state = self._get_base_state(user_message=user_message)
        state["active_exercise"] = active_exercise

        # Call the classify_intent node function
        result_state = await nodes.classify_intent(state)

        # Corrected assertion: Remove extra whitespace from active_task_context
        expected_task_context = (
            f"Active Exercise: {active_exercise.type} - {active_exercise.question}"
        )
        mock_load_prompt.assert_called_once_with(
            "intent_classification",
            user_message=user_message,
            conversation_history=ANY,
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
        # Check potential_answer is set correctly for submit_answer mode
        if expected_mode == "submit_answer":
            assert result_state.get("potential_answer") == user_message
        else:
            assert result_state.get("potential_answer") is None

    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch(
        "backend.ai.lessons.nodes.call_llm_with_json_parsing",
        new_callable=AsyncMock,
        return_value=None,
    )  # Simulate LLM failure
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    async def test_classify_intent_llm_failure(self, mock_call_llm, mock_load_prompt):
        """Test routing default when intent classification LLM call fails."""
        mock_load_prompt.return_value = "mocked_intent_prompt"
        state = self._get_base_state(user_message="Something weird")

        # Patch logger error for assertion
        with patch("backend.ai.lessons.nodes.logger.error") as mock_logger_error:
            result_state = await nodes.classify_intent(state)

            mock_call_llm.assert_called_once()
            mock_logger_error.assert_called_once()  # Check error was logged
            # Should default to chatting on failure
            assert result_state["current_interaction_mode"] == "chatting"

    @patch("backend.ai.lessons.nodes.load_prompt", side_effect=Exception("LLM Error"))
    @patch(
        "backend.ai.lessons.nodes.call_llm_with_json_parsing", new_callable=AsyncMock
    )
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    async def test_classify_intent_exception(self, mock_call_llm, mock_load_prompt_exc):
        """Test routing default when an exception occurs during intent classification."""
        state = self._get_base_state(user_message="Something weird")

        # Patch logger error for assertion
        with patch("backend.ai.lessons.nodes.logger.error") as mock_logger_error:
            result_state = await nodes.classify_intent(state)

            mock_load_prompt_exc.assert_called_once()  # Prompt load failed
            mock_call_llm.assert_not_called()  # LLM call skipped
            mock_logger_error.assert_called_once()  # Check error was logged
            # Should default to chatting on exception
            assert result_state["current_interaction_mode"] == "chatting"

    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    async def test_classify_intent_no_user_message(self):
        """Test classification when the last message isn't from the user."""
        state = self._get_base_state(user_message=None)  # No user message added

        # Patch logger warning for assertion
        with patch("backend.ai.lessons.nodes.logger.warning") as mock_logger_warning:
            result_state = await nodes.classify_intent(state)

            mock_logger_warning.assert_called_once()  # Check warning was logged
            # Should default to chatting if no user message
            assert result_state["current_interaction_mode"] == "chatting"
