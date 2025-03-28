# backend/tests/ai/lessons/test_lessons_graph_routing.py
"""tests for backend/ai/lessons/lessons_graph.py routing logic"""
# pylint: disable=protected-access, unused-argument, invalid-name

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.models import IntentClassificationResult, LessonState
# Import the nodes module instead of LessonAI for direct function calls
from backend.ai.lessons import nodes


class TestLessonAIRouting:
    """Tests for the routing logic (nodes.route_message_logic)."""

    # Remove LessonAI init patches, update logger patch target
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    @pytest.mark.parametrize("mode", ["doing_exercise", "taking_quiz"])
    def test_route_message_logic_evaluation_mode(self, mode):
        """Test routing when mode requires evaluation."""
        # lesson_ai = LessonAI() # Removed
        state: LessonState = {
            "current_interaction_mode": mode,
            "conversation_history": [{"role": "user", "content": "My answer"}],
            # Other state fields...
        }
        # Call node function directly
        route = nodes.route_message_logic(state)
        assert route == "evaluate_chat_answer"

    # Remove LessonAI init patches, update logger patch target
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_route_message_logic_chatting_no_user_message(self):
        """Test routing in chatting mode with no preceding user message."""
        # lesson_ai = LessonAI() # Removed
        state: LessonState = {
            "current_interaction_mode": "chatting",
            "conversation_history": [{"role": "assistant", "content": "Hi there!"}],
            # Other state fields...
        }
        # Patch logger where it's used (nodes module)
        with patch("backend.ai.lessons.nodes.logger.warning") as mock_warning:
            # Call node function directly
            route = nodes.route_message_logic(state)
            assert route == "generate_chat_response"
            mock_warning.assert_called_once()

    # Update patches to target 'nodes' module
    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch("backend.ai.lessons.nodes.call_llm_with_json_parsing")
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    @pytest.mark.parametrize(
        "intent, expected_route",
        [
            ("request_exercise", "generate_new_exercise"), # Updated expected route
            ("request_quiz", "generate_new_assessment_question"), # Updated expected route
            ("ask_question", "generate_chat_response"),
            ("other_chat", "generate_chat_response"),
            ("unknown_intent", "generate_chat_response"),  # Test default for unknown
        ],
    )
    # Removed MockStateGraph from parameters
    def test_route_message_logic_chatting_intent_classification(
        self, mock_call_llm, MockLoadPrompt, intent, expected_route
    ):
        """Test routing based on LLM intent classification."""
        # lesson_ai = LessonAI() # Removed
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

        # Call node function directly
        route = nodes.route_message_logic(state)

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
            # Patch logger warning where it's used (nodes module)
            with patch(
                "backend.ai.lessons.nodes.logger.warning"
            ) as mock_warning:
                nodes.route_message_logic(state)  # Call again to check warning
                mock_warning.assert_called_once()

    # Update patches to target 'nodes' module
    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch("backend.ai.lessons.nodes.call_llm_with_json_parsing")
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_route_message_logic_chatting_intent_failure(
        self, mock_call_llm, MockLoadPrompt
    ):
        """Test routing default when intent classification fails."""
        # lesson_ai = LessonAI() # Removed
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
        # Patch logger where it's used (nodes module)
        with patch("backend.ai.lessons.nodes.logger.warning") as mock_warning:
            # Call node function directly
            route = nodes.route_message_logic(state)
            assert route == "generate_chat_response"  # Default route
            mock_warning.assert_called_once()

    # Update patches to target 'nodes' module
    @patch(
        "backend.ai.lessons.nodes.load_prompt", # Target nodes
        side_effect=Exception("LLM Error"),
    )
    @patch(
        "backend.ai.lessons.nodes.call_llm_with_json_parsing" # Target nodes
    )  # Need to patch this even if not called
    @patch("backend.ai.lessons.nodes.logger", MagicMock()) # Target nodes
    def test_route_message_logic_chatting_intent_exception(
        self, mock_call_llm, MockLoadPrompt_exc
    ):
        """Test routing default when an exception occurs during intent classification."""
        # lesson_ai = LessonAI() # Removed

        state: LessonState = {
            "current_interaction_mode": "chatting",
            "conversation_history": [
                {"role": "assistant", "content": "Hello"},
                {"role": "user", "content": "Something weird"},
            ],
            "user_id": "test_user",
            # Other state fields...
        }
        # Patch logger where it's used (nodes module)
        with patch("backend.ai.lessons.nodes.logger.error") as mock_error:
            # Call node function directly
            route = nodes.route_message_logic(state)
            assert route == "generate_chat_response"  # Default route
            mock_error.assert_called_once()
            mock_call_llm.assert_not_called()  # Ensure LLM call was skipped

    # Remove LessonAI init patches, update logger patch target
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_route_message_logic_unexpected_mode(self):
        """Test routing default for an unexpected interaction mode."""
        # lesson_ai = LessonAI() # Removed
        state: LessonState = {
            "current_interaction_mode": "unexpected_mode",
            "conversation_history": [{"role": "user", "content": "My answer"}],
            "user_id": "test_user",
            # Other state fields...
        }
        # Patch logger where it's used (nodes module)
        with patch("backend.ai.lessons.nodes.logger.warning") as mock_warning:
            # Call node function directly
            route = nodes.route_message_logic(state)
            assert route == "generate_chat_response"
            mock_warning.assert_called_once()
