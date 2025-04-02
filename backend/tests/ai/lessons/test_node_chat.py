# backend/tests/ai/lessons/test_node_chat.py
"""Tests for backend/ai/lessons/nodes.py generate_chat_response node"""
# pylint: disable=protected-access, unused-argument, invalid-name

from unittest.mock import MagicMock, patch
from unittest.mock import ANY
from typing import (
    Optional,
    List,
    Dict,
    Any,
    cast,
)  # Added Optional, List, Dict, Any, cast


from google.api_core.exceptions import ResourceExhausted

# Import the node functions directly
from backend.ai.lessons import nodes
from backend.models import (
    GeneratedLessonContent,
    LessonState,
)
from backend.ai.prompt_formatting import LATEX_FORMATTING_INSTRUCTIONS



class TestGenerateChatResponse:
    """Tests for the generate_chat_response node action."""

    # Basic state setup helper (copied and adapted)
    def _get_base_state(
        self,
        user_message: Optional[str] = "Test message",  # Allow None
        history: Optional[List[Dict[str, str]]] = None,  # Use List[Dict[str, str]]
    ) -> LessonState:
        """Creates a base LessonState dictionary for testing chat response."""
        current_history = list(history) if history is not None else []
        if user_message:
            current_history.append({"role": "user", "content": user_message})

        # Ensure all keys from LessonState are present
        state: LessonState = {
            "topic": "Chatting",
            "knowledge_level": "beginner",
            "syllabus": None,
            "lesson_title": "Chat Lesson",
            "module_title": "Module Chat",
            "generated_content": GeneratedLessonContent(
                exposition_content="Some exposition."
            ),
            "user_responses": [],
            "user_performance": {},
            "user_id": "chat_user",
            "lesson_uid": "chat_lesson_uid",
            "created_at": "sometime",
            "updated_at": "sometime",
            "history_context": current_history,  # Use history_context
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
    @patch("backend.ai.lessons.nodes.call_llm_plain_text")
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_generate_chat_response_success(
        self,
        mock_call_llm: MagicMock,
        mock_load_prompt: MagicMock,
    ) -> None:  # Added return type hint
        """Test successful chat response generation."""
        mock_load_prompt.return_value = "mocked_chat_prompt"
        mock_call_llm.return_value = "This is the AI response."

        initial_history = [{"role": "user", "content": "Tell me more."}]
        state = self._get_base_state(user_message=None, history=initial_history)

        # Cast state before calling node, now returns only state dict
        updated_state = nodes.generate_chat_response(
            cast(Dict[str, Any], state)
        )

        mock_load_prompt.assert_called_once_with(
            "chat_response",
            user_message="Tell me more.",
            history_json="",  # Check if prompt uses history_json or conversation_history
            topic="Chatting",
            lesson_title="Chat Lesson",
            user_level="beginner",
            exposition=ANY,  # Check prompt key
            active_task_context="None",
            latex_formatting_instructions=LATEX_FORMATTING_INSTRUCTIONS,
        )
        mock_call_llm.assert_called_once_with("mocked_chat_prompt", max_retries=3)

        # Check the returned assistant message
        # Check the message within the returned state
        new_message = updated_state.get("new_assistant_message")
        assert isinstance(new_message, dict)
        assert new_message.get("role") == "assistant"
        assert new_message.get("content") == "This is the AI response."

        # Check the updated state
        assert isinstance(updated_state, dict)
        assert updated_state.get("current_interaction_mode") == "chatting"
        # Ensure history is NOT in the returned state
        assert "conversation_history" not in updated_state
        assert "history_context" not in updated_state

    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_generate_chat_response_no_user_message(
        self,
    ) -> None:  # Added return type hint
        """Test chat response generation when no user message precedes."""
        initial_history = [{"role": "assistant", "content": "Welcome!"}]
        state = self._get_base_state(user_message=None, history=initial_history)

        with patch("backend.ai.lessons.nodes.logger.warning") as mock_warning:
            # Cast state before calling node, now returns only state dict
            updated_state = nodes.generate_chat_response(
                cast(Dict[str, Any], state)
            )

            mock_warning.assert_called_once_with(
                "Cannot generate chat response: No user message found in "
                f"history_context for user {state['user_id']}."
            )
            # Node should return original state and None message in this case
            # Check the message within the returned state (should be None)
            assert updated_state.get("new_assistant_message") is None
            assert updated_state == state

    @patch("backend.ai.lessons.nodes.load_prompt")
    @patch(
        "backend.ai.lessons.nodes.call_llm_plain_text",
        side_effect=ResourceExhausted("Quota exceeded"),  # type: ignore[no-untyped-call]
    )
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_generate_chat_response_resource_exhausted(
        self,
        mock_call_llm: MagicMock,
        mock_load_prompt: MagicMock,
    ) -> None:  # Added return type hint
        """Test chat response generation handling ResourceExhausted."""
        mock_load_prompt.return_value = "mocked_chat_prompt"
        initial_history = [{"role": "user", "content": "Tell me more."}]
        state = self._get_base_state(user_message=None, history=initial_history)

        with patch("backend.ai.lessons.nodes.logger.error") as mock_error:
            # Cast state before calling node, now returns only state dict
            updated_state = nodes.generate_chat_response(
                cast(Dict[str, Any], state)
            )

            mock_error.assert_called_once()
            assert "LLM call failed" in mock_error.call_args[0][0]

            # Check the returned assistant message (should be error fallback)
            # Check the message within the returned state
            new_message = updated_state.get("new_assistant_message")
            assert isinstance(new_message, dict)
            assert new_message.get("role") == "assistant"
            assert (
                "Sorry, I encountered an error while generating a response."
                in new_message.get("content", "")
            )

            # Check the updated state
            assert isinstance(updated_state, dict)
            assert updated_state.get("current_interaction_mode") == "chatting"

    @patch(
        "backend.ai.lessons.nodes.load_prompt",
        side_effect=Exception("Prompt loading failed"),
    )
    @patch("backend.ai.lessons.nodes.call_llm_plain_text")
    @patch("backend.ai.lessons.nodes.logger", MagicMock())
    def test_generate_chat_response_generic_exception(
        self,
        mock_call_llm: MagicMock,
        mock_load_prompt_exc: MagicMock,
    ) -> None:  # Added return type hint
        """Test chat response generation handling a generic exception."""
        initial_history = [{"role": "user", "content": "Tell me more."}]
        state = self._get_base_state(user_message=None, history=initial_history)

        with patch("backend.ai.lessons.nodes.logger.error") as mock_error:
            # Cast state before calling node, now returns only state dict
            updated_state = nodes.generate_chat_response(
                cast(Dict[str, Any], state)
            )

            mock_error.assert_called_once()
            assert "LLM call failed" in mock_error.call_args[0][0]
            mock_call_llm.assert_not_called()

            # Check the returned assistant message (should be error fallback)
            # Check the message within the returned state
            new_message = updated_state.get("new_assistant_message")
            assert isinstance(new_message, dict)
            assert new_message.get("role") == "assistant"
            assert (
                "Sorry, I encountered an error while generating a response."
                in new_message.get("content", "")
            )

            # Check the updated state
            assert isinstance(updated_state, dict)
            assert updated_state.get("current_interaction_mode") == "chatting"
