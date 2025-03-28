# backend/tests/ai/lessons/test_lessons_graph_routing.py
"""tests for backend/ai/lessons/lessons_graph.py routing logic"""
# pylint: disable=protected-access, unused-argument, invalid-name

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.models import IntentClassificationResult, LessonState
from backend.ai.lessons.lessons_graph import LessonAI


class TestLessonAIRouting:
    """Tests for the routing logic (_route_message_logic) in LessonAI."""

    @patch("backend.ai.lessons.lessons_graph.load_dotenv", MagicMock())
    @patch("backend.ai.lessons.lessons_graph.StateGraph")
    @patch("backend.ai.lessons.lessons_graph.logger", MagicMock())
    @pytest.mark.parametrize("mode", ["doing_exercise", "taking_quiz"])
    def test_route_message_logic_evaluation_mode(self, MockStateGraph, mode):
        """Test routing when mode requires evaluation."""
        lesson_ai = LessonAI()  # Instantiation needed to access the method
        state: LessonState = {
            "current_interaction_mode": mode,
            "conversation_history": [{"role": "user", "content": "My answer"}],
            # Other state fields...
        }
        route = lesson_ai._route_message_logic(state)
        assert route == "evaluate_chat_answer"

    @patch("backend.ai.lessons.lessons_graph.load_dotenv", MagicMock())
    @patch("backend.ai.lessons.lessons_graph.StateGraph")
    @patch("backend.ai.lessons.lessons_graph.logger", MagicMock())
    def test_route_message_logic_chatting_no_user_message(self, MockStateGraph):
        """Test routing in chatting mode with no preceding user message."""
        lesson_ai = LessonAI()
        state: LessonState = {
            "current_interaction_mode": "chatting",
            "conversation_history": [{"role": "assistant", "content": "Hi there!"}],
            # Other state fields...
        }
        with patch("backend.ai.lessons.lessons_graph.logger.warning") as mock_warning:
            route = lesson_ai._route_message_logic(state)
            assert route == "generate_chat_response"
            mock_warning.assert_called_once()

    @patch("backend.ai.lessons.lessons_graph.load_prompt")
    @patch("backend.ai.lessons.lessons_graph.call_llm_with_json_parsing")
    @patch("backend.ai.lessons.lessons_graph.load_dotenv", MagicMock())
    @patch("backend.ai.lessons.lessons_graph.StateGraph")
    @patch("backend.ai.lessons.lessons_graph.logger", MagicMock())
    @pytest.mark.parametrize(
        "intent, expected_route",
        [
            ("request_exercise", "present_exercise"),
            ("request_quiz", "present_quiz_question"),
            ("ask_question", "generate_chat_response"),
            ("other_chat", "generate_chat_response"),
            ("unknown_intent", "generate_chat_response"),  # Test default for unknown
        ],
    )
    def test_route_message_logic_chatting_intent_classification(
        self, MockStateGraph, mock_call_llm, MockLoadPrompt, intent, expected_route
    ):
        """Test routing based on LLM intent classification."""
        lesson_ai = LessonAI()
        MockLoadPrompt.return_value = "mocked_prompt"
        mock_call_llm.return_value = IntentClassificationResult(intent=intent)

        state: LessonState = {
            "current_interaction_mode": "chatting",
            "conversation_history": [
                {"role": "assistant", "content": "Hello"},
                {"role": "user", "content": "Give me an exercise"},
            ],
            "user_id": "test_user",
            # Other state fields...
        }

        route = lesson_ai._route_message_logic(state)

        MockLoadPrompt.assert_called_once_with(
            "intent_classification",
            history_json=json.dumps(state["conversation_history"], indent=2),
            user_input="Give me an exercise",
        )
        mock_call_llm.assert_called_once_with(
            "mocked_prompt", validation_model=IntentClassificationResult
        )
        assert route == expected_route
        # Check warning for unknown intent
        if intent == "unknown_intent":
            # Reset mock for the second call check
            mock_call_llm.reset_mock()
            mock_call_llm.return_value = IntentClassificationResult(intent=intent)
            with patch(
                "backend.ai.lessons.lessons_graph.logger.warning"
            ) as mock_warning:
                lesson_ai._route_message_logic(state)  # Call again to check warning
                mock_warning.assert_called_once()

    @patch("backend.ai.lessons.lessons_graph.load_prompt")
    @patch("backend.ai.lessons.lessons_graph.call_llm_with_json_parsing")
    @patch("backend.ai.lessons.lessons_graph.load_dotenv", MagicMock())
    @patch("backend.ai.lessons.lessons_graph.StateGraph")
    @patch("backend.ai.lessons.lessons_graph.logger", MagicMock())
    def test_route_message_logic_chatting_intent_failure(
        self, MockStateGraph, mock_call_llm, MockLoadPrompt
    ):
        """Test routing default when intent classification fails."""
        lesson_ai = LessonAI()
        MockLoadPrompt.return_value = "mocked_prompt"
        mock_call_llm.return_value = None  # Simulate LLM/parsing failure

        state: LessonState = {
            "current_interaction_mode": "chatting",
            "conversation_history": [
                {"role": "assistant", "content": "Hello"},
                {"role": "user", "content": "Something weird"},
            ],
            "user_id": "test_user",
            # Other state fields...
        }
        with patch("backend.ai.lessons.lessons_graph.logger.warning") as mock_warning:
            route = lesson_ai._route_message_logic(state)
            assert route == "generate_chat_response"  # Default route
            mock_warning.assert_called_once()

    @patch(
        "backend.ai.lessons.lessons_graph.load_prompt",
        side_effect=Exception("LLM Error"),
    )
    @patch(
        "backend.ai.lessons.lessons_graph.call_llm_with_json_parsing"
    )  # Need to patch this even if not called
    @patch("backend.ai.lessons.lessons_graph.load_dotenv", MagicMock())
    @patch("backend.ai.lessons.lessons_graph.StateGraph")
    @patch("backend.ai.lessons.lessons_graph.logger", MagicMock())
    def test_route_message_logic_chatting_intent_exception(
        self, MockStateGraph, mock_call_llm, MockLoadPrompt_exc
    ):
        """Test routing default when an exception occurs during intent classification."""
        lesson_ai = LessonAI()

        state: LessonState = {
            "current_interaction_mode": "chatting",
            "conversation_history": [
                {"role": "assistant", "content": "Hello"},
                {"role": "user", "content": "Something weird"},
            ],
            "user_id": "test_user",
            # Other state fields...
        }
        with patch("backend.ai.lessons.lessons_graph.logger.error") as mock_error:
            route = lesson_ai._route_message_logic(state)
            assert route == "generate_chat_response"  # Default route
            mock_error.assert_called_once()
            mock_call_llm.assert_not_called()  # Ensure LLM call was skipped

    @patch("backend.ai.lessons.lessons_graph.load_dotenv", MagicMock())
    @patch("backend.ai.lessons.lessons_graph.StateGraph")
    @patch("backend.ai.lessons.lessons_graph.logger", MagicMock())
    def test_route_message_logic_unexpected_mode(self, MockStateGraph):
        """Test routing default for an unexpected interaction mode."""
        lesson_ai = LessonAI()
        state: LessonState = {
            "current_interaction_mode": "unexpected_mode",
            "conversation_history": [{"role": "user", "content": "My answer"}],
            "user_id": "test_user",
            # Other state fields...
        }
        with patch("backend.ai.lessons.lessons_graph.logger.warning") as mock_warning:
            route = lesson_ai._route_message_logic(state)
            assert route == "generate_chat_response"
            mock_warning.assert_called_once()
